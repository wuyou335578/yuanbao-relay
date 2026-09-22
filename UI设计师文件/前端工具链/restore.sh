#!/bin/bash
# 前端工具链恢复脚本 —— TypeScript + Tailwind CSS v4 + pnpm
# 用法： source restore.sh
# 沙盒重置后一键恢复，全程走腾讯内网镜像，不碰官方源
#
# 实测耗时参考（2026-09-22）：
#   pnpm 全局安装  ~43 s
#   pnpm install   ~117 s（--ignore-scripts）
#   tsc 编译        <1 s
#   tailwind 构建   ~1 s

set -u
ulimit -f unlimited
cd "$(dirname "$0")"

# ── 1. npm / pnpm 镜像 ──────────────────────────
# 实测：腾讯镜像 359 ms vs 官方 npmjs 5307 ms（14.8 倍）
npm config set registry https://mirrors.cloud.tencent.com/npm/ 2>/dev/null
echo "[fe] npm registry: $(npm config get registry)"

# ── 2. pnpm ─────────────────────────────────────
# ⚠️ 不要用官方安装脚本（curl get.pnpm.io），沙盒网关会拒。
#    用 npm 全局装，走腾讯镜像，实测 43 s。
if ! command -v pnpm >/dev/null 2>&1; then
    echo "[fe] 安装 pnpm ..."
    npm install -g pnpm --no-audit --no-fund 2>&1 | tail -2
fi
echo "[fe] pnpm: $(pnpm -v 2>/dev/null || echo 失败)"

# ── 3. 装依赖 ───────────────────────────────────
# ⚠️ 必须带 --ignore-scripts。
#    否则 pnpm 12 报 ERR_PNPM_IGNORED_BUILDS
#    （@parcel/watcher 的 build script 被拦截）
#    @parcel/watcher 只是 Tailwind watch 模式的可选依赖，
#    CLI 构建不需要，忽略后实测功能完全正常。
if [ ! -d node_modules/.bin ] || [ ! -f node_modules/.bin/tsc ]; then
    echo "[fe] 安装 TypeScript + Tailwind（--ignore-scripts）..."
    pnpm install --ignore-scripts 2>&1 | tail -5
fi

# ── 4. 验证 ─────────────────────────────────────
echo ""
echo "[fe] ✅ 工具链就绪"
echo "     tsc      $(./node_modules/.bin/tsc -v 2>/dev/null)"
echo "     tailwind $(./node_modules/.bin/tailwindcss --help 2>&1 | head -1)"
echo "     pnpm     $(pnpm -v 2>/dev/null)"
echo ""
echo "     用法:"
echo "       ./node_modules/.bin/tsc --strict --outDir dist src/demo.ts"
echo "       ./node_modules/.bin/tailwindcss -i css/input.css -o css/output.css --minify"
