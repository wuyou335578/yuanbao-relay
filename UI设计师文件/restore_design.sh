#!/bin/bash
# ============================================================
# restore_design.sh —— 恢复「真实渲染 + 可编辑源文件 + 在线字体」三件套
#
# 解决的问题：
#   1. 缺 Chromium/Playwright → 只能 jsdom 验逻辑，看不到像素与断点响应
#   2. 缺 Figma/Sketch      → 交不出可编辑源文件（.fig/.sketch）
#   3. 缺 fonts.googleapis  → 拉不到在线字体
#
# 用法：source /data/workspace/restore_design.sh
#      （用 source 才能导出环境变量）
# ============================================================
set -u
ulimit -f unlimited
export DEBIAN_FRONTEND=noninteractive
ENV_DIR=/data/workspace/env
WORK=/tmp/fast/chr

echo "════ 恢复设计三件套 ════"

# ---------- 1. 字体（最快，先做）----------
echo "[1/4] Google Fonts ..."
if ls /usr/share/fonts/truetype/gf/*.ttf >/dev/null 2>&1; then
  echo "  ✅ 字体已在（$(ls /usr/share/fonts/truetype/gf/*.ttf | wc -l) 个）"
else
  if [ -f "$ENV_DIR/gf_fonts.tar.gz" ]; then
    tar -xzf "$ENV_DIR/gf_fonts.tar.gz" -C /usr/share/fonts/truetype/ && \
    fc-cache -f >/dev/null 2>&1
    echo "  ✅ 已从持久包恢复并刷新缓存"
  else
    echo "  ⚠️  持久包缺失，改从 Google Fonts 现拉（实测可达）"
    mkdir -p /usr/share/fonts/truetype/gf
    curl -s -m 20 "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap" \
      -o /tmp/gf.css
    grep -o "https://fonts.gstatic.com[^)]*" /tmp/gf.css | sort -u | while read -r u; do
      curl -s -m 30 "$u" -o "/usr/share/fonts/truetype/gf/$(basename "$u")"
    done
    fc-cache -f >/dev/null 2>&1
    echo "  ✅ 现拉完成"
  fi
fi

# ---------- 2. Chromium ----------
echo "[2/4] Chromium ..."
if command -v chromium >/dev/null 2>&1 && chromium --version 2>/dev/null | grep -q Chromium; then
  echo "  ✅ chromium 已在"
else
  # 2a. apt 换腾讯内网镜像（官方源会 403/未签名）
  if ! grep -q "mirrors.tencent.com" /etc/apt/sources.list 2>/dev/null; then
    cp /etc/apt/sources.list /tmp/sources.list.bak 2>/dev/null
    cat > /etc/apt/sources.list <<'EOF'
deb http://mirrors.tencent.com/ubuntu/ jammy main restricted universe multiverse
deb http://mirrors.tencent.com/ubuntu/ jammy-updates main restricted universe multiverse
deb http://mirrors.tencent.com/ubuntu/ jammy-security main restricted universe multiverse
deb http://mirrors.tencent.com/ubuntu/ jammy-backports main restricted universe multiverse
EOF
    echo "     apt 源已换腾讯内网镜像"
  fi
  apt-get update -qq >/dev/null 2>&1

  # 2b. Ubuntu 的 chromium-browser 是 snap 空壳，不能用；
  #     改用 Debian bookworm 的真 chromium deb
  mkdir -p "$WORK"
  if [ -f "$ENV_DIR/chromium_debs.tar.gz" ]; then
    tar -xzf "$ENV_DIR/chromium_debs.tar.gz" -C "$WORK"
    echo "     已从持久包解出 $(ls "$WORK"/*.deb 2>/dev/null | wc -l) 个 deb"
  else
    echo "  ⚠️  持久包缺失，需手工重下（见手册）"
  fi

  cd "$WORK" 2>/dev/null || exit 1
  # 顺序很重要：先依赖库，后 common，最后主包
  dpkg -i libdav1d6.deb libdouble-conversion3.deb libflac12.deb libminizip1.deb \
          libjpeg62-turbo.deb libopenh264-7.deb libopenjp2-7.deb libopus0.deb \
          >/dev/null 2>&1
  dpkg -i libharfbuzz-subset0.deb libharfbuzz0b.deb >/dev/null 2>&1
  dpkg -i libzstd1.deb >/dev/null 2>&1              # 需要 >=1.5.2，Ubuntu 自带是 1.4.8
  dpkg -i chromium-common.deb >/dev/null 2>&1
  dpkg -i chromium.deb >/dev/null 2>&1
  apt-get -f install -y -qq >/dev/null 2>&1         # 补剩余依赖
  if command -v chromium >/dev/null 2>&1; then
    echo "  ✅ chromium 安装完成"
  else
    echo "  ❌ chromium 安装失败，检查 deb 是否完整"
  fi
fi

# ---------- 3. Playwright ----------
echo "[3/4] Playwright ..."
if python3 -c "import playwright" 2>/dev/null; then
  echo "  ✅ playwright 模块已在"
else
  pip install -q playwright >/dev/null 2>&1 && echo "  ✅ playwright 已装" \
    || echo "  ❌ 装失败（pip 走内网镜像应该能过）"
fi

# ---------- 4. .sketch 生成器 ----------
echo "[4/4] .sketch 生成器 ..."
if [ -f /data/workspace/tools/sketch_gen.py ]; then
  echo "  ✅ sketch_gen.py 在 /data/workspace/tools/"
else
  echo "  ❌ 缺失，需从仓库/持久区找回"
fi

echo
echo "════ 验证 ════"
command -v chromium >/dev/null 2>&1 && echo "  chromium:  $(chromium --version 2>/dev/null | tail -1)"
python3 -c "import playwright; print('  playwright: 模块 OK')" 2>/dev/null || echo "  playwright: ❌"
echo "  字体总数:   $(fc-list 2>/dev/null | wc -l)"
ls -la /data/workspace/tools/sketch_gen.py 2>/dev/null | awk '{print "  sketch_gen: "$5" 字节"}'
echo
echo "  用法："
echo "    chromium --headless --no-sandbox --disable-gpu --disable-dev-shm-usage \\"
echo "             --window-size=375,812 --screenshot=out.png file:///path.html"
echo
echo "    python3 -c \"from playwright.sync_api import sync_playwright\"  # 用 executable_path='/usr/bin/chromium'"
echo
echo "    python3 /data/workspace/tools/sketch_gen.py design.json out.sketch"
echo "════════════════════════════"
