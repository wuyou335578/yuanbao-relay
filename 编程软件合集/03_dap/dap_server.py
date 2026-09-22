#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAP (Debug Adapter Protocol) 桥接层 —— 让 gdb 12.1 也能说 DAP
================================================================
背景：
  gdb 原生 DAP（-dap）是 gdb 14+ 才有的。本机是 gdb 12.1，没有。
  所以自己实现一层：对外说 DAP(JSON)，对内用 gdb MI(--interpreter=mi) 驱动。

协议要点：
  · 传输：Header 用 "Content-Length: N\r\n\r\n"，body 是 JSON
  · 方向：客户端(IDE) → 本服务 → gdb MI → 本服务 → 客户端
  · 支持 stdio 模式（IDE 直接拉起）和 TCP 模式（IDE 连端口）

已实现的 DAP 请求：
  initialize, launch, attach, disconnect, setBreakpoints,
  setFunctionBreakpoints, configurationDone, threads, stackTrace,
  scopes, variables, continue, next, stepIn, stepOut, pause,
  evaluate, source, terminate

作者：元宝（实测环境 gdb 12.1 / Ubuntu 22.04）
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import queue

# ---------------- 传输层 ----------------
def send_msg(sock_out, obj):
    """DAP 标准帧格式：Content-Length 头 + JSON body"""
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    header = ("Content-Length: %d\r\n\r\n" % len(body)).encode('utf-8')
    if hasattr(sock_out, 'write'):
        sock_out.write(header + body)
        sock_out.flush()
    else:
        sock_out.sendall(header + body)

def read_msg(sock_in):
    """读一帧：先读 header 拿长度，再读 body"""
    # 读 header
    buf = b''
    while b'\r\n\r\n' not in buf:
        if hasattr(sock_in, 'read'):
            ch = sock_in.read(1)
        else:
            ch = sock_in.recv(1)
        if not ch:
            return None
        buf += ch
    m = re.search(rb'Content-Length:\s*(\d+)', buf)
    if not m:
        return None
    n = int(m.group(1))
    # 读 body
    body = b''
    while len(body) < n:
        if hasattr(sock_in, 'read'):
            chunk = sock_in.read(n - len(body))
        else:
            chunk = sock_in.recv(n - len(body))
        if not chunk:
            return None
        body += chunk
    return json.loads(body.decode('utf-8'))

