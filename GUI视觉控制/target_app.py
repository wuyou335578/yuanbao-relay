#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
被测目标 GUI：模拟一个「项目配置表单」
刻意设计：不向 stdout 打印任何控件坐标，验证方必须纯靠看图识别控件位置。
"""
import tkinter as tk
from tkinter import ttk

STATE = {"submitted": False, "color": "#3A3F44"}


def build():
    root = tk.Tk()
    root.title("Project Config")
    root.geometry("760x520+40+40")
    root.configure(bg="#2B2F33")

    tk.Label(root, text="项目配置", font=("WenQuanYi Micro Hei", 18, "bold"),
             bg="#2B2F33", fg="#E8EAED").place(x=24, y=18)

    # 三个输入框
    labels = ["项目名称", "包名", "版本号"]
    entries = []
    for i, t in enumerate(labels):
        y = 78 + i * 62
        tk.Label(root, text=t, font=("WenQuanYi Micro Hei", 11),
                 bg="#2B2F33", fg="#9AA0A6").place(x=28, y=y)
        e = tk.Entry(root, font=("WenQuanYi Micro Hei", 12), width=26,
                     bg="#1E2124", fg="#E8EAED", insertbackground="#4DD0E1",
                     relief="flat", highlightthickness=2,
                     highlightbackground="#3A3F44", highlightcolor="#4DD0E1")
        e.place(x=130, y=y - 2, height=32)
        entries.append(e)

    # 复选框
    cb_var = tk.BooleanVar(value=False)
    cb = tk.Checkbutton(root, text="启用自动布局", variable=cb_var,
                        font=("WenQuanYi Micro Hei", 11),
                        bg="#2B2F33", fg="#E8EAED",
                        selectcolor="#1E2124", activebackground="#2B2F33",
                        activeforeground="#E8EAED")
    cb.place(x=28, y=272)

    # 状态显示区（初始中性色）
    status = tk.Label(root, text="等待提交", font=("WenQuanYi Micro Hei", 13, "bold"),
                      bg=STATE["color"], fg="#E8EAED", width=22, height=2)
    status.place(x=28, y=330)

    # 提交按钮
    def on_submit():
        name = entries[0].get().strip()
        pkg = entries[1].get().strip()
        ver = entries[2].get().strip()
        if not (name and pkg and ver):
            status.config(text="请填写完整", bg="#B00020")
            STATE["submitted"] = False
            return
        STATE["submitted"] = True
        status.config(text=f"已提交: {name}", bg="#00C853")

    btn = tk.Button(root, text="提交配置", font=("WenQuanYi Micro Hei", 12, "bold"),
                    bg="#4DD0E1", fg="#102027", activebackground="#26C6DA",
                    relief="flat", width=12, height=1, command=on_submit)
    btn.place(x=28, y=430)

    # 重置按钮
    def on_reset():
        for e in entries:
            e.delete(0, tk.END)
        cb_var.set(False)
        STATE["submitted"] = False
        status.config(text="已重置", bg="#3A3F44")

    tk.Button(root, text="重置", font=("WenQuanYi Micro Hei", 11),
              bg="#5F6368", fg="#E8EAED", relief="flat",
              width=8, command=on_reset).place(x=170, y=432)

    root.mainloop()


if __name__ == "__main__":
    build()
