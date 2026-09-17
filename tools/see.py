#!/usr/bin/env python3
"""
see.py —— 沙盒"视觉中枢"：把一张图翻译成纯文本可读的完整描述。

整合了本地安装的所有视觉能力：
  · 基础元信息      尺寸 / 格式 / 通道
  · 色彩分析        主色（含色名）/ 亮度 / 饱和度 / 对比度
  · 构图分析        边缘密度 / 区域亮度九宫格
  · ASCII 预览      让纯文本模型直接"看到"画面轮廓
  · OCR 文字识别    Tesseract（中/英/繁，LSTM 神经网络）
  · 人脸检测        MediaPipe BlazeFace（神经网络）
  · 面部关键点      MediaPipe Face Mesh 468 点
  · 姿态估计        MediaPipe Pose 33 点（全身时）
  · 手部关键点      MediaPipe Hands 21 点/手
  · 轮廓/形状       OpenCV 轮廓检测，推断几何形状

用法:
  python3 see.py <图片路径> [--ascii 72] [--no-ocr] [--lang chi_sim+eng]
"""
import sys, os, argparse
import numpy as np
from PIL import Image
import cv2

# ---------- 色彩名对照（粗粒度，够用） ----------
COLOR_NAMES = [
    ("红", (220, 40, 40)), ("深红", (140, 20, 20)), ("粉", (255, 160, 190)),
    ("橙", (245, 140, 40)), ("黄", (245, 215, 50)), ("棕", (140, 95, 55)),
    ("绿", (45, 165, 85)), ("深绿", (25, 95, 55)), ("青", (60, 195, 195)),
    ("蓝", (50, 105, 215)), ("深蓝", (20, 45, 130)), ("紫", (135, 80, 200)),
    ("白", (250, 250, 250)), ("浅灰", (200, 200, 200)), ("灰", (130, 130, 130)),
    ("深灰", (70, 70, 70)), ("黑", (20, 20, 20)),
]

def nearest_color(rgb):
    r, g, b = rgb
    best, bd = "?", 1e9
    for name, (cr, cg, cb) in COLOR_NAMES:
        d = (r-cr)**2 + (g-cg)**2 + (b-cb)**2
        if d < bd:
            bd, best = d, name
    return best

