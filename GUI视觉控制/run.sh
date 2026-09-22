#!/bin/bash
# GUI Agent 执行器
# 用法: ./run.sh shot                      启动并截初始图后退出
#       ./run.sh act "click:60,90" "type:hello" ...   执行动作序列后截图退出
# 每次都重启窗口，末尾强制清理，保证命令正常返回不挂起
cd /data/workspace/guiagent
OUT=/data/workspace/guiagent/step.png

cleanup() {
  for p in $(pgrep -x python3); do kill -9 "$p" 2>/dev/null; done
  for p in $(pgrep -x Xvfb); do kill -9 "$p" 2>/dev/null; done
}
trap cleanup EXIT

cleanup
sleep 1

Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 &
XPID=$!
sleep 3

DISPLAY=:99 python3 /data/workspace/guiagent/target_app.py >/dev/null 2>&1 &
APPID=$!
sleep 5

MODE="$1"; shift
if [ "$MODE" = "act" ]; then
  for a in "$@"; do
    kind="${a%%:*}"; val="${a#*:}"
    case "$kind" in
      click)
        x="${val%%,*}"; y="${val##*,}"
        DISPLAY=:99 xdotool mousemove --sync "$x" "$y" >/dev/null 2>&1
        DISPLAY=:99 xdotool click 1 >/dev/null 2>&1
        sleep 1
        ;;
      type)
        DISPLAY=:99 xdotool type --delay 30 "$val" >/dev/null 2>&1
        sleep 0.5
        ;;
      key)
        DISPLAY=:99 xdotool key "$val" >/dev/null 2>&1
        sleep 0.5
        ;;
      sleep) sleep "$val" ;;
    esac
  done
fi

DISPLAY=:99 scrot -o "$OUT" >/dev/null 2>&1
sleep 1

# 采样状态区颜色（验证用，非坐标泄露）
python3 - <<'PY'
from PIL import Image
try:
    im = Image.open('/data/workspace/guiagent/step.png').convert('RGB')
    w, h = im.size
    print(f"  图像尺寸: {w}x{h}")
    # 统计状态色出现次数
    targets = {"绿(已提交)": (0,200,83), "红(填写不完整)": (176,0,32), "青(按钮)": (77,208,225), "灰(等待/重置)": (58,63,68)}
    for name, c in targets.items():
        n = sum(1 for px in im.getdata() if abs(px[0]-c[0])<12 and abs(px[1]-c[1])<12 and abs(px[2]-c[2])<12)
        print(f"  {name}: {n} px")
except Exception as e:
    print(f"  采样失败: {e}")
PY

kill -9 "$APPID" 2>/dev/null
kill -9 "$XPID" 2>/dev/null
exit 0
