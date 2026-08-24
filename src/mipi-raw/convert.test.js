import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  encodeBmp,
  guessLayouts,
  makeSampleRaw10,
  packRaw10Mipi,
  packedRowBytes,
  rawToRgb,
  unpackRaw10Mipi,
} from "./convert.js";

test("MIPI RAW10 uses CSI-2 LSB nibble order", () => {
  const packed = Uint8Array.of(0xff, 0x00, 0xaa, 0x55, 0b11_10_01_00);
  const pixels = unpackRaw10Mipi(packed, 4, 1);
  assert.equal(pixels[0], (0xff << 2) | 0b00);
  assert.equal(pixels[1], (0x00 << 2) | 0b01);
  assert.equal(pixels[2], (0xaa << 2) | 0b10);
  assert.equal(pixels[3], (0x55 << 2) | 0b11);
});

test("MIPI RAW10 pack/unpack roundtrip", () => {
  const width = 16;
  const height = 8;
  const source = new Uint16Array(width * height);
  for (let i = 0; i < source.length; i += 1) source[i] = (i * 37) & 1023;
  const packed = packRaw10Mipi(source, width, height);
  assert.equal(packed.length, packedRowBytes(width) * height);
  const restored = unpackRaw10Mipi(packed, width, height);
  assert.deepEqual([...restored], [...source]);
});

test("sample chart demosaic keeps the red patch red", () => {
  const packed = makeSampleRaw10(64, 48, "RGGB");
  const pixels = unpackRaw10Mipi(packed, 64, 48);
  const rgb = rawToRgb(pixels, 64, 48, { bayer: "RGGB", whiteBalance: [1, 1, 1], tone: "shift" });
  const index = (8 * 64 + 4) * 3;
  assert.ok(rgb[index] > 200, `red=${rgb[index]}`);
  assert.ok(rgb[index + 1] < 40, `green=${rgb[index + 1]}`);
  assert.ok(rgb[index + 2] < 40, `blue=${rgb[index + 2]}`);
});

test("BMP payload starts with BM and uses the requested size", async () => {
  const rgb = Uint8Array.of(255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255);
  const blob = encodeBmp(rgb, 2, 2);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  assert.equal(bytes[0], 0x42);
  assert.equal(bytes[1], 0x4d);
  const width = bytes[18] | (bytes[19] << 8) | (bytes[20] << 16) | (bytes[21] << 24);
  const height = bytes[22] | (bytes[23] << 8) | (bytes[24] << 16) | (bytes[25] << 24);
  assert.equal(width, 2);
  assert.equal(height, 2);
});

test("guessLayouts finds packed 1080p", () => {
  const guesses = guessLayouts((1920 * 1080 * 5) / 4);
  const match = guesses.find((item) => item.width === 1920 && item.height === 1080);
  assert.ok(match);
  assert.equal(match.format, "mipi10");
});

test("standalone HTML can be opened without a dev server", () => {
  const html = readFileSync(new URL("../../mipi-raw.html", import.meta.url), "utf8");
  assert.match(html, /function unpackRaw10Mipi/);
  assert.match(html, /function convertCurrent/);
  assert.equal(html.includes('type="module"'), false);
  assert.equal(html.includes('src="/src/'), false);
});
