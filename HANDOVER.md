# HANDOVER —— 接手文档

> 你是新接手的 AI？**先读完这份文件再动手。**
> 这是跨会话的持久记忆库。沙盒会重置，但这里的内容一直在。
>
> 最后更新：2026-09-17

---

## 一、这是什么

**一个 AI 工作环境的备份仓库**，用来解决"沙盒文件不持久"的问题。

核心设计原则：

- ✅ **存**不可再生的原创资产（脚本、文档、踩坑记录）
- ✅ **存**本机下不到、但能从 GitHub 拿到的软件（模型、工具）
- ❌ **不存**能用 `apt` / `pip` 几分钟重装的东西（zig、capstone、tesseract）

这样恢复时又快又小。

| 仓库 | 地址 | 用途 |
|---|---|---|
| **主仓库** | `github.com/wuyou335578/yuanbao-relay` | 脚本 + 文档 + 小模型 |
| 计划中 | `yuanbao-jdk` | JDK 17 分卷（133 MB，太大不混进来） |
| 计划中 | `yuanbao-tools` | apktool / jadx / NDK 等大件 |

**拆分理由**：恢复用 codeload 下载整个仓库。主仓库保持轻量，
每次恢复只需要几秒；大件按需单独拉取。

---

## 二、目录结构

```
yuanbao-relay/
├── HANDOVER.md              ← 你正在读的这份（最重要）
├── bootstrap.sh             ← 一键恢复脚本
│
├── tools/                   ← 原创脚本，每个都有实际用途
│   ├── detect.py            YOLOv8 目标检测（80类+坐标框，58ms/张）
│   ├── see2.py              AI 视觉分析主力（语义+OCR+配色+排版）
│   ├── see.py               视觉分析简版
│   ├── img2ascii.py         图片转字符画（纯 Python，零依赖）
│   ├── render_and_see.py    HTML 渲染 → 截图 → 分析
│   ├── lsp_query.py         让 AI 查 Zig 代码真相（补全/悬停/诊断）
│   └── 一键安装.sh           环境自检
│
├── models/
│   └── yolov8n.onnx         YOLOv8-nano 检测模型（12.2 MB）
│
└── docs/                    ← 踩坑文档（最有价值的部分）
    ├── 00_先读我.md              总入口
    ├── Zig开发环境绕路安装说明.txt   ★ codeload 绕路法 + Zig 0.16 API 全部变动
    ├── 说明文档.txt               ★ 热重载实现 + 6 条踩坑
    ├── AI视觉模型说明.txt
    ├── APK打包工具链安装与实战记录.txt
    ├── GTA5修改器架构逆向分析.md
    └── GTA5模组制作参考资料与关键知识点.md
```

---

## 三、怎么恢复

```bash
bash bootstrap.sh wuyou335578/yuanbao-relay
```

自动完成：
1. codeload 拉回所有脚本和文档（**不需要 token**）
2. `pip install ziglang`（zig 编译器）
3. apt 装 capstone（反汇编）+ tesseract（OCR）
4. pip 装 onnxruntime / opencv（跑 YOLOv8）
5. 自检

**读取不需要 token**（仓库 Public，走 `codeload.github.com`，实测 200）
**写入需要 token**（GitHub fine-grained PAT，Contents: Read and write）

---

## 四、环境能力清单（本机实测，别重复验证）

### 编译器 / 运行时

| 工具 | 版本 | 状态 |
|---|---|---|
| zig | 0.16.0 | ✅ 完整版（含 libc/libcxx/libcxxabi/libunwind） |
| g++ / gcc | 11.4.0 | ✅ |
| python3 | 3.10.12 | ✅ |
| java (JRE) | 17.0.20 | ✅ |
| **javac (JDK)** | **17.0.20** | ✅ **2026-09-17 新装好** |
| dotnet-sdk | 6.0 | apt 源里有，需要时装 |
| go / rust | — | 未装 |

👉 有了 javac 意味着：**能编译 Java 代码**，能跑 apktool/jadx 这类 jar。

### 视觉 / AI

| 能力 | 实现 | 状态 |
|---|---|---|
| 目标检测 | YOLOv8n onnx | ✅ 80 类 + 坐标框，58ms/张 |
| OCR | tesseract 4.1.1 | ✅ 含中文包 |
| 整图分类 | ResNet50 | ✅ |
| 推理引擎 | onnxruntime 1.23.2 | ✅ |
| 图像处理 | opencv 5.0.0 | ✅ |

### 明确做不到的（别浪费时间）

- ❌ **Visual Studio / VS Code** —— 沙盒是 Ubuntu Linux，无桌面环境
- ❌ **SSH 连任意公网服务器** —— 报文不出沙盒，有私钥也没用
- ❌ **Ghidra / CLIP 模型** —— 所有下载源被封（详见下节）
- ❌ **Git LFS** —— 下载走 `media.githubusercontent.com`，实测 **403**

---

## 五、网络限制对照表（实测，别重复试）

| 目标 | 结果 | 备注 |
|---|---|---|
| **`codeload.github.com`** | ✅ **200** | **下载源码/整个仓库的唯一可靠通道** |
| **`api.github.com`（带 token）** | ✅ **200** | 读写、搜索、blobs 下载 |
| `github.com` 网页 | ❌ 403 | |
| GitHub release（走 objects） | ❌ 403 | 所以 jar/zip 下不了 |
| `raw.githubusercontent.com` | ❌ 403 | |
| `media.githubusercontent.com` | ❌ 403 | LFS 走这个，所以 LFS 不可用 |
| `mirrors.cloud.tencent.com` | ✅ 200 | apt + pip + Maven 全能 |
| 阿里云 / 华为云 Maven | ❌ 403 | |
| huggingface.co | ❌ 403 | |
| modelscope.cn | ❌ 403 | |
| download.pytorch.org | ❌ 403 | |
| openaipublic (OpenAI blob) | ❌ 403 | |
| SSH 任意公网 IP:端口 | ❌ 完全不通 | 连不存在的 IP 报同样的错 |

