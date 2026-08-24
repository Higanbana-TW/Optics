import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { deflateSync, inflateSync } from "node:zlib";

import {
  BAYER_PATTERNS,
  bytesPerRow,
  frameByteLength,
  frameCount,
  guessDimensions,
  parseDimensionsFromName,
  parsePatternFromName,
} from "../src/raw10/format.js";
import { packFrame, unpackFrame } from "../src/raw10/unpack.js";
import { analyzeSamples, processRaw } from "../src/raw10/process.js";
import { encodeBmp, encodePng, rgbToRgba } from "../src/raw10/encode.js";

function randomSamples(count, seed = 1) {
  const out = new Uint16Array(count);
  let state = seed;
  for (let i = 0; i < count; i += 1) {
    state = (state * 1103515245 + 12345) & 0x7fffffff;
    out[i] = state % 1024;
  }
  return out;
}

/** Mosaic an RGB image into a CFA frame using the given Bayer pattern. */
function mosaic(rgb, width, height, pattern) {
  const cells = BAYER_PATTERNS[pattern].cells;
  const samples = new Uint16Array(width * height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const channel = cells[y & 1][x & 1];
      samples[y * width + x] = rgb[(y * width + x) * 3 + channel];
    }
  }
  return samples;
}

describe("format helpers", () => {
  it("computes packed and unpacked row sizes", () => {
    assert.equal(bytesPerRow(1920, "mipi10"), 2400);
    assert.equal(bytesPerRow(6, "mipi10"), 10);
    assert.equal(bytesPerRow(1920, "raw16le"), 3840);
    assert.equal(frameByteLength(1920, 1080, "mipi10"), 2400 * 1080);
    assert.equal(frameByteLength(64, 4, "mipi10", 128), 512);
  });

  it("counts frames in a multi-frame dump", () => {
    const bytes = frameByteLength(640, 480, "mipi10") * 3;
    assert.equal(frameCount(bytes, 640, 480, "mipi10"), 3);
    assert.equal(frameCount(bytes + 16, 640, 480, "mipi10", 0, 16), 3);
  });

  it("suggests resolutions that divide the file exactly", () => {
    const bytes = frameByteLength(1920, 1080, "mipi10");
    const guesses = guessDimensions(bytes, "mipi10");
    assert.equal(guesses[0].width, 1920);
    assert.equal(guesses[0].height, 1080);
    assert.equal(guesses[0].frames, 1);
  });

  it("still suggests the frame size for a multi-frame dump", () => {
    const bytes = frameByteLength(1920, 1080, "mipi10") * 2;
    const guesses = guessDimensions(bytes, "mipi10");
    const match = guesses.find((g) => g.width === 1920 && g.height === 1080);
    assert.ok(match, JSON.stringify(guesses));
    assert.equal(match.frames, 2);
  });

  it("reads hints from file names", () => {
    assert.deepEqual(parseDimensionsFromName("capture_1920x1080_bggr.raw"), { width: 1920, height: 1080 });
    assert.equal(parsePatternFromName("capture_1920x1080_bggr.raw"), "bggr");
    assert.equal(parseDimensionsFromName("capture.raw"), null);
  });
});

describe("MIPI RAW10 unpacking", () => {
  it("decodes the documented 5-byte group", () => {
    const bytes = new Uint8Array([0xab, 0x01, 0xff, 0x10, 0b11100100]);
    const pixels = unpackFrame(bytes, { width: 4, height: 1, packing: "mipi10" });
    assert.deepEqual(Array.from(pixels), [(0xab << 2) | 0, (0x01 << 2) | 1, (0xff << 2) | 2, (0x10 << 2) | 3]);
  });

  it("decodes the reversed low-bit ordering", () => {
    const bytes = new Uint8Array([0xab, 0x01, 0xff, 0x10, 0b11100100]);
    const pixels = unpackFrame(bytes, { width: 4, height: 1, packing: "mipi10lsbrev" });
    assert.deepEqual(Array.from(pixels), [(0xab << 2) | 3, (0x01 << 2) | 2, (0xff << 2) | 1, (0x10 << 2) | 0]);
  });

  it("round-trips every packing mode", () => {
    for (const packing of ["mipi10", "mipi10lsbrev", "raw16le", "raw16be"]) {
      const width = 20;
      const height = 6;
      const samples = randomSamples(width * height, 7);
      const bytes = packFrame(samples, { width, height, packing });
      const decoded = unpackFrame(bytes, { width, height, packing });
      assert.deepEqual(Array.from(decoded), Array.from(samples), packing);
    }
  });

  it("round-trips 16-bit data that is left aligned", () => {
    const samples = randomSamples(32, 3);
    const bytes = packFrame(samples, { width: 8, height: 4, packing: "raw16le", align: "msb" });
    const decoded = unpackFrame(bytes, { width: 8, height: 4, packing: "raw16le", align: "msb" });
    assert.deepEqual(Array.from(decoded), Array.from(samples));
  });

  it("honours row padding and a header offset", () => {
    const width = 12;
    const height = 3;
    const stride = bytesPerRow(width, "mipi10") + 7;
    const offset = 11;
    const samples = randomSamples(width * height, 99);
    const body = packFrame(samples, { width, height, packing: "mipi10", stride });
    const bytes = new Uint8Array(offset + body.length);
    bytes.set(body, offset);
    const decoded = unpackFrame(bytes, { width, height, packing: "mipi10", stride, offset });
    assert.deepEqual(Array.from(decoded), Array.from(samples));
  });

  it("stops safely when the buffer is truncated", () => {
    const bytes = new Uint8Array(7);
    const decoded = unpackFrame(bytes, { width: 8, height: 4, packing: "mipi10" });
    assert.equal(decoded.length, 32);
  });
});

