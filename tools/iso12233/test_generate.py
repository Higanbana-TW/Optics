#!/usr/bin/env python3
"""Geometry checks for the ISO 12233 DXF generator."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import ezdxf
from ezdxf import bbox

from generate import (
    ACTIVE_H,
    ACTIVE_W,
    BASE_PH_MM,
    CROP_4X3_LEFT,
    CROP_4X3_RIGHT,
    DEFAULT_SVG,
    clip_polyline,
    load_svg,
    parse_path,
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
        # 4:3 active is 1066.7 x 800 mm plus 80 mm borders → ~1226.7 x 960,
        # plus title/footer from the original SVG y-flip.
        self.assertGreater(width, BASE_PH_MM * 4 * 4 / 3)
        self.assertLess(width, BASE_PH_MM * 4 * 16 / 9)
        self.assertGreater(height, BASE_PH_MM * 4)
        self.assertAlmostEqual(width / (BASE_PH_MM * 4 * 4 / 3 + 160), 1.0, delta=0.15)

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