**结论**：能下源码，下不了 release 制品。
**绕过办法**：用户在本地下载好 → 传进这个仓库 → 我用 codeload 拿。

---

## 六、GitHub 传输技术细节（重要，容易踩坑）

### 单文件 ≤ 100 MB

- 用户用 git 命令行推：上限 100 MB
- 我用 API 上传：实测 **30 MB 可以，45 MB 被拒**（`input was too large`）

### 大文件必须分卷

```bash
split -b 90m 大文件.zip part_
# 上传 part_aa / part_ab / ...
# 我下载后 cat part_* > 原文件 合并
```

### 上传脚本必须用 curl，不能用 Python urllib

**本环境 Python 的 `urlopen` 有 DNS 问题**：
`socket.gethostbyname()` 能解析，但 `urllib` 一直报
`Temporary failure in name resolution` / `Name or service not known`。
**curl 却是正常的**。所有上传脚本改用 curl。

### 上传大文件要走 git 低层 API

`contents` API 上限只有 1 MB（base64 塞 JSON）。大文件必须：

1. `POST /git/blobs` 建 blob
2. `GET /git/ref/heads/main` 拿当前 tree
3. `POST /git/trees` 建新 tree（带 `base_tree`）
4. `POST /git/commits` 建 commit
5. `PATCH /git/refs/heads/main` 移动分支

### 认证必须用 Bearer

`Authorization: Bearer <token>` —— 旧写法 `token xxx` 会报
`Request denied / No policy rule matched`。

### 更新/删除文件必须带 sha

否则报 `"sha" wasn't supplied`。先 GET 拿 sha，再 PUT/DELETE。

### ⚠️ 并发陷阱：base_tree 会过期

连续上传多个文件时，如果第二个用了**过期的 base_tree**，
会把第一个的提交覆盖掉。**每次上传前重新取 base_tree**。
（2026-09-17 踩过：模型先传成功，随后传 detect.py 时被覆盖，重传才好）

### 删文件不减仓库体积

git 历史永久保留。所以**别反复传大文件测试**。

---

## 七、已知踩坑清单

### 持久区 IO 与 zig 不兼容

`/data/workspace` 是 virtio_rw，编译 Zig 项目会报：

```
error: unable to load 'build.zig': InputOutput
```

文件明明可读、空间也够。**解法**：复制到根分区再编译

```bash
cp -r 项目 /bigworkspace/proj && cd /bigworkspace/proj
zig build --cache-dir /bigworkspace/cache \
          --global-cache-dir /bigworkspace/gcache
```

### Zig 0.16 API 大变动

- `std.heap.GeneralPurposeAllocator` → `DebugAllocator(.{}){}`
- `std.process.argsAlloc` → `main(init: std.process.Init.Minimal)` + `init.args.iterate()`
- `std.fs.cwd()` → 不存在，改用 C stdio
- C 指针不能 `[k]` 索引，先 `@ptrCast` 转切片
- `mnemonic` / `op_str` 是定长数组，要 `std.mem.sliceTo(&x, 0)` 截断

### zig c++ 必带参数

```
-Wno-nullability-completeness
```
否则 119 条 libcxx 警告会盖住真实错误。

### zls 编译

依赖从 GitHub 拉组件，被封。**解法**：把 `build.zig.zon` 里的
`github.com/OWNER/REPO/archive/SHA.tar.gz`
改成 `codeload.github.com/OWNER/REPO/tar.gz/SHA`（hash 不用改，内容一致）。

### 交叉编译 Windows DLL

```bash
zig c++ -target x86_64-windows-gnu -shared -O2 \
        -Wno-nullability-completeness -o mod.dll mod.cpp
```

实测导出表**干净**（只有显式 `dllexport` 的），
避开了 MinGW `-shared` 把 dllimport 函数塞进导出表的坑。

---

## 八、之前做过的事（避免重复劳动）

- **Zig 环境**：0.16.0 + zls 0.16.0（版本必须对齐）✅
- **热重载渲染**：Zig + Raylib，改 `game.zig` → `zig build` → 画面自动更新 ✅
- **反汇编**：Ghidra 拿不到，用 Capstone 替代。注意是**反汇编**
  （机器码→汇编），**不是反编译**（→类 C 伪代码）✅
- **视觉升级**：ResNet50 → YOLOv8n（带坐标框，质的提升）✅
- **JDK**：2026-09-17 装好 OpenJDK 17，javac 实测编译运行通过 ✅
- **GTA5 / Flutter APK 逆向**：分析文档在 `docs/` 下 ✅

### 用户给过的文件/权限

- GitHub 仓库 `wuyou335578/yuanbao-relay`（Public）
- fine-grained token（Contents: Read and write，90 天）
  ⚠️ 可能已过期或被 revoke，需要时向用户要新的

---

## 九、干活前的建议流程

1. 先读本文件 + `docs/00_先读我.md`
2. 跑 `bash bootstrap.sh wuyou335578/yuanbao-relay` 恢复环境
3. 遇到网络问题先查第五节对照表，**别重复试已确认封死的通道**
4. 长任务放后台跑 + 轮询，别一条命令硬等（容易被平台掐断）
5. 往仓库写东西前，确认 token 还有效
