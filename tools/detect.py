#!/usr/bin/env python3
# ============================================================
#  detect.py —— YOLOv8 目标检测（纯 ONNX Runtime，无需 PyTorch）
#
#  比 ResNet50 强在哪：
#    ResNet50 只回答"这张图整体像什么"（1000 个 ImageNet 类别）
#    本脚本回答"图里有什么东西、各自在哪" —— 80 个 COCO 类别 + 坐标框
#
#  用法：
#    python3 detect.py 图片.jpg
#    python3 detect.py 图片.jpg --conf 0.4
#    python3 detect.py 图片.jpg --save out.jpg
#
#  依赖：pip install onnxruntime opencv-python-headless numpy
#  模型：同目录下 yolov8n.onnx（YOLOv8-nano，12MB，CPU 可实时）
# ============================================================
import sys, os, time, argparse
import numpy as np

MODEL_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.onnx")

# COCO 80 类（YOLOv8 官方顺序）
COCO = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
"traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse",
"sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase",
"frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard",
"surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana",
"apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
"potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone",
"microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear",
"hair drier","toothbrush"]


def letterbox(im, size=640):
    """保持长宽比缩放并补灰边，YOLOv8 要求的预处理"""
    h, w = im.shape[:2]
    r = min(size / h, size / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, r, left, top


def nms(boxes, scores, iou_thr=0.45):
    """非极大值抑制：去掉重叠的重复框"""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest]); yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest]); yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou <= iou_thr]
    return keep


def detect(model_path, img_path, conf=0.25, iou=0.45):
    import onnxruntime as ort
    import cv2

    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    im0 = cv2.imread(img_path)
    if im0 is None:
        raise SystemExit(f"读不了图片: {img_path}")

    t0 = time.time()
    im, r, left, top = letterbox(im0)
    blob = im[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = np.expand_dims(blob, 0)

    out = sess.run(None, {sess.get_inputs()[0].name: blob})[0]  # [1,84,8400]
    pred = out[0].T                                             # [8400,84]

    boxes_cxcywh = pred[:, :4]
    cls_scores = pred[:, 4:]
    cls_ids = cls_scores.argmax(1)
    scores = cls_scores.max(1)

    mask = scores > conf
    boxes_cxcywh, scores, cls_ids = boxes_cxcywh[mask], scores[mask], cls_ids[mask]
    if len(scores) == 0:
        return [], im0, time.time() - t0

    # cx,cy,w,h -> x1,y1,x2,y2，并映射回原图坐标
    cx, cy, bw, bh = boxes_cxcywh.T
    x1 = (cx - bw / 2 - left) / r
    y1 = (cy - bh / 2 - top) / r
    x2 = (cx + bw / 2 - left) / r
    y2 = (cy + bh / 2 - top) / r
    boxes = np.stack([x1, y1, x2, y2], 1)
    boxes[:, 0::2] = np.clip(boxes[:, 0::2], 0, im0.shape[1])
    boxes[:, 1::2] = np.clip(boxes[:, 1::2], 0, im0.shape[0])

    keep = nms(boxes, scores, iou)
    results = [(COCO[cls_ids[i]], float(scores[i]),
                [float(v) for v in boxes[i]]) for i in keep]
    return results, im0, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--save", default=None, help="把画框结果存成图片")
    a = ap.parse_args()

    results, im0, dt = detect(a.model, a.image, a.conf)
    print(f"═══ {os.path.basename(a.image)}  检测 {len(results)} 个目标  耗时 {dt*1000:.0f}ms ═══")
    for name, score, (x1, y1, x2, y2) in results:
        print(f"  {name:<16} {score:.2f}  [{x1:.0f},{y1:.0f}]-[{x2:.0f},{y2:.0f}]")

    if a.save:
        import cv2
        for name, score, (x1, y1, x2, y2) in results:
            cv2.rectangle(im0, (int(x1), int(y1)), (int(x2), int(y2)), (0, 200, 0), 2)
            cv2.putText(im0, f"{name} {score:.2f}", (int(x1), max(int(y1) - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 2)
        cv2.imwrite(a.save, im0)
        print(f"  已存: {a.save}")


if __name__ == "__main__":
    import cv2  # noqa
    main()
