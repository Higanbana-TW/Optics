import assert from "node:assert/strict";
import test from "node:test";
import {
  calculateAutoWhiteBalance,
  encodeBmp,
  packedRowBytes,
  renderRaw10,
  requiredFileBytes,
  unpackRaw10,
} from "../src/raw10.js";

function packFour(values) {
  return Uint8Array.of(
    values[0] >> 2,
    values[1] >> 2,
    values[2] >> 2,
    values[3] >> 2,
    (values[0] & 3) | ((values[1] & 3) << 2) | ((values[2] & 3) << 4) | ((values[3] & 3) << 6),
  );
}

test("calculates tightly packed RAW10 row and file sizes", () => {
  assert.equal(packedRowBytes(1920), 2400);
  assert.equal(packedRowBytes(5), 10);
  assert.equal(requiredFileBytes(8, 2, 12, 4), 26);
});

test("unpacks all ten bits from standard 4-pixel/5-byte groups", () => {
  const expected = [0, 1, 2, 3, 256, 511, 700, 1023];
  const packed = new Uint8Array([...packFour(expected.slice(0, 4)), ...packFour(expected.slice(4))]);
  assert.deepEqual([...unpackRaw10(packed, 8, 1)], expected);
});

test("honors header offset and row stride padding", () => {
  const row1 = packFour([10, 20, 30, 40]);
  const row2 = packFour([50, 60, 70, 80]);
  const data = new Uint8Array([9, 9, ...row1, 0, 0, 0, ...row2]);
  assert.deepEqual([...unpackRaw10(data, 4, 2, { offset: 2, stride: 8 })], [10, 20, 30, 40, 50, 60, 70, 80]);
});

test("rejects files that are shorter than configured geometry", () => {
  assert.throws(() => unpackRaw10(new Uint8Array(4), 4, 1), /檔案大小不足/);
});

test("renders black and white monochrome endpoints", () => {
  const rgba = renderRaw10(new Uint16Array([64, 1023]), 2, 1, {
    pattern: "MONO",
    blackLevel: 64,
    whiteLevel: 1023,
    gamma: 2.2,
  });
  assert.deepEqual([...rgba], [0, 0, 0, 255, 255, 255, 255, 255]);
});

test("calculates bounded gray-world white balance gains", () => {
  const pixels = new Uint16Array([
    100, 200,
    200, 400,
  ]);
  assert.deepEqual(calculateAutoWhiteBalance(pixels, 2, 2, "RGGB"), { r: 2, g: 1, b: 0.5 });
});

test("encodes a valid 24-bit bottom-up BMP", async () => {
  const rgba = new Uint8ClampedArray([
    255, 0, 0, 255,
    0, 255, 0, 255,
  ]);
  const bytes = new Uint8Array(await encodeBmp(rgba, 1, 2).arrayBuffer());
  const view = new DataView(bytes.buffer);

  assert.equal(String.fromCharCode(bytes[0], bytes[1]), "BM");
  assert.equal(view.getUint32(2, true), 62);
  assert.equal(view.getInt32(18, true), 1);
  assert.equal(view.getInt32(22, true), 2);
  assert.equal(view.getUint16(28, true), 24);
  assert.deepEqual([...bytes.slice(54, 57)], [0, 255, 0]);
  assert.deepEqual([...bytes.slice(58, 61)], [0, 0, 255]);
});
