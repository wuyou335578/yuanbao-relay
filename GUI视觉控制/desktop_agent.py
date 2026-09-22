#!/usr/bin/env python3
"""
元宝沙盒 · 桌面代理工具包
==========================
能力：启动虚拟屏 → 看到界面 → 操作界面 → 验证结果
用途：自己验证 UI，不用等用户在真机反馈

用法（库）:
    from desktop_agent import Agent
    a = Agent()
    a.start_display()                 # 起 Xvfb
    a.launch("python3 my_gui.py")     # 启动程序
    a.click(348, 369)                 # 点击
    a.shot("out.png")                 # 截图
    a.pixel(348, 250)                 # 读像素颜色
    a.has_color((255,82,82))          # 判断某颜色是否出现
    a.type_text("hello")              # 键盘输入

命令行:
    python3 desktop_agent.py status
    python3 desktop_agent.py shot out.png
    python3 desktop_agent.py pixel 100 200
"""
import subprocess, os, time, signal, sys, json
from PIL import Image

DISPLAY = ':99'
RES = '1600x1000x24'

class Agent:
    def __init__(self, display=DISPLAY):
        self.display = display
        self.env = dict(os.environ); self.env['DISPLAY'] = display
        self.procs = []

    # ---- 基础设施 ----
    def start_display(self, restart=False):
        r = subprocess.run(['pgrep','-x','Xvfb'], capture_output=True, text=True)
        if restart or not r.stdout.strip():
            subprocess.run(['pkill','-x','Xvfb'], capture_output=True)
            time.sleep(1)
            subprocess.Popen(['Xvfb', self.display, '-screen','0',RES,'-nolisten','tcp'],
                env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(4)
        pid = subprocess.run(['pgrep','-x','Xvfb'], capture_output=True, text=True).stdout.strip()
        return bool(pid), pid

    def launch(self, cmd, wait=5):
        """启动 GUI 程序。cmd 可为 list 或字符串"""
        c = cmd.split() if isinstance(cmd, str) else cmd
        p = subprocess.Popen(c, env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.procs.append(p); time.sleep(wait)
        return p.pid

    # ---- 眼睛 ----
    def shot(self, path='/tmp/fast/shot.png'):
        subprocess.run(['scrot', path], env=self.env, capture_output=True, timeout=30)
        self.last = path
        return Image.open(path).convert('RGB')

    def pixel(self, x, y, img=None):
        im = img or Image.open(self.last).convert('RGB')
        return im.getpixel((x, y))

    def has_color(self, rgb, tol=40, img=None):
        """统计某颜色出现像素数 —— 判断界面状态的核心手段"""
        im = img or Image.open(self.last).convert('RGB')
        return sum(1 for p in im.getdata()
                   if abs(p[0]-rgb[0])<tol and abs(p[1]-rgb[1])<tol and abs(p[2]-rgb[2])<tol)

    def diff(self, path_a, path_b):
        """两张截图差异像素数 —— 判断操作是否引起界面变化"""
        a = Image.open(path_a).convert('RGB'); b = Image.open(path_b).convert('RGB')
        return sum(1 for x,y in zip(a.getdata(), b.getdata()) if x!=y)

    # ---- 手 ----
    def click(self, x, y, button=1):
        e = self.env
        subprocess.run(['xdotool','mousemove',str(x),str(y)], env=e, capture_output=True, timeout=20)
        time.sleep(0.3)
        subprocess.run(['xdotool','click',str(button)], env=e, capture_output=True, timeout=20)
        time.sleep(0.8)

    def type_text(self, text):
        subprocess.run(['xdotool','type','--delay','20',text],
                       env=self.env, capture_output=True, timeout=30)

    def key(self, combo):
        subprocess.run(['xdotool','key',combo], env=self.env, capture_output=True, timeout=20)

    def mouse_pos(self):
        r = subprocess.run(['xdotool','getmouselocation'], env=self.env,
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip()

    # ---- 清理 ----
    def close(self):
        for p in self.procs:
            try: p.send_signal(signal.SIGTERM)
            except: pass

if __name__ == '__main__':
    a = Agent()
    cmd = sys.argv[1] if len(sys.argv)>1 else 'status'
    if cmd == 'status':
        ok, pid = a.start_display()
        print(f"Xvfb: {'✅ pid='+pid if ok else '❌'}")
        print("xdotool:", 'xdotool' if subprocess.run(['which','xdotool'],capture_output=True).returncode==0 else '❌')
        print("scrot  :", 'scrot' if subprocess.run(['which','scrot'],capture_output=True).returncode==0 else '❌')
    elif cmd == 'shot':
        im = a.shot(sys.argv[2] if len(sys.argv)>2 else '/tmp/fast/shot.png')
        print(f"截图 {im.size} ✅")
    elif cmd == 'pixel':
        a.shot('/tmp/fast/_p.png')
        print(a.pixel(int(sys.argv[2]), int(sys.argv[3])))