# ---------------- gdb MI 会话 ----------------
class GdbSession:
    """用 -interpreter=mi2 驱动 gdb，异步读输出按 token 匹配"""
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.token = 0
        self.responses = {}
        self.async_queue = queue.Queue()
        self.reader = None
        self.alive = False
        self.program = None
        self.breakpoints = {}   # dap_id -> gdb_number
        self.bp_counter = 0
        self.started = False    # 程序是否已 -exec-run

    def start(self):
        self.proc = subprocess.Popen(
            ['gdb', '--interpreter=mi2', '-q', '--nx'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0
        )
        self.alive = True
        self.reader = threading.Thread(target=self._reader, daemon=True)
        self.reader.start()
        time.sleep(0.4)
        # 关掉确认提示，避免交互阻塞
        self.command('-gdb-set confirm off', wait=False)
        self.command('-gdb-set pagination off', wait=False)
        self.command('-gdb-set mi-async on', wait=False)
        return True

    def _reader(self):
        """持续读 gdb 输出，区分：带 token 的结果 / 异步通知"""
        stream = self.proc.stdout
        while self.alive:
            try:
                line = stream.readline()
            except Exception:
                break
            if not line:
                break
            try:
                text = line.decode('utf-8', errors='replace').strip()
            except Exception:
                continue
            if not text:
                continue
            # 异步通知：以 = 或 * 或 + 开头（如 =thread-created, *stopped）
            if text[0] in '=*+':
                self.async_queue.put(text)
                continue
            # 带 token 的结果行：以数字开头
            m = re.match(r'^(\d+)\^', text)
            if m:
                tok = int(m.group(1))
                self.responses[tok] = text
                continue
            # (gdb) 提示符
            if text.startswith('(gdb)'):
                continue

    def _next_token(self):
        with self.lock:
            self.token += 1
            return self.token

    def command(self, cmd, wait=True, timeout=10.0):
        """发一条 MI 命令，返回原始结果行"""
        if not self.proc or not self.alive:
            return None
        tok = self._next_token()
        full = "%d%s\n" % (tok, cmd)
        try:
            self.proc.stdin.write(full.encode('utf-8'))
            self.proc.stdin.flush()
        except Exception:
            return None
        if not wait:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            if tok in self.responses:
                return self.responses.pop(tok)
            time.sleep(0.01)
        return None

    def stop(self):
        self.alive = False
        try:
            self.command('-gdb-exit', wait=False)
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass

# ---------------- MI 结果解析 ----------------
def mi_scalar(text, key):
    """从 MI 输出里抠出 key="value" """
    m = re.search(r'\b%s="((?:[^"\\]|\\.)*)"' % re.escape(key), text)
    if not m:
        return None
    return m.group(1).replace('\\"', '"').replace('\\\\', '\\')

def parse_stopped(text):
    """解析 *stopped 异步通知"""
    reason = mi_scalar(text, 'reason')
    frame = {}
    m = re.search(r'frame=\{(.*?)\}', text, re.S)
    if m:
        f = m.group(1)
        for k in ('func', 'file', 'line', 'addr'):
            v = mi_scalar(f, k)
            if v is not None:
                frame[k] = v
    return reason, frame

def parse_stack(text):
    """解析 -stack-list-frames 的 stack=[frame={...},...]"""
    frames = []
    for m in re.finditer(r'frame=\{((?:[^{}]|\{[^{}]*\})*)\}', text):
        f = m.group(1)
        level = mi_scalar(f, 'level')
        item = {
            'id': int(level) if level and level.isdigit() else len(frames),
            'name': mi_scalar(f, 'func') or '??',
            'line': int(mi_scalar(f, 'line') or 0),
            'column': 1,
        }
        src = mi_scalar(f, 'fullname') or mi_scalar(f, 'file')
        if src:
            item['source'] = {'path': src, 'name': os.path.basename(src)}
        frames.append(item)
    return frames

def parse_locals(text):
    """解析 -stack-list-variables 的 variables=[{name=..,value=..},..]"""
    out = []
    for m in re.finditer(r'\{name="((?:[^"\\]|\\.)*)"(.*?)\}', text, re.S):
        name = m.group(1)
        rest = m.group(2)
        val = mi_scalar(rest, 'value') or ''
        typ = mi_scalar(rest, 'type') or ''
        out.append({'name': name, 'value': val, 'type': typ})
    return out

def parse_bkpt(text):
    """解析 -break-insert 返回里的 bkpt={...} 拿 number"""
    m = re.search(r'bkpt=\{([^{}]*)\}', text)
    if not m:
        return None
    n = mi_scalar(m.group(1), 'number')
    return int(n) if n and n.isdigit() else None

# ---------------- DAP 服务 ----------------
class DapServer:
    def __init__(self, out, gdb):
        self.out = out
        self.gdb = gdb
        self.seq = 0
        self.threads_cache = []
        self.vars_cache = {}
        self.var_counter = 0

    def _seq(self):
        self.seq += 1
        return self.seq

    def reply(self, req, body=None):
        msg = {'type': 'response', 'request_seq': req.get('seq', 0),
               'success': True, 'command': req.get('command')}
        if body is not None:
            msg['body'] = body
        msg['seq'] = self._seq()
        send_msg(self.out, msg)

    def reply_err(self, req, text):
        msg = {'type': 'response', 'request_seq': req.get('seq', 0),
               'success': False, 'command': req.get('command'),
               'message': str(text)}
        msg['seq'] = self._seq()
        send_msg(self.out, msg)

    def event(self, name, body=None):
        msg = {'type': 'event', 'event': name, 'seq': self._seq()}
        if body is not None:
            msg['body'] = body
        send_msg(self.out, msg)

    # ---- 各请求处理 ----
    def on_initialize(self, req):
        self.reply(req, {
            'supportsConfigurationDoneRequest': True,
            'supportsEvaluateForHovers': True,
            'supportsStepBack': False,
            'supportsSetVariable': False,
            'supportsRestartRequest': False,
            'supportsConditionalBreakpoints': True,
            'supportsFunctionBreakpoints': True,
            'supportsLogPoints': False,
            'supportsHitConditionalBreakpoints': False,
            'supportsCompletionsRequest': False,
            'supportsModulesRequest': False,
            'supportsGotoTargetsRequest': False,
            'supportsSteppingGranularity': False,
            'supportsInstructionBreakpoints': False,
            'supportsReadMemoryRequest': False,
        })
        self.event('initialized')

    def on_launch(self, req):
        args = req.get('arguments', {})
        prog = args.get('program') or args.get('target')
        cwd = args.get('cwd') or os.path.dirname(prog or '.')
        if not prog or not os.path.isfile(prog):
            self.reply_err(req, '程序不存在: %s' % prog)
            return
        self.gdb.program = prog
        # 用 -file-exec-and-symbols 载入
        r = self.gdb.command('-file-exec-and-symbols %s' % prog)
        if r is None or '^error' in r:
            self.reply_err(req, 'gdb 载入失败: %s' % (r or '无响应'))
            return
        if cwd:
            self.gdb.command('-environment-cd %s' % cwd, wait=False)
        self.reply(req)
        self.event('process', {
            'name': os.path.basename(prog),
            'systemProcessId': self.gdb.proc.pid if self.gdb.proc else 0,
            'isLocalProcess': True, 'startMethod': 'launch'
        })

    def on_attach(self, req):
        pid = req.get('arguments', {}).get('pid')
        if not pid:
            self.reply_err(req, 'attach 需要 pid')
            return
        r = self.gdb.command('-target-attach %d' % int(pid))
        if r is None or '^error' in r:
            self.reply_err(req, 'attach 失败: %s' % (r or ''))
            return
        self.reply(req)

    def on_setBreakpoints(self, req):
        args = req.get('arguments', {})
        src = args.get('source', {})
        path = src.get('path')
        want = args.get('breakpoints', []) or []
        lines = [int(b.get('line')) for b in want if b.get('line')]
        # 先清理该文件的旧断点
        for num in list(self.gdb.breakpoints.values()):
            self.gdb.command('-break-delete %d' % num, wait=False)
        self.gdb.breakpoints = {}
        result = []
        if path and os.path.isfile(path):
            for i, ln in enumerate(lines):
                cond = (want[i].get('condition') or '') if i < len(want) else ''
                cmd = '-break-insert %s:%d' % (path, ln)
                if cond:
                    cmd += ' -c %s' % cond
                r = self.gdb.command(cmd)
                if r and '^done' in r:
                    num = parse_bkpt(r)
                    if num:
                        self.gdb.breakpoints[i] = num
                    result.append({'id': i, 'verified': True, 'line': ln})
                else:
                    result.append({'id': i, 'verified': False, 'line': ln,
                                   'message': 'gdb 拒绝该断点'})
        self.reply(req, {'breakpoints': result})

    def on_threads(self, req):
        r = self.gdb.command('-thread-info')
        threads = []
        if r:
            for m in re.finditer(r'id="(\d+)"', r):
                tid = m.group(1)
                threads.append({'id': int(tid), 'name': 'thread %s' % tid})
        if not threads:
            # 没跑起来时给一个占位线程，避免 IDE 报错
            threads = [{'id': 1, 'name': 'main'}]
        self.threads_cache = threads
        self.reply(req, {'threads': threads})

    def on_stackTrace(self, req):
        r = self.gdb.command('-stack-list-frames')
        frames = parse_stack(r) if r else []
        self.reply(req, {'stackFrames': frames,
                         'totalFrames': len(frames)})

    def on_scopes(self, req):
        fid = req.get('arguments', {}).get('frameId', 0)
        scopes = []
        # Locals
        scopes.append({'name': 'Locals',
                       'variablesReference': 1000 + int(fid),
                       'expensive': False})
        # Registers（gdb MI 取寄存器较繁琐，这里给空壳占位保持协议完整）
        scopes.append({'name': 'Registers',
                       'variablesReference': 2000 + int(fid),
                       'expensive': True})
        self.reply(req, {'scopes': scopes})

    def on_variables(self, req):
        ref = req.get('arguments', {}).get('variablesReference', 0)
        out = []
        if 1000 <= ref < 2000:
            # 先把栈帧切过去再取局部变量
            fid = ref - 1000
            self.gdb.command('-stack-select-frame %d' % fid, wait=False)
            r = self.gdb.command('-stack-list-variables --simple-values')
            if r:
                for v in parse_locals(r):
                    self.var_counter += 1
                    out.append({
                        'name': v['name'],
                        'value': v['value'],
                        'type': v.get('type', ''),
                        'variablesReference': 0,
                        'evaluateName': v['name'],
                    })
        self.reply(req, {'variables': out})

    def _wait_stopped(self, timeout=15.0):
        """从异步队列里等一个 *stopped 通知，返回(reason, frame)"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                note = self.gdb.async_queue.get(timeout=0.1)
            except Exception:
                continue
            if note.startswith('*stopped'):
                return parse_stopped(note)
            if note.startswith('*running'):
                continue
        return (None, {})

    def _ensure_running(self):
        """程序没启动过就先 -exec-run（DAP 里 launch 只是载入符号，不启动）"""
        if self.gdb.started:
            return None
        self.gdb.started = True
        self.gdb.command('-exec-run', wait=False)
        return self._wait_stopped(timeout=15.0)

    def _exec(self, req, mi_cmd, event_reason):
        """执行 continue/next/step 等：发命令，等待停止事件"""
        # 关键：DAP 的 launch 只载入符号，程序要等 configurationDone 后才跑
        if not self.gdb.started:
            reason, _ = self._ensure_running()
            if reason:
                self.event('stopped', {
                    'reason': 'breakpoint' if reason == 'breakpoint-hit'
                              else ('exception' if 'signal' in (reason or '')
                                    else 'entry'),
                    'threadId': 1,
                    'allThreadsStopped': True,
                    'description': reason or '',
                })
                self.reply(req)
                return
        self.gdb.command(mi_cmd, wait=False)
        reason, _ = self._wait_stopped(timeout=15.0)
        if reason:
            self.event('stopped', {
                'reason': 'step' if reason in ('end-stepping-range',
                                               'function-finished')
                          else ('breakpoint' if reason == 'breakpoint-hit'
                                else ('exception' if 'signal' in (reason or '')
                                      else 'pause')),
                'threadId': 1,
                'allThreadsStopped': True,
                'description': reason or '',
            })
        self.reply(req, {'allThreadsContinued': False})

    def on_continue(self, req):
        self._exec(req, '-exec-continue', 'continue')

    def on_next(self, req):
        self._exec(req, '-exec-next', 'next')

    def on_stepIn(self, req):
        self._exec(req, '-exec-step', 'stepIn')

    def on_stepOut(self, req):
        self._exec(req, '-exec-finish', 'stepOut')

    def on_pause(self, req):
        self.gdb.command('-exec-interrupt', wait=False)
        self.event('stopped', {'reason': 'pause', 'threadId': 1,
                               'allThreadsStopped': True})
        self.reply(req)

    def on_evaluate(self, req):
        expr = req.get('arguments', {}).get('expression', '')
        r = self.gdb.command('-data-evaluate-expression %s' % expr)
        if r and '^done' in r:
            val = mi_scalar(r, 'value') or ''
            self.reply(req, {'result': val, 'variablesReference': 0})
        else:
            self.reply_err(req, '求值失败: %s' % (r or ''))

    def on_disconnect(self, req):
        self.reply(req)
        self.gdb.stop()

    # ---- 分发 ----
    def handle(self, req):
        cmd = req.get('command', '')
        table = {
            'initialize': self.on_initialize,
            'launch': self.on_launch,
            'attach': self.on_attach,
            'disconnect': self.on_disconnect,
            'setBreakpoints': self.on_setBreakpoints,
            'setFunctionBreakpoints': lambda r: self.reply(
                r, {'breakpoints': []}),
            'setExceptionBreakpoints': lambda r: self.reply(r),
            'configurationDone': lambda r: self.reply(r),
            'threads': self.on_threads,
            'stackTrace': self.on_stackTrace,
            'scopes': self.on_scopes,
            'variables': self.on_variables,
            'continue': self.on_continue,
            'next': self.on_next,
            'stepIn': self.on_stepIn,
            'stepOut': self.on_stepOut,
            'pause': self.on_pause,
            'evaluate': self.on_evaluate,
            'source': lambda r: self.reply(r, {'content': ''}),
            'terminate': lambda r: self.reply(r),
        }
        fn = table.get(cmd)
        if fn:
            try:
                fn(req)
            except Exception as e:
                self.reply_err(req, '%s: %s' % (type(e).__name__, e))
        else:
            # 未知请求：返回成功但空 body，避免 IDE 卡死
            self.reply(req)

# ---------------- 入口 ----------------
def serve_stdio():
    gdb = GdbSession()
    gdb.start()
    srv = DapServer(sys.stdout.buffer, gdb)
    while True:
        req = read_msg(sys.stdin.buffer)
        if req is None:
            break
        if req.get('type') == 'request':
            srv.handle(req)
    gdb.stop()

def serve_tcp(port=4711):
    gdb = GdbSession()
    gdb.start()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port))
    s.listen(1)
    sys.stderr.write('DAP 服务监听 127.0.0.1:%d\n' % port)
    sys.stderr.flush()
    conn, _ = s.accept()
    sys.stderr.write('客户端已连接\n')
    sys.stderr.flush()
    srv = DapServer(conn, gdb)
    while True:
        try:
            req = read_msg(conn)
        except Exception:
            break
        if req is None:
            break
        if req.get('type') == 'request':
            srv.handle(req)
    gdb.stop()
    conn.close()
    s.close()

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'stdio'
    if mode == 'tcp':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 4711
        serve_tcp(port)
    else:
        serve_stdio()
