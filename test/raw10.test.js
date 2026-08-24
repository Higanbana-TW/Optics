import test from "node:test";
import assert from "node:assert/strict";
import {
  demosaicRaw10,
  encodeBmp,
  expectedRaw10Bytes,
  packedRowBytes,
  unpackRaw10,
} from "../src/raw10.js";

function packRow(values, stride = Math.ceil(values.length / 4) * 5) {
  const output = new Uint8Array(stride);
  for (let x = 0; x < values.length; x += 4) {
    const target = Math.floor(x / 4) * 5;
    let lowBits = 0;
    for (let index = 0; index < Math.min(4, values.length - x); index += 1) {
      output[target + index] = values[x + index] >> 2;
      lowBits |= (values[x + index] & 0x03) << (index * 2);
    }
    output[target + 4] = lowBits;
  }
  return output;
}

test("calculates packed RAW10 rows and frame sizes", () => {
  assert.equal(packedRowBytes(1920), 2400);
  assert.equal(packedRowBytes(5), 10);
  assert.equal(expectedRaw10Bytes(8, 3, 16), 48);
  assert.throws(() => expectedRaw10Bytes(8, 3, 9), /不可小於 10/);
});

test("unpacks all ten bits in MIPI RAW10 order", () => {
  const expected = [0, 1, 2, 3, 4, 255, 512, 1023];
  const bytes = packRow(expected);
  assert.deepEqual([...unpackRaw10(bytes, 8, 1)], expected);
});

test("handles partial groups and skips row padding", () => {
  const first = packRow([7, 128, 511, 900, 1022], 12);
  const second = packRow([1023, 700, 300, 100, 0], 12);
  first[10] = 0xee;
  first[11] = 0xee;
  const bytes = new Uint8Array([...first, ...second]);

  assert.deepEqual(
    [...unpackRaw10(bytes, 5, 2, 12)],
    [7, 128, 511, 900, 1022, 1023, 700, 300, 100, 0],
  );
});

test("rejects a frame shorter than its configured dimensions", () => {
  assert.throws(() => unpackRaw10(new Uint8Array(9), 8, 1), /檔案太小/);
});

test("demosaics a stable RGGB color field to 8-bit RGBA", () => {
  const width = 4;
  const height = 4;
  const values = new Uint16Array(width * height);
  const pattern = "RGGB";
  const sensorValues = { R: 1023, G: 512, B: 0 };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      values[y * width + x] = sensorValues[pattern[(y % 2) * 2 + (x % 2)]];
    }
  }

  const rgba = demosaicRaw10(values, width, height, {
    pattern,
    blackLevel: 0,
    whiteLevel: 1023,
  });

  for (let index = 0; index < rgba.length; index += 4) {
    assert.deepEqual([...rgba.slice(index, index + 4)], [255, 128, 0, 255]);
  }
});

test("encodes a bottom-up 32-bit BMP with BGR pixel order", async () => {
  const rgba = new Uint8ClampedArray([
    255, 0, 0, 255,
    0, 255, 0, 255,
    0, 0, 255, 255,
    255, 255, 255, 255,
  ]);
  const blob = encodeBmp(rgba, 2, 2);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const view = new DataView(bytes.buffer);

  assert.equal(blob.type, "image/bmp");
  assert.equal(String.fromCharCode(bytes[0], bytes[1]), "BM");
  assert.equal(view.getUint32(2, true), 70);
  assert.equal(view.getInt32(18, true), 2);
  assert.equal(view.getInt32(22, true), 2);
  assert.equal(view.getUint16(28, true), 32);
  assert.deepEqual([...bytes.slice(54, 58)], [255, 0, 0, 255]);
});
