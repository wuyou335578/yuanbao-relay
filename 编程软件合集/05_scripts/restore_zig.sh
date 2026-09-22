#!/usr/bin/env bash
# Zig 0.16.0 完整版一键恢复（从持久盘 zip 解压到内存盘）
# 为什么解压到 /dev/shm：virtiofs 文件数 IOPS 极低（约 7），19542 个文件会很慢
# 为什么必须 remount exec：/dev/shm 默认 noexec，二进制跑不起来（实测 Permission denied）
set -e
ulimit -f unlimited
Z=/data/user_persistent_data/zig_full/zig完整版.zip
D=/dev/shm/zigtest
mount -o remount,size=2G,exec /dev/shm 2>/dev/null || true
if [ ! -x "$D/zig" ]; then
  mkdir -p "$D"
  python3 -c "
import zipfile
zipfile.ZipFile('$Z').extractall('$D')
"
  chmod +x "$D/zig"
fi
"$D/zig" version
echo "zig 就绪: $D/zig"
echo "C++ 编译: $D/zig c++ -Wno-nullability-completeness -o out in.cpp"
