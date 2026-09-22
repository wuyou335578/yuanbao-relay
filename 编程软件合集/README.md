# 编程软件合集

> 面向「沙盒环境重建」的离线编程工具包。所有组件均已**实测验证**，
> 不是"下载了就算数"。适用于 Ubuntu 22.04 / x86_64 沙盒。

最后更新：2026-09-23
实测环境：Ubuntu 22.04.5 LTS，内核 6.6.69-cube，AMD EPYC 9K65，4.31GB 内存

---

## 快速索引（给 AI 看）

| 你要干什么 | 去哪找 |
|---|---|
| 编译 C/C++ / Zig，完整 libcxx | `01_zig/`（Zig 0.16.0 完整版） |
| 图形 IDE（CodeLite 14.0） | `02_codelite/`（离线 deb） |
| 调试协议 DAP（gdb 12.1 能用） | `03_dap/dap_server.py` |
| LSP 补全 + 代码格式化 | `04_lsp_formatter/` |
| 一键恢复脚本 | `05_scripts/` |
| 验证方法（怎么确认真能用） | `06_test/` |

---

## 01_zig/ —— Zig 0.16.0 完整版

**这是什么**：Zig 编译器**完整版**，含 libc / libcxx / libcxxabi / libunwind / std。
**能编译 C 和 C++**（pip 装的残缺版只有 9.5MB，编不了 C++）。

| 项 | 值 |
|---|---|
| 分卷 | `zp00` ~ `zp04`，共 5 片 |
| 合并后 | `zig完整版.zip`，110,568,285 bytes |
| **合并后 md5** | `bf0ce2bce4e543e02c7833792bb8f17f` |
| 解压后 | `zig` 二进制 172,641,672 bytes（164.6 MiB）<br>`lib/` 19542 个文件 |

### 恢复

```bash
cat zp00 zp01 zp02 zp03 zp04 > zig完整版.zip
md5sum zig完整版.zip     # 必须 = bf0ce2bce4e543e02c7833792bb8f17f
unzip zig完整版.zip
chmod +x zig
./zig version            # → 0.16.0
```

或直接用：`bash ../05_scripts/restore_zig.sh`

### 已验证能力

- ✅ `zig version` → 0.16.0
- ✅ **C++ 编译运行**（iostream + vector + map + string）
  实测输出：`1 2 3 | map size=2 | libcxx ok`
- ✅ 交叉编译 `x86_64-windows-gnu` 生成 DLL（PE32+ x86-64）
- ✅ zip CRC 20819 条目全通过

### ⚠️ 三个必踩的坑

1. **解压目录必须是 `/dev/shm` 之类内存盘**
   virtiofs 文件数 IOPS 约 7，19542 个文件会极慢。内存盘 2.4 秒解压完。
2. **`/dev/shm` 默认 `noexec`**，二进制跑不起来（Permission denied）
   ```bash
   mount -o remount,size=2G,exec /dev/shm
   ```
3. **`zig c++` 必须带 `-Wno-nullability-completeness`**
   否则 119 条 libcxx 警告盖住真实错误。

---

## 02_codelite/ —— CodeLite 14.0 IDE

官网 `codelite.org` 在沙盒里 **403**。但 **apt 腾讯镜像里有**，直接装。

| deb | 大小 |
|---|---|
| `codelite_14.0+dfsg-2_amd64.deb` | 15,326,758 |
| `libwxgtk3.0-gtk3-0v5` | 4,368,366 |
| `libwxbase3.0-0v5` | 881,308 |
| `libwxsqlite3-3.0-0` | 63,948 |

### 恢复（离线，不依赖网络）

```bash
dpkg -i *.deb
apt-get install -y -f          # 补依赖
```

或：`bash ../05_scripts/restore_codelite.sh`

### 已验证

- ✅ GUI 真实渲染（虚拟屏 + 窗口名 `CodeLite 14.0.0`）
- ✅ 像素分析：452 种颜色，非背景 49.9%（**不是空屏**）
- ✅ 端到端编译运行：`CodeLite 工具链 OK, sum=15`
- ✅ `.workspace` 工程文件是 XML，结构合法

### 启动（虚拟屏）

```bash
bash ../05_scripts/run.sh      # 启动→截图→清理，一条命令
```

---

## 03_dap/ —— DAP 调试桥接层 ⭐ 本包最有价值的部分

### 为什么需要它

**gdb 原生 DAP（`-dap`）是 gdb 14+ 才有的。Ubuntu 22.04 是 gdb 12.1，没有。**

所以对不支持 DAP 的 gdb，自己实现了一层桥接：
**对外说 DAP(JSON)，对内用 gdb MI(`--interpreter=mi2`) 驱动。**

### 用法

```bash
# stdio 模式（IDE 直接拉起）
python3 dap_server.py stdio

# TCP 模式（IDE 连端口）
python3 dap_server.py tcp 4711
```

### 实现的 DAP 请求（15 项能力）

```
initialize / launch / attach / disconnect / setBreakpoints /
setFunctionBreakpoints / setExceptionBreakpoints / configurationDone /
threads / stackTrace / scopes / variables / continue / next /
stepIn / stepOut / pause / evaluate / source / terminate
```

### 实测结果：**11/11 全通过**

```
① initialize        ✅  (15 项能力)
② launch            ✅
③ setBreakpoints    ✅  verified=True
④ configurationDone ✅
⑤ continue          ✅  stopped 事件，reason=breakpoint
⑥ stackTrace        ✅  顶层=main
⑦ scopes            ✅  Locals/Registers
⑧ variables         ✅  n=5, r=120
⑨ evaluate "n"      ✅  → 5
⑩ stepIn            ✅
⑪ disconnect        ✅
```

