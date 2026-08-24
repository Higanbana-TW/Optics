#!/usr/bin/env python3
"""Geometry checks for the ISO 12233 DXF generator."""

from __future__ import annotations

import math
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import ezdxf
from ezdxf import bbox

from generate import (
    ACTIVE,
    ACTIVE_H,
    ACTIVE_W,
    BASE_PH_MM,
    CENTER_X,
    CENTER_Y,
    CROP_4X3_LEFT,
    CROP_4X3_RIGHT,
    DEFAULT_SVG,
    EIAJ_FIELD_NX,
    EIAJ_FIELD_NY,
    HALF_DIAG_16X9,
    bbox_center,
    clip_polyline,
    field_point_4x3,
    is_corner_cross_shape,
    layout_native_4x3,
    load_svg,
    parse_path,
    plus_center,
    translate_shape,
    write_dxf,
)


class PathParserTests(unittest.TestCase):
    def test_rectangle_hvz(self) -> None:
        polys = parse_path("M1121.273,680.314H0V0h1121.273V680.314z")
        self.assertEqual(len(polys), 1)
        self.assertEqual(polys[0][0], polys[0][-1])
        xs = [p[0] for p in polys[0]]
        ys = [p[1] for p in polys[0]]
        self.assertAlmostEqual(min(xs), 0.0)
        self.assertAlmostEqual(max(xs), 1121.273)
        self.assertAlmostEqual(min(ys), 0.0)
        self.assertAlmostEqual(max(ys), 680.314)


