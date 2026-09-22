#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉分析：从像素中反推控件位置（不依赖程序上报坐标）"""
from PIL import Image
import sys

path = sys.argv[1] if len(sys.argv) > 1 else '/data/workspace/guiagent/step.png'
im = Image.open(path).convert('RGB')
W, H = im.size
px = im.load()

def find_color(target, tol=14):
    """扫描整幅图，返回匹配像素的包围盒与重心"""
    xs, ys = [], []
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            if abs(r-target[0]) < tol and abs(g-target[1]) < tol and abs(b-target[2]) < tol:
                xs.append(x); ys.append(y)
    if not xs:
        return None
    return {
        'count': len(xs),
        'bbox': (min(xs), min(ys), max(xs), max(ys)),
        'center': (sum(xs)//len(xs), sum(ys)//len(ys)),
    }

print(f"图像尺寸: {W}x{H}\n")

targets = {
    '提交按钮(青 #4DD0E1)': (77, 208, 225),
    '状态区-灰 #3A3F44': (58, 63, 68),
    '状态区-绿 #00C853': (0, 200, 83),
    '状态区-红 #B00020': (176, 0, 32),
    '重置按钮(灰 #5F6368)': (95, 99, 104),
    '输入框底 #1E2124': (30, 33, 36),
}

for name, c in targets.items():
    r = find_color(c)
    if r:
        x0, y0, x1, y1 = r['bbox']
        print(f"【{name}】")
        print(f"  像素数: {r['count']}")
        print(f"  包围盒: x {x0}-{x1}, y {y0}-{y1}  (宽{x1-x0} 高{y1-y0})")
        print(f"  重心:   {r['center']}\n")
    else:
        print(f"【{name}】 未找到\n")

# 找输入框：在 y=76..270 区间扫描 #1E2124 的横向连续带
print("── 输入框逐行定位（扫描 #1E2124 深色带）──")
rows = {}
for y in range(60, 300):
    cnt = sum(1 for x in range(100, 700) if abs(px[x,y][0]-30)<10 and abs(px[x,y][1]-33)<10 and abs(px[x,y][2]-36)<10)
    if cnt > 100:
        rows[y] = cnt
if rows:
    # 归并连续行
    ys = sorted(rows)
    groups, cur = [], [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= 2: cur.append(y)
        else: groups.append(cur); cur = [y]
    groups.append(cur)
    for i, g in enumerate(groups, 1):
        # 取该带中间行的 x 范围
        my = g[len(g)//2]
        xs = [x for x in range(100, 700) if abs(px[x,my][0]-30)<10 and abs(px[x,my][1]-33)<10 and abs(px[x,my][2]-36)<10]
        print(f"  输入框{i}: y {g[0]}-{g[-1]} (高{g[-1]-g[0]+1}), x {min(xs)}-{max(xs)}, 中心 ({sum(xs)//len(xs)},{my})")
else:
    print("  未检出输入框")
