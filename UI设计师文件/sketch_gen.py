#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 渲染稿 -> 真 .sketch 源文件生成器

依据 Sketch 官方公开格式（Sketch 43+ / 2017 起）：
  .sketch = ZIP 容器，内含
    meta.json                文档元数据（页面/画板列表、版本、字体）
    document.json            共享样式 + 指向 pages/ 的引用
    user.json                画布视口/缩放
    pages/<UUID>.json        每页内容（artboard 及图层树）
    previews/preview.png     缩略图（可选）

关键点：
  · 颜色用 RGBA，取值 0.0-1.0 浮点（不是 0-255）
  · 每个图层必须有 _class / do_objectID / frame / name
  · frame 用字符串 "{{x,y},{w,h}}"
  · Figma 官方支持直接导入 .sketch，所以这一份同时解决两个工具的源文件需求

用法：
  python3 sketch_gen.py <输入.json> <输出.sketch>
"""
import json
import os
import sys
import uuid
import zipfile
from io import BytesIO

U = lambda: str(uuid.uuid4()).upper()


def frame(x, y, w, h):
    return {"_class": "rect", "constrainProportions": False,
            "height": float(h), "width": float(w), "x": float(x), "y": float(y)}


def color(hexstr, alpha=1.0):
    """#RRGGBB -> Sketch color dict (RGBA 0-1 浮点)"""
    h = (hexstr or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return {"_class": "color", "alpha": alpha,
            "blue": round(b / 255, 8), "green": round(g / 255, 8),
            "red": round(r / 255, 8)}


def border(color_hex, thickness=1.0, alpha=1.0):
    return {"_class": "border", "isEnabled": True,
            "color": color(color_hex, alpha), "fillType": 0,
            "thickness": thickness, "position": 1}


def style(fill_hex=None, border_hex=None, radius=0, thickness=1.0):
    st = {"_class": "style", "endMarkerType": 0, "startMarkerType": 0,
          "miterLimit": 10, "windingRule": 1,
          "borders": [border(border_hex, thickness)] if border_hex else [],
          "fills": [{"_class": "fill", "isEnabled": True,
                     "color": color(fill_hex or "#FFFFFF"),
                     "fillType": 0, "noiseIndex": 0, "noiseIntensity": 0,
                     "patternFillType": 1, "patternTileScale": 1}]
          if fill_hex else [],
          "contextSettings": {"_class": "graphicsContextSettings",
                              "blendMode": 0, "opacity": 1},
          "do_objectID": U()}
    if radius:
        st["borderOptions"] = {"_class": "borderOptions", "isEnabled": True,
                               "dashPattern": [], "lineCapStyle": 0,
                               "lineJoinStyle": 0}
    return st


def rect_layer(name, x, y, w, h, fill="#FFFFFF", radius=0, border_hex=None):
    return {"_class": "rectangle", "do_objectID": U(), "name": name,
            "isVisible": True, "isLocked": False, "isFlippedHorizontal": False,
            "isFlippedVertical": False, "booleanOperation": -1,
            "frame": frame(x, y, w, h),
            "rotation": 0, "fixedRadius": float(radius),
            "hasConvertedToNewRoundCorners": True,
            "hasSlice": False, "exportOptions": {
                "_class": "exportOptions", "exportFormats": [],
                "includedLayerIds": [], "layerOptions": 0,
                "shouldTrim": False},
            "style": style(fill, border_hex, radius),
            "resizingConstraint": 63, "resizingType": 0}


def oval_layer(name, x, y, w, h, fill="#FFFFFF"):
    return {"_class": "oval", "do_objectID": U(), "name": name,
            "isVisible": True, "isLocked": False,
            "frame": frame(x, y, w, h), "rotation": 0,
            "booleanOperation": -1, "isClosed": True,
            "points": [
                {"_class": "curvePoint", "cornerRadius": 0, "curveFrom": "{0.77614237490000004, 1}",
                 "curveMode": 2, "curveTo": "{0.22385762510000001, 1}",
                 "hasCurveFrom": True, "hasCurveTo": True, "point": "{0.5, 1}"},
                {"_class": "curvePoint", "cornerRadius": 0, "curveFrom": "{1, 0.77614237490000004}",
                 "curveMode": 2, "curveTo": "{1, 0.22385762510000001}",
                 "hasCurveFrom": True, "hasCurveTo": True, "point": "{1, 0.5}"},
                {"_class": "curvePoint", "cornerRadius": 0, "curveFrom": "{0.22385762510000001, 0}",
                 "curveMode": 2, "curveTo": "{0.77614237490000004, 0}",
                 "hasCurveFrom": True, "hasCurveTo": True, "point": "{0.5, 0}"},
                {"_class": "curvePoint", "cornerRadius": 0, "curveFrom": "{0, 0.22385762510000001}",
                 "curveMode": 2, "curveTo": "{0, 0.77614237490000004}",
                 "hasCurveFrom": True, "hasCurveTo": True, "point": "{0, 0.5}"}],
            "style": style(fill),
            "resizingConstraint": 63, "resizingType": 0,
            "exportOptions": {"_class": "exportOptions", "exportFormats": [],
                              "includedLayerIds": [], "layerOptions": 0,
                              "shouldTrim": False}}


def text_layer(name, x, y, w, h, text, size=14, weight=400,
               fill="#000000", align="left", font="Helvetica"):
    amap = {"left": 0, "right": 1, "center": 2, "justified": 3}
    return {"_class": "text", "do_objectID": U(), "name": name,
            "isVisible": True, "isLocked": False,
            "frame": frame(x, y, w, h), "rotation": 0,
            "booleanOperation": -1, "isFixedToViewport": False,
            "resizingConstraint": 47, "resizingType": 0,
            "textBehaviour": 0, "lineSpacingBehaviour": 2,
            "automaticallyDrawOnUnderlyingPath": False,
            "dontSynchroniseWithSymbol": False,
            "glyphBounds": "{{0, 3}, {%s, %s}}" % (w, size * 1.4),
            "attributedString": {"_class": "attributedString", "string": text,
                                 "attributes": [{"_class": "stringAttribute",
                                                 "location": 0, "length": len(text),
                                                 "attributes": {
                                                     "_class": "attributes",
                                                     "MSAttributedStringFontAttribute": {
                                                         "_class": "fontDescriptor",
                                                         "attributes": {"name": font, "size": float(size)}},
                                                     "MSAttributedStringColorAttribute": color(fill),
                                                     "textStyleVerticalAlignmentKey": 0,
                                                     "kerning": 0, "paragraphStyle": {
                                                         "_class": "paragraphStyle",
                                                         "alignment": amap.get(align, 0),
                                                         "maximumLineHeight": float(size * 1.4),
                                                         "minimumLineHeight": float(size * 1.4)}}}]},
            "style": {"_class": "style", "endMarkerType": 0, "startMarkerType": 0,
                      "miterLimit": 10, "windingRule": 1, "borders": [], "fills": [],
                      "contextSettings": {"_class": "graphicsContextSettings",
                                          "blendMode": 0, "opacity": 1},
                      "do_objectID": U(),
                      "textStyle": {"_class": "textStyle",
                                    "encodedAttributes": {
                                        "MSAttributedStringFontAttribute": {
                                            "_class": "fontDescriptor",
                                            "attributes": {"name": font, "size": float(size)}},
                                        "MSAttributedStringColorAttribute": color(fill),
                                        "textStyleVerticalAlignmentKey": 0,
                                        "paragraphStyle": {"_class": "paragraphStyle",
                                                           "alignment": amap.get(align, 0)}}}},
            "exportOptions": {"_class": "exportOptions", "exportFormats": [],
                              "includedLayerIds": [], "layerOptions": 0,
                              "shouldTrim": False}}


def build_layer(spec):
    """spec: {"type":"rect|oval|text", ...}"""
    t = spec.get("type", "rect")
    if t == "text":
        return text_layer(spec.get("name", "文本"), spec.get("x", 0), spec.get("y", 0),
                          spec.get("w", 100), spec.get("h", 20),
                          spec.get("text", ""), spec.get("size", 14),
                          spec.get("weight", 400), spec.get("fill", "#000000"),
                          spec.get("align", "left"), spec.get("font", "Helvetica"))
    if t == "oval":
        return oval_layer(spec.get("name", "椭圆"), spec.get("x", 0), spec.get("y", 0),
                          spec.get("w", 100), spec.get("h", 100), spec.get("fill", "#FFFFFF"))
    return rect_layer(spec.get("name", "矩形"), spec.get("x", 0), spec.get("y", 0),
                      spec.get("w", 100), spec.get("h", 100),
                      spec.get("fill", "#FFFFFF"), spec.get("radius", 0),
                      spec.get("border"))


def build_sketch(design, out_path):
    """
    design = {
      "name": "文档名",
      "pages": [{"name":"Page 1",
                 "artboards":[{"name":"画板名","w":375,"h":812,
                               "background":"#FFFFFF",
                               "layers":[{...spec}]}]}]
    }
    """
    doc_id = U()
    page_ids, meta_pages = [], {}

    for _ in design.get("pages", []):
        pid = U()
        page_ids.append({"_class": "MSJSONFileReference",
                         "_ref_class": "MSImmutablePage",
                         "_ref": "pages/%s" % pid})
        meta_pages[pid] = {"name": None, "artboards": {}}

    # pages 内容
    pages_files = {}
    for i, pg in enumerate(design.get("pages", [])):
        pid = page_ids[i]["_ref"].split("/")[-1]
        meta_pages[pid]["name"] = pg.get("name", "Page %d" % (i + 1))
        ab_entries = {}
        layers = []
        for ab in pg.get("artboards", []):
            ab_id = U()
            ab_layers = [build_layer(s) for s in ab.get("layers", [])]
            layers.append({
                "_class": "artboard", "do_objectID": ab_id,
                "name": ab.get("name", "画板"),
                "isVisible": True, "isLocked": False,
                "frame": frame(ab.get("x", 0), ab.get("y", 0),
                               ab.get("w", 375), ab.get("h", 812)),
                "rotation": 0, "booleanOperation": -1,
                "hasBackgroundColor": True,
                "backgroundColor": color(ab.get("background", "#FFFFFF")),
                "resizingConstraint": 63, "resizingType": 0,
                "layers": ab_layers,
                "exportOptions": {"_class": "exportOptions", "exportFormats": [],
                                  "includedLayerIds": [], "layerOptions": 0,
                                  "shouldTrim": False},
                "includeBackgroundColorInInstance": False,
                "includeInCloudUpload": True,
                "clipsContentToBounds": True})
            ab_entries[ab_id] = {"name": ab.get("name", "画板")}
        meta_pages[pid]["artboards"] = ab_entries
        pages_files["pages/%s.json" % pid] = {
            "_class": "page", "do_objectID": pid,
            "name": pg.get("name", "Page %d" % (i + 1)),
            "isVisible": True, "isLocked": False,
            "frame": frame(0, 0, 1000, 1000), "rotation": 0,
            "booleanOperation": -1, "hasClickThrough": True,
            "resizingConstraint": 63, "resizingType": 0,
            "layers": layers,
            "exportOptions": {"_class": "exportOptions", "exportFormats": [],
                              "includedLayerIds": [], "layerOptions": 0,
                              "shouldTrim": False},
            "includeInCloudUpload": True}

    # document.json
    document = {
        "_class": "document", "do_objectID": doc_id,
        "assets": {"_class": "assetCollection", "colorAssets": [],
                   "gradientAssets": [], "images": [], "colors": [],
                   "gradients": []},
        "colorSpace": 0, "currentPageIndex": 0,
        "layerStyles": {"_class": "sharedStyleContainer", "objects": []},
        "layerSymbols": {"_class": "symbolContainer", "objects": []},
        "layerTextStyles": {"_class": "sharedTextStyleContainer", "objects": []},
        "enableLayerInteraction": True, "enableSliceInteraction": True,
        "pages": page_ids,
        "perDocumentLibraries": [], "fontReferences": []}

    # meta.json
    meta = {
        "commit": "generated-by-yuanbao",
        "pagesAndArtboards": meta_pages,
        "version": 143,
        "fonts": [],
        "compatibilityVersion": 99,
        "app": "com.bohemiancoding.sketch3",
        "autosaved": 0,
        "variant": "NONAPPSTORE",
        "created": {"commit": "generated", "appVersion": "99.1",
                    "build": 1, "app": "com.bohemiancoding.sketch3",
                    "compatibilityVersion": 99, "version": 143,
                    "variant": "NONAPPSTORE"},
        "saveHistory": ["NONAPPSTORE.1"],
        "appVersion": "99.1",
        "build": 1}

    # user.json
    user = {}
    for i, pg in enumerate(design.get("pages", [])):
        pid = page_ids[i]["_ref"].split("/")[-1]
        user["document.%s" % doc_id] = {}
        user["page.%s" % pid] = {"scrollOrigin": "{0, 0}", "zoomValue": 1}

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False))
        z.writestr("document.json", json.dumps(document, ensure_ascii=False))
        z.writestr("user.json", json.dumps(user, ensure_ascii=False))
        for k, v in pages_files.items():
            z.writestr(k, json.dumps(v, ensure_ascii=False))
    return out_path


