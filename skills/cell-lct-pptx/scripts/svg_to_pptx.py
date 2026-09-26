#!/usr/bin/env python3
"""
svg_to_pptx.py - Render an SVG into native, editable PowerPoint shapes.

Every SVG path is recreated as a PowerPoint Freeform (cubic Beziers map 1:1 to
msoSegmentCurve nodes), primitives (rect/circle/ellipse/line/polygon/polyline)
are converted to paths, and <text> becomes a native textbox with live text.

Targets the user's currently open slide via the PowerPoint COM interface.
Existing shapes on the slide are never modified.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# ---------------------------------------------------------------- constants
# Office MSO enum values
MSO_FALSE = 0
MSO_TRUE = -1
MSO_SEGMENT_LINE = 0
MSO_SEGMENT_CURVE = 1
MSO_EDITING_AUTO = 0
MSO_EDITING_CORNER = 1
MSO_TEXT_ORIENT_HORIZONTAL = 1
PP_AUTOSIZE_SHAPE_TO_FIT_TEXT = 1
PP_ALIGN_LEFT = 1
PP_ALIGN_CENTER = 2
PP_ALIGN_RIGHT = 3
PP_ANCHOR_TOP = 1
PP_ANCHOR_MIDDLE = 3
PP_ANCHOR_BOTTOM = 4


# ---------------------------------------------------------------- geometry
@dataclass
class Matrix:
    a: float = 1.0; b: float = 0.0; c: float = 0.0
    d: float = 1.0; e: float = 0.0; f: float = 0.0

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e,
                self.b * x + self.d * y + self.f)

    def multiply(self, o: "Matrix") -> "Matrix":
        return Matrix(
            self.a * o.a + self.c * o.b,
            self.b * o.a + self.d * o.b,
            self.a * o.c + self.c * o.d,
            self.b * o.c + self.d * o.d,
            self.a * o.e + self.c * o.f + self.e,
            self.b * o.e + self.d * o.f + self.f,
        )


def parse_transform(text: str | None) -> Matrix:
    m = Matrix()
    if not text:
        return m
    for cmd in re.finditer(r"([a-zA-Z]+)\s*\(([^)]*)\)", text):
        name = cmd.group(1)
        vals = [float(v) for v in re.split(r"[\s,]+", cmd.group(2).strip()) or []]
        if name == "matrix" and len(vals) == 6:
            t = Matrix(*vals)
        elif name == "translate":
            t = Matrix(e=vals[0], f=vals[1] if len(vals) > 1 else 0.0)
        elif name == "scale":
            t = Matrix(a=vals[0], d=vals[1] if len(vals) > 1 else vals[0])
        elif name == "rotate":
            ang = math.radians(vals[0])
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            r = Matrix(cos_a, sin_a, -sin_a, cos_a, 0, 0)
            if len(vals) >= 3:
                pre = Matrix(e=vals[1], f=vals[2])
                post = Matrix(e=-vals[1], f=-vals[2])
                t = pre.multiply(r).multiply(post)
            else:
                t = r
        elif name in ("skewX", "skewY"):
            t = math.tan(math.radians(vals[0]))
            if name == "skewX":
                t = Matrix(c=t)
            else:
                t = Matrix(b=t)
        else:
            continue
        m = m.multiply(t)
    return m


# A subpath is a list of segments; each segment is a tuple:
#   ("M", x, y)
#   ("L", x, y)
#   ("C", c1x, c1y, c2x, c2y, x, y)
#   ("Q", cx, cy, x, y)
#   ("Z",)
@dataclass
class PathData:
    subpaths: list[list[tuple]] = field(default_factory=list)


def _arc_to_cubics(x0, y0, rx, ry, phi_deg, large_arc, sweep, x, y):
    """Endpoint-to-center parameterization, then cubic Bezier segments."""
    phi = math.radians(phi_deg)
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [("L", x, y)]
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x) / 2, (y0 - y) / 2
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = s * rx, s * ry
    sign = -1 if large_arc != sweep else 1
    num = max(0.0, rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2)
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    coef = sign * math.sqrt(num / den) if den else 0
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x0 + x) / 2
    cy = sin_p * cxp + cos_p * cyp + (y0 + y) / 2

    def angle(ux, uy, vx, vy):
        a = math.atan2(uy, ux) - math.atan2(vy, vx)
        if a < 0:
            a += 2 * math.pi
        return a

    a1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
    da = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
               (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep:
        da -= 2 * math.pi
    segments = max(1, int(math.ceil(abs(da) / (math.pi / 2))))
    out = []
    for i in range(segments):
        a_start = a1 + da * i / segments
        a_end = a1 + da * (i + 1) / segments
        k = 4.0 / 3.0 * math.tan((a_end - a_start) / 4)
        p1 = (cx + rx * math.cos(a_start) - k * rx * math.sin(a_start),
              cy + ry * math.sin(a_start) + k * ry * math.cos(a_start))
        p2 = (cx + rx * math.cos(a_end) + k * rx * math.sin(a_end),
              cy + ry * math.sin(a_end) - k * ry * math.cos(a_end))
        pe = (cx + rx * math.cos(a_end), cy + ry * math.sin(a_end))
        p1r = (cos_p * p1[0] - sin_p * p1[1], sin_p * p1[0] + cos_p * p1[1])
        p2r = (cos_p * p2[0] - sin_p * p2[1], sin_p * p2[0] + cos_p * p2[1])
        per = (cos_p * pe[0] - sin_p * pe[1], sin_p * pe[0] + cos_p * pe[1])
        out.append(("C", p1r[0], p1r[1], p2r[0], p2r[1], per[0], per[1]))
    return out


def parse_path_d(d: str) -> PathData:
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\.?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", d)
    pd = PathData()
    cur = None          # current point
    start = None        # subpath start
    last_cmd = ""
    i = 0

    def num():
        nonlocal i
        v = float(tokens[i]); i += 1; return v

    def is_cmd(tok):
        return re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz]", tok)

    while i < len(tokens):
        tok = tokens[i]
        if is_cmd(tok):
            cmd = tok; i += 1
        else:
            cmd = last_cmd
        rel = cmd.islower()
        C = cmd.upper()

        def pt(absx, absy):
            if rel:
                return cur[0] + absx, cur[1] + absy
            return absx, absy

        if C == "M":
            x, y = num(), num()
            x, y = (cur[0] + x, cur[1] + y) if rel else (x, y)
            cur = start = (x, y)
            pd.subpaths.append([("M", x, y)])
            # implicit L for subsequent coordinate pairs
            while i < len(tokens) and not is_cmd(tokens[i]):
                x, y = num(), num()
                x, y = (cur[0] + x, cur[1] + y) if rel else (x, y)
                pd.subpaths[-1].append(("L", x, y)); cur = (x, y)
        elif C in ("L", "T"):
            while i < len(tokens) and not is_cmd(tokens[i]):
                if C == "L":
                    x, y = num(), num()
                    x, y = (cur[0] + x, cur[1] + y) if rel else (x, y)
                else:
                    x, y = num(), num()
                    x, y = (cur[0] + x, cur[1] + y) if rel else (x, y)
                pd.subpaths[-1].append(("L", x, y)); cur = (x, y)
        elif C == "H":
            while i < len(tokens) and not is_cmd(tokens[i]):
                x = num(); x = cur[0] + x if rel else x
                pd.subpaths[-1].append(("L", x, cur[1])); cur = (x, cur[1])
        elif C == "V":
            while i < len(tokens) and not is_cmd(tokens[i]):
                y = num(); y = cur[1] + y if rel else y
                pd.subpaths[-1].append(("L", cur[0], y)); cur = (cur[0], y)
        elif C in ("C", "S", "Q"):
            while i < len(tokens) and not is_cmd(tokens[i]):
                if C == "C":
                    c1 = pt(num(), num()); c2 = pt(num(), num()); e = pt(num(), num())
                elif C == "S":
                    if last_cmd.upper() in ("C", "S"):
                        prev = pd.subpaths[-1][-1]
                        c1 = (2 * cur[0] - prev[3], 2 * cur[1] - prev[4])
                    else:
                        c1 = cur
                    c2 = pt(num(), num()); e = pt(num(), num())
                    pd.subpaths[-1].append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
                    cur = e
                    continue
                else:
                    qc = pt(num(), num()); e = pt(num(), num())
                    c1 = (cur[0] + 2 / 3 * (qc[0] - cur[0]), cur[1] + 2 / 3 * (qc[1] - cur[1]))
                    c2 = (e[0] + 2 / 3 * (qc[0] - e[0]), e[1] + 2 / 3 * (qc[1] - e[1]))
                    pd.subpaths[-1].append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
                    cur = e
                    continue
                pd.subpaths[-1].append(("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]))
                cur = e
        elif C == "A":
            while i < len(tokens) and not is_cmd(tokens[i]):
                rx, ry = num(), num(); phi = num()
                large = num(); sweep = num(); x, y = num(), num()
                x, y = (cur[0] + x, cur[1] + y) if rel else (x, y)
                for seg in _arc_to_cubics(cur[0], cur[1], rx, ry, phi, large, sweep, x, y):
                    pd.subpaths[-1].append(seg)
                cur = (x, y)
        elif C == "Z":
            pd.subpaths[-1].append(("Z",))
            cur = start
        last_cmd = cmd
    return pd


# ---------------------------------------------------------------- styling
NAMED_COLORS = {
    "white": "#ffffff", "black": "#000000", "red": "#ff0000",
    "none": "none", "transparent": "none",
}


def parse_color(value: str | None):
    if value is None:
        return None
    value = value.strip().lower()
    if value in NAMED_COLORS:
        value = NAMED_COLORS[value]
    if value == "none":
        return "none"
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 8:
            r, g, b, a = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
            return (r, g, b, a / 255)
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgb\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\)", value)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 1.0)
    m = re.fullmatch(r"rgba\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)[,\s]+([\d.]+)\s*\)", value)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4)))
    return None


@dataclass
class Style:
    fill: object = (0, 0, 0, 1.0)
    stroke: object = "none"
    stroke_width: float = 1.0
    opacity: float = 1.0
    fill_opacity: float = 1.0
    stroke_opacity: float = 1.0
    font_family: str = "Arial"
    font_size: float = 18.0
    font_weight: str = "normal"
    font_style: str = "normal"
    text_anchor: str = "start"

    def inherited(self, elem: ET.Element) -> "Style":
        s = Style(
            fill=self.fill, stroke=self.stroke,
            stroke_width=self.stroke_width, opacity=self.opacity,
            fill_opacity=self.fill_opacity, stroke_opacity=self.stroke_opacity,
            font_family=self.font_family, font_size=self.font_size,
            font_weight=self.font_weight, font_style=self.font_style,
            text_anchor=self.text_anchor,
        )
        a = elem.attrib

        def attr(name):
            return a.get(name)

        presentation = {
            "fill": "fill", "stroke": "stroke", "stroke-width": "stroke_width",
            "opacity": "opacity", "fill-opacity": "fill_opacity",
            "stroke-opacity": "stroke_opacity", "font-family": "font_family",
            "font-size": "font_size", "font-weight": "font_weight",
            "font-style": "font_style", "text-anchor": "text_anchor",
        }
        for svg_name, py_name in presentation.items():
            v = attr(svg_name)
            if v is None:
                continue
            if py_name in ("fill", "stroke"):
                c = parse_color(v)
                if c is not None:
                    setattr(s, py_name, c)
            elif py_name in ("stroke_width", "opacity", "fill_opacity",
                             "stroke_opacity", "font_size"):
                try:
                    setattr(s, py_name, float(re.sub(r"[a-z%]+$", "", v)))
                except ValueError:
                    pass
            else:
                setattr(s, py_name, v.strip().strip("'\""))
        return s


# ---------------------------------------------------------------- IR
@dataclass
class Shape:
    kind: str                       # "path" | "text"
    path: PathData | None = None
    style: Style | None = None
    text: str = ""
    x: float = 0.0; y: float = 0.0
    name: str = ""


def primitives_to_path(tag: str, a: dict) -> PathData:
    def P(*segments):
        pd = PathData(); pd.subpaths.append(list(segments)); return pd

    if tag == "rect":
        x, y = float(a.get("x", 0)), float(a.get("y", 0))
        w, h = float(a.get("width", 0)), float(a.get("height", 0))
        rx = a.get("rx"); ry = a.get("ry")
        rx = float(rx) if rx is not None else 0.0
        ry = float(ry) if ry is not None else rx
        if rx == 0 and ry == 0:
            return P(("M", x, y), ("L", x + w, y), ("L", x + w, y + h),
                     ("L", x, y + h), ("Z",))
        r = min(rx, w / 2), min(ry, h / 2)
        k = 0.5523
        return P(
            ("M", x + r[0], y),
            ("L", x + w - r[0], y),
            ("C", x + w - r[0] + k * r[0], y, x + w, y + k * r[1], x + w, y + r[1]),
            ("L", x + w, y + h - r[1]),
            ("C", x + w, y + h - r[1] + k * r[1], x + w - r[0] + k * r[0], y + h, x + w - r[0], y + h),
            ("L", x + r[0], y + h),
            ("C", x + r[0] - k * r[0], y + h, x, y + h - r[1] + k * r[1], x, y + h - r[1]),
            ("L", x, y + r[1]),
            ("C", x, y + k * r[1], x + r[0] - k * r[0], y, x + r[0], y),
            ("Z",))
    if tag == "circle":
        cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
        k = 0.5523 * r
        return P(("M", cx - r, cy),
                 ("C", cx - r, cy - k, cx - k, cy - r, cx, cy - r),
                 ("C", cx + k, cy - r, cx + r, cy - k, cx + r, cy),
                 ("C", cx + r, cy + k, cx + k, cy + r, cx, cy + r),
                 ("C", cx - k, cy + r, cx - r, cy + k, cx - r, cy), ("Z",))
    if tag == "ellipse":
        cx, cy, rx, ry = float(a["cx"]), float(a["cy"]), float(a["rx"]), float(a["ry"])
        kx, ky = 0.5523 * rx, 0.5523 * ry
        return P(("M", cx - rx, cy),
                 ("C", cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry),
                 ("C", cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy),
                 ("C", cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry),
                 ("C", cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy), ("Z",))
    if tag == "line":
        x1, y1 = float(a["x1"]), float(a["y1"])
        x2, y2 = float(a["x2"]), float(a["y2"])
        return P(("M", x1, y1), ("L", x2, y2))
    if tag in ("polygon", "polyline"):
        pts = re.findall(r"-?\d*\.?\d+(?:[eE][+-]?\d+)?", a["points"])
        pts = [float(v) for v in pts]
        segs = [("M", pts[0], pts[1])]
        for j in range(2, len(pts), 2):
            segs.append(("L", pts[j], pts[j + 1]))
        if tag == "polygon":
            segs.append(("Z",))
        return P(*segs)
    return PathData()


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def collect_shapes(root: ET.Element, view_w: float, view_h: float) -> list[Shape]:
    shapes: list[Shape] = []
    counter = [0]

    def walk(elem: ET.Element, m: Matrix, style: Style):
        tag = localname(elem.tag)
        m = m.multiply(parse_transform(elem.attrib.get("transform")))
        st = style.inherited(elem)
        a = elem.attrib

        if tag in ("path", "rect", "circle", "ellipse", "line",
                   "polygon", "polyline"):
            counter[0] += 1
            pd = (parse_path_d(a["d"]) if tag == "path"
                  else primitives_to_path(tag, a))
            transformed = PathData()
            for sp in pd.subpaths:
                nsp = []
                for seg in sp:
                    if seg[0] in ("M", "L"):
                        x, y = m.apply(seg[1], seg[2])
                        nsp.append((seg[0], x, y))
                    elif seg[0] == "C":
                        p1 = m.apply(seg[1], seg[2]); p2 = m.apply(seg[3], seg[4])
                        p3 = m.apply(seg[5], seg[6])
                        nsp.append(("C", *p1, *p2, *p3))
                    else:
                        nsp.append(seg)
                transformed.subpaths.append(nsp)
            shapes.append(Shape(kind="path", path=transformed, style=st,
                                name=f"svg-path-{counter[0]}"))
        elif tag == "text":
            counter[0] += 1
            lines = []
            x = float(a.get("x", 0)); y = float(a.get("y", 0))
            tspans = [c for c in elem if localname(c.tag) == "tspan"]
            if tspans:
                for ts in tspans:
                    txt = "".join(ts.itertext())
                    lines.append(txt)
            else:
                lines = ["".join(elem.itertext())]
            tx, ty = m.apply(x, y)
            shapes.append(Shape(kind="text", style=st, text="\n".join(lines),
                                x=tx, y=ty, name=f"svg-text-{counter[0]}"))
        for child in elem:
            walk(child, m, st)

    walk(root, Matrix(), Style())
    return shapes


# ---------------------------------------------------------------- PPT render
def bgr_int(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return r + g * 256 + b * 65536


def render(svg_path: Path, placement: str, max_w_frac: float,
           max_h_frac: float, dry_run: bool, group_name: str):
    import win32com.client  # noqa
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = root.attrib.get("viewBox")
    if vb:
        parts = [float(v) for v in re.split(r"[\s,]+", vb.strip())]
        vx, vy, vw, vh = parts
    else:
        vx, vy = 0.0, 0.0
        vw = float(re.sub(r"px", "", root.attrib.get("width", "1000")))
        vh = float(re.sub(r"px", "", root.attrib.get("height", "1000")))

    shapes = collect_shapes(root, vw, vh)

    # geometry bounds
    xs, ys = [], []
    for sh in shapes:
        if sh.kind == "path":
            for sp in sh.path.subpaths:
                for seg in sp:
                    for k in range(1, len(seg) - 1, 2):
                        xs.append(seg[k]); ys.append(seg[k + 1])
        else:
            xs.append(sh.x); ys.append(sh.y)
    if not xs:
        raise RuntimeError("SVG has no renderable geometry")
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    gw, gh = max(maxx - minx, 1), max(maxy - miny, 1)

    if dry_run:
        print(json.dumps({"ok": True, "dry_run": True,
                          "shape_count": len(shapes),
                          "bounds": [minx, miny, gw, gh]}, indent=2))
        return

    try:
        app = win32com.client.GetActiveObject("PowerPoint.Application")
    except Exception:
        app = win32com.client.Dispatch("PowerPoint.Application")
    try:
        slide = app.ActiveWindow.View.Slide
    except Exception:
        raise RuntimeError("No active slide: open a presentation and select a slide first.")
    pres = app.ActivePresentation
    slide_w = pres.PageSetup.SlideWidth
    slide_h = pres.PageSetup.SlideHeight

    scale = min(slide_w * max_w_frac / gw, slide_h * max_h_frac / gh)

    def mapx(x):
        px = (x - minx) * scale
        if placement in ("center", "top-center", "bottom-center"):
            px += (slide_w - gw * scale) / 2
        elif placement in ("top-right", "bottom-right"):
            px += slide_w - gw * scale - slide_w * 0.05
        else:
            px += slide_w * 0.05
        return px

    def mapy(y):
        py = (y - miny) * scale
        if placement in ("center", "left-center", "center"):
            py += (slide_h - gh * scale) / 2
        elif placement in ("bottom-left", "bottom-right", "bottom-center"):
            py += slide_h - gh * scale - slide_h * 0.05
        else:
            py += slide_h * 0.05
        return py

    created_names = []

    def build_freeform(geom):
        """Build and convert one freeform from M/L/C segments.

        Cubic Beziers must use msoEditingCorner: with msoEditingAuto PowerPoint
        treats X1,Y1 as the segment endpoint and computes handles itself, so
        passing two explicit handles corrupts the curve. Corner nodes accept
        the full (handle1, handle2, endpoint) triple and map SVG C 1:1.
        """
        ff = None
        for seg in geom:
            if seg[0] == "M":
                ff = slide.Shapes.BuildFreeform(
                    MSO_EDITING_CORNER, mapx(seg[1]), mapy(seg[2]))
            elif seg[0] == "L":
                ff.AddNodes(MSO_SEGMENT_LINE, MSO_EDITING_AUTO,
                            mapx(seg[1]), mapy(seg[2]))
            elif seg[0] == "C":
                ff.AddNodes(MSO_SEGMENT_CURVE, MSO_EDITING_CORNER,
                            mapx(seg[1]), mapy(seg[2]),
                            mapx(seg[3]), mapy(seg[4]),
                            mapx(seg[5]), mapy(seg[6]))
        return ff.ConvertToShape() if ff is not None else None

    for sh in shapes:
        st = sh.style
        if sh.kind == "path":
            for sp in sh.path.subpaths:
                closed = any(seg[0] == "Z" for seg in sp)
                geom = [seg for seg in sp if seg[0] != "Z"]
                if not geom:
                    continue
                has_fill = isinstance(st.fill, tuple)
                has_stroke = isinstance(st.stroke, tuple)
                if closed:
                    shape = build_freeform(geom)
                    shape.Name = f"{sh.name}-{len(created_names)+1}"
                    _apply_path_style(shape, st, scale)
                    created_names.append(shape.Name)
                else:
                    # Open subpath: PowerPoint forbids fills on open freeforms.
                    # 1) closed fill-only twin (line back to the start point)
                    if has_fill:
                        s0 = geom[0]
                        fill_shape = build_freeform(geom + [("L", s0[1], s0[2])])
                        fill_shape.Name = f"{sh.name}-fill-{len(created_names)+1}"
                        _apply_fill_only(fill_shape, st)
                        created_names.append(fill_shape.Name)
                    # 2) open stroke-only shape
                    stroke_shape = build_freeform(geom)
                    stroke_shape.Name = f"{sh.name}-line-{len(created_names)+1}"
                    if has_stroke:
                        _apply_stroke_only(stroke_shape, st, scale)
                    else:
                        stroke_shape.Fill.Visible = MSO_FALSE
                        stroke_shape.Line.Visible = MSO_FALSE
                    created_names.append(stroke_shape.Name)
        else:
            fs_pt = max(8.0, st.font_size * scale)
            line_count = max(1, sh.text.count("\n") + 1)
            # generous initial box so text never wraps or clips
            est_w = max(80.0, (len(sh.text) - line_count + 1) * fs_pt * 0.62 + 20)
            est_h = fs_pt * line_count * 1.35 + 10
            tb = slide.Shapes.AddTextbox(
                MSO_TEXT_ORIENT_HORIZONTAL,
                mapx(sh.x), mapy(sh.y) - fs_pt, est_w, est_h)
            tb.Name = sh.name
            tf = tb.TextFrame
            tf.WordWrap = MSO_FALSE
            tf.AutoSize = MSO_FALSE
            tr = tf.TextRange
            tr.Text = sh.text
            tr.Font.Name = st.font_family
            tr.Font.Size = fs_pt
            tr.Font.Bold = MSO_TRUE if st.font_weight in ("bold", "700", "800", "900") else MSO_FALSE
            tr.Font.Italic = MSO_TRUE if "italic" in st.font_style else MSO_FALSE
            if isinstance(st.fill, tuple):
                tr.Font.Color.RGB = bgr_int(st.fill)
            anchor = {"start": PP_ALIGN_LEFT, "middle": PP_ALIGN_CENTER,
                      "end": PP_ALIGN_RIGHT}.get(st.text_anchor, PP_ALIGN_LEFT)
            tr.ParagraphFormat.Alignment = anchor
            # reposition using the real (fixed) box size so the SVG anchor holds
            final_w, final_h = tb.Width, tb.Height
            if anchor == PP_ALIGN_CENTER:
                tb.Left = mapx(sh.x) - final_w / 2
            elif anchor == PP_ALIGN_RIGHT:
                tb.Left = mapx(sh.x) - final_w
            else:
                tb.Left = mapx(sh.x)
            tb.Top = mapy(sh.y) - final_h * 0.72
            created_names.append(tb.Name)

    group = None
    if len(created_names) > 1:
        rng = slide.Shapes.Range(created_names)
        group = rng.Group()
        group.Name = group_name
    elif created_names:
        slide.Shapes(created_names[0]).Name = group_name

    print(json.dumps({"ok": True, "shapes": len(created_names),
                      "group": group_name}, ensure_ascii=False))


def _apply_path_style(shape, st: Style, scale: float):
    # fill
    fill = st.fill
    if fill == "none":
        shape.Fill.Visible = MSO_FALSE
    elif isinstance(fill, tuple):
        shape.Fill.Visible = MSO_TRUE
        shape.Fill.ForeColor.RGB = bgr_int(fill)
        shape.Fill.Transparency = 1 - min(1.0, st.opacity * st.fill_opacity * fill[3])
    # stroke
    stroke = st.stroke
    if stroke == "none":
        shape.Line.Visible = MSO_FALSE
    elif isinstance(stroke, tuple):
        shape.Line.Visible = MSO_TRUE
        shape.Line.ForeColor.RGB = bgr_int(stroke)
        shape.Line.Weight = max(0.25, st.stroke_width * scale)
        shape.Line.Transparency = 1 - min(1.0, st.opacity * st.stroke_opacity * stroke[3])


def _apply_fill_only(shape, st: Style):
    shape.Line.Visible = MSO_FALSE
    fill = st.fill
    if isinstance(fill, tuple):
        shape.Fill.Visible = MSO_TRUE
        shape.Fill.ForeColor.RGB = bgr_int(fill)
        shape.Fill.Transparency = 1 - min(1.0, st.opacity * st.fill_opacity * fill[3])
    else:
        shape.Fill.Visible = MSO_FALSE


def _apply_stroke_only(shape, st: Style, scale: float):
    shape.Fill.Visible = MSO_FALSE
    stroke = st.stroke
    if isinstance(stroke, tuple):
        shape.Line.Visible = MSO_TRUE
        shape.Line.ForeColor.RGB = bgr_int(stroke)
        shape.Line.Weight = max(0.25, st.stroke_width * scale)
        shape.Line.Transparency = 1 - min(1.0, st.opacity * st.stroke_opacity * stroke[3])
    else:
        shape.Line.Visible = MSO_FALSE


def main() -> int:
    ap = argparse.ArgumentParser(description="Render SVG to native PPT shapes")
    ap.add_argument("--input", "-i", required=True, type=Path)
    ap.add_argument("--placement", default="center")
    ap.add_argument("--max-width-fraction", type=float, default=0.85)
    ap.add_argument("--max-height-fraction", type=float, default=0.85)
    ap.add_argument("--group-name", default="SVG Vector Figure")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        render(args.input, args.placement, args.max_width_fraction,
               args.max_height_fraction, args.dry_run, args.group_name)
    except Exception as exc:
        print(f"PPT_RENDER_ERROR|{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
