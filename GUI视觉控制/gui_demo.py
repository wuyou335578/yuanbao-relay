import tkinter as tk, json, sys
root = tk.Tk()
root.title("AgentTestWindow")
root.geometry("700x450+120+120")
root.configure(bg="#121212")
def click(color, name):
    lbl.config(text="CLICKED:"+name, fg=color); frame.config(bg=color)
    open('/tmp/fast/state.txt','w').write(name)
tk.Label(root, text="Desktop Agent Verified", font=("Sans",18,"bold"),
         bg="#121212", fg="#00E5FF").pack(pady=14)
lbl = tk.Label(root, text="WAITING", font=("Sans",14), bg="#121212", fg="#888888")
lbl.pack(pady=8)
frame = tk.Frame(root, bg="#333333", width=400, height=90); frame.pack(pady=10)
btnf = tk.Frame(root, bg="#121212"); btnf.pack(pady=12)
btns=[]
for c,n in [("#FF5252","RED"),("#00E5FF","CYAN"),("#69F0AE","GREEN")]:
    b=tk.Button(btnf,text=n,font=("Sans",12),bg="#2D2D2D",fg="white",
                relief="flat",padx=22,pady=8,command=lambda c=c,n=n:click(c,n))
    b.pack(side="left",padx=10); btns.append((b,n))
root.update_idletasks(); root.update()
coords=[{"name":n,"x":b.winfo_rootx()+b.winfo_width()//2,
         "y":b.winfo_rooty()+b.winfo_height()//2} for b,n in btns]
json.dump(coords, open('/tmp/fast/coords.json','w'))
sys.stdout.write("READY\n"); sys.stdout.flush()
root.mainloop()
