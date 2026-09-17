#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
see2.py —— AI 视觉完整分析工具（原创）

把四类能力整合成一条命令，回答"这张图到底是什么、对不对"：

  1. AI 语义识别  ResNet50 / ImageNet-1000 → "这是什么"（真正看懂内容）
  2. OCR 文字     Tesseract              → 文字内容 + 坐标
  3. 颜色分析     精确 RGB 采样           → 颜色对不对
  4. 排版检测     几何分析               → 重叠/超界/空区
  5. ASCII 预览   字符画                 → 直观印象

为什么不用 chafa/jp2a 那种"更清晰的渲染"：
  实测盲测证明，渲染工具只能给直观印象，读不出文字、判不了颜色对错。
  判断"对不对"必须靠结构化提取（RGB/OCR/几何），不是靠把图渲染得更清楚。

用法:
  python3 see2.py 图片.png              # 完整分析
  python3 see2.py 图片.png --no-ai      # 跳过AI识别（快）
  python3 see2.py 图片.png --region x0,y0,x1,y1  # 只分析局部
  python3 see2.py 图片.png --cols 100   # 指定ASCII宽度

依赖（缺失会自动降级，不会崩）:
  onnxruntime   AI识别（可选）
  pytesseract   OCR（可选）
  PIL/numpy     必需