def verify(path):
    """验证生成的 .sketch 结构与官方格式一致"""
    rep = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        rep.append("ZIP 条目 %d 个" % len(names))
        for need in ["meta.json", "document.json", "user.json"]:
            rep.append("  %-14s %s" % (need, "✅" if need in names else "❌"))
        pages = [n for n in names if n.startswith("pages/")]
        rep.append("  pages/*.json   %s（%d 个）" % ("✅" if pages else "❌", len(pages)))
        # JSON 可解析
        for n in names:
            if n.endswith(".json"):
                json.loads(z.read(n).decode("utf-8"))
        rep.append("  全部 JSON 解析   ✅")
        # 图层统计
        total = 0
        classes = {}
        for n in pages:
            d = json.loads(z.read(n).decode("utf-8"))
            def walk(ls):
                c = 0
                for l in ls:
                    c += 1
                    classes[l.get("_class")] = classes.get(l.get("_class"), 0) + 1
                    c += walk(l.get("layers", []))
                return c
            total += walk(d.get("layers", []))
        rep.append("  图层总数 %d" % total)
        for k, v in sorted(classes.items()):
            rep.append("    %-12s %d" % (k, v))
        # 检查每个图层必备字段
        ok = True
        for n in pages:
            d = json.loads(z.read(n).decode("utf-8"))
            def chk(ls):
                nonlocal ok
                for l in ls:
                    for f in ["_class", "do_objectID", "frame", "name"]:
                        if f not in l:
                            ok = False
                    chk(l.get("layers", []))
            chk(d.get("layers", []))
        rep.append("  必备字段完整     %s" % ("✅" if ok else "❌"))
        # 颜色范围
        rng_ok = True
        def cchk(o):
            nonlocal rng_ok
            if isinstance(o, dict):
                if o.get("_class") == "color":
                    for k in ["red", "green", "blue"]:
                        if not (0.0 <= o.get(k, 0) <= 1.0):
                            rng_ok = False
                for v in o.values():
                    cchk(v)
            elif isinstance(o, list):
                for v in o:
                    cchk(v)
        for n in pages:
            cchk(json.loads(z.read(n).decode("utf-8")))
        rep.append("  颜色 0-1 范围    %s" % ("✅" if rng_ok else "❌"))
    return "\n".join(rep)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    design = json.load(open(sys.argv[1], encoding="utf-8"))
    out = build_sketch(design, sys.argv[2])
    print("✅ 已生成:", out, os.path.getsize(out), "字节")
    print("──── 自检 ────")
    print(verify(out))
