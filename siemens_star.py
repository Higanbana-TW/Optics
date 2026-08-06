#!/usr/bin/env python3
"""Generate a print-ready Siemens star as an SVG file."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from xml.etree import ElementTree as ET


PAPER_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}


def _fmt(value: float) -> str:
    """Format SVG coordinates without unnecessary trailing zeroes."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _paper_dimensions(paper: str, orientation: str) -> tuple[float, float]:
    try:
        width, height = PAPER_SIZES_MM[paper.upper()]
    except KeyError as exc:
        choices = ", ".join(PAPER_SIZES_MM)
        raise ValueError(f"不支援的紙張尺寸：{paper}（可用：{choices}）") from exc

    if orientation == "landscape":
        return height, width
    if orientation != "portrait":
        raise ValueError("orientation 必須是 portrait 或 landscape")
    return width, height


def create_siemens_star(
    angle_deg: float,
    paper: str = "A4",
    orientation: str = "portrait",
    fill_page: bool = True,
    margin_mm: float = 10.0,
    radius_mm: float | None = None,
) -> ET.Element:
    """Create the root element for a printable Siemens star SVG.

    ``angle_deg`` is the angle of each individual black or white sector.
    It must divide 360 degrees exactly so the first and last sectors align.
    """
    if not 0 < angle_deg < 180:
        raise ValueError("區隔角度必須大於 0 且小於 180 度")

    sector_count_float = 360.0 / angle_deg
    sector_count = round(sector_count_float)
    if not math.isclose(sector_count_float, sector_count, abs_tol=1e-9):
        raise ValueError("區隔角度必須能整除 360 度")
    if sector_count % 2:
        raise ValueError("區隔總數必須是偶數，才能讓黑白區塊交替閉合")

    width, height = _paper_dimensions(paper, orientation)
    if fill_page:
        # A radius larger than the page diagonal places every circular arc
        # outside the page. Clipping then turns each sector into a ray-filled
        # region that reaches the rectangular paper edges.
        radius = math.hypot(width, height)
    else:
        if margin_mm < 0:
            raise ValueError("邊界不可小於 0 mm")
        max_radius = min(width, height) / 2 - margin_mm
        radius = max_radius if radius_mm is None else radius_mm
        if radius <= 0:
            raise ValueError("星形半徑必須大於 0 mm")
        if radius > max_radius:
            raise ValueError(
                f"星形半徑過大；目前紙張與邊界設定最多可用 {_fmt(max_radius)} mm"
            )

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{_fmt(width)}mm",
            "height": f"{_fmt(height)}mm",
            "viewBox": f"0 0 {_fmt(width)} {_fmt(height)}",
        },
    )
    mode = "full page" if fill_page else "circular"
    ET.SubElement(svg, "title").text = (
        f"Siemens star: {angle_deg:g} degree sectors, {paper.upper()}, {mode}"
    )
    defs = ET.SubElement(svg, "defs")
    clip_path = ET.SubElement(defs, "clipPath", {"id": "paper-clip"})
    ET.SubElement(
        clip_path,
        "rect",
        {
            "width": _fmt(width),
            "height": _fmt(height),
        },
    )
    ET.SubElement(
        svg,
        "rect",
        {
            "width": _fmt(width),
            "height": _fmt(height),
            "fill": "white",
        },
    )

    center_x, center_y = width / 2, height / 2
    star = ET.SubElement(
        svg,
        "g",
        {
            "id": "siemens-star",
            "fill": "black",
            "shape-rendering": "geometricPrecision",
            "clip-path": "url(#paper-clip)",
        },
    )

    # Draw every other sector; the white page supplies the intervening sectors.
    start_offset = -90.0
    for index in range(0, sector_count, 2):
        start = math.radians(start_offset + index * angle_deg)
        end = math.radians(start_offset + (index + 1) * angle_deg)
        x1 = center_x + radius * math.cos(start)
        y1 = center_y + radius * math.sin(start)
        x2 = center_x + radius * math.cos(end)
        y2 = center_y + radius * math.sin(end)
        path = (
            f"M {_fmt(center_x)} {_fmt(center_y)} "
            f"L {_fmt(x1)} {_fmt(y1)} "
            f"A {_fmt(radius)} {_fmt(radius)} 0 0 1 {_fmt(x2)} {_fmt(y2)} Z"
        )
        ET.SubElement(star, "path", {"d": path})

    return svg


def save_svg(root: ET.Element, output: str | Path) -> Path:
    """Write an SVG tree to disk and return its path."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="產生可依實際尺寸列印的西門子星 SVG 測試圖。",
    )
    parser.add_argument(
        "--angle",
        type=float,
        required=True,
        help="每個黑色或白色區隔的角度，例如 2 或 5",
    )
    parser.add_argument(
        "--paper",
        choices=tuple(PAPER_SIZES_MM),
        default="A4",
        help="紙張尺寸（預設：A4）",
    )
    parser.add_argument(
        "--orientation",
        choices=("portrait", "landscape"),
        default="portrait",
        help="紙張方向（預設：portrait）",
    )
    parser.add_argument(
        "--circle",
        action="store_true",
        help="產生傳統圓形版本（預設會讓放射區塊佈滿整張紙）",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=10.0,
        help="圓形模式的紙張邊界，單位 mm（預設：10）",
    )
    parser.add_argument(
        "--radius",
        type=float,
        help="圓形模式的星形半徑，單位 mm",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("siemens_star.svg"),
        help="輸出 SVG 路徑（預設：siemens_star.svg）",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.radius is not None and not args.circle:
        parser.error("--radius 必須搭配 --circle 使用")
    svg = create_siemens_star(
        angle_deg=args.angle,
        paper=args.paper,
        orientation=args.orientation,
        fill_page=not args.circle,
        margin_mm=args.margin,
        radius_mm=args.radius,
    )
    output = save_svg(svg, args.output)
    print(f"已產生：{output}")
    print("列印時請選擇「實際大小」或 100%，並關閉「符合頁面」。")


if __name__ == "__main__":
    main()
