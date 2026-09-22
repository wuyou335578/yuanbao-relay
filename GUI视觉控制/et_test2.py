import subprocess, os, time, json, signal
from PIL import Image
ENV = dict(os.environ); ENV['DISPLAY'] = ':99'
ET = '/tmp/fast/et/lib/node_modules/easytouch-linux/bin/et_x64'
def et(*a, t=60):
    r = subprocess.run([ET]+list(a), env=ENV, capture_output=True, text=True, timeout=t)
    return (r.stdout or r.stderr).strip()

gui = subprocess.Popen(['python3','/data/workspace/deskagent/gui_demo.py'], env=ENV,
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    start_new_session=True)
time.sleep(6)
# 先点 RED 制造可验证状态
c = json.load(open('/tmp/fast/coords.json')); red=[x for x in c if x['name']=='RED'][0]
et('mouse','move','--x',str(red['x']),'--y',str(red['y'])); time.sleep(0.4)
et('mouse','click'); time.sleep(1.2)

print("① screen capture:")
print("   ", et('screen','capture','--path','/tmp/fast/et2.png')[:200].replace('\n',' '))
if os.path.exists('/tmp/fast/et2.png'):
    im=Image.open('/tmp/fast/et2.png').convert('RGB')
    print(f"   截图成功 {im.size} {os.path.getsize('/tmp/fast/et2.png')} bytes ✅")
    def px(t,tol=40): return sum(1 for p in im.getdata()
        if abs(p[0]-t[0])<tol and abs(p[1]-t[1])<tol and abs(p[2]-t[2])<tol)
    print(f"   红色像素 {px((255,82,82))} → 点击生效 {'✅' if px((255,82,82))>500 else '❌'}")
else: print("   ❌ 未生成")

print("\n② screen pixel-color (RED按钮处):")
print("   ", et('screen','pixel-color','--x',str(red['x']),'--y','250')[:180].replace('\n',' '))

print("\n③ element tree（UI元素树，需AT-SPI）:")
print("   ", et('element','tree','--max-nodes','15')[:400].replace('\n',' '))

print("\n④ screen displays:")
print("   ", et('screen','displays')[:200].replace('\n',' '))
gui.send_signal(signal.SIGTERM)
