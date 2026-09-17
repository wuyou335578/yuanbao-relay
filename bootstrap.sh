#!/bin/bash
# ============================================================
#  bootstrap.sh —— 从 GitHub 仓库一键恢复工作环境
#
#  用法（只需仓库地址，无需 token，因为仓库可设为 public；
#  若私有，加 -H "Authorization: token xxx" 或用 git clone 走 SSH）
#
#    bash bootstrap.sh <owner>/<repo>
#
#  例：bash bootstrap.sh zhangsan/yuanbao-relay
#
#  它会：
#    1. 从仓库拉回所有原创脚本与文档（真正不可再生的资产）
#    2. 用 pip 装 zig 编译器（可再生，不占仓库体积）
#    3. apt 装 capstone（反汇编依赖）
#    4. 跑自检，报告缺什么
# ============================================================
set -u
REPO="${1:-}"
if [ -z "$REPO" ]; then
    echo "用法: bash bootstrap.sh <owner>/<repo>"
    exit 1
fi

DEST="${2:-$HOME/yuanbao-workspace}"
echo "═══ 恢复到: $DEST ═══"
mkdir -p "$DEST"

# ---------- 1. 拉回原创资产 ----------
echo
echo "【1/4】拉取原创脚本与文档"
TMP=$(mktemp -d)
ARCHIVE="$TMP/repo.tar.gz"

# 优先用 codeload（实测 200；objects.githubusercontent 是 403，不能用 LFS）
if ! curl -sL -o "$ARCHIVE" "https://codeload.github.com/$REPO/tar.gz/refs/heads/main"; then
    echo "  ❌ 下载失败，检查仓库名或网络"
    rm -rf "$TMP"; exit 1
fi

if [ ! -s "$ARCHIVE" ]; then
    echo "  ❌ 下载为空"
    rm -rf "$TMP"; exit 1
fi

tar xzf "$ARCHIVE" -C "$TMP" 2>/dev/null
SRC=$(find "$TMP" -maxdepth 1 -type d -name "*-*" | head -1)
if [ -z "$SRC" ]; then
    echo "  ❌ 解压失败"
    rm -rf "$TMP"; exit 1
fi

# 把仓库内容拷到目标（跳过本脚本自身和 .git）
cp -r "$SRC"/. "$DEST/" 2>/dev/null
echo "  ✅ 已恢复 $(find "$DEST" -type f | wc -l) 个文件"
rm -rf "$TMP"

# ---------- 2. 装 zig ----------
echo
echo "【2/4】安装 zig 编译器（可再生资产，不存仓库）"
if command -v zig >/dev/null 2>&1; then
    echo "  ✅ 已存在: $(zig version)"
else
    echo "  正在 pip install ziglang ...（约 165MB，需几分钟）"
    pip install ziglang -i https://mirrors.cloud.tencent.com/pypi/simple \
        --no-cache-dir -q 2>&1 | tail -2
    Z=$(find / -name "zig" -type f -size +100M 2>/dev/null | head -1)
    if [ -n "$Z" ]; then
        echo "  ✅ zig 就绪: $("$Z" version 2>&1 | head -1)"
        echo "     路径: $Z"
    else
        echo "  ⚠️  未找到，可手动: pip install ziglang"
    fi
fi

# ---------- 3. 装 capstone ----------
echo
echo "【3/4】安装 capstone（反汇编依赖）"
if [ -f /usr/include/capstone/capstone.h ]; then
    echo "  ✅ 已存在"
else
    # 先换成腾讯镜像，官方源在本环境是 403
    sed -i 's|archive.ubuntu.com/ubuntu|mirrors.cloud.tencent.com/ubuntu|g; \
            s|security.ubuntu.com/ubuntu|mirrors.cloud.tencent.com/ubuntu|g' \
        /etc/apt/sources.list 2>/dev/null
    apt-get update -qq >/dev/null 2>&1
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libcapstone-dev >/dev/null 2>&1
    [ -f /usr/include/capstone/capstone.h ] && echo "  ✅ 已安装" || echo "  ⚠️  失败"
fi

# ---------- 4. 自检 ----------
echo
echo "【4/4】自检"
echo "  ── 原创脚本 ──"
for f in see2.py lsp_query.py img2ascii.py; do
    P=$(find "$DEST" -name "$f" 2>/dev/null | head -1)
    [ -n "$P" ] && echo "     ✅ $f" || echo "     ❌ $f 缺失"
done
echo "  ── 磁盘 ──"
df -h "$DEST" | tail -1 | awk '{print "     可用: "$4}'

echo
echo "═══ 完成 ═══"
echo "  工作目录: $DEST"
echo "  注意: 本机是 Linux 环境；Windows 需把 dlopen 换成 LoadLibrary"
