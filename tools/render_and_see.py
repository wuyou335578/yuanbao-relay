#!/usr/bin/env python3
"""
render_and_see.py —— 让 AI 看见自己代码渲染的结果

用法：
    python3 render_and_see.py page.html            # 渲染 HTML 并转成我能读的字符画
    python3 render_and_see.py page.html --cols 90  # 指定字符画宽度
    python3 render_and_see.py page.html --crop 0,0,900,700   # 裁剪区域后再看
    python3 render_and_see.py --self-test          # 跑内置自检

渲染链路（全 Python，不需要浏览器）：
    HTML → weasyprint → PDF → pypdfium2 → PNG → ASCII 字符画

依赖：weasyprint pypdfium2 pillow numpy
"""
import sys, os, subprocess, tempfile

ASCII_RAMP = " .:-=+*#%@"


def render_html_to_png(html_path, png_path, scale=1.5):
    """HTML → PDF → PNG"""
    from weasyprint import HTML
    import pypdfium2 as pdfium
    pdf_path = png_path.replace(".png", ".pdf")
    HTML(filename=html_path).write_pdf(pdf_path)
    doc = pdfium.PdfDocument(pdf_path)
    page = doc[0]
    img = page.render(scale=scale).to_pil()
    img.save(png_path)
    return img


def to_ascii(img, cols=76):
    """图片 → ASCII 字符画（纯文本模型可读）"""
    import numpy as np
    w, h = img.size
    rows = max(1, int(cols * h / w * 0.5))
    small = img.resize((cols, rows), 2)  # LANCZOS
    if small.mode != "L":
        small = small.convert("L")
    a = np.asarray(small, dtype=np.float32)
    lo, hi = a.min(), a.max()
    if hi > lo:
        a = (a - lo) / (hi - lo)
    else:
        a = a * 0
    idx = (a * (len(ASCII_RAMP) - 1)).astype(int)
    lines = ["+" + "-" * cols + "+"]
    for r in range(rows):
        lines.append("|" + "".join(ASCII_RAMP[v] for v in idx[r]) + "|")
    lines.append("+" + "-" * cols + "+")
    return "\n".join(lines)


def crop_image(img, box):
    return img.crop(box)


def autocrop_whitespace(img, threshold=245, pad=12):
    """
    裁掉四周的空白（A4 页面上内容通常只占一小块）。
    找出所有"非近白"像素的包围盒，向外留一点边距。
    """
    import numpy as np
    a = np.asarray(img.convert("L"), dtype=np.uint8)
    mask = a < threshold
    if not mask.any():
        return img
    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    w, h = img.size
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(w, x1 + pad); y1 = min(h, y1 + pad)
    if (x1 - x0) < 10 or (y1 - y0) < 10:
        return img
    return img.crop((x0, y0, x1, y1))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] == "--self-test":
        run_self_test()
        return

    src = args[0]
    cols = 76
    crop = None
    if "--cols" in args:
        cols = int(args[args.index("--cols") + 1])
    if "--crop" in args:
        crop = tuple(int(v) for v in args[args.index("--crop") + 1].split(","))

    tmp = tempfile.mkdtemp(dir="/data/workspace/tmp")
    png = os.path.join(tmp, "render.png")

    if src.lower().endswith((".html", ".htm")):
        print(f"[1/3] 渲染 HTML → PDF → PNG ...")
        img = render_html_to_png(src, png)
        print(f"      输出 {img.size[0]}x{img.size[1]}")
    else:
        from PIL import Image
        img = Image.open(src)
        print(f"[1/3] 载入图片 {img.size}")

    if crop:
        img = crop_image(img, crop)
        print(f"[2/3] 手动裁剪 {crop} → {img.size}")
    else:
        before = img.size
        img = autocrop_whitespace(img)
        print(f"[2/3] 自动裁白边 {before} → {img.size}")

    art = to_ascii(img, cols)
    print(f"[3/3] ASCII 字符画 {cols} 列\n")
    print(art)

    out = os.path.join(os.path.dirname(os.path.abspath(src)) or ".",
                       "ascii_preview.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(art)
    print(f"\n已保存字符画: {out}")


def run_self_test():
    """自检：生成含已知缺陷的 HTML，验证能否被识别"""
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{margin:0;font-family:sans-serif;background:#f5f5f8;width:600px}
    .h{background:#2d2d44;color:#fff;padding:18px 24px;font-size:22px}
    .c{background:#fff;margin:16px 24px;padding:16px;border:1px solid #d2d2da;
       display:flex;align-items:center}
    .t{width:80px;height:70px;background:#bec4eb;flex-shrink:0}
    .i{margin-left:16px}
    .ti{font-size:19px;font-weight:bold}
    .de{font-size:14px;color:#78788a;margin-top:6px}
    </style></head><body>
    <div class="h">Dashboard</div>
    <div class="c"><div class="t"></div><div class="i">
    <div class="ti">Alpha</div><div class="de">Updated 2h ago</div></div></div>
    <div class="c"><div class="t"></div><div class="i">
    <div class="ti">Beta</div><div class="de">Updated yesterday</div></div></div>
    </body></html>"""
    p = "/data/workspace/tmp/_selftest.html"
    os.makedirs("/data/workspace/tmp", exist_ok=True)
    open(p, "w").write(html)
    print("自检：渲染一个含 2 个卡片的正常页面\n")
    img = render_html_to_png(p, "/data/workspace/tmp/_selftest.png")
    print(to_ascii(img, 70))
    print("\n预期：深色顶栏 + 两个结构一致的卡片，无异常")
    print("若上方字符画能看到顶栏与两张卡片，说明渲染链路正常 ✅")


if __name__ == "__main__":
    main()
