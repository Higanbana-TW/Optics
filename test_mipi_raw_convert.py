#!/usr/bin/env python3
"""Tests for 10-bit MIPI RAW packing, unpacking, demosaic, and image export."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import mipi_raw_convert as raw


class PackUnpackTests(unittest.TestCase):
    def test_mipi10_known_lsb_layout(self):
        # byte4 bits: P3[1:0] P2[1:0] P1[1:0] P0[1:0]  =>  11 10 01 00
        packed = bytes([0xFF, 0x00, 0xAA, 0x55, 0b11_10_01_00])
        pixels = raw.unpack_raw10_mipi(packed, width=4, height=1)
        np.testing.assert_array_equal(
            pixels,
            np.array([[(0xFF << 2) | 0b00, (0x00 << 2) | 0b01, (0xAA << 2) | 0b10, (0x55 << 2) | 0b11]], dtype=np.uint16),
        )

    def test_mipi10_roundtrip_random(self):
        rng = np.random.default_rng(20260824)
        source = rng.integers(0, 1024, size=(48, 64), dtype=np.uint16)
        packed = raw.pack_raw10_mipi(source)
        self.assertEqual(len(packed), 48 * 64 * 5 // 4)
        restored = raw.unpack_raw10_mipi(packed, width=64, height=48)
        np.testing.assert_array_equal(restored, source)

    def test_mipi10_rejects_width_not_multiple_of_four(self):
        with self.assertRaisesRegex(raw.RawConvertError, "4 的倍數"):
            raw.packed_row_bytes(1921)

    def test_mipi10_stride_padding(self):
        source = np.arange(32, dtype=np.uint16).reshape(4, 8) & 0x3FF
        packed_rows = raw.pack_raw10_mipi(source)
        row = 8 * 5 // 4
        padded = bytearray()
        for y in range(4):
            padded.extend(packed_rows[y * row : (y + 1) * row])
            padded.extend(b"\xAA\xBB")
        restored = raw.unpack_raw10_mipi(bytes(padded), width=8, height=4, stride=row + 2)
        np.testing.assert_array_equal(restored, source)

    def test_u16le_and_msb_aligned(self):
        values = np.array([[1, 512, 1023, 7]], dtype=np.uint16)
        little = values.astype("<u2").tobytes()
        np.testing.assert_array_equal(raw.unpack_u16(little, 4, 1, endian="<"), values)
        shifted = (values << 6).astype("<u2").tobytes()
        np.testing.assert_array_equal(
            raw.unpack_u16(shifted, 4, 1, endian="<", msb_aligned=True),
            values,
        )


class DemosaicTests(unittest.TestCase):
    def test_solid_red_rggb_stays_red(self):
        rgb = np.zeros((32, 32, 3), dtype=np.uint16)
        rgb[..., 0] = 1023
        cfa = raw.mosaic_bayer(rgb, "RGGB")
        out = raw.demosaic_bilinear(cfa, "RGGB")
        interior = out[2:-2, 2:-2]
        self.assertGreater(interior[..., 0].min(), 1000)
        self.assertLess(interior[..., 1].max(), 1.0)
        self.assertLess(interior[..., 2].max(), 1.0)

    def test_solid_blue_bggr_stays_blue(self):
        rgb = np.zeros((32, 32, 3), dtype=np.uint16)
        rgb[..., 2] = 800
        cfa = raw.mosaic_bayer(rgb, "BGGR")
        out = raw.demosaic_bilinear(cfa, "BGGR")
        interior = out[2:-2, 2:-2]
        self.assertGreater(interior[..., 2].min(), 790)
        self.assertLess(interior[..., 0].max(), 1.0)

    def test_wrong_bayer_pattern_rejected(self):
        with self.assertRaisesRegex(raw.RawConvertError, "Bayer"):
            raw.demosaic_bilinear(np.zeros((8, 8), dtype=np.uint16), "RGBG")


class ConvertExportTests(unittest.TestCase):
    def test_sample_chart_exports_all_formats(self):
        rgb10 = raw.make_sample_rgb(64, 48)
        cfa = raw.mosaic_bayer(rgb10, "RGGB")
        packed = raw.pack_raw10_mipi(cfa)
        pixels = raw.unpack_raw10_mipi(packed, 64, 48)
        rgb8 = raw.raw_to_rgb(pixels, bayer="RGGB", white_balance="off", tone="shift")

        red_patch = rgb8[4:20, 2:6]
        self.assertGreater(red_patch[..., 0].mean(), 200)
        self.assertLess(red_patch[..., 1].mean(), 40)
        self.assertLess(red_patch[..., 2].mean(), 40)

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for suffix in (".png", ".jpg", ".bmp"):
                target = folder / f"chart{suffix}"
                raw.save_image(rgb8, target, quality=90)
                with Image.open(target) as opened:
                    self.assertEqual(opened.size, (64, 48))
                self.assertGreater(target.stat().st_size, 32)

    def test_guess_layouts_finds_packed_1080p(self):
        size = 1920 * 1080 * 5 // 4
        guesses = raw.guess_layouts(size)
        match = next(item for item in guesses if item["width"] == 1920 and item["height"] == 1080)
        self.assertEqual(match["format"], "mipi10")
        self.assertEqual(match["frames"], 1)

    def test_cli_make_sample_and_convert(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            sample = folder / "sample.raw"
            png = folder / "out.png"
            bmp = folder / "out.bmp"
            jpg = folder / "out.jpg"
            script = Path(__file__).resolve().parent / "mipi_raw_convert.py"
            subprocess.run(
                [sys.executable, str(script), "--make-sample", "80x64", "--bayer", "RGGB", "-o", str(sample)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(sample.stat().st_size, 80 * 64 * 5 // 4)
            for output in (png, bmp, jpg):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(script),
                        str(sample),
                        "-W",
                        "80",
                        "-H",
                        "64",
                        "--bayer",
                        "RGGB",
                        "--wb",
                        "off",
                        "-o",
                        str(output),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertIn(output.name, completed.stdout)
                with Image.open(output) as image:
                    self.assertEqual(image.size, (80, 64))

    def test_tone_shift_maps_10bit_peak_to_8bit(self):
        rgb = np.array([[[1023, 0, 511]]], dtype=np.float32)
        mapped = raw.tone_map_to_u8(rgb, "shift")
        self.assertEqual(mapped[0, 0, 0], 255)
        self.assertEqual(mapped[0, 0, 1], 0)
        self.assertEqual(mapped[0, 0, 2], 127)


class HelpTests(unittest.TestCase):
    def test_no_args_prints_usage(self):
        buffer = io.StringIO()
        previous = sys.stdout
        sys.stdout = buffer
        try:
            code = raw.main([])
        finally:
            sys.stdout = previous
        self.assertEqual(code, 0)
        self.assertIn("MIPI RAW", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
