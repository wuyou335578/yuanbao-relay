#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lsp_query.py —— 让 AI 直接查询语言服务器（原创）

用途：不打开编辑器，也能获得编译器级别的真实代码信息：
  · 诊断（语法/类型错误，来自真实编译器前端，不是猜的）
  · 补全（真有哪些成员可用）
  · 悬停（标识符的真实类型）
  · 定义跳转位置

为什么需要它：
  AI 写 Zig 代码时，光靠记忆容易写出过时的 API。
  ZLS 跑的是与编译器同源的分析器，它说的才是准的。

用法:
  python3 lsp_query.py diagnose 文件.zig     # 查错误
  python3 lsp_query.py hover 文件.zig 行 列  # 查类型（1-based 行，0-based 列）
  python3 lsp_query.py complete 文件.zig 行 列
  python3 lsp_query.py definition 文件.zig 行 列
  python3 lsp_query.py symbols 文件.zig

依赖: 仅标准库 + zls（/usr/local/bin/zls）
"""

import json
import os
import subprocess
import sys
import threading
import time
import queue

ZLS_PATH = os.environ.get("ZLS_PATH", "/usr/local/bin/zls")
TIMEOUT = 30.0


class LspClient:
    """极简 LSP 客户端（同步封装），只实现必要的方法。"""

    def __init__(self, cmd, root_uri):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.root_uri = root_uri
        self._id = 0
        self._q = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        """后台线程持续读 stdout，按 id 分派到队列。"""
        while True:
            try:
                n = None
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        return
                    line = line.strip()
                    if not line:
                        break
                    if line.lower().startswith(b"content-length:"):
                        n = int(line.split(b":")[1].strip())
                if n is None:
                    continue
                body = self.proc.stdout.read(n)
                self._q.put(json.loads(body))
            except (ValueError, OSError):
                return

    def _next_id(self):
        self._id += 1
        return self._id

    def request(self, method, params, wait_id=None, timeout=TIMEOUT):
        mid = self._next_id()
        self.notify(method, params, mid)
        return self.wait_for(mid, timeout)

    def notify(self, method, params, mid=None):
        obj = {"jsonrpc": "2.0", "method": method, "params": params}
        if mid is not None:
            obj["id"] = mid
        body = json.dumps(obj).encode()
        try:
            self.proc.stdin.write(
                f"Content-Length: {len(body)}\r\n\r\n".encode() + body
            )
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def wait_for(self, mid, timeout=TIMEOUT):
        """等待指定 id 的响应，同时把通知（如诊断）交给调用方处理。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("id") == mid:
                return msg
        return None

    def drain(self, seconds=3.0, method=None):
        """收集通知（诊断等）。"""
        out = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                msg = self._q.get(timeout=0.3)
            except queue.Empty:
                continue
            if method is None or msg.get("method") == method:
                out.append(msg)
        return out

    def close(self):
        try:
            self.proc.kill()
        except OSError:
            pass


def path_to_uri(p):
    return "file://" + os.path.abspath(p)


def start_session(filepath):
    """启动 ZLS 会话并完成 initialize/initialized 握手。"""
    if not os.path.exists(ZLS_PATH):
        return None, f"ZLS 不存在: {ZLS_PATH}"
    if not os.path.exists(filepath):
        return None, f"文件不存在: {filepath}"

    root = os.path.dirname(os.path.abspath(filepath)) or "."
    c = LspClient([ZLS_PATH], path_to_uri(root))
    resp = c.request("initialize", {
        "processId": os.getpid(),
        "rootUri": path_to_uri(root),
        "capabilities": {
            "textDocument": {
                "publishDiagnostics": {},
                "completion": {"completionItem": {"snippetSupport": True}},
                "hover": {"contentFormat": ["plaintext"]},
                "definition": {},
                "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
            }
        },
        "workspaceFolders": [{"uri": path_to_uri(root), "name": root}],
    })
    if resp is None or "result" not in resp:
        c.close()
        return None, "initialize 超时或失败"
    c.notify("initialized", {})

    # 打开文件
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    c.notify("textDocument/didOpen", {
        "textDocument": {
            "uri": path_to_uri(filepath),
            "languageId": "zig",
            "version": 1,
            "text": text,
        }
    })
    return c, None


SEVERITY = {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}