describe("processing pipeline", () => {
  const width = 32;
  const height = 24;

  it("reconstructs a flat colour patch exactly", () => {
    const source = new Uint16Array(width * height * 3);
    for (let i = 0; i < width * height; i += 1) {
      source[i * 3] = 800;
      source[i * 3 + 1] = 500;
      source[i * 3 + 2] = 300;
    }
    const samples = mosaic(source, width, height, "rggb");
    const bytes = packFrame(samples, { width, height, packing: "mipi10" });
    const image = processRaw(bytes, {
      width,
      height,
      pattern: "rggb",
      blackLevel: 0,
      whiteLevel: 1023,
      tone: "linear",
    });

    const centre = ((height / 2) * width + width / 2) * 3;
    assert.equal(image.rgb[centre], Math.round((800 / 1023) * 255));
    assert.equal(image.rgb[centre + 1], Math.round((500 / 1023) * 255));
    assert.equal(image.rgb[centre + 2], Math.round((300 / 1023) * 255));
  });

  it("keeps a smooth gradient close to the source through mosaic and demosaic", () => {
    const source = new Uint16Array(width * height * 3);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const i = (y * width + x) * 3;
        source[i] = Math.round((x / (width - 1)) * 900) + 60;
        source[i + 1] = Math.round((y / (height - 1)) * 900) + 60;
        source[i + 2] = 500;
      }
    }
    const samples = mosaic(source, width, height, "bggr");
    const bytes = packFrame(samples, { width, height, packing: "mipi10" });
    const image = processRaw(bytes, {
      width,
      height,
      pattern: "bggr",
      blackLevel: 0,
      whiteLevel: 1023,
      tone: "linear",
    });

    let error = 0;
    let count = 0;
    for (let y = 2; y < height - 2; y += 1) {
      for (let x = 2; x < width - 2; x += 1) {
        for (let c = 0; c < 3; c += 1) {
          const expected = (source[(y * width + x) * 3 + c] / 1023) * 255;
          error += Math.abs(image.rgb[(y * width + x) * 3 + c] - expected);
          count += 1;
        }
      }
    }
    assert.ok(error / count < 2, `mean error ${error / count}`);
  });

  it("supports binning, grayscale and mono patterns", () => {
    const samples = randomSamples(width * height, 5);
    const bytes = packFrame(samples, { width, height, packing: "mipi10" });

    const binned = processRaw(bytes, { width, height, demosaic: "binning" });
    assert.equal(binned.width, width / 2);
    assert.equal(binned.height, height / 2);
    assert.equal(binned.rgb.length, (width / 2) * (height / 2) * 3);

    const gray = processRaw(bytes, { width, height, demosaic: "none" });
    assert.equal(gray.rgb[0], gray.rgb[1]);
    assert.equal(gray.rgb[1], gray.rgb[2]);

    const mono = processRaw(bytes, { width, height, pattern: "mono" });
    assert.equal(mono.rgb[3], mono.rgb[5]);
  });

  it("neutralises a colour cast with the automatic settings", () => {
    // A dark-to-bright ramp lit by an illuminant that starves red and blue.
    const source = new Uint16Array(width * height * 3);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const base = (x / (width - 1)) * 900;
        const i = (y * width + x) * 3;
        source[i] = Math.round(64 + base * 0.4);
        source[i + 1] = Math.round(64 + base);
        source[i + 2] = Math.round(64 + base * 0.7);
      }
    }
    const samples = mosaic(source, width, height, "rggb");
    const stats = analyzeSamples(samples, { width, height, pattern: "rggb" });
    assert.ok(Math.abs(stats.blackLevel - 64) <= 12, `black level ${stats.blackLevel}`);
    assert.ok(Math.abs(stats.gains[0] - 2.5) < 0.15, `red gain ${stats.gains[0]}`);
    assert.ok(Math.abs(stats.gains[2] - 1.43) < 0.15, `blue gain ${stats.gains[2]}`);
    assert.equal(stats.gains[1], 1);

    const bytes = packFrame(samples, { width, height, packing: "mipi10" });
    const image = processRaw(bytes, { width, height, pattern: "rggb", auto: true, tone: "linear" });
    // Grey-world gains are sampled on the CFA grid, so a ramp leaves a couple of
    // levels of residual cast rather than a perfectly neutral pixel.
    const centre = ((height / 2) * width + width / 2) * 3;
    assert.ok(Math.abs(image.rgb[centre] - image.rgb[centre + 1]) <= 6);
    assert.ok(Math.abs(image.rgb[centre + 2] - image.rgb[centre + 1]) <= 6);
  });

  it("brightens the image when exposure compensation is applied", () => {
    const samples = new Uint16Array(width * height).fill(300);
    const bytes = packFrame(samples, { width, height, packing: "mipi10" });
    const base = processRaw(bytes, { width, height, blackLevel: 0, tone: "linear", demosaic: "none" });
    const brighter = processRaw(bytes, {
      width,
      height,
      blackLevel: 0,
      exposure: 1,
      tone: "linear",
      demosaic: "none",
    });
    assert.ok(brighter.rgb[0] > base.rgb[0] * 1.8);
  });
});