def dominant_colors(pil, k=5):
    """用 Pillow 自适应调色板取主色。"""
    q = pil.convert("RGB").resize((160, 160))
    pal = q.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    p = pal.convert("RGB")
    counts = sorted(pal.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for cnt, idx in counts:
        rgb = p.getpixel((0, 0))  # 占位，下面用 palette 取
        # 从调色板取实际颜色
        pal_data = pal.getpalette()
        r, g, b = pal_data[idx*3: idx*3+3]
        out.append((round(cnt/total*100, 1), (r, g, b), nearest_color((r, g, b))))
    return out

def ascii_art(pil, width=72, aspect=0.5):
    RAMP = "@%#*+=-:. "  # 亮 -> 暗
    w, h = pil.size
    nh = max(1, int(width * h / w * aspect))
    small = pil.convert("RGB").resize((width, nh), Image.LANCZOS)
    px = small.load()
    lines = []
    for y in range(nh):
        lines.append("".join(
            RAMP[min(9, int(0.299*px[x,y][0] + 0.587*px[x,y][1] + 0.114*px[x,y][2]) * 10 // 256)]
            for x in range(width)))
    return lines

def ocr(path, lang="chi_sim+eng"):
    """返回 (文本, 是否可信)。无文字的图片常被 OCR 读成乱码，需过滤。"""
    import subprocess, re
    try:
        r = subprocess.run(["tesseract", path, "stdout", "-l", lang, "--psm", "6"],
                           capture_output=True, text=True, timeout=180)
        t = r.stdout.strip()
        if not t or len(t) < 2:
            return None, False
        # 统计"像话"的字符占比：字母/数字/CJK/空格/常见标点
        good = re.findall(r"[A-Za-z0-9\u4e00-\u9fff\s.,;:!?'\-()/]", t)
        ratio = len(good) / len(t) if t else 0
        # 真实文字会形成多个长度>=3 的连续词；噪声图只会有一堆单双字符碎片
        words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{3,}", t)
        ok = ratio > 0.8 and len(words) >= 3
        return t, ok
    except Exception:
        return None, False

def detect_faces(cv_img):
    try:
        import mediapipe as mp
    except Exception:
        return None
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    h, w = cv_img.shape[:2]
    res = {"faces": [], "mesh": None, "hands": None, "pose": None}
    with mp.solutions.face_detection.FaceDetection(model_selection=1,
                                                   min_detection_confidence=0.5) as fd:
        r = fd.process(rgb)
        for d in (r.detections or []):
            b = d.location_data.relative_bounding_box
            res["faces"].append({
                "score": round(float(d.score[0]), 3),
                "box": [round(b.xmin,2), round(b.ymin,2), round(b.width,2), round(b.height,2)],
                "px": [int(b.xmin*w), int(b.ymin*h), int(b.width*w), int(b.height*h)],
            })
    if res["faces"]:
        with mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as fm:
            r = fm.process(rgb)
            if r.multi_face_landmarks:
                lm = r.multi_face_landmarks[0]
                pts = [(int(p.x*w), int(p.y*h)) for p in lm.landmark]
                res["mesh"] = {
                    "count": len(pts),
                    "nose_tip": pts[1], "chin": pts[152],
                    "left_eye": pts[33], "right_eye": pts[263],
                    "mouth": pts[13],
                }
    with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=2,
                                  min_detection_confidence=0.5) as hd:
        r = hd.process(rgb)
        if r.multi_hand_landmarks:
            res["hands"] = [{"points": len(l.landmark)} for l in r.multi_hand_landmarks]
    with mp.solutions.pose.Pose(static_image_mode=True, min_detection_confidence=0.5) as ps:
        r = ps.process(rgb)
        if r.pose_landmarks:
            res["pose"] = {"points": len(r.pose_landmarks.landmark)}
    return res

def shapes(cv_img):
    """轮廓检测 + 形状推断。"""
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) > 500]
    out = []
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:6]:
        area = cv2.contourArea(c)
        peri = cv2.arcLength(c, True)
        if peri == 0: continue
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        n = len(approx)
        x, y, w, h = cv2.boundingRect(c)
        ar = w / float(h) if h else 0
        circ = 4 * np.pi * area / (peri * peri) if peri else 0
        if n == 3: kind = "三角形"
        elif n == 4: kind = "正方形" if 0.85 < ar < 1.18 else "矩形"
        elif circ > 0.75: kind = "圆形"
        elif n >= 8: kind = "椭圆/圆"
        else: kind = f"多边形({n}边)"
        out.append({"kind": kind, "area": int(area), "box": [int(x), int(y), int(w), int(h)]})
    return {"edge_density": round(float(np.count_nonzero(edges)) / edges.size, 4),
            "count": len(cnts), "shapes": out}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--ascii", type=int, default=72)
    ap.add_argument("--lang", default="chi_sim+eng")
    ap.add_argument("--no-ocr", action="store_true")
    a = ap.parse_args()

    pil = Image.open(a.path)
    cv_img = cv2.imread(a.path)
    arr = np.array(pil.convert("RGB"))

    print("=" * 74)
    print(f"图像分析报告: {os.path.basename(a.path)}")
    print("=" * 74)
    print(f"[基本信息] 尺寸 {pil.size[0]}x{pil.size[1]}  格式 {pil.format}  模式 {pil.mode}")
    print(f"           文件大小 {os.path.getsize(a.path)} 字节")

    print(f"\n[明暗统计] 平均亮度 {arr.mean():.1f}/255   标准差(对比度) {arr.std():.1f}")
    hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
    print(f"           平均饱和度 {hsv[:,:,1].mean():.1f}/255")

    print("\n[主色构成]")
    for pct, rgb, name in dominant_colors(pil):
        bar = "█" * max(1, int(pct / 3))
        print(f"   {pct:5.1f}%  RGB{str(rgb):16s} {name:4s} {bar}")

    print("\n[九宫格亮度分布] (看构图重心)")
    g = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    for r in range(3):
        row = []
        for c in range(3):
            blk = g[r*H//3:(r+1)*H//3, c*W//3:(c+1)*W//3]
            row.append(f"{int(blk.mean()):4d}")
        print("   " + " ".join(row))

    sh = shapes(cv_img)
    print(f"\n[轮廓与形状] 边缘密度 {sh['edge_density']:.4f}  检出 {sh['count']} 个轮廓")
    for s in sh["shapes"][:5]:
        print(f"   · {s['kind']:10s} 面积 {s['area']:7d}  位置 {s['box']}")

    if not a.no_ocr:
        t, ok = ocr(a.path, a.lang)
        print("\n[文字识别 OCR]")
        if ok:
            for line in t.splitlines()[:14]:
                print("   " + line)
        elif t:
            print(f"   （识别到 {len(t.splitlines())} 行碎片，置信度过低，判定为无文字图像）")
        else:
            print("   未识别到文字")

    det = detect_faces(cv_img)
    print("\n[神经网络视觉模型]")
    if det:
        print(f"   人脸检测(BlazeFace): 检出 {len(det['faces'])} 张")
        for f in det["faces"]:
            print(f"      置信度 {f['score']}  像素框 {f['px']}")
        if det["mesh"]:
            m = det["mesh"]
            print(f"   面部关键点(FaceMesh): {m['count']} 点")
            print(f"      鼻尖 {m['nose_tip']} 下巴 {m['chin']} 左眼 {m['left_eye']} 右眼 {m['right_eye']}")
        print(f"   手部关键点: {len(det['hands']) if det['hands'] else 0} 只手"
              + (f" x {det['hands'][0]['points']} 点" if det["hands"] else ""))
        print(f"   人体姿态: {'检出 33 点' if det['pose'] else '未检出'}")
    else:
        print("   (mediapipe 未安装)")

    print(f"\n[ASCII 预览] 我自己看到的画面：")
    print("+" + "-" * a.ascii + "+")
    for l in ascii_art(pil, a.ascii):
        print("|" + l + "|")
    print("+" + "-" * a.ascii + "+")

if __name__ == "__main__":
    main()
