#!/usr/bin/env python3
"""Generate ISO 12233:2000-style resolution charts as print-ready DXF files.

Source geometry is the public vector recreation published by Stephen H. Westin
(Cornell). This is not an ISO-certified printed target; line geometry follows
the published 2000 chart features (hyperbolic wedges, slanted-edge SFR bars,
framing arrows). 4x output uses an 800 mm active picture height (4 × 200 mm).

The official 2000 visual chart is 16:9. Native 4:3 files keep every
feature’s shape (no anamorphic squeeze). The four corner crosses are
translated so their centres sit at 0.7 of the 4:3 half-diagonal, the
same field point they occupy on the 16:9 plate. The centre zone plate
stays put.

Regions can be isolated by DXF layer or by exporting a cropped file:
    FRAME, CENTER, PERIPHERY, SFR, LABELS
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence
from xml.etree import ElementTree as ET

import ezdxf
try:
    from ezdxf.enums import TextEntityAlignment
except ImportError:  # ezdxf < 1.1
    from ezdxf.lldxf.const import TextEntityAlignment  # type: ignore

ROOT = Path(__file__).resolve().parent
DEFAULT_SVG = ROOT / "data" / "iso12233_2000.svg"
DEFAULT_OUT = ROOT / "output"

# Illustrator 72 dpi user units. The published chart's white active area is
# exactly 16:9 with a 200 mm picture height (1X).
PT_PER_MM = 72.0 / 25.4
SVG_W = 1121.273
SVG_H = 697.5
BODY_H = 680.314
BORDER_PT = 56.693  # 20 mm
ACTIVE = (56.693, 56.693, 1064.579, 623.622)  # x0,y0,x1,y1 SVG
ACTIVE_W = ACTIVE[2] - ACTIVE[0]
ACTIVE_H = ACTIVE[3] - ACTIVE[1]
CENTER_X = (ACTIVE[0] + ACTIVE[2]) / 2.0
CENTER_Y = (ACTIVE[1] + ACTIVE[3]) / 2.0
# Official 4:3 crop ticks on the 16:9 chart (element D) — also the native
# 4:3 active rectangle (same picture height, width = 4/3 × height).
CROP_4X3_LEFT = 182.694
CROP_4X3_RIGHT = CENTER_X * 2.0 - CROP_4X3_LEFT
ACTIVE_4X3 = (CROP_4X3_LEFT, ACTIVE[1], CROP_4X3_RIGHT, ACTIVE[3])
ACTIVE_4X3_W = CROP_4X3_RIGHT - CROP_4X3_LEFT
HALF_DIAG_16X9 = math.hypot(ACTIVE_W, ACTIVE_H) / 2.0
HALF_DIAG_4X3 = math.hypot(ACTIVE_4X3_W, ACTIVE_H) / 2.0
# Peripheral visual-resolution crosses sit at this fraction of the
# half-diagonal (centre → corner). Measured ~0.73 on the 16:9 artwork.
FIELD_FRACTION = 0.7
QUAD_CORNERS_4X3 = {
    "LT": (CROP_4X3_LEFT, ACTIVE[1]),
    "RT": (CROP_4X3_RIGHT, ACTIVE[1]),
    "LB": (CROP_4X3_LEFT, ACTIVE[3]),
    "RB": (CROP_4X3_RIGHT, ACTIVE[3]),
}

BASE_PH_MM = 200.0  # 1X active height


def _norm_id(value: str) -> str:
    return value.replace("_x0022_", '"').replace("_x002F_", "/")


GROUP_BASE_REGION: dict[str, str] = {
    "Black_border": "frame",
    "White_background": "frame",
    '"B"_White_and_Black_Arrows': "frame",
    "B1:_Additional_white_outer_arrows": "frame",
    "Text_at_top": "frame",
    "C:_Center_zone_plate": "center",
    "D:_Aspect_Ratio_Arrow_Tips": "frame",
    "T1/T2:__H-shaped_bars": "sfr",
    'R1/R2:_"Auto-registration_marks"': "frame",
    "L1-L4:filled_black_bars": "sfr",
    "G1/G2:_10_line_impulses": "center",
    "G2": "center",
    "G1": "center",
    "N:_Checkerboard_patterns": "periphery",
    "E:_Long_vert._and_ho._lines": "periphery",
    "M:_Circle_with_X_and_cross": "center",
    "J1/J2:_Low_frequency_5_black_line_Large_Center_Resolution_Wedge": "center",
    "JS1/JS2:_Low_Frequency_5_line_Small_Corner_Resolution_Wedge": "periphery",
    "KS1/KS2/KD_9_line_High_Resolution_Wedges": "mixed",
    '"F"_Small_Corner_Squares': "periphery",
    "O1/O2_Tilted_Square_Wave_Patches": "mixed",
    "P1/P2_Square_Wave_Sweep": "mixed",
    "credit": "frame",
}

SFR_GROUPS = {
    "T1/T2:__H-shaped_bars",
    "L1-L4:filled_black_bars",
}

FRAME_GROUPS = {gid for gid, region in GROUP_BASE_REGION.items() if region == "frame"}


# ---------------------------------------------------------------------------
# SVG path parsing
# ---------------------------------------------------------------------------

_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
_TOKEN_RE = re.compile(rf"([MmLlHhVvCcSsQqTtAaZz])|({_NUM})|,|[ \t\r\n]+")


def tokenize_path(d: str) -> list[str | float]:
    tokens: list[str | float] = []
    for match in _TOKEN_RE.finditer(d):
        cmd, num = match.group(1), match.group(2)
        if cmd:
            tokens.append(cmd)
        elif num:
            tokens.append(float(num))
    return tokens


def _flatten_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    *,
    tol: float = 0.15,
) -> list[tuple[float, float]]:
    """Adaptive cubic Bezier flattening in SVG user units."""

    out: list[tuple[float, float]] = []

    def rec(a, b, c, d, depth: int) -> None:
        chord_x, chord_y = d[0] - a[0], d[1] - a[1]
        chord_len = math.hypot(chord_x, chord_y) or 1.0
        d1 = abs((b[0] - a[0]) * chord_y - (b[1] - a[1]) * chord_x) / chord_len
        d2 = abs((c[0] - a[0]) * chord_y - (c[1] - a[1]) * chord_x) / chord_len
        if max(d1, d2) <= tol or depth >= 8:
            out.append(d)
            return
        # de Casteljau
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        cd = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
        abc = ((ab[0] + bc[0]) / 2, (ab[1] + bc[1]) / 2)
        bcd = ((bc[0] + cd[0]) / 2, (bc[1] + cd[1]) / 2)
        mid = ((abc[0] + bcd[0]) / 2, (abc[1] + bcd[1]) / 2)
        rec(a, ab, abc, mid, depth + 1)
        rec(mid, bcd, cd, d, depth + 1)

    rec(p0, p1, p2, p3, 0)
    return out


def parse_path(d: str) -> list[list[tuple[float, float]]]:
    """Return list of polylines (each a list of points). Closed subpaths repeat the start."""
    tokens = tokenize_path(d)
    i = 0
    polylines: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cx = cy = 0.0
    startx = starty = 0.0
    last_cmd = ""

    def take(n: int) -> list[float]:
        nonlocal i
        vals = [float(tokens[i + k]) for k in range(n)]
        i += n
        return vals

    def ensure() -> None:
        nonlocal current
        if not current:
            current = [(cx, cy)]

    while i < len(tokens):
        token = tokens[i]
        if isinstance(token, str):
            last_cmd = token
            i += 1
        else:
            if not last_cmd:
                raise ValueError(f"path starts with number: {d[:80]}")
            # implicit command: M/m → L/l after the first pair
            if last_cmd == "M":
                last_cmd = "L"
            elif last_cmd == "m":
                last_cmd = "l"
        cmd = last_cmd
        if cmd in "Mm":
            x, y = take(2)
            if cmd == "m":
                x += cx
                y += cy
            if current:
                polylines.append(current)
            cx, cy = x, y
            startx, starty = x, y
            current = [(cx, cy)]
        elif cmd in "Ll":
            x, y = take(2)
            if cmd == "l":
                x += cx
                y += cy
            ensure()
            cx, cy = x, y
            current.append((cx, cy))
        elif cmd in "Hh":
            x = take(1)[0]
            if cmd == "h":
                x += cx
            ensure()
            cx = x
            current.append((cx, cy))
        elif cmd in "Vv":
            y = take(1)[0]
            if cmd == "v":
                y += cy
            ensure()
            cy = y
            current.append((cx, cy))
        elif cmd in "Cc":
            vals = take(6)
            if cmd == "c":
                vals[0] += cx
                vals[1] += cy
                vals[2] += cx
                vals[3] += cy
                vals[4] += cx
                vals[5] += cy
            ensure()
            p0 = (cx, cy)
            p1 = (vals[0], vals[1])
            p2 = (vals[2], vals[3])
            p3 = (vals[4], vals[5])
            current.extend(_flatten_cubic(p0, p1, p2, p3))
            cx, cy = p3
        elif cmd in "Ss":
            vals = take(4)
            if cmd == "s":
                vals[0] += cx
                vals[1] += cy
                vals[2] += cx
                vals[3] += cy
            ensure()
            # reflect previous control point; fall back to current point
            p0 = (cx, cy)
            p1 = p0
            p2 = (vals[0], vals[1])
            p3 = (vals[2], vals[3])
            current.extend(_flatten_cubic(p0, p1, p2, p3))
            cx, cy = p3
        elif cmd in "Zz":
            if current:
                if current[0] != current[-1]:
                    current.append(current[0])
                polylines.append(current)
            current = []
            cx, cy = startx, starty
        else:
            raise ValueError(f"unsupported SVG path command {cmd!r}")
    if current:
        polylines.append(current)
    return polylines


def parse_fill(value: str | None) -> tuple[int, int, int] | None:
    if not value or value == "none":
        return None
    if value.startswith("#") and len(value) == 7:
        r = int(value[1:3], 16)
        g = int(value[3:5], 16)
        b = int(value[5:7], 16)
        return (r, g, b)
    return None


def parse_matrix(transform: str | None) -> tuple[float, float] | None:
    if not transform:
        return None
    match = re.search(
        r"matrix\(\s*([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)\s*\)",
        transform,
    )
    if not match:
        return None
    nums = [float(v) for v in match.groups()]
    return nums[4], nums[5]


def path_bbox(polylines: Sequence[Sequence[tuple[float, float]]]) -> tuple[float, float, float, float] | None:
    pts = [p for poly in polylines for p in poly]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def classify_mixed(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return "center"
    cx, cy = bbox_center(bbox)
    nx = abs(cx - CENTER_X) / (ACTIVE_W / 2.0)
    ny = abs(cy - CENTER_Y) / (ACTIVE_H / 2.0)
    return "center" if max(nx, ny) < 0.42 else "periphery"


def classify_sfr_location(shape: Shape) -> str:
    """L3/L4 live on the chart axes; L1 corners and T1/T2 H-bars are peripheral."""
    if shape.group.startswith("T1"):
        return "periphery"
    bbox = shape.bbox
    if bbox is None:
        return "center"
    cx, cy = bbox_center(bbox)
    nx = abs(cx - CENTER_X) / (ACTIVE_W / 2.0)
    ny = abs(cy - CENTER_Y) / (ACTIVE_H / 2.0)
    if nx < 0.22 or ny < 0.22:
        return "center"
    return "periphery"


# ---------------------------------------------------------------------------
# Polygon clipping (Sutherland–Hodgman)
# ---------------------------------------------------------------------------

def _inside(p: tuple[float, float], edge: str, rect: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = rect
    x, y = p
    if edge == "left":
        return x >= x0
    if edge == "right":
        return x <= x1
    if edge == "top":
        return y >= y0
    return y <= y1


def _intersect(
    s: tuple[float, float],
    e: tuple[float, float],
    edge: str,
    rect: tuple[float, float, float, float],
) -> tuple[float, float]:
    x0, y0, x1, y1 = rect
    x3, y3 = s
    x4, y4 = e
    dx, dy = x4 - x3, y4 - y3
    if edge == "left":
        t = 0 if dx == 0 else (x0 - x3) / dx
        return (x0, y3 + t * dy)
    if edge == "right":
        t = 0 if dx == 0 else (x1 - x3) / dx
        return (x1, y3 + t * dy)
    if edge == "top":
        t = 0 if dy == 0 else (y0 - y3) / dy
        return (x3 + t * dx, y0)
    t = 0 if dy == 0 else (y1 - y3) / dy
    return (x3 + t * dx, y1)


def clip_polyline(
    poly: Sequence[tuple[float, float]],
    rect: tuple[float, float, float, float],
    *,
    closed: bool,
) -> list[list[tuple[float, float]]]:
    if len(poly) < 2:
        return []
    x0, y0, x1, y1 = rect
    if closed:
        pts = list(poly)
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        for edge in ("left", "right", "top", "bottom"):
            if len(pts) < 3:
                return []
            out: list[tuple[float, float]] = []
            prev = pts[-1]
            for cur in pts:
                pin, cin = _inside(prev, edge, rect), _inside(cur, edge, rect)
                if cin:
                    if not pin:
                        out.append(_intersect(prev, cur, edge, rect))
                    out.append(cur)
                elif pin:
                    out.append(_intersect(prev, cur, edge, rect))
                prev = cur
            pts = out
        if len(pts) < 3:
            return []
        pts.append(pts[0])
        return [pts]

    # open stroke: emit inside segments
    segs: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    def flush() -> None:
        nonlocal current
        if len(current) >= 2:
            segs.append(current)
        current = []

    for a, b in zip(poly, poly[1:]):
        ax, ay = a
        bx, by = b
        t0, t1 = 0.0, 1.0
        dx, dy = bx - ax, by - ay
        for p, q in (
            (ax - x0, -dx),
            (x1 - ax, dx),
            (ay - y0, -dy),
            (y1 - ay, dy),
        ):
            if q == 0:
                if p < 0:
                    t0 = 1
                    t1 = 0
                    break
                continue
            r = p / q
            if q < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
        if t0 > t1:
            flush()
            continue
        p0 = (ax + dx * t0, ay + dy * t0)
        p1 = (ax + dx * t1, ay + dy * t1)
        if not current:
            current = [p0, p1]
        else:
            if math.hypot(current[-1][0] - p0[0], current[-1][1] - p0[1]) > 1e-6:
                flush()
                current = [p0, p1]
            else:
                current.append(p1)
    flush()
    return segs


# ---------------------------------------------------------------------------
# Scene model
# ---------------------------------------------------------------------------

@dataclass
class Shape:
    polylines: list[list[tuple[float, float]]]
    fill: tuple[int, int, int] | None
    stroke: tuple[int, int, int] | None
    stroke_width: float
    closed: bool
    group: str
    regions: set[str] = field(default_factory=set)
    kind: str = "path"  # path | text
    text: str = ""
    font_size: float = 12.0
    insert: tuple[float, float] = (0.0, 0.0)

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        if self.kind == "text":
            x, y = self.insert
            w = max(len(self.text) * self.font_size * 0.5, self.font_size)
            return x, y - self.font_size, x + w, y
        return path_bbox(self.polylines)


def load_svg(path: Path) -> list[Shape]:
    tree = ET.parse(path)
    root = tree.getroot()
    shapes: list[Shape] = []

    def walk(
        node: ET.Element,
        group: str,
        inh_fill: tuple[int, int, int] | None,
        inh_stroke: tuple[int, int, int] | None,
        inh_sw: float,
    ) -> None:
        tag = node.tag.split("}")[-1]
        fill_attr = node.get("fill")
        stroke_attr = node.get("stroke")
        sw_attr = node.get("stroke-width")
        fill = parse_fill(fill_attr) if fill_attr is not None else inh_fill
        stroke = parse_fill(stroke_attr) if stroke_attr is not None else inh_stroke
        sw = float(sw_attr) if sw_attr is not None else inh_sw
        if tag == "g":
            gid = node.get("id")
            next_group = _norm_id(gid) if gid else group
            for child in list(node):
                walk(child, next_group, fill, stroke, sw)
            return
        if tag == "path":
            d = node.get("d")
            if not d:
                return
            if fill_attr == "none" and stroke is None:
                return
            if fill is None and stroke is None:
                fill = (0, 0, 0)
            if fill == (39, 37, 37):
                fill = (0, 0, 0)
            polys = parse_path(d)
            if not polys:
                return
            closed = fill is not None
            shape = Shape(
                polylines=polys,
                fill=fill,
                stroke=stroke,
                stroke_width=sw,
                closed=closed,
                group=group,
            )
            assign_regions(shape)
            # skip degenerate white specks
            bb = shape.bbox
            if bb and (bb[2] - bb[0]) < 0.2 and (bb[3] - bb[1]) < 0.2:
                return
            shapes.append(shape)
            return
        if tag == "text":
            insert = parse_matrix(node.get("transform")) or (0.0, 0.0)
            parts: list[str] = []
            fill = parse_fill(node.get("fill"))
            size = float(node.get("font-size") or 12.0)
            if node.text and node.text.strip():
                parts.append(node.text.strip())
            for child in list(node):
                ctag = child.tag.split("}")[-1]
                if ctag == "tspan":
                    fill = parse_fill(child.get("fill")) or fill
                    size = float(child.get("font-size") or size)
                    if child.text:
                        parts.append(child.text)
            text = "".join(parts).strip()
            if text.startswith("This test chart is for use"):
                text = "ISO 12233:2000-style chart  |  public vector geometry"
            if not text:
                return
            shape = Shape(
                polylines=[],
                fill=fill or (39, 37, 37),
                stroke=None,
                stroke_width=0.0,
                closed=False,
                group=group,
                kind="text",
                text=text,
                font_size=size,
                insert=insert,
            )
            assign_regions(shape)
            shapes.append(shape)

    for child in list(root):
        walk(child, "", (0, 0, 0), None, 0.0)
    return shapes


def assign_regions(shape: Shape) -> None:
    base = GROUP_BASE_REGION.get(shape.group, "center")
    if base == "mixed":
        base = classify_mixed(shape.bbox)
    if base == "sfr":
        loc = classify_sfr_location(shape)
        shape.regions = {loc, "sfr"}
        return
    if base == "frame":
        shape.regions = {"frame"}
        if shape.kind == "text":
            shape.regions.add("labels")
        return
    shape.regions = {base}
    if shape.group in SFR_GROUPS:
        shape.regions.add("sfr")
    if shape.kind == "text":
        shape.regions.add("labels")


def svg_to_mm(x: float, y: float, scale: float) -> tuple[float, float]:
    mm = scale / PT_PER_MM
    return x * mm, (SVG_H - y) * mm


def poly_to_mm(poly: Sequence[tuple[float, float]], scale: float) -> list[tuple[float, float]]:
    return [svg_to_mm(x, y, scale) for x, y in poly]


def _quadrant(cx: float, cy: float) -> str:
    return ("L" if cx < CENTER_X else "R") + ("B" if cy > CENTER_Y else "T")


def _radius_frac(cx: float, cy: float) -> float:
    return math.hypot(cx - CENTER_X, cy - CENTER_Y) / HALF_DIAG_16X9


def is_corner_cross_shape(shape: Shape) -> bool:
    """Four peripheral plus-clusters (JS/KS wedges, F squares, L1 corners)."""
    bbox = shape.bbox
    if bbox is None:
        return False
    cx, cy = bbox_center(bbox)
    nx = abs(cx - CENTER_X) / (ACTIVE_W / 2.0)
    ny = abs(cy - CENTER_Y) / (ACTIVE_H / 2.0)
    if nx < 0.45 or _radius_frac(cx, cy) < 0.55:
        return False
    g = shape.group
    if g.startswith('"F"') or g.startswith("JS") or g.startswith("KS"):
        return True
    if g.startswith("L1") and ny > 0.35:
        return True
    return False


def is_side_hbar(shape: Shape) -> bool:
    return shape.group.startswith("T1")


def plus_center(cluster: Sequence[Shape]) -> tuple[float, float]:
    """Centre of a corner cross: intersection of KS horizontal and vertical arms."""
    hs: list[tuple[float, float]] = []
    vs: list[tuple[float, float]] = []
    for shape in cluster:
        if not shape.group.startswith("KS") or shape.kind != "path" or not shape.bbox:
            continue
        x0, y0, x1, y1 = shape.bbox
        w, h = x1 - x0, y1 - y0
        c = bbox_center(shape.bbox)
        if w > h * 1.5:
            hs.append(c)
        elif h > w * 1.5:
            vs.append(c)
    if vs and hs:
        return sum(p[0] for p in vs) / len(vs), sum(p[1] for p in hs) / len(hs)
    fs = [s for s in cluster if s.group.startswith('"F"') and s.bbox]
    if fs:
        pts = [bbox_center(s.bbox) for s in fs]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    raise ValueError("corner cluster has no measurable plus centre")


def field_point_4x3(quad: str) -> tuple[float, float]:
    x, y = QUAD_CORNERS_4X3[quad]
    return (
        CENTER_X + FIELD_FRACTION * (x - CENTER_X),
        CENTER_Y + FIELD_FRACTION * (y - CENTER_Y),
    )


def translate_shape(shape: Shape, dx: float, dy: float) -> Shape:
    polys = [[(x + dx, y + dy) for x, y in poly] for poly in shape.polylines]
    insert = (shape.insert[0] + dx, shape.insert[1] + dy)
    return replace(shape, polylines=polys, insert=insert)


def layout_native_4x3(shapes: Sequence[Shape]) -> list[Shape]:
    """4:3 layout: translate the four corner crosses, do not deform anything.

    Each plus centre moves to 0.7 of the 4:3 half-diagonal along that
    quadrant's corner. T1/T2 H-bars shift in X with the same side offset
    so they stay between the two crosses. Centre zone plate is unchanged.
    """
    crosses: dict[str, list[Shape]] = {q: [] for q in QUAD_CORNERS_4X3}
    hbars: list[Shape] = []
    rest: list[Shape] = []
    for shape in shapes:
        if is_corner_cross_shape(shape):
            cx, cy = bbox_center(shape.bbox)
            crosses[_quadrant(cx, cy)].append(shape)
        elif is_side_hbar(shape):
            hbars.append(shape)
        else:
            rest.append(shape)
    out = list(rest)
    dx_by_side: dict[str, float] = {}
    for quad, cluster in crosses.items():
        if not cluster:
            continue
        cx, cy = plus_center(cluster)
        tx, ty = field_point_4x3(quad)
        dx, dy = tx - cx, ty - cy
        dx_by_side[quad[0]] = dx
        for shape in cluster:
            out.append(translate_shape(shape, dx, dy))
    for shape in hbars:
        cx, _cy = bbox_center(shape.bbox)
        side = "L" if cx < CENTER_X else "R"
        out.append(translate_shape(shape, dx_by_side.get(side, 0.0), 0.0))
    return out


# ---------------------------------------------------------------------------
# DXF output
# ---------------------------------------------------------------------------

LAYER_DEFS = [
    ("FRAME", 7, "Border, framing arrows, registration"),
    ("CENTER", 7, "Central wedges, zone plate, pulse bars"),
    ("PERIPHERY", 7, "Corner wedges, checkerboards, edge patterns"),
    ("SFR", 7, "Slanted-edge SFR bars, H-bars, corner squares"),
    ("LABELS", 7, "Frequency and aspect-ratio labels"),
    ("NOTES", 7, "Print notes and picture-height callouts"),
]


def layer_for(shape: Shape, prefer: str | None = None) -> str:
    if prefer and prefer in shape.regions:
        if prefer == "sfr":
            return "SFR"
        return prefer.upper()
    if "sfr" in shape.regions and prefer is None:
        # In the combined drawing, SFR geometry stays on SFR even if it is
        # also classified as center/periphery, so it can be plotted alone.
        return "SFR"
    if "frame" in shape.regions:
        return "FRAME"
    if "center" in shape.regions:
        return "CENTER"
    if "periphery" in shape.regions:
        return "PERIPHERY"
    if "labels" in shape.regions:
        return "LABELS"
    return "FRAME"


def new_doc():
    doc = ezdxf.new("R2013", setup=True)
    doc.units = 4  # millimeters
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.header["$FILLMODE"] = 1
    doc.header["$LWDISPLAY"] = 1
    for name, color, desc in LAYER_DEFS:
        if name not in doc.layers:
            layer = doc.layers.add(name, color=color)
            layer.description = desc
    return doc


def _poly_area(pts: Sequence[tuple[float, float]]) -> float:
    area = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def _cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    c1, c2, c3 = _cross(a, b, p), _cross(b, c, p), _cross(c, a, p)
    return not ((c1 < 0 or c2 < 0 or c3 < 0) and (c1 > 0 or c2 > 0 or c3 > 0))


def triangulate(poly: Sequence[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    pts: list[tuple[float, float]] = []
    for p in poly:
        if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > 1e-9:
            pts.append((p[0], p[1]))
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return []
    if _poly_area(pts) < 0:
        pts.reverse()
    remaining = list(range(len(pts)))
    tris: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []
    guard = 0
    limit = max(len(pts) * 4, 16)
    while len(remaining) > 3 and guard < limit:
        guard += 1
        n = len(remaining)
        ear = None
        for i in range(n):
            a = pts[remaining[i - 1]]
            b = pts[remaining[i]]
            c = pts[remaining[(i + 1) % n]]
            if _cross(a, b, c) <= 1e-12:
                continue
            if any(
                _point_in_triangle(pts[remaining[j]], a, b, c)
                for j in range(n)
                if remaining[j] not in (remaining[i - 1], remaining[i], remaining[(i + 1) % n])
            ):
                continue
            ear = i
            tris.append((a, b, c))
            del remaining[i]
            break
        if ear is None:
            break
    if len(remaining) == 3:
        a, b, c = (pts[remaining[0]], pts[remaining[1]], pts[remaining[2]])
        if abs(_cross(a, b, c)) > 1e-12:
            tris.append((a, b, c))
    return tris


def is_white(rgb: tuple[int, int, int] | None) -> bool:
    return rgb is not None and rgb[0] > 200 and rgb[1] > 200 and rgb[2] > 200


def add_filled_polygon(msp, points: Sequence[tuple[float, float]], layer: str) -> None:
    """Filled black geometry that viewers can display without HATCH support.

    Many CAD / DXF previewers skip HATCH. A full-sheet black-then-white hatch
    also paints the chart away. SOLID triangles + closed polylines stay visible
    on dark and light backgrounds (ACI 7).
    """
    if len(points) < 3:
        return
    pts = list(points)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if max(xs) - min(xs) < 0.02 and max(ys) - min(ys) < 0.02:
        return
    attribs = {"layer": layer, "color": 250}
    msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
    for a, b, c in triangulate(pts):
        solid = msp.add_solid([a, b, c, c], dxfattribs=attribs)
        solid.rgb = (0, 0, 0)
    hatch = msp.add_hatch(dxfattribs=attribs)
    hatch.set_solid_fill()
    hatch.rgb = (0, 0, 0)
    hatch.paths.add_polyline_path([(p[0], p[1]) for p in pts], is_closed=True)


def add_stroke(msp, points: Sequence[tuple[float, float]], width: float, layer: str) -> None:
    if len(points) < 2:
        return
    msp.add_lwpolyline(
        points,
        dxfattribs={
            "layer": layer,
            "color": 250,
            "lineweight": 35,
            "const_width": max(width, 0.15),
        },
    )


def add_frame_strips(
    msp,
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    scale: float,
    layer: str = "FRAME",
) -> None:
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    strips = (
        (ox0, oy0, ox1, iy0),
        (ox0, iy1, ox1, oy1),
        (ox0, iy0, ix0, iy1),
        (ix1, iy0, ox1, iy1),
    )
    for a, b, c, d in strips:
        add_filled_polygon(
            msp,
            [
                svg_to_mm(a, b, scale),
                svg_to_mm(c, b, scale),
                svg_to_mm(c, d, scale),
                svg_to_mm(a, d, scale),
            ],
            layer,
        )


def draw_shape(
    msp,
    shape: Shape,
    scale: float,
    layer: str,
    clip: tuple[float, float, float, float] | None,
) -> None:
    if shape.group in {"Black_border", "White_background"}:
        return
    if shape.kind == "text":
        x, y = shape.insert
        if clip and not (clip[0] <= x <= clip[2] and clip[1] <= y <= clip[3]):
            return
        px, py = svg_to_mm(x, y, scale)
        height = max(shape.font_size * scale / PT_PER_MM, 1.6)
        msp.add_text(
            shape.text,
            height=height,
            dxfattribs={"layer": "LABELS" if layer != "NOTES" else layer, "color": 250},
        ).set_placement((px, py), align=TextEntityAlignment.LEFT)
        return

    for poly in shape.polylines:
        closed = shape.closed or (len(poly) >= 4 and poly[0] == poly[-1])
        pieces = clip_polyline(poly, clip, closed=closed) if clip else [list(poly)]
        for piece in pieces:
            pts = poly_to_mm(piece, scale)
            if is_white(shape.fill):
                continue
            if shape.fill is not None and closed:
                add_filled_polygon(msp, pts, layer)
            elif shape.stroke is not None:
                add_stroke(msp, pts, shape.stroke_width * scale / PT_PER_MM, layer)
            elif shape.fill is not None:
                add_filled_polygon(msp, pts, layer)


def content_clip_for_aspect(aspect: str) -> tuple[float, float, float, float] | None:
    """4:3 drawings clip to the 4:3 active rectangle after crosses are moved."""
    if aspect == "4:3":
        return ACTIVE_4X3
    return None


def rebuild_4x3_frame(msp, scale: float) -> None:
    """Native 4:3 frame around the official 4:3 active rectangle.

    Corner crosses are translated into this rectangle; they are not cropped
    at the 16:9 4:3 arrows and they are not anamorphically squeezed.
    """
    x0, y0, x1, y1 = CROP_4X3_LEFT, ACTIVE[1], CROP_4X3_RIGHT, ACTIVE[3]
    border = BORDER_PT
    ox0, oy0, ox1, oy1 = x0 - border, y0 - border, x1 + border, y1 + border
    add_frame_strips(msp, (ox0, oy0, ox1, oy1), (x0, y0, x1, y1), scale)

    arrow = 28.347
    mid_y = (y0 + y1) / 2.0
    for x_inner, direction in ((x0, 1), (x1, -1)):
        add_filled_polygon(
            msp,
            [
                svg_to_mm(x_inner + direction * 8.5, mid_y - arrow / 2, scale),
                svg_to_mm(x_inner + direction * 8.5, mid_y + arrow / 2, scale),
                svg_to_mm(x_inner + direction * (8.5 + arrow), mid_y, scale),
            ],
            "FRAME",
        )

    q1 = x0 + (x1 - x0) * 0.25
    q3 = x0 + (x1 - x0) * 0.75
    for x in (q1, q3):
        add_filled_polygon(
            msp,
            [
                svg_to_mm(x - 8.5, y0 + 28.3, scale),
                svg_to_mm(x + 8.5, y0 + 28.3, scale),
                svg_to_mm(x, y0, scale),
            ],
            "FRAME",
        )
        add_filled_polygon(
            msp,
            [
                svg_to_mm(x - 8.5, y1 - 28.3, scale),
                svg_to_mm(x + 8.5, y1 - 28.3, scale),
                svg_to_mm(x, y1, scale),
            ],
            "FRAME",
        )

    one_left = CENTER_X - ACTIVE_H / 2.0
    one_right = CENTER_X + ACTIVE_H / 2.0
    for x in (one_left, one_right):
        add_filled_polygon(
            msp,
            [
                svg_to_mm(x - 2.8, y0, scale),
                svg_to_mm(x + 2.8, y0, scale),
                svg_to_mm(x + 2.8, y0 + 34, scale),
                svg_to_mm(x - 2.8, y0 + 34, scale),
            ],
            "FRAME",
        )
        add_filled_polygon(
            msp,
            [
                svg_to_mm(x - 2.8, y1 - 34, scale),
                svg_to_mm(x + 2.8, y1 - 34, scale),
                svg_to_mm(x + 2.8, y1, scale),
                svg_to_mm(x - 2.8, y1, scale),
            ],
            "FRAME",
        )

    ph = BASE_PH_MM * scale
    pw = ph * 4.0 / 3.0
    height = 3.2 * scale
    for tx, ty, label in (
        (x0 + 4, y1 - 22, "4:3"),
        (x1 - 40, y1 - 22, "4:3"),
        (one_left + 6, y1 - 22, "1:1"),
        (one_right - 28, y1 - 22, "1:1"),
        (x0 + 4, y0 + 18, "4:3"),
        (x1 - 40, y0 + 18, "4:3"),
    ):
        px, py = svg_to_mm(tx, ty, scale)
        msp.add_text(label, height=max(height, 2.4), dxfattribs={"layer": "LABELS", "color": 250}).set_placement(
            (px, py), align=TextEntityAlignment.LEFT
        )

    title_x, title_y = svg_to_mm((x0 + x1) / 2.0, 12, scale)
    msp.add_text(
        f"ISO 12233 4:3  {scale:.0f}X   active {pw:.0f} x {ph:.0f} mm   values in 100x LW/PH",
        height=max(3.5 * scale, 2.8),
        dxfattribs={"layer": "NOTES", "color": 250},
    ).set_placement((title_x, title_y), align=TextEntityAlignment.MIDDLE_CENTER)


def add_title_16x9(msp, scale: float) -> None:
    ph = BASE_PH_MM * scale
    pw = ph * 16.0 / 9.0
    x, y = svg_to_mm(SVG_W / 2.0, 12, scale)
    msp.add_text(
        f"ISO 12233 16:9  {scale:.0f}X   active {pw:.0f} x {ph:.0f} mm   values in 100x LW/PH",
        height=max(3.5 * scale / 4.0 * 4, 2.8),
        dxfattribs={"layer": "NOTES", "color": 250},
    ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)


def iter_content(shapes: Sequence[Shape], aspect: str, region: str) -> Iterable[Shape]:
    for shape in shapes:
        if region == "full":
            if aspect == "4:3" and "frame" in shape.regions:
                # Native 4:3 drawing rebuilds the frame.
                continue
            yield shape
            continue
        if region == "sfr":
            if "sfr" in shape.regions:
                yield shape
            continue
        if region in shape.regions or (region == "center" and "sfr" in shape.regions and "center" in shape.regions):
            yield shape
        elif region == "periphery" and "sfr" in shape.regions and "periphery" in shape.regions:
            yield shape


def region_clip(shapes: Sequence[Shape], aspect: str, region: str) -> tuple[float, float, float, float] | None:
    if region == "full":
        return content_clip_for_aspect(aspect)
    boxes = []
    for shape in iter_content(shapes, aspect, region):
        if "frame" in shape.regions and region != "full":
            continue
        bb = shape.bbox
        if bb:
            boxes.append(bb)
    if not boxes:
        return content_clip_for_aspect(aspect)
    pad = ACTIVE_H * 0.04
    x0 = min(b[0] for b in boxes) - pad
    y0 = min(b[1] for b in boxes) - pad
    x1 = max(b[2] for b in boxes) + pad
    y1 = max(b[3] for b in boxes) + pad
    aspect_clip = content_clip_for_aspect(aspect)
    if aspect_clip:
        x0 = max(x0, aspect_clip[0])
        y0 = max(y0, aspect_clip[1])
        x1 = min(x1, aspect_clip[2])
        y1 = min(y1, aspect_clip[3])
    return x0, y0, x1, y1


def add_print_notes(
    msp,
    scale: float,
    aspect: str,
    region: str,
    clip: tuple[float, float, float, float] | None,
) -> None:
    ph = BASE_PH_MM * scale
    if clip:
        cx = (clip[0] + clip[2]) / 2.0
        cy = clip[1] - 18
        x, y = svg_to_mm(cx, min(max(cy, 8), SVG_H - 8), scale)
    else:
        x, y = svg_to_mm(SVG_W / 2.0, BODY_H + 10, scale)
    tile_h = ((clip[3] - clip[1]) / PT_PER_MM * scale) if clip else ph
    note = (
        f"Region: {region.upper()}   Aspect: {aspect}   {scale:.0f}X   "
        f"Full PH={ph:.0f} mm   Tile height={tile_h:.0f} mm   "
        f"If this tile fills the frame, multiply labeled LW/PH by {ph / tile_h:.2f}"
    )
    msp.add_text(note, height=max(2.4 * scale, 2.0), dxfattribs={"layer": "NOTES", "color": 250}).set_placement(
        (x, y), align=TextEntityAlignment.MIDDLE_CENTER
    )


def write_dxf(
    shapes: Sequence[Shape],
    dest: Path,
    *,
    aspect: str,
    region: str,
    scale: float,
) -> Path:
    doc = new_doc()
    msp = doc.modelspace()
    if aspect == "4:3":
        shapes = layout_native_4x3(shapes)
    clip = region_clip(shapes, aspect, region)

    if aspect == "16:9" and region == "full":
        add_frame_strips(
            msp,
            (0.0, 0.0, SVG_W, BODY_H),
            ACTIVE,
            scale,
        )
        add_title_16x9(msp, scale)
        for shape in shapes:
            draw_shape(msp, shape, scale, layer_for(shape), None)
    elif aspect == "4:3" and region == "full":
        rebuild_4x3_frame(msp, scale)
        for shape in shapes:
            if "frame" in shape.regions and not shape.group.startswith("R1"):
                continue
            draw_shape(msp, shape, scale, layer_for(shape), ACTIVE_4X3)
    else:
        if clip:
            x0, y0, x1, y1 = clip
            border = BORDER_PT * 0.35
            add_frame_strips(
                msp,
                (x0 - border, y0 - border, x1 + border, y1 + border),
                clip,
                scale,
            )
        prefer = region if region in {"center", "periphery", "sfr"} else None
        for shape in iter_content(shapes, aspect, region):
            if "frame" in shape.regions:
                continue
            draw_shape(msp, shape, scale, layer_for(shape, prefer), clip)
        add_print_notes(msp, scale, aspect, region, clip)

    from ezdxf import bbox as ezbbox

    ext = ezbbox.extents(msp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ext.has_data:
        _fit_active_vport(doc, ext.extmin, ext.extmax)
    doc.saveas(dest)
    if ext.has_data:
        _patch_dxf_extents(dest, ext.extmin, ext.extmax)
    return dest


def _fit_active_vport(doc, extmin, extmax) -> None:
    width = float(extmax[0] - extmin[0]) or 1.0
    height = float(extmax[1] - extmin[1]) or 1.0
    center = ((extmin[0] + extmax[0]) / 2.0, (extmin[1] + extmax[1]) / 2.0)
    try:
        vports = doc.viewports.get("*Active")
    except Exception:
        return
    for vport in vports:
        vport.dxf.center = center
        vport.dxf.height = height * 1.08
        try:
            vport.dxf.aspect_ratio = width / height
        except Exception:
            pass


def _patch_dxf_extents(path: Path, extmin, extmax) -> None:
    """ezdxf resets EXTMIN/EXTMAX/LIMMAX on save; many viewers zoom to A3 limits."""
    text = path.read_text(encoding="utf-8", errors="replace")

    def repl_xyz(varname: str, x: float, y: float, z: float = 0.0) -> None:
        nonlocal text
        pattern = rf"(  9\n\${varname}\n 10\n)[^\n]+(\n 20\n)[^\n]+(\n 30\n)[^\n]+"
        replacement = rf"\g<1>{x:.6f}\g<2>{y:.6f}\g<3>{z:.6f}"
        text, n = re.subn(pattern, replacement, text, count=1)
        if n != 1:
            pattern2 = rf"(  9\n\${varname}\n 10\n)[^\n]+(\n 20\n)[^\n]+"
            replacement2 = rf"\g<1>{x:.6f}\g<2>{y:.6f}"
            text, n = re.subn(pattern2, replacement2, text, count=1)

    repl_xyz("EXTMIN", float(extmin[0]), float(extmin[1]), float(extmin[2]) if len(extmin) > 2 else 0.0)
    repl_xyz("EXTMAX", float(extmax[0]), float(extmax[1]), float(extmax[2]) if len(extmax) > 2 else 0.0)
    repl_xyz("LIMMIN", float(extmin[0]), float(extmin[1]))
    repl_xyz("LIMMAX", float(extmax[0]), float(extmax[1]))
    path.write_text(text, encoding="utf-8")


def render_preview(dxf_path: Path, png_path: Path, *, dpi: int = 72) -> None:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    doc = ezdxf.readfile(dxf_path)
    fig = plt.figure(figsize=(12.8, 7.2), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
    ax.set_axis_off()
    fig.savefig(png_path, dpi=dpi, facecolor="white")
    plt.close(fig)


def aspect_slug(aspect: str) -> str:
    return aspect.replace(":", "x")


def generate_all(svg: Path, out_dir: Path, scale: float, previews: bool) -> list[Path]:
    shapes = load_svg(svg)
    if not shapes:
        raise SystemExit(f"no shapes parsed from {svg}")
    written: list[Path] = []
    for aspect in ("16:9", "4:3"):
        for region in ("full", "center", "periphery", "sfr"):
            name = f"iso12233_{aspect_slug(aspect)}_{scale:.0f}x_{region}.dxf"
            path = write_dxf(shapes, out_dir / name, aspect=aspect, region=region, scale=scale)
            written.append(path)
            print(f"wrote {path}  ({path.stat().st_size / 1024:.0f} KiB)")
    if previews:
        preview_dir = out_dir / "previews"
        preview_dir.mkdir(exist_ok=True)
        for path in written:
            png = preview_dir / (path.stem + ".png")
            try:
                render_preview(path, png, dpi=48)
                print(f"preview {png}")
            except Exception as exc:  # pragma: no cover - preview is optional
                print(f"preview failed for {path.name}: {exc}", file=sys.stderr)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--scale", type=float, default=4.0, help="Linear size vs 1X (200 mm PH). 4 = 800 mm PH.")
    parser.add_argument("--aspect", choices=("16:9", "4:3", "all"), default="all")
    parser.add_argument("--region", choices=("full", "center", "periphery", "sfr", "all"), default="all")
    parser.add_argument("--preview", action="store_true", help="Also rasterize PNG previews")
    args = parser.parse_args(argv)

    shapes = load_svg(args.svg)
    print(f"parsed {len(shapes)} shapes from {args.svg}")
    aspects = ("16:9", "4:3") if args.aspect == "all" else (args.aspect,)
    regions = ("full", "center", "periphery", "sfr") if args.region == "all" else (args.region,)
    written: list[Path] = []
    for aspect in aspects:
        for region in regions:
            name = f"iso12233_{aspect_slug(aspect)}_{args.scale:.0f}x_{region}.dxf"
            path = write_dxf(shapes, args.out / name, aspect=aspect, region=region, scale=args.scale)
            written.append(path)
            print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KiB)")
    if args.preview:
        preview_dir = args.out / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        for path in written:
            png = preview_dir / (path.stem + ".png")
            render_preview(path, png, dpi=48)
            print(f"preview {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
