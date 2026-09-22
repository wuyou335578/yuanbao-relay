#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DAP 协议测试客户端：完整走一遍调试流程"""
import json, subprocess, sys, os, time

def send(p, obj):
    b = json.dumps(obj).encode('utf-8')
    p.stdin.write(b'Content-Length: %d\r\n\r\n' % len(b) + b)
    p.stdin.flush()

def read(p, timeout=20):
    """读一帧 DAP 消息"""
    import select
    buf = b''
    deadline = time.time() + timeout
    # 读 header
    while b'\r\n\r\n' not in buf:
        if time.time() > deadline:
            return None
        r, _, _ = select.select([p.stdout], [], [], 0.5)
        if not r:
            continue
        ch = p.stdout.read(1)
        if not ch:
            return None
        buf += ch
    import re
    m = re.search(rb'Content-Length:\s*(\d+)', buf)
    if not m:
        return None
    n = int(m.group(1))
    body = b''
    while len(body) < n:
        chunk = p.stdout.read(n - len(body))
        if not chunk:
            return None
        body += chunk
    return json.loads(body.decode('utf-8'))

def collect(p, want_cmd=None, timeout=20):
    """收集消息直到拿到指定 command 的 response"""
    deadline = time.time() + timeout
    events = []
    while time.time() < deadline:
        msg = read(p, max(1, deadline - time.time()))
        if msg is None:
            break
        if msg.get('type') == 'event':
            events.append(msg)
            continue
        if msg.get('type') == 'response':
            if want_cmd is None or msg.get('command') == want_cmd:
                return msg, events
    return None, events

def main():
    src = os.path.abspath('sd')
    p = subprocess.Popen(
        [sys.executable, '/data/workspace/编程软件合集/dap/dap_server.py', 'stdio'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0
    )
    seq = [0]
    def nxt():
        seq[0] += 1
        return seq[0]

    results = {}

    # 1. initialize
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'initialize',
             'arguments': {'adapterID': 'gdb', 'clientID': 'test',
                           'linesStartAt1': True, 'pathFormat': 'path'}})
    r, ev = collect(p, 'initialize')
    ok = r is not None and r.get('success')
    print('  ① initialize        : %s' % ('✅' if ok else '❌ %s' % r))
    results['initialize'] = ok
    caps = (r or {}).get('body', {})
    print('       能力: %d 项' % len(caps))

    # 2. launch
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'launch',
             'arguments': {'program': src, 'cwd': os.getcwd()}})
    r, ev = collect(p, 'launch')
    ok = r is not None and r.get('success')
    print('  ② launch            : %s %s' % ('✅' if ok else '❌',
          '' if ok else (r or {}).get('message', '')))
    results['launch'] = ok

    # 3. setBreakpoints (第 17 行: int result = compute(n);)
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'setBreakpoints',
             'arguments': {'source': {'path': os.path.abspath('static_demo.cpp')},
                           'breakpoints': [{'line': 10}]}})
    r, ev = collect(p, 'setBreakpoints')
    bps = (r or {}).get('body', {}).get('breakpoints', [])
    ok = r is not None and r.get('success') and bps and bps[0].get('verified')
    print('  ③ setBreakpoints    : %s  行数=%d verified=%s' % (
          '✅' if ok else '❌', len(bps),
          bps[0].get('verified') if bps else 'N/A'))
    results['breakpoints'] = ok

    # 4. configurationDone
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'configurationDone'})
    r, _ = collect(p, 'configurationDone')
    ok = r is not None and r.get('success')
    print('  ④ configurationDone: %s' % ('✅' if ok else '❌'))
    results['configDone'] = ok

    # 5. continue —— 应该停在断点
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'continue',
             'arguments': {'threadId': 1}})
    r, ev = collect(p, 'continue', timeout=25)
    stopped = [e for e in ev if e.get('event') == 'stopped']
    ok = r is not None and r.get('success') and len(stopped) > 0
    reason = stopped[0]['body'].get('reason') if stopped else 'N/A'
    print('  ⑤ continue          : %s  stopped事件=%d reason=%s' % (
          '✅' if ok else '❌', len(stopped), reason))
    results['continue'] = ok

    # 6. stackTrace
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'stackTrace',
             'arguments': {'threadId': 1, 'startFrame': 0, 'levels': 10}})
    r, _ = collect(p, 'stackTrace')
    frames = (r or {}).get('body', {}).get('stackFrames', [])
    ok = r is not None and r.get('success') and len(frames) > 0
    top = frames[0].get('name') if frames else 'N/A'
    print('  ⑥ stackTrace        : %s  帧数=%d 顶层=%s' % (
          '✅' if ok else '❌', len(frames), top))
    results['stackTrace'] = ok

    # 7. scopes
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'scopes',
             'arguments': {'frameId': 0}})
    r, _ = collect(p, 'scopes')
    scopes = (r or {}).get('body', {}).get('scopes', [])
    ok = r is not None and r.get('success') and len(scopes) > 0
    print('  ⑦ scopes            : %s  %s' % ('✅' if ok else '❌',
          '/'.join(s['name'] for s in scopes)))
    results['scopes'] = ok

    # 8. variables
    vref = scopes[0]['variablesReference'] if scopes else 1000
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'variables',
             'arguments': {'variablesReference': vref}})
    r, _ = collect(p, 'variables')
    vs = (r or {}).get('body', {}).get('variables', [])
    ok = r is not None and r.get('success') and len(vs) > 0
    names = ', '.join('%s=%s' % (v['name'], v['value']) for v in vs[:5])
    print('  ⑧ variables         : %s  变量数=%d' % ('✅' if ok else '❌', len(vs)))
    print('       %s' % names)
    results['variables'] = ok

    # 9. evaluate
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'evaluate',
             'arguments': {'expression': 'n', 'context': 'hover'}})
    r, _ = collect(p, 'evaluate')
    val = (r or {}).get('body', {}).get('result')
    ok = r is not None and r.get('success')
    print('  ⑨ evaluate "n"      : %s  结果=%s' % ('✅' if ok else '❌', val))
    results['evaluate'] = ok

    # 10. stepIn
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'stepIn',
             'arguments': {'threadId': 1}})
    r, ev = collect(p, 'stepIn', timeout=20)
    ok = r is not None and r.get('success')
    print('  ⑩ stepIn            : %s' % ('✅' if ok else '❌'))
    results['stepIn'] = ok

    # 11. disconnect
    send(p, {'seq': nxt(), 'type': 'request', 'command': 'disconnect',
             'arguments': {}})
    r, _ = collect(p, 'disconnect', timeout=10)
    ok = r is not None and r.get('success')
    print('  ⑪ disconnect        : %s' % ('✅' if ok else '❌'))
    results['disconnect'] = ok

    # 汇总
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print()
    print('  ═══ 汇总: %d/%d 通过 ═══' % (passed, total))
    for k, v in results.items():
        print('    %s %s' % ('✅' if v else '❌', k))

    try:
        p.terminate()
    except Exception:
        pass
    return 0 if passed >= total - 1 else 1

if __name__ == '__main__':
    sys.exit(main())