def cmd_diagnose(path):
    c, err = start_session(path)
    if err:
        print(f"  ❌ {err}")
        return 1
    try:
        diags = []
        for msg in c.drain(seconds=20.0):
            if msg.get("method") == "textDocument/publishDiagnostics":
                diags = msg["params"].get("diagnostics", [])
                if diags:
                    break
        if not diags:
            print("  ✅ 未发现问题")
            return 0
        print(f"  ⚠️ 发现 {len(diags)} 个问题：")
        for d in diags:
            line = d["range"]["start"]["line"] + 1
            col = d["range"]["start"]["character"] + 1
            sev = SEVERITY.get(d.get("severity"), "?")
            msg_txt = d["message"].split("\n")[0]
            print(f"    行{line}:{col} [{sev}] {msg_txt}")
        return 0
    finally:
        c.close()


def cmd_hover(path, line, col):
    c, err = start_session(path)
    if err:
        print(f"  ❌ {err}")
        return 1
    try:
        r = c.request("textDocument/hover", {
            "textDocument": {"uri": path_to_uri(path)},
            "position": {"line": line - 1, "character": col},
        })
        if r is None or not r.get("result"):
            print("  该位置无悬停信息")
            return 0
        cont = r["result"].get("contents")
        if isinstance(cont, dict):
            print(f"  {cont.get('value', '')}")
        elif isinstance(cont, list):
            for x in cont:
                print(f"  {x if isinstance(x,str) else x.get('value','')}")
        else:
            print(f"  {cont}")
        return 0
    finally:
        c.close()


def cmd_complete(path, line, col, limit=25):
    c, err = start_session(path)
    if err:
        print(f"  ❌ {err}")
        return 1
    try:
        r = c.request("textDocument/completion", {
            "textDocument": {"uri": path_to_uri(path)},
            "position": {"line": line - 1, "character": col},
        })
        if r is None:
            print("  补全请求超时")
            return 1
        res = r.get("result")
        items = res.get("items", []) if isinstance(res, dict) else (res or [])
        print(f"  返回 {len(items)} 个补全项：")
        for it in items[:limit]:
            detail = it.get("detail", "")
            print(f"    {it.get('label')}" + (f"  ({detail})" if detail else ""))
        if len(items) > limit:
            print(f"    ...共 {len(items)} 项")
        return 0
    finally:
        c.close()


def cmd_definition(path, line, col):
    c, err = start_session(path)
    if err:
        print(f"  ❌ {err}")
        return 1
    try:
        r = c.request("textDocument/definition", {
            "textDocument": {"uri": path_to_uri(path)},
            "position": {"line": line - 1, "character": col},
        })
        res = r.get("result") if r else None
        if not res:
            print("  未找到定义")
            return 0
        if isinstance(res, list):
            res = res[0]
        uri = res.get("uri", "")
        st = res.get("range", {}).get("start", {})
        print(f"  定义位置: {uri}")
        print(f"    行 {st.get('line',0)+1}, 列 {st.get('character',0)+1}")
        return 0
    finally:
        c.close()


def cmd_symbols(path):
    c, err = start_session(path)
    if err:
        print(f"  ❌ {err}")
        return 1
    try:
        r = c.request("textDocument/documentSymbol", {
            "textDocument": {"uri": path_to_uri(path)}
        })
        res = r.get("result") if r else None
        if not res:
            print("  无符号")
            return 0

        def walk(items, depth=0):
            for it in items:
                kind = it.get("kind", 0)
                name = it.get("name", "?")
                st = it.get("location", {}).get("range", {}).get("start", {})
                ln = st.get("line", 0) + 1
                print(f"  {'  '*depth}{name}  (kind={kind}, 行{ln})")
                if it.get("children"):
                    walk(it["children"], depth + 1)

        walk(res)
        return 0
    finally:
        c.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    path = sys.argv[2]

    if cmd == "diagnose":
        return cmd_diagnose(path)
    if cmd in ("hover", "complete", "definition"):
        if len(sys.argv) < 5:
            print(f"用法: {sys.argv[0]} {cmd} <文件> <行> <列>")
            return 1
        try:
            line = int(sys.argv[3]); col = int(sys.argv[4])
        except ValueError:
            print("行/列必须是整数")
            return 1
        fn = {"hover": cmd_hover, "complete": cmd_complete,
              "definition": cmd_definition}[cmd]
        return fn(path, line, col)
    if cmd == "symbols":
        return cmd_symbols(path)

    print(f"未知命令: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
