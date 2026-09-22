#!/usr/bin/env bash
# 沙盒开启 3GB swap（基于 vda 未使用区域）
# 背景：物理内存 4.31GB 是硬顶；memsw 无限制，故 swap 可突破
# 风险：总内存占用超约 4.0GB 会触发宿主级 502，勿依赖 swap 冲更高
set -e
ulimit -f unlimited
# vda 前 1MB 有残留数据，用 offset 1GB 避开；sizelimit 3GB
LO=$(losetup -f)
losetup -o 1073741824 --sizelimit 3221225472 "$LO" /dev/vda
mkswap "$LO" >/dev/null
swapon "$LO"
echo "swap 已启用: $(grep -m1 SwapTotal /proc/meminfo)"
