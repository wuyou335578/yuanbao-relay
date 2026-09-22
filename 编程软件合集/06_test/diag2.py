import subprocess, time, threading, queue

def run(target, label):
    print('  ── %s (%s) ──' % (label, target))
    p = subprocess.Popen(['gdb','--interpreter=mi2','-q','--nx',target],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, bufsize=0)
    q=queue.Queue()
    def rd():
        while True:
            l=p.stdout.readline()
            if not l: break
            t=l.decode('utf-8',errors='replace').strip()
            if t: q.put(t)
    threading.Thread(target=rd,daemon=True).start()
    def cmd(c,wait=1.5):
        p.stdin.write((c+'\n').encode()); p.stdin.flush()
        time.sleep(wait)
        out=[]
        while not q.empty(): out.append(q.get())
        return out
    cmd('-gdb-set confirm off')
    cmd('-break-insert main')
    out = cmd('-exec-run', wait=3.0)
    stopped=False; segv=False
    for o in out:
        if '*stopped' in o:
            stopped=True
            if 'signal-received' in o or 'SIGSEGV' in o: segv=True
    print('     stopped=%s  segv=%s' % (stopped, segv))
    if stopped and not segv:
        f=cmd('-stack-list-frames')
        for o in f: print('     %s' % o[:150])
        v=cmd('-data-evaluate-expression x' if target=='./mini' else '-data-evaluate-expression n')
        for o in v: print('     %s' % o[:150])
    p.stdin.write(b'-gdb-exit\n'); p.stdin.flush()
    try: p.wait(timeout=5)
    except: p.kill()

run('./mini','静态链接 C')
run('./demo','动态链接 C++')