class ChartGeometryTests(unittest.TestCase):
    def test_active_area_is_16x9(self) -> None:
        self.assertAlmostEqual(ACTIVE_W / ACTIVE_H, 16 / 9, places=4)

    def test_official_4x3_crop_matches_ticks(self) -> None:
        width = CROP_4X3_RIGHT - CROP_4X3_LEFT
        self.assertAlmostEqual(width / ACTIVE_H, 4 / 3, places=3)

    def test_16x9_cross_centres_near_0_7_half_diagonal(self) -> None:
        shapes = load_svg(DEFAULT_SVG)
        clusters: dict[str, list] = defaultdict(list)
        for shape in shapes:
            if is_corner_cross_shape(shape):
                cx = (shape.bbox[0] + shape.bbox[2]) / 2.0
                cy = (shape.bbox[1] + shape.bbox[3]) / 2.0
                quad = ("L" if cx < CENTER_X else "R") + ("B" if cy > CENTER_Y else "T")
                clusters[quad].append(shape)
        self.assertEqual(set(clusters), {"LT", "RT", "LB", "RB"})
        for cluster in clusters.values():
            cx, cy = plus_center(cluster)
            frac = math.hypot(cx - CENTER_X, cy - CENTER_Y) / HALF_DIAG_16X9
            self.assertGreater(frac, 0.65)
            self.assertLess(frac, 0.70)

    def test_4x3_translates_crosses_to_eiaj_field(self) -> None:
        original = load_svg(DEFAULT_SVG)
        clusters: dict[str, list] = defaultdict(list)
        for shape in original:
            if is_corner_cross_shape(shape):
                cx = (shape.bbox[0] + shape.bbox[2]) / 2.0
                cy = (shape.bbox[1] + shape.bbox[3]) / 2.0
                quad = ("L" if cx < CENTER_X else "R") + ("B" if cy > CENTER_Y else "T")
                clusters[quad].append(shape)
        laid = layout_native_4x3(original)
        half_w = (CROP_4X3_RIGHT - CROP_4X3_LEFT) / 2.0
        half_h = ACTIVE_H / 2.0
        for quad, cluster in clusters.items():
            cx, cy = plus_center(cluster)
            tx, ty = field_point_4x3(quad)
            dx, dy = tx - cx, ty - cy
            moved = [translate_shape(s, dx, dy) for s in cluster]
            mx, my = plus_center(moved)
            self.assertAlmostEqual(mx, tx, delta=0.05)
            self.assertAlmostEqual(my, ty, delta=0.05)
            nx = abs(mx - CENTER_X) / half_w
            ny = abs(my - CENTER_Y) / half_h
            self.assertAlmostEqual(nx, EIAJ_FIELD_NX, delta=0.005)
            self.assertAlmostEqual(ny, EIAJ_FIELD_NY, delta=0.005)
            self.assertTrue(any(s.group == cluster[0].group for s in laid))

    def test_4x3_moves_inward_js_arms_with_the_plus(self) -> None:
        original = load_svg(DEFAULT_SVG)
        inward = [
            s
            for s in original
            if s.group.startswith("JS")
            and s.kind == "path"
            and s.bbox
            and not is_corner_cross_shape(s)
        ]
        self.assertTrue(inward)
        orig_x = [bbox_center(s.bbox)[0] for s in inward]
        self.assertTrue(all(700.0 < x < 790.0 for x in orig_x))
        laid = layout_native_4x3(original)
        moved_x = [
            bbox_center(s.bbox)[0]
            for s in laid
            if s.group.startswith("JS") and s.kind == "path" and s.bbox
        ]
        # RT inward arms (~x=740) travel with the plus (~dx=-86), not stay put.
        self.assertTrue(any(600.0 < x < 700.0 for x in moved_x))
        self.assertFalse(any(700.0 < x < 790.0 for x in moved_x))

    def test_eiaj_corner_circles_match_field_constants(self) -> None:
        svg = Path(__file__).resolve().parent.parent / "eiaj" / "data" / "eiaj_1956.svg"
        if not svg.is_file():
            self.skipTest("EIAJ SVG not present")
        from xml.etree import ElementTree as ET

        frame = (292.0, 382.0, 10689.0, 8230.0)
        cx = (frame[0] + frame[2]) / 2.0
        cy = (frame[1] + frame[3]) / 2.0
        half_w = (frame[2] - frame[0]) / 2.0
        half_h = (frame[3] - frame[1]) / 2.0
        root = ET.parse(svg).getroot()
        circles: list[tuple[float, float]] = []

        def walk(node: ET.Element) -> None:
            tag = node.tag.split("}")[-1]
            if tag == "path" and node.get("d"):
                for poly in parse_path(node.get("d") or ""):
                    if len(poly) < 200:
                        continue
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    w, h = max(xs) - min(xs), max(ys) - min(ys)
                    if abs(w - 1950) > 40 or abs(h - 1950) > 40:
                        continue
                    circles.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0))
            for child in list(node):
                walk(child)

        walk(root)
        self.assertGreaterEqual(len(circles), 4)
        nxs = [abs(x - cx) / half_w for x, _y in circles]
        nys = [abs(y - cy) / half_h for _x, y in circles]
        self.assertAlmostEqual(sum(nxs) / len(nxs), EIAJ_FIELD_NX, delta=0.01)
        self.assertAlmostEqual(sum(nys) / len(nys), EIAJ_FIELD_NY, delta=0.01)

    def test_4x3_does_not_deform_zone_plate_or_corner_squares(self) -> None:
        original = load_svg(DEFAULT_SVG)
        moved = layout_native_4x3(original)

        def zone_plate(shapes):
            return [s for s in shapes if s.group.startswith("C:_Center") and s.bbox]

        zp0 = zone_plate(original)
        zp1 = zone_plate(moved)
        self.assertTrue(zp0)
        for a, b in zip(zp0, zp1):
            self.assertEqual(a.bbox, b.bbox)

        def f_square_aspect(shapes):
            out = []
            for s in shapes:
                if s.group.startswith('"F"') and s.bbox and s.kind == "path":
                    w = s.bbox[2] - s.bbox[0]
                    h = s.bbox[3] - s.bbox[1]
                    if w > 5 and h > 5:
                        out.append(w / h)
            return out

        a0 = f_square_aspect(original)
        a1 = f_square_aspect(moved)
        self.assertTrue(a0)
        self.assertEqual(len(a0), len(a1))
        for x, y in zip(sorted(a0), sorted(a1)):
            self.assertAlmostEqual(x, y, places=5)

    def test_4x3_keeps_centre_resolution_numbers(self) -> None:
        original = load_svg(DEFAULT_SVG)
        moved = layout_native_4x3(original)
        groups = {s.group for s in moved}
        self.assertTrue(any(g.startswith("J1") for g in groups))
        self.assertTrue(any(g.startswith("C:_Center") for g in groups))
        # Centre frequency labels (本数) come back with J / KS wedges.
        texts = [s.text for s in moved if s.kind == "text"]
        self.assertTrue(any(t in {"10", "12", "14", "16"} for t in texts))
        self.assertFalse(any(g.startswith("O1") for g in groups))
        self.assertFalse(any(g.startswith("P1") for g in groups))
        # Diamond + axis parallelograms stay with L1-L4.
        diamonds = []
        paras = []
        for s in moved:
            if not s.group.startswith("L1") or not s.bbox or s.kind != "path":
                continue
            w = s.bbox[2] - s.bbox[0]
            h = s.bbox[3] - s.bbox[1]
            if min(w, h) > 70 and abs(w - h) < 5:
                diamonds.append(s)
            elif min(w, h) > 40 and max(w, h) > 100:
                paras.append(s)
        self.assertGreaterEqual(len(diamonds), 1)
        self.assertGreaterEqual(len(paras), 2)

    def test_svg_groups_are_classified(self) -> None:
        shapes = load_svg(DEFAULT_SVG)
        regions = {tuple(sorted(s.regions)) for s in shapes}
        self.assertTrue(any("center" in r for r in regions))
        self.assertTrue(any("periphery" in r for r in regions))
        self.assertTrue(any("sfr" in r for r in regions))
        self.assertGreater(len(shapes), 500)


