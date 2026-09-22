import subprocess, os, time, json, signal
ENV=dict(os.environ); ENV['DISPLAY']=':99'
ENV['GTK_MODULES']='gail:atk-bridge'
ENV['AT_SPI_BUS_ADDRESS']='unix:path=/tmp/atspi'
ET='/tmp/fast/et/lib/node_modules/easytouch-linux/bin/et_x64'
def et(*a,t=60):
    r=subprocess.run([ET]+list(a),env=ENV,capture_output=True,text=True,timeout=t)
    return (r.stdout or r.stderr).strip()
# AT-SPI 总线守护
subprocess.run(['/usr/libexec/at-spi-bus-launcher','--launch-immediately'],
    env=ENV,capture_output=True,timeout=10) if os.path.exists('/usr/libexec/at-spi-bus-launcher') else None
subprocess.run(['pgrep','-x','at-spi-bus-launcher'],capture_output=True)
g=subprocess.Popen(['python3','/data/workspace/deskagent/gtk_demo.py'],env=ENV,
    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
    start_new_session=True)
time.sleep(7)
print("① window list:")
r=et('window','list')
try:
    d=json.loads(r)['data']; print(f"   {d['count']} 个窗口")
    for w in d['windows'][:3]: print(f"     - {w.get('title','?')}")
except Exception as e: print("   ", r[:150])
print("\n② element tree:")
r=et('element','tree','--max-nodes','12')
print("   ", r[:280].replace('\n',' '))
g.send_signal(signal.SIGTERM)
