#!/usr/bin/env python3
"""Generate EIAJ / ITE Test Chart A (EIA 1956) as a print-ready 4:3 DXF.

EIAJ Test Chart A is the Japanese 4:3 resolution chart (ITE Resolution Chart),
the same family as EIA 1956 / RETMA. Geometry is native 4:3: the large circle
must stay round, and wedge labels are TV lines (200–800), not ISO LW/PH.

1X ITE valid area is 240 × 180 mm. Default --scale 4 is 960 × 720 mm.

Source vector: public-domain recreation on Wikimedia Commons
(File:EIA_Resolution_Chart_1956.svg). Not an ITE-certified print.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Sequence
from xml.etree import ElementTree as ET

import ezdxf
try:
    from ezdxf.enums import TextEntityAlignment
except ImportError:
    from ezdxf.lldxf.const import TextEntityAlignment  # type: ignore

ROOT = Path(__file__).resolve().parent
DEFAULT_SVG = ROOT / "data" / "eiaj_1956.svg"
DEFAULT_OUT = ROOT / "output"
ISO = ROOT.parent / "iso12233"
sys.path.insert(0, str(ISO))
from generate import (  # noqa: E402
    _fit_active_vport,
    _patch_dxf_extents,
    parse_path,
    render_preview,
    triangulate,
)

# ITE 4:3 valid area at 1X (height × width in the ITE catalog: 180 × 240 mm).
ITE_PH_MM = 180.0
ITE_PW_MM = 240.0
# Inner black frame in the Wikimedia SVG (user units).
FRAME = (292.0, 382.0, 10689.0, 8230.0)
FRAME_H = FRAME[3] - FRAME[1]


def _parse_css(root: ET.Element) -> dict[str, tuple[int, int, int] | None]:
    colors: dict[str, tuple[int, int, int] | None] = {}
    for style in root.iter():
        if style.tag.split("}")[-1] != "style":
            continue
        text = "".join(style.itertext())
        for name, hexcol in re.findall(r"\.(fil\d+)\s*\{fill:#([0-9A-Fa-f]{6})\}", text):
            colors[name] = (int(hexcol[0:2], 16), int(hexcol[2:4], 16), int(hexcol[4:6], 16))
        for name in re.findall(r"\.(fil\d+)\s*\{fill:none\}", text):
            colors[name] = None
        sizes: dict[str, float] = {}
        for name, size in re.findall(r"\.(fnt\d+)\s*\{[^}]*font-size:([\d.]+)", text):
            sizes[name] = float(size)
        colors["_font_sizes"] = sizes  # type: ignore[assignment]
    return colors


def _parse_matrix(transform: str | None) -> tuple[float, float, float, float, float, float]:
    if not transform:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    match = re.search(
        r"matrix\(\s*([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)[,\s]+([^\s,]+)\s*\)",
        transform,
    )
    if not match:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    a, b, c, d, e, f = (float(v) for v in match.groups())
    return a, b, c, d, e, f


def _mul(
    m1: tuple[float, float, float, float, float, float],
    m2: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply(m: tuple[float, float, float, float, float, float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _class_fill(cls: str | None, css: dict) -> tuple[int, int, int] | None:
    if not cls:
        return (31, 26, 23)
    for token in cls.split():
        if token in css and not token.startswith("_"):
            return css[token]
    return (31, 26, 23)


def svg_to_mm(x: float, y: float, scale: float) -> tuple[float, float]:
    mm = (ITE_PH_MM * scale) / FRAME_H
    return (x - FRAME[0]) * mm, (FRAME[3] - y) * mm


def add_poly(msp, points: Sequence[tuple[float, float]], rgb: tuple[int, int, int], layer: str) -> None:
    if len(points) < 3:
        return
    pts = list(points)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    attribs = {"layer": layer, "color": 250 if rgb[0] < 40 else 7}
    msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
    for a, b, c in triangulate(pts):
        solid = msp.add_solid([a, b, c, c], dxfattribs=attribs)
        solid.rgb = rgb
    hatch = msp.add_hatch(dxfattribs=attribs)
    hatch.set_solid_fill()
    hatch.rgb = rgb
    hatch.paths.add_polyline_path([(p[0], p[1]) for p in pts], is_closed=True)


def write_dxf(svg: Path, dest: Path, scale: float) -> Path:
    tree = ET.parse(svg)
    root = tree.getroot()
    css = _parse_css(root)
    font_sizes = css.get("_font_sizes", {})  # type: ignore[assignment]
    if not isinstance(font_sizes, dict):
        font_sizes = {}

    doc = ezdxf.new("R2013", setup=True)
    doc.units = 4
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.header["$FILLMODE"] = 1
    for name in ("FRAME", "PATTERN", "GRAY", "LABELS", "NOTES"):
        if name not in doc.layers:
            doc.layers.add(name, color=7)
    msp = doc.modelspace()

    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def walk(node: ET.Element, matrix) -> None:
        tag = node.tag.split("}")[-1]
        if tag in {"defs", "style", "font", "glyph", "missing-glyph", "font-face"}:
            return
        matrix = _mul(matrix, _parse_matrix(node.get("transform")))
        cls = node.get("class")
        fill = _class_fill(cls, css)
        if tag == "path" and node.get("d") and fill is not None:
            layer = "GRAY" if 40 < fill[0] < 230 else "PATTERN"
            for poly in parse_path(node.get("d") or ""):
                pts = [svg_to_mm(*_apply(matrix, x, y), scale) for x, y in poly]
                add_poly(msp, pts, fill, layer)
        elif tag == "rect" and fill is not None:
            x = float(node.get("x", 0))
            y = float(node.get("y", 0))
            w = float(node.get("width", 0))
            h = float(node.get("height", 0))
            poly = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            pts = [svg_to_mm(*_apply(matrix, px, py), scale) for px, py in poly]
            layer = "GRAY" if 40 < fill[0] < 230 else "PATTERN"
            add_poly(msp, pts, fill, layer)
        elif tag == "text" and node.text:
            x = float(node.get("x", 0))
            y = float(node.get("y", 0))
            px, py = svg_to_mm(*_apply(matrix, x, y), scale)
            size = 12.0
            if cls:
                for token in cls.split():
                    if token in font_sizes:
                        size = float(font_sizes[token])
            height = max(size * (ITE_PH_MM * scale) / FRAME_H * 0.85, 2.0)
            rgb = fill or (31, 26, 23)
            text = msp.add_text(
                node.text.strip(),
                height=height,
                dxfattribs={"layer": "LABELS", "color": 250 if rgb[0] < 40 else 7},
            )
            text.set_placement((px, py), align=TextEntityAlignment.MIDDLE_CENTER)
            try:
                text.rgb = rgb
            except Exception:
                pass
        for child in list(node):
            walk(child, matrix)

    walk(root, identity)

    ph = ITE_PH_MM * scale
    pw = ITE_PW_MM * scale
    title_x, title_y = svg_to_mm((FRAME[0] + FRAME[2]) / 2.0, FRAME[1] - 80, scale)
    msp.add_text(
        f"EIAJ / ITE Test Chart A   {scale:.0f}X   active {pw:.0f} x {ph:.0f} mm   TVL 200-800",
        height=max(3.2 * scale, 2.4),
        dxfattribs={"layer": "NOTES", "color": 250},
    ).set_placement((title_x, title_y), align=TextEntityAlignment.MIDDLE_CENTER)

    from ezdxf import bbox as ezbbox

    ext = ezbbox.extents(msp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ext.has_data:
        _fit_active_vport(doc, ext.extmin, ext.extmax)
    doc.saveas(dest)
    if ext.has_data:
        _patch_dxf_extents(dest, ext.extmin, ext.extmax)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--scale", type=float, default=4.0, help="Linear size vs ITE 1X (180 mm PH). 4 = 720 mm PH.")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    dest = args.out / f"eiaj_4x3_{args.scale:.0f}x_full.dxf"
    path = write_dxf(args.svg, dest, args.scale)
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KiB)")
    if args.preview:
        png = args.out / "previews" / (path.stem + ".png")
        png.parent.mkdir(parents=True, exist_ok=True)
        render_preview(path, png, dpi=72)
        print(f"preview {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
