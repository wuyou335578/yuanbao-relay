#!/usr/bin/env python3
"""
img2ascii.py —— 把图片渲染成终端/文本 ASCII 画，让纯文本模型也能"看到"图片内容。
用法: python3 img2ascii.py <图片路径> [宽度] [--color]
"""
import sys
from PIL import Image

# 由深到浅的字符集（视觉上对应"墨多 -> 墨少"）
RAMP = " .:-=+*#%@"
RAMP = RAMP[::-1]  # 反转：越亮的像素用越"重"的字符


def to_ascii(path, width=80, color=False, aspect=0.5):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    new_h = max(1, int(width * h / w * aspect))
    small = im.resize((width, new_h), Image.LANCZOS)
    px = small.load()

    lines = []
    for y in range(new_h):
        row = []
        for x in range(width):
            r, g, b = px[x, y]
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            ch = RAMP[min(len(RAMP) - 1, lum * len(RAMP) // 256)]
            row.append(ch)
        lines.append("".join(row))
    return lines, (w, h)


def to_ascii_color(path, width=60, aspect=0.5):
    """用 ANSI 24 位色输出彩色字符画（终端支持真彩时效果更好）。"""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    new_h = max(1, int(width * h / w * aspect))
    small = im.resize((width, new_h), Image.LANCZOS)
    px = small.load()
    out = []
    for y in range(new_h):
        row = []
        for x in range(width):
            r, g, b = px[x, y]
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            ch = RAMP[min(len(RAMP) - 1, lum * len(RAMP) // 256)]
            row.append(f"\033[38;2;{r};{g};{b}m{ch}\033[0m")
        out.append("".join(row))
    return out, (w, h)


if __name__ == "__main__":
    p = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    color = "--color" in sys.argv
    if color:
        lines, size = to_ascii_color(p, w)
    else:
        lines, size = to_ascii(p, w)
    print(f"# 原图尺寸 {size[0]}x{size[1]}  ->  ASCII {w} 列")
    print("+" + "-" * w + "+")
    for l in lines:
        print("|" + l + "|")
    print("+" + "-" * w + "+")