describe("encoders", () => {
  const width = 3;
  const height = 2;
  const rgb = new Uint8ClampedArray([
    255, 0, 0, 0, 255, 0, 0, 0, 255, 10, 20, 30, 40, 50, 60, 70, 80, 90,
  ]);

  it("writes a bottom-up 24-bit BMP", () => {
    const bmp = encodeBmp(rgb, width, height);
    const view = new DataView(bmp.buffer);
    assert.equal(bmp[0], 0x42);
    assert.equal(bmp[1], 0x4d);
    assert.equal(view.getUint32(2, true), bmp.length);
    assert.equal(view.getInt32(18, true), width);
    assert.equal(view.getInt32(22, true), height);
    assert.equal(view.getUint16(28, true), 24);

    const rowSize = (width * 3 + 3) & ~3;
    // The last source row is stored first, as BGR.
    assert.deepEqual(Array.from(bmp.subarray(54, 54 + 9)), [30, 20, 10, 60, 50, 40, 90, 80, 70]);
    assert.equal(bmp.length, 54 + rowSize * height);
  });

  it("writes a PNG whose IDAT decodes back to the source pixels", () => {
    const png = encodePng(rgb, width, height, deflateSync);
    assert.deepEqual(Array.from(png.subarray(0, 8)), [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

    const chunks = [];
    let offset = 8;
    while (offset < png.length) {
      const view = new DataView(png.buffer, png.byteOffset + offset);
      const length = view.getUint32(0);
      const type = String.fromCharCode(...png.subarray(offset + 4, offset + 8));
      chunks.push({ type, data: png.subarray(offset + 8, offset + 8 + length) });
      offset += length + 12;
    }
    assert.deepEqual(chunks.map((c) => c.type), ["IHDR", "IDAT", "IEND"]);

    const header = new DataView(chunks[0].data.buffer, chunks[0].data.byteOffset);
    assert.equal(header.getUint32(0), width);
    assert.equal(header.getUint32(4), height);
    assert.equal(chunks[0].data[8], 8);
    assert.equal(chunks[0].data[9], 2);

    const raw = inflateSync(Buffer.from(chunks[1].data));
    assert.equal(raw.length, (width * 3 + 1) * height);
    assert.equal(raw[0], 0);
    assert.deepEqual(Array.from(raw.subarray(1, 1 + width * 3)), Array.from(rgb.subarray(0, width * 3)));
  });

  it("expands RGB to opaque RGBA", () => {
    const rgba = rgbToRgba(rgb, width, height);
    assert.equal(rgba.length, width * height * 4);
    assert.deepEqual(Array.from(rgba.subarray(0, 8)), [255, 0, 0, 255, 0, 255, 0, 255]);
  });
});
