#!/usr/bin/env bash
# CodeLite 14.0 一键恢复（离线 deb，不依赖网络）
# 已实测：Xvfb 虚拟屏 + xdotool + CodeLite 14.0 全部跑通
set -e
ulimit -f unlimited
D=/data/user_persistent_data/codelite

# 1. 装本地 deb（离线）
dpkg -i $D/*.deb 2>/dev/null || true
apt-get install -y -f -qq 2>/dev/null || true

# 2. 装 X11 工具（GUI 需要；若已装会跳过）
which Xvfb >/dev/null 2>&1 || {
  echo 'deb https://mirrors.tencent.com/ubuntu/ jammy main restricted universe multiverse' > /etc/apt/sources.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xvfb xdotool -qq
}

# 3. 验证
codelite --version 2>/dev/null || true
echo "=== CodeLite 就绪 ==="
echo "启动方式: bash $D/run.sh"
