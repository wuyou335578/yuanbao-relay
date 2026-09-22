import subprocess, os, time, json, signal, sys
from PIL import Image
ENV = dict(os.environ); ENV['DISPLAY'] = ':99'
W = '/data/workspace/deskagent'

def sh(args, t=30): return subprocess.run(args, env=ENV, capture_output=True, timeout=t)
def shot(p):
    sh(['scrot', p]); return Image.open(p).convert('RGB')
def px(im, target, tol=40):
    return sum(1 for p in im.getdata()
               if abs(p[0]-target[0])<tol and abs(p[1]-target[1])<tol and abs(p[2]-target[2])<tol)

# 确保 Xvfb
r = subprocess.run(['pgrep','-x','Xvfb'], capture_output=True, text=True)
if not r.stdout.strip():
    subprocess.Popen(['Xvfb',':99','-screen','0','1600x1000x24','-nolisten','tcp'],
        env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(4)
print("① Xvfb:", subprocess.run(['pgrep','-x','Xvfb'],capture_output=True,text=True).stdout.strip())

try: os.remove('/tmp/fast/state.txt')
except: pass
gui = subprocess.Popen(['python3', f'{W}/gui_demo.py'], env=ENV,
    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    start_new_session=True, text=True)
time.sleep(6)

coords = json.load(open('/tmp/fast/coords.json'))
print("② 按钮屏幕坐标:", [(c['name'], c['x'], c['y']) for c in coords])

before = shot('/tmp/fast/b.png')
print(f"③ 点击前  青={px(before,(0,229,255))}px  红={px(before,(255,82,82))}px")

red = [c for c in coords if c['name']=='RED'][0]
sh(['xdotool','mousemove',str(red['x']),str(red['y'])])
time.sleep(0.5)
sh(['xdotool','click','1'])
time.sleep(1.5)
after = shot('/tmp/fast/a.png')
print(f"④ 点击RED后 红={px(after,(255,82,82))}px")

st = open('/tmp/fast/state.txt').read().strip() if os.path.exists('/tmp/fast/state.txt') else 'NONE'
print("⑤ GUI 内部状态:", st)
diff = sum(1 for a,b in zip(before.getdata(), after.getdata()) if a!=b)
print(f"⑥ 前后差异像素: {diff}")
ok = diff>1000 and px(after,(255,82,82))>500 and st=='RED'
print("\n★ 结论:", "桌面代理闭环成立 ✅ 我能看见并操作界面" if ok else "未成立 ❌")
gui.send_signal(signal.SIGTERM)
