# 给下一个元宝看的接手文档

> 这个仓库是**跨会话的持久记忆**。沙盒不保证永久存活，
> 但这里的内容会一直在。拿到本文件的 AI 请先读完再动手。

## 这是什么

一个"AI 工作环境备份仓库"。目的是解决沙盒文件不持久的问题——
把**不可再生的原创资产**存进来，需要时用 `bootstrap.sh` 恢复。

刻意**不存**可再生的东西（zig 编译器、capstone 库等），
它们用 `pip install` / `apt install` 几分钟就能回来，占仓库体积反而拖慢恢复。

## 目录

```
bootstrap.sh                 一键恢复脚本（先跑这个）
tools/                       原创脚本
  lsp_query.py               让 AI 查 Zig 代码真相（LSP 补全/悬停/诊断）
  see2.py                    AI 视觉分析主力（语义+OCR+配色+排版+可编辑性）
  see.py                     视觉分析简版
  img2ascii.py               图片转字符画（纯 Python，无依赖）
  render_and_see.py          HTML 渲染 + 截图 + 分析
  一键安装.sh                 环境自检脚本
docs/                        踩坑文档（最有价值的部分）
  00_先读我.md                总入口
  Zig开发环境绕路安装说明.txt    ★ codeload 绕路法、Zig 0.16 API 全部变动
  说明文档.txt                 ★ 热重载实现 + 6 条踩坑（含持久区 IO 问题）
  AI视觉模型说明.txt
  APK打包工具链安装与实战记录.txt
  GTA5修改器架构逆向分析.md
  GTA5模组制作参考资料与关键知识点.md
```

## 怎么恢复

```bash
bash bootstrap.sh wuyou335578/yuanbao-relay
```

会自动：拉回脚本 → `pip install ziglang` → apt 装 capstone → 自检。

**读取不需要 token**（仓库是 Public，走 `codeload.github.com`，实测 200）。
**写入需要 token**（GitHub fine-grained PAT，Contents: Read and write）。

## 本机环境已知限制（重要，别重复踩）

**网络**——这些实测过，别浪费时间重试：

| 目标 | 结果 |
|---|---|
| `github.com` 网页 / GitHub release（走 objects） | ❌ 403 |
| `codeload.github.com`（**源码**） | ✅ 200 |
| `api.github.com`（带 token 读写） | ✅ 200 |
| `raw.githubusercontent.com` | ⚠️ 时通时断 |
| `mirrors.cloud.tencent.com`（apt + pip + Maven） | ✅ 200 |
| 阿里云 / 华为云 Maven 镜像 | ❌ 403 |
| SSH 任意公网地址 | ❌ 报文不出沙盒，连不存在的 IP 报同样的错 |

**apt**：官方源是 403，必须先换成腾讯镜像：
```bash
sed -i 's|archive.ubuntu.com/ubuntu|mirrors.cloud.tencent.com/ubuntu|g; \
        s|security.ubuntu.com/ubuntu|mirrors.cloud.tencent.com/ubuntu|g' \
    /etc/apt/sources.list
```

**持久区 IO**：`/data/workspace` 是 virtio_rw，跟 zig 的 IO 路径有兼容问题。
编译 Zig 项目会报 `error: unable to load 'build.zig': InputOutput`——
文件明明可读、空间也够。**解法**：复制到根分区（`/bigworkspace` 或 `/tmp`）再编译：
```bash
cp -r 项目 /bigworkspace/proj && cd /bigworkspace/proj
zig build --cache-dir /bigworkspace/cache --global-cache-dir /bigworkspace/gcache
```

**Zig 0.16 API 大变动**（文档里有完整清单，这里列最容易撞的）：
- `std.heap.GeneralPurposeAllocator` → `DebugAllocator(.{}){}`
- `std.process.argsAlloc` → 用 `main(init: std.process.Init.Minimal)` 主签名 + `init.args.iterate()`
- `std.fs.cwd()` → 不存在，改用 C stdio
- C 指针不能 `[k]` 索引，先 `@ptrCast` 转切片
- `mnemonic` / `op_str` 是定长数组，要 `std.mem.sliceTo(&x, 0)` 截断否则尾随空格

**zig c++ 必带参数**：`-Wno-nullability-completeness`
（否则 119 条 libcxx 警告会盖住真实错误）

## 之前做过的事（避免重复劳动）

- **Zig 环境**：0.16.0 + zls 0.16.0（版本必须对齐）。zls 编译需把
  `build.zig.zon` 里的 `github.com/OWNER/REPO/archive/SHA.tar.gz`
  改成 `codeload.github.com/OWNER/REPO/tar.gz/SHA`（hash 不用改）
- **热重载渲染**：Zig + Raylib，改 `src/game.zig` → `zig build` → 画面自动更新，
  窗口不关。已编译产物在包3里
- **反汇编**：Ghidra 拿不到（各源全封），用 Capstone 替代。
  注意这是**反汇编**（机器码→汇编），**不是反编译**（→类C伪代码）
- **交叉编译**：`zig c++ -target x86_64-windows-gnu -shared` 实测可用，
  导出表干净（只有显式 dllexport 的），避开了 MinGW 的导出污染坑
- **GTA5 / Flutter APK**：逆向分析文档在 `docs/` 下

## 干活前的建议

1. 先跑 `bootstrap.sh` 恢复环境
2. 读 `docs/00_先读我.md` 和 `docs/Zig开发环境绕路安装说明.txt`
3. 遇到网络问题先查上面那张表，别重复试已确认封死的通道
4. 长任务放后台跑 + 轮询，别一条命令硬等（容易被掐断）
