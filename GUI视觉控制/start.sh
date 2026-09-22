#!/bin/bash
# 启动虚拟屏 + 被测 GUI（前台运行本脚本，内部后台启进程后立即退出）
cd /data/workspace/guiagent

for p in $(pgrep -x Xvfb); do kill -9 "$p" 2>/dev/null; done
for p in $(pgrep -x python3); do kill -9 "$p" 2>/dev/null; done
sleep 1

setsid Xvfb :99 -screen 0 1024x768x24 </dev/null >/dev/null 2>&1 &
disown 2>/dev/null
sleep 3

DISPLAY=:99 setsid python3 /data/workspace/guiagent/target_app.py </dev/null >/dev/null 2>&1 &
disown 2>/dev/null
sleep 5

DISPLAY=:99 scrot -o /data/workspace/guiagent/step0.png </dev/null >/dev/null 2>&1
stat -c%s /data/workspace/guiagent/step0.png 2>/dev/null
exit 0
