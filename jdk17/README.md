# jdk17/ —— OpenJDK 17 完整版（分卷存放）

> 给接手的 AI / 用户看。**这目录是 6 个分卷，不是 6 个独立文件。**

## 这是什么

OpenJDK 17.0.20 完整版，260 MB 安装体积打包压缩成 **133.8 MB**，
因为单文件不能用 API 传（实测上限约 30 MB），切成 6 份。

**原始信息**

| 项 | 值 |
|---|---|
| 原始文件 | `jdk17.tar.gz` |
| 大小 | 133.8 MB（140,252,112 字节） |
| **合并后 md5** | `41aacb511817897a1f59a653730cf78f` |
| 内容 | `java-17-openjdk-amd64/` 完整目录 |
| 来源 | `apt install openjdk-17-jdk-headless`（Ubuntu 22.04） |

## 分卷清单（按顺序）

| 文件 | 大小 |
|---|---|
| `jdk17_paa` | 25.0 MB |
| `jdk17_pab` | 25.0 MB |
| `jdk17_pac` | 25.0 MB |
| `jdk17_pad` | 25.0 MB |
| `jdk17_pae` | 25.0 MB |
| `jdk17_paf` | 8.8 MB |

## 怎么恢复（两步）

```bash
# 1. 按文件名顺序合并
cat jdk17_paa jdk17_pab jdk17_pac jdk17_pad jdk17_pae jdk17_paf > jdk17.tar.gz

# 2. 校验 + 解压
md5sum jdk17.tar.gz    # 应得 41aacb511817897a1f59a653730cf78f
tar xzf jdk17.tar.gz

# 3. 放到 JDK 目录（解压出来是 java-17-openjdk-amd64/）
sudo mv java-17-openjdk-amd64 /usr/lib/jvm/
export PATH=/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# 4. 验证
javac -version    # 应输出 javac 17.0.20
java -version     # 应输出 openjdk version "17.0.20"
```

> ⚠️ `cat` 合并时**必须按 paa→paf 字母顺序**，顺序错了 tar 会解压失败。

## 包含哪些工具

解压后 `bin/` 下有完整 JDK 工具链：

```
javac      Java 编译器（关键，JRE 没有这个）
java       运行时
jar        打包
jarsigner  jar 签名
jlink      制作精简运行时
javap      反编译看字节码
javadoc / jshell / jdb / jmod / jpackage ...
```

## 为什么备份它

- 有了 `javac` 才能**编译 Java 代码**（之前只有 JRE，只能跑不能编）
- 才能跑 **apktool / jadx** 这类 jar（处理安卓 APK）
- 是走安卓 APP 构建链路的前提

## 更省事的替代方案

如果只需要编译 Java、不在乎完整性和额外工具，可以：

```bash
# 方案A：apt 直接装（几分钟，不用从仓库下 133MB）
apt-get install -y openjdk-17-jdk-headless

# 方案B：用 jlink 做精简版（实测 71 MB，含 javac）
jlink --add-modules jdk.compiler,java.se,jdk.jartool,jdk.jdeps \
      --output ./minijdk --compress=2 --no-header-files --no-man-pages
```

**建议**：网络通畅时优先 `apt install`，比从仓库拉 133 MB 快。
这份备份主要用于 apt 源不可用时兜底。