"""

import sys
import os
import numpy as np
from PIL import Image

MODEL_PATH = os.environ.get("VISION_MODEL", "/data/workspace/models/resnet50.onnx")
LABELS_PATH = os.environ.get("VISION_LABELS", "/data/workspace/models/imagenet_classes.txt")

RAMP = " .:-=+*#%@"


# ============================================================
#  1. AI 语义识别（ResNet50 / ImageNet-1000）
# ============================================================
def ai_recognize(im, topk=3):
    """返回 [(类别名, 置信度), ...]；失败返回 None"""
    try:
        import onnxruntime as ort
    except ImportError:
        return None, "onnxruntime 未装"
    if not os.path.exists(MODEL_PATH):
        return None, f"模型不存在: {MODEL_PATH}"
    try:
        sess = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
        a = np.asarray(im.convert("RGB").resize((224, 224))).astype(np.float32)
        # 关键：该模型由 CoreML 转换，内部 ImageScaler 的 bias 是
        # [-103.939, -116.779, -123.68]，即 Caffe 的 BGR 均值，
        # 因此必须传 BGR 顺序 + 0-255，让模型内部自行减均值。
        bgr = a[:, :, ::-1].copy()
        x = np.expand_dims(bgr.transpose(2, 0, 1), 0)  # HWC->CHW->NCHW
        out = sess.run(None, {"image": x})
        # 该模型直接输出类别名字符串
        if out and out[0] is not None and len(out[0]) > 0:
            name = out[0][0]
            if isinstance(name, (bytes, bytearray)):
                name = name.decode("utf-8", errors="ignore")
            return [(str(name), 1.0)], None
        return None, "模型无输出"
    except Exception as e:
        return None, f"AI识别失败: {str(e)[:80]}"


# ============================================================
#  2. OCR 文字识别
# ============================================================
def ocr_text(im):
    """返回 [(x0,y0,x1,y1,文字), ...]；失败返回 []"""
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return [], "pytesseract 未装"
    try:
        d = pytesseract.image_to_data(
            im.convert("RGB"), lang="eng", output_type=Output.DICT
        )
        items = []
        n = len(d.get("text", []))
        for i in range(n):
            t = (d["text"][i] or "").strip()
            if not t:
                continue
            try:
                conf = float(d["conf"][i])
            except (ValueError, TypeError):
                conf = -1
            if conf < 30:      # 过滤低置信度
                continue
            x0 = int(d["left"][i]); y0 = int(d["top"][i])
            x1 = x0 + int(d["width"][i]); y1 = y0 + int(d["height"][i])
            items.append((x0, y0, x1, y1, t))
        return items, None
    except Exception as e:
        return [], f"OCR失败: {str(e)[:70]}"


# ============================================================
#  3. 颜色分析
# ============================================================
def color_analysis(im):
    """返回 (主色列表, 采样点颜色字典)"""
    rgb = im.convert("RGB")
    a = np.asarray(rgb).astype(np.int32)
    h, w = a.shape[:2]

    # 主色：kmeans 量化（无cv2时退化为网格采样统计）
    try:
        import cv2
        pix = a.reshape(-1, 3).astype(np.float32)
        k = 5
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, lab, cen = cv2.kmeans(pix, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(lab.flatten(), minlength=k)
        order = np.argsort(-counts)
        main = [tuple(int(v) for v in cen[i][::-1]) for i in order]  # BGR->RGB
        pct = [float(counts[i]) / len(pix) * 100 for i in order]
    except Exception:
        # 退化：均匀网格采样取最常见色
        step = max(1, min(h, w) // 40)
        samples = a[::step, ::step].reshape(-1, 3)
        uniq, cnt = np.unique(samples, axis=0, return_counts=True)
        order = np.argsort(-cnt)[:5]
        main = [tuple(int(v) for v in uniq[i]) for i in order]
        pct = [float(cnt[i]) / len(samples) * 100 for i in order]

    # 关键点采样
    pts = {}
    for name, (px, py) in {
        "左上": (int(w * 0.1), int(h * 0.1)),
        "中心": (w // 2, h // 2),
        "右下": (int(w * 0.9), int(h * 0.9)),
        "底部中间": (w // 2, int(h * 0.95)),
    }.items():
        if 0 <= px < w and 0 <= py < h:
            pts[name] = tuple(int(v) for v in rgb.getpixel((px, py)))
    return list(zip(main, pct)), pts


# ============================================================
#  4a. 矩形重叠检测（UI 元素压盖）
# ============================================================
def rect_overlap(im, min_area=2000):
    """找出图中所有矩形轮廓，两两判定是否重叠。
    返回 (矩形列表, 重叠对列表)"""
    try:
        import cv2
    except ImportError:
        return [], [], "cv2 未装"
    try:
        a = np.asarray(im.convert("RGB")).astype(np.uint8)
        g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        # 自适应二值化，适应不同背景
        bw = cv2.adaptiveThreshold(
            g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )
        # 形态学闭操作，让边框连成整体
        k = np.ones((3, 3), np.uint8)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k)
        # RETR_LIST：取所有轮廓（RETR_EXTERNAL 会把重叠元素合并成一个外轮廓，
        # 导致压盖无法检出）
        cnts, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        cands = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if w * h < min_area:
                continue
            ca = cv2.contourArea(c)
            if ca <= 0:
                continue
            fill_ratio = ca / float(w * h)
            if fill_ratio < 0.30:      # 太空心（线条/文字）跳过
                continue
            cands.append((x, y, x + w, y + h))

        # 去包含：若 A 完全包住 B，且 B 面积>35%A，保留两者（可能是压盖）；
        # 若只是大背景包小元素，丢掉大的那个（避免把整页当一个元素）
        rects = []
        for i, r in enumerate(cands):
            ax0, ay0, ax1, ay1 = r
            aa = (ax1 - ax0) * (ay1 - ay0)
            dominated = False
            for j, o in enumerate(cands):
                if i == j:
                    continue
                bx0, by0, bx1, by1 = o
                ba = (bx1 - bx0) * (by1 - by0)
                # o 包住 r
                if bx0 <= ax0 and by0 <= ay0 and bx1 >= ax1 and by1 >= ay1:
                    if ba > aa and aa / float(ba) < 0.35:
                        dominated = True
                        break
            if not dominated:
                rects.append(r)

        # 去重（相同或几乎相同的矩形）
        uniq = []
        for r in rects:
            dup = False
            for u in uniq:
                if (abs(r[0] - u[0]) < 6 and abs(r[1] - u[1]) < 6 and
                        abs(r[2] - u[2]) < 6 and abs(r[3] - u[3]) < 6):
                    dup = True
                    break
            if not dup:
                uniq.append(r)
        rects = uniq
        if len(rects) < 2:
            return rects, [], None

        # 两两判定重叠
        pairs = []
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                ax0, ay0, ax1, ay1 = rects[i]
                bx0, by0, bx1, by1 = rects[j]
                ix0, ix1 = max(ax0, bx0), min(ax1, bx1)
                iy0, iy1 = max(ay0, by0), min(ay1, by1)
                if ix1 > ix0 and iy1 > iy0:
                    inter = (ix1 - ix0) * (iy1 - iy0)
                    ua = float((ax1 - ax0) * (ay1 - ay0))
                    ub = float((bx1 - bx0) * (by1 - by0))
                    union = ua + ub - inter
                    iou = inter / union if union > 0 else 0
                    if inter > 500:    # 忽略极小重叠
                        pairs.append({
                            "a": rects[i], "b": rects[j],
                            "area": int(inter), "iou": round(iou, 3),
                            "box": (ix0, iy0, ix1, iy1),
                        })
        return rects, pairs, None
    except Exception as e:
        return [], [], f"矩形检测失败: {str(e)[:70]}"


# ============================================================
#  4. 排版检测
# ============================================================
def layout_check(im):
    """检测：内容边界、是否超出画布、暗区分布"""
    rgb = im.convert("RGB")
    a = np.asarray(rgb).astype(np.int32)
    h, w = a.shape[:2]
    issues = []

    # 内容边界（非背景像素范围）
    bright = a.sum(axis=2)
    bg_val = np.median(bright)
    mask = np.abs(bright - bg_val) > 60
    if mask.any():
        ys, xs = np.where(mask)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        bbox = (x0, y0, x1, y1)
        # 是否贴边（内容顶到画布边缘 = 可能溢出）
        if x1 >= w - 2:
            issues.append(f"内容右边界 {x1} 贴到画布边缘(宽{w})，可能溢出")
        if y1 >= h - 2:
            issues.append(f"内容下边界 {y1} 贴到画布边缘(高{h})，可能溢出")
        if x0 <= 2:
            issues.append(f"内容左边界 {x0} 贴边")
        if y0 <= 2:
            issues.append(f"内容上边界 {y0} 贴边")
        fill = float(mask.sum()) / (h * w) * 100
    else:
        bbox = None
        fill = 0.0
        issues.append("整图几乎无内容（纯色/空白）")

    # 九宫格亮度分布（判断是否大片空白）
    grid = []
    gh, gw = 3, 3
    for i in range(gh):
        row = []
        for j in range(gw):
            blk = a[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw]
            std = float(blk.std()) if blk.size else 0.0
            row.append(round(std, 1))
        grid.append(row)
    flat = [v for r in grid for v in r]
    empty = sum(1 for v in flat if v < 5)
    if empty >= 6:
        issues.append(f"九宫格中有 {empty}/9 格近乎空白（std<5）")
    return bbox, fill, grid, issues


# ============================================================
#  5. ASCII 预览
# ============================================================
def ascii_preview(im, cols=78):
    g = im.convert("L")
    w, h = g.size
    rows = max(1, int(cols * h / w * 0.5))
    small = np.asarray(g.resize((cols, rows), Image.LANCZOS)).astype(np.float32)
    idx = np.clip((small / 255.0 * (len(RAMP) - 1)).astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row) for row in idx]


# ============================================================
#  主流程
# ============================================================
def analyze(path, use_ai=True, region=None, cols=78):
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        return 1
    try:
        im = Image.open(path)
    except Exception as e:
        print(f"无法打开图片: {e}")
        return 1

    orig_size = im.size
    if region:
        try:
            x0, y0, x1, y1 = [int(v) for v in region.split(",")]
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(im.size[0], x1), min(im.size[1], y1)
            if x1 <= x0 or y1 <= y0:
                print(f"区域无效: {region}")
                return 1
            im = im.crop((x0, y0, x1, y1))
        except ValueError:
            print(f"区域格式错误(需 x0,y0,x1,y1): {region}")
            return 1

    print("=" * 62)
    print(f"  图片分析: {os.path.basename(path)}")
    print(f"  尺寸 {orig_size}" + (f"  区域 {im.size}" if region else ""))
    print("=" * 62)

    # 1. AI 语义
    print("\n【1】AI 语义识别（这是什么）")
    if use_ai:
        res, err = ai_recognize(im)
        if res:
            for name, conf in res:
                print(f"  → {name}")
            print("  （ImageNet-1000 类别，ResNet50）")
        else:
            print(f"  ⚠️ 跳过: {err}")
    else:
        print("  （已用 --no-ai 跳过）")

    # 2. OCR
    print("\n【2】文字内容（OCR）")
    items, err = ocr_text(im)
    if err:
        print(f"  ⚠️ {err}")
    elif items:
        for x0, y0, x1, y1, t in items[:25]:
            print(f"  x[{x0:4d}-{x1:4d}] y{y0:4d}  \"{t}\"")
        if len(items) > 25:
            print(f"  ...共 {len(items)} 项")
    else:
        print("  未识别到文字（可能无文字，或白字深底反色导致）")

    # 3. 颜色
    print("\n【3】颜色分析")
    try:
        main, pts = color_analysis(im)
        print("  主色（占比）:")
        for c, p in main:
            print(f"    RGB{c}  {p:5.1f}%")
        print("  关键位置采样:")
        for k, v in pts.items():
            print(f"    {k:8s} RGB{v}")
    except Exception as e:
        print(f"  ⚠️ 颜色分析失败: {str(e)[:70]}")

    # 4. 排版
    print("\n【4】排版检测")
    try:
        bbox, fill, grid, issues = layout_check(im)
        if bbox:
            print(f"  内容边界: x[{bbox[0]}-{bbox[2]}] y[{bbox[1]}-{bbox[3]}]")
        print(f"  内容占比: {fill:.1f}%")
        print("  九宫格细节密度(std，越大越有内容):")
        for r in grid:
            print("    " + "  ".join(f"{v:6.1f}" for v in r))
        if issues:
            print("  ⚠️ 发现的问题:")
            for s in issues:
                print(f"    - {s}")
        else:
            print("  ✅ 未发现边界/空白问题")

        # 矩形重叠（UI 元素压盖）
        rects, pairs, rerr = rect_overlap(im)
        if rerr:
            print(f"  （重叠检测跳过: {rerr}）")
        elif rects:
            print(f"  检出矩形元素 {len(rects)} 个")
            for i, r in enumerate(rects[:8]):
                print(f"    #{i} x[{r[0]}-{r[2]}] y[{r[1]}-{r[3]}]")
            if len(rects) > 8:
                print(f"    ...共 {len(rects)} 个")
            if pairs:
                print(f"  ⚠️ 发现 {len(pairs)} 处元素重叠:")
                for p in pairs[:6]:
                    print(f"    - #{rects.index(p['a'])} 与 #{rects.index(p['b'])} "
                          f"重叠面积 {p['area']} (IoU {p['iou']}) "
                          f"区域 x[{p['box'][0]}-{p['box'][2]}] y[{p['box'][1]}-{p['box'][3]}]")
            else:
                print("  ✅ 未发现元素重叠")
    except Exception as e:
        print(f"  ⚠️ 排版检测失败: {str(e)[:70]}")

    # 5. ASCII
    print(f"\n【5】ASCII 预览（{cols}列）")
    try:
        for line in ascii_preview(im, cols):
            print("  " + line)
    except Exception as e:
        print(f"  ⚠️ 预览失败: {str(e)[:70]}")

    print("\n" + "=" * 62)
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = args[0]
    use_ai = "--no-ai" not in args
    region = None
    cols = 78
    if "--region" in args:
        try:
            region = args[args.index("--region") + 1]
        except IndexError:
            pass
    if "--cols" in args:
        try:
            cols = int(args[args.index("--cols") + 1])
        except (IndexError, ValueError):
            pass
    return analyze(path, use_ai=use_ai, region=region, cols=cols)


if __name__ == "__main__":
    sys.exit(main())
