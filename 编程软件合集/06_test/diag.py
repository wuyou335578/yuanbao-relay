import subprocess, time, threading, queue, sys

p = subprocess.Popen(['gdb','--interpreter=mi2','-q','--nx','./demo'],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, bufsize=0)
q = queue.Queue()
def reader():
    while True:
        line = p.stdout.readline()
        if not line: break
        t = line.decode('utf-8',errors='replace').strip()
        if t: q.put(t)
threading.Thread(target=reader, daemon=True).start()

def cmd(c, wait=1.5):
    print('  >> %s' % c)
    p.stdin.write((c+'\n').encode()); p.stdin.flush()
    time.sleep(wait)
    out=[]
    while not q.empty(): out.append(q.get())
    for o in out: print('     %s' % o[:170])

cmd('-gdb-set confirm off')
cmd('-gdb-set pagination off')
cmd('-break-insert demo.cpp:17')
print()
print('  === 关键：现在下 -exec-run ===')
cmd('-exec-run', wait=3.0)
print()
print('  === 看它停在哪 ===')
cmd('-stack-list-frames')
cmd('-stack-list-variables --simple-values')
cmd('-data-evaluate-expression n')
p.stdin.write(b'-gdb-exit\n'); p.stdin.flush()