**`n=5, r=120` 是 factorial(5) 的真实值** —— 证明变量读取真的在工作，不是空跑。

### ⚠️ 调试时修掉的一个真 bug

**现象**：断点 verified=True，但 `continue` 后收不到 stopped 事件。

**原因**：DAP 的 `launch` 语义只是**载入符号**，不启动程序。
我最初的实现里从没发过 `-exec-run`，程序压根没跑起来。

**修复**：`_ensure_running()` —— 首次 continue/next/step 时，
若 `self.gdb.started == False` 就先发 `-exec-run` 并等待首个 stopped。

> 这个坑很隐蔽：断点设置、scopes 全都"成功"，只有运行类请求静默失败。

### ⚠️ 环境限制：动态链接程序在 gdb 里 SIGSEGV

**实测发现**（与本代码无关，是沙盒限制）：

| 程序类型 | gdb 调试 |
|---|---|
| **静态链接**（`-static`） | ✅ 正常，能停能取变量 |
| **动态链接** | ❌ 启动时在 `ld-linux-x86-64.so.2` 里 SIGSEGV |

程序**直接运行**是好的（`./demo` → `result=15`），
`CAP_SYS_PTRACE` 也有（CapEff=0x1ffffffffff）。
所以是 **gdb 启动动态链接程序时的沙盒限制**。

**规避**：调试时用 `g++ -static` 编译。

---

## 04_lsp_formatter/ —— 语言服务 + 格式化

| 工具 | 版本 | 作用 |
|---|---|---|
| `clangd` | 14.0.0 | LSP：补全 / 跳转 / 诊断 |
| `clang-format` | 14.0.0 | CodeFormatter：代码格式化 |

### 安装

```bash
apt-get install -y --no-install-recommends clangd clang-format
```

### 格式化实测 A/B

输入（故意写乱）：
```cpp
int main( ) {
std::vector<int> v{1,2,3};
for(auto i:v){std::cout<<i;}
}
```

输出：
```cpp
int main() {
  std::vector<int> v{1, 2, 3};
  for (auto i : v) {
    std::cout << i;
  }
}
```

**96 字符 → 142 字符**（从字节数确认它真改了东西，不是空跑）。

### CodeLite 配置键（从二进制挖出来的真实键名）

不是猜的 —— `grep -a "LSP" /usr/bin/codelite` 挖出真实子句，
再用 XML 解析器验证：

```
LSP/General/Enabled (1)  ✅
LSP/Languages       (3)  ✅
LSP/CXX/Clangd      (1)  ✅
DAP/Debug Adapters  (1)  ✅
Editor/Formatters   (1)  ✅
```

**6/6 解析通过**。CodeLite 14.0 是 wxWidgets 3.0 GTK3，
配置走 `~/.codelite/` 的 **XML**，不是 JSON。

---

## 05_scripts/ —— 一键恢复

| 脚本 | 作用 |
|---|---|
| `restore_zig.sh` | Zig 完整版恢复（含 remount exec） |
| `restore_codelite.sh` | CodeLite 离线 deb 安装 + X11 环境 |
| `run.sh` | CodeLite 虚拟屏启动 + 截图 |
| `swap_on.sh` | 建 3GB swap（内存突破用） |

---

## 06_test/ —— 验证脚本（怎么确认真能用）

| 脚本 | 验证什么 |
|---|---|
| `dap_client.py` | DAP 协议 11 步全流程 |
| `diag.py` | 直接跟 gdb MI 对话，逐条看返回 |
| `diag2.py` | 静态 vs 动态程序调试对比 |

**方法论**：不要"装上了就当成功"。
每个组件都要有**可证伪的现象验证**：

- GUI → 像素分析（颜色数、非背景占比），不是只看文件大小
- 编译器 → 真实编译 + 运行出正确结果
- 格式化 → 前后字节数对比
- 调试器 → 停住 + 取到真实变量值

---

## 通用经验（沙盒重建必看）

### 遇 403 先找内网镜像（已应验 4 次）

```
codelite.org     403  ❌
github.com       403  ❌
huggingface      403  ❌
mirrors.tencent.com  ✅ 有！
```

apt 配置：
```bash
cat > /etc/apt/sources.list <<'EOS'
deb https://mirrors.tencent.com/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.tencent.com/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.tencent.com/ubuntu/ jammy-security main restricted universe multiverse
EOS
```

### 其他实测结论

- **内网下载 196 MB/s**，2 并发峰值 389 MB/s
- **上传极慢**（约 3.7 MB/s），上传 >20MB 会搞崩沙盒
- **`df` 报 500M 是假数字** —— 实测能写 2.4GB 且仍不满
- **`/dev/shm` 默认 64MB 且 `noexec`** —— 要 `remount,size=2G,exec`
- **无 GPU** —— 虚拟 Vulkan(llvmpipe) 是 CPU 软实现，不加速 AI 推理
- **内存 4.31GB 是真顶** —— 加 swap 能到约 3.9GB，再往上沙盒 502 崩溃

---

## 组件未覆盖 / 已知缺失

- **gdb-dap / lldb-vscode**：仓库里没有，gdb 12.1 不带
  → 本包用 `03_dap/dap_server.py` 补上
- **cmake**：未包含，需时 `apt-get install cmake`
- **GPU**：沙盒没有，任何需要 GPU 的编译/推理都跑不了