class ClipTests(unittest.TestCase):
    def test_closed_square_clipped_to_half(self) -> None:
        square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        clipped = clip_polyline(square, (0, 0, 5, 10), closed=True)
        self.assertEqual(len(clipped), 1)
        xs = [p[0] for p in clipped[0]]
        self.assertAlmostEqual(max(xs), 5.0)
        self.assertAlmostEqual(min(xs), 0.0)


class DxfOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shapes = load_svg(DEFAULT_SVG)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _write(self, aspect: str, region: str, scale: float = 4.0) -> Path:
        dest = self.out / f"{aspect.replace(':', 'x')}_{region}.dxf"
        return write_dxf(self.shapes, dest, aspect=aspect, region=region, scale=scale)

    def test_16x9_4x_full_size(self) -> None:
        path = self._write("16:9", "full")
        doc = ezdxf.readfile(path)
        ext = bbox.extents(doc.modelspace())
        width = ext.extmax.x - ext.extmin.x
        height = ext.extmax.y - ext.extmin.y
        self.assertAlmostEqual(width, 1121.273 * 25.4 / 72 * 4, delta=2.0)
        self.assertAlmostEqual(height, 697.5 * 25.4 / 72 * 4, delta=2.0)
        layers = {layer.dxf.name for layer in doc.layers}
        for name in ("FRAME", "CENTER", "PERIPHERY", "SFR", "LABELS"):
            self.assertIn(name, layers)
        used = {e.dxf.layer for e in doc.modelspace()}
        self.assertTrue({"CENTER", "PERIPHERY", "SFR"} <= used)
        types = {e.dxftype() for e in doc.modelspace()}
        self.assertIn("SOLID", types)
        self.assertIn("LWPOLYLINE", types)
        extmin = doc.header["$EXTMIN"]
        self.assertLess(extmin[0], 1e10)
        solids = sum(1 for e in doc.modelspace() if e.dxftype() == "SOLID")
        self.assertGreater(solids, 200)

    def test_4x3_full_aspect(self) -> None:
        path = self._write("4:3", "full")
        doc = ezdxf.readfile(path)
        ext = bbox.extents(doc.modelspace())
        width = ext.extmax.x - ext.extmin.x
        height = ext.extmax.y - ext.extmin.y
        self.assertGreater(width, BASE_PH_MM * 4 * 4 / 3)
        self.assertLess(width, BASE_PH_MM * 4 * 16 / 9)
        self.assertGreater(height, BASE_PH_MM * 4)
        self.assertAlmostEqual(width / (BASE_PH_MM * 4 * 4 / 3 + 160), 1.0, delta=0.15)

    def test_4x3_full_keeps_translated_crosses(self) -> None:
        path43 = self._write("4:3", "full")
        doc43 = ezdxf.readfile(path43)
        sfr_xs = []
        for e in doc43.modelspace().query("LWPOLYLINE"):
            if e.dxf.layer != "SFR":
                continue
            sfr_xs.extend(p[0] for p in e.get_points())
        self.assertTrue(sfr_xs)
        inner_left_mm = CROP_4X3_LEFT * 4 * 25.4 / 72.0
        # Crosses sit inside the 4:3 frame, not out on the old 16:9 edge.
        self.assertGreater(min(sfr_xs), inner_left_mm - 5.0)
        self.assertLess(min(sfr_xs), inner_left_mm + 80.0)

    def test_region_files_have_sfr_or_center(self) -> None:
        sfr = self._write("16:9", "sfr")
        center = self._write("16:9", "center")
        sfr_doc = ezdxf.readfile(sfr)
        center_doc = ezdxf.readfile(center)
        sfr_layers = {e.dxf.layer for e in sfr_doc.modelspace()}
        center_layers = {e.dxf.layer for e in center_doc.modelspace()}
        self.assertIn("SFR", sfr_layers)
        self.assertIn("CENTER", center_layers)
        self.assertNotIn("PERIPHERY", sfr_layers)


if __name__ == "__main__":
    unittest.main()
