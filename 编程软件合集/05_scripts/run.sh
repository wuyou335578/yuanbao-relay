#!/usr/bin/env bash
# 在虚拟屏启动 CodeLite 并截图（批处理：启动→截→清理，避免后台挂起）
export DISPLAY=:99
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp >/dev/null 2>&1 &
XPID=$!
sleep 3
codelite >/tmp/codelite.log 2>&1 &
CID=$!
sleep 12
echo "CodeLite PID=$CID $(kill -0 $CID 2>/dev/null && echo '运行中' || echo '已退出')"
xdotool search --onlyvisible --name "CodeLite" 2>/dev/null | head -3
mkdir -p /data/workspace/codelite_test
import -window root -silent /data/workspace/codelite_test/screen.png 2>/dev/null
echo "截图: $(stat -c%s /data/workspace/codelite_test/screen.png) bytes"
kill -9 $CID $XPID 2>/dev/null
sleep 1
echo "已清理"
