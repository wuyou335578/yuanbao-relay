#!/bin/bash
# ============================================================
#  一键安装：AI 全栈开发环境（Zig + ZLS + AI视觉 + 热重载渲染）
# ============================================================
#  用法:  bash 一键安装.sh
#  作用:  在本机（或新沙盒）重建完整环境，装完自动自检
# ============================================================

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }

echo "═══════════════════════════════════════════"
echo "  AI 全栈开发环境 · 一键安装"
echo "═══════════════════════════════════════════"
echo "  根目录: $ROOT"
echo

# ---------- 0. 解除文件大小限制 ----------
echo "【0】解除文件大小限制"
ulimit -f unlimited 2>/dev/null && ok "ulimit -f unlimited" || fail "解除失败(非root?)"

# ---------- 1. Zig 编译器 ----------
echo
echo "【1】Zig 编译器"
if command -v zig >/dev/null 2>&1; then
    ok "已安装: $(zig version)"
else
    echo "  未找到，尝试安装..."
    if command -v pip >/dev/null 2>&1; then
        pip install ziglang \
          -i https://mirrors.cloud.tencent.com/pypi/simple \
          --no-cache-dir -q 2>/dev/null
        Z=$(python3 -c "import ziglang,os;print(os.path.dirname(ziglang.__file__)+'/zig')" 2>/dev/null)
        if [ -n "$Z" ] && [ -f "$Z" ]; then
            chmod +x "$Z"
            ln -sf "$Z" /usr/local/bin/zig 2>/dev/null
            ok "已安装: $(zig version 2>/dev/null)"
        else
            fail "安装失败，请手动: pip install ziglang"
        fi
    else
        fail "无 pip，请手动装 Zig 0.16.0"
    fi
fi

# ---------- 2. ZLS 语言服务器 ----------
echo
echo "【2】ZLS 语言服务器"
ZLS_SRC="$ROOT/01_Zig与ZLS/zls"
if [ -f "$ZLS_SRC" ]; then
    chmod +x "$ZLS_SRC"
    mkdir -p "$HOME/.local/bin"
    cp "$ZLS_SRC" "$HOME/.local/bin/zls" 2>/dev/null
    cp "$ZLS_SRC" /usr/local/bin/zls 2>/dev/null
    if command -v zls >/dev/null 2>&1; then
        ok "已部署: $(zls --version 2>/dev/null | head -1)"
    else
        ok "已复制到 $HOME/.local/bin/zls（需确保该目录在 PATH）"
    fi
else
    fail "未找到 zls 二进制"
fi

# ---------- 3. AI 视觉依赖 ----------
echo
echo "【3】AI 视觉依赖"
python3 - <<'PY' 2>/dev/null
import importlib
need = {'onnxruntime':'AI识别','PIL':'图像处理','numpy':'数组计算'}
for m,desc in need.items():
    try:
        importlib.import_module(m); print(f"  ✅ {m} ({desc})")
    except ImportError:
        print(f"  ⚠️  {m} ({desc}) 未装 → pip install {m if m!='PIL' else 'pillow'}")
PY

# ---------- 4. 系统库（图形/虚拟屏幕）----------
echo
echo "【4】系统库（图形渲染用）"
MISSING=0
for b in Xvfb scrot; do
    if command -v $b >/dev/null 2>&1; then ok "$b"; else fail "$b 未装"; MISSING=1; fi
done
if [ "$MISSING" = "1" ]; then
    echo "  安装命令: apt-get install -y xvfb scrot"
    echo "            + libx11-dev libgl1-mesa-dev libasound2-dev"
fi

# ---------- 5. raylib 运行时 ----------
echo
echo "【5】raylib 运行时"
RL="$ROOT/03_热重载渲染工程/raylib运行时"
if [ -f "$RL/libraylib.so.6.0.0" ] && [ -f "$RL/raylib.h" ]; then
    ok "已内置: libraylib.so + raylib.h"
else
    fail "raylib 运行时缺失"
fi

# ---------- 6. 自检 ----------
echo
echo "═══════════════════════════════════════════"
echo "  自检"
echo "═══════════════════════════════════════════"

# 6.1 ZLS 能否工作
echo "【6.1】ZLS 诊断能力"
T=$(mktemp -d); cat > "$T/t.zig" <<'EOF'
pub fn main() void {
    const x = not_defined_xyz;
}
EOF
if command -v zls >/dev/null 2>&1; then
    R=$(ZLS_PATH="$(command -v zls)" timeout 90 python3 \
        "$ROOT/01_Zig与ZLS/lsp_query.py" diagnose "$T/t.zig" 2>&1 | head -3)
    if echo "$R" | grep -q "not_defined_xyz"; then ok "ZLS 检出错误正常"; else fail "ZLS 无输出"; fi
else
    fail "zls 不在 PATH"
fi

# 6.2 AI 视觉
echo "【6.2】AI 视觉模型"
M="$ROOT/02_AI视觉辅助/models/resnet50.onnx"
L="$ROOT/02_AI视觉辅助/models/imagenet_classes.txt"
if [ -f "$M" ] && [ -f "$L" ]; then
    SZ=$(du -h "$M" | cut -f1)
    ok "模型就位 ($SZ), 标签 $(wc -l < "$L") 类"
else
    fail "模型或标签缺失"
fi

# 6.3 热重载工程能否编译
echo "【6.3】热重载工程编译"
if command -v zig >/dev/null 2>&1; then
    PJ="$ROOT/03_热重载渲染工程/项目源码"
    cd "$PJ" 2>/dev/null || PJ="$PJ"
    if RAYLIB_INC="$RL" RAYLIB_LIB="$RL" timeout 300 zig build >/tmp/bt.log 2>&1; then
        ok "编译通过"
    else
        fail "编译失败，见 /tmp/bt.log"
        tail -3 /tmp/bt.log | sed 's/^/      /'
    fi
else
    fail "无 zig，跳过"
fi


# 6.4 反汇编工具
echo "【6.4】反汇编工具"
DZ="$ROOT/04_反汇编能力/zig-out/bin/disasm"
if [ -f "$DZ" ]; then
    chmod +x "$DZ"
    if "$DZ" "$DZ" 0 3 >/dev/null 2>&1; then ok "disasm 可运行"
    else fail "disasm 运行失败（可能缺 libcapstone）"; fi
else
    fail "未找到 disasm，需先编译: cd 04_反汇编能力 && zig build"
fi

rm -rf "$T"
echo
echo "═══════════════════════════════════════════"
echo "  完成。下一步："
echo "    cd 03_热重载渲染工程/项目源码"
echo "    zig build && ./zig-out/bin/host &"
echo "    改 src/game.zig → zig build → 画面自动更新"
echo "═══════════════════════════════════════════"
