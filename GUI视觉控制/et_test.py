import subprocess, os, time, json, signal
from PIL import Image
ENV = dict(os.environ); ENV['DISPLAY'] = ':99'
ET = '/tmp/fast/et/lib/node_modules/easytouch-linux/bin/et_x64'
def et(*args, t=60):
    r = subprocess.run([ET]+list(args), env=ENV, capture_output=True, text=True, timeout=t)
    return r.stdout.strip()

# 启动 GUI
gui = subprocess.Popen(['python3','/data/workspace/deskagent/gui_demo.py'], env=ENV,
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    start_new_session=True)
time.sleep(6)

print("【EasyTouch 桌面代理闭环】\n")
print("① 窗口列表:")
wl = et('window','list')
try:
    d = json.loads(wl)['data']
    print(f"   发现 {d['count']} 个窗口")
    for w in d['windows'][:3]:
        print(f"     - {w.get('title','?')[:40]}  handle={w.get('handle')}")
except Exception as e: print("   ", wl[:150])

print("\n② 鼠标定位:", et('mouse','position')[:100].replace('\n',' '))

coords = json.load(open('/tmp/fast/coords.json'))
red = [c for c in coords if c['name']=='RED'][0]
print(f"\n③ 移动鼠标到 RED 按钮 ({red['x']},{red['y']}):")
print("   ", et('mouse','move','--x',str(red['x']),'--y',str(red['y']))[:120].replace('\n',' '))
time.sleep(0.5)
print("\n④ 点击:")
print("   ", et('mouse','click','--button','left')[:120].replace('\n',' '))
time.sleep(1.5)

print("\n⑤ 截图:")
out = et('screenshot','--output','/tmp/fast/et_shot.png')
print("   ", out[:150].replace('\n',' '))

if os.path.exists('/tmp/fast/et_shot.png'):
    im = Image.open('/tmp/fast/et_shot.png').convert('RGB')
    def px(t,tol=40): return sum(1 for p in im.getdata()
        if abs(p[0]-t[0])<tol and abs(p[1]-t[1])<tol and abs(p[2]-t[2])<tol)
    print(f"\n⑥ 截图像素验证 ({im.size}):")
    print(f"   红色像素: {px((255,82,82))}  → {'按钮已响应 ✅' if px((255,82,82))>500 else '未响应 ❌'}")
else: print("   截图文件未生成 ❌")

try: print("\n⑦ GUI 内部状态:", open('/tmp/fast/state.txt').read().strip())
except: print("\n⑦ 无状态")
gui.send_signal(signal.SIGTERM)
