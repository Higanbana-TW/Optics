import { BAYER_PATTERNS } from "./format.js";
import { packFrame } from "./unpack.js";

const COLOR_BARS = [
  [0.85, 0.85, 0.85],
  [0.85, 0.85, 0.12],
  [0.12, 0.82, 0.85],
  [0.12, 0.8, 0.15],
  [0.85, 0.14, 0.78],
  [0.85, 0.16, 0.14],
  [0.14, 0.16, 0.82],
  [0.05, 0.05, 0.06],
];

// Sensors rarely see a neutral scene, so bake in a warm illuminant to give the
// automatic white balance something real to correct.
const ILLUMINANT = [0.62, 1.0, 0.78];
export const SAMPLE_BLACK_LEVEL = 64;
export const SAMPLE_WHITE_LEVEL = 1000;

/** Cheap per-pixel hash so the synthetic frame carries sensor-like grain. */
function shotNoise(x, y) {
  let hash = (x * 374761393 + y * 668265263) | 0;
  hash = Math.imul(hash ^ (hash >>> 13), 1274126177);
  return ((hash ^ (hash >>> 16)) >>> 0) / 4294967295 - 0.5;
}

function scenePixel(x, y, width, height, phase) {
  const u = x / width;
  const v = y / height;

  if (v < 0.28) {
    return COLOR_BARS[Math.min(COLOR_BARS.length - 1, Math.floor(u * COLOR_BARS.length))];
  }

  if (v > 0.78) {
    const step = Math.floor(u * 11) / 10;
    return [step, step, step];
  }

  const cx = (u - 0.32) * 2.2;
  const cy = (v - 0.53) * 2.2;
  const radius = Math.hypot(cx, cy);
  if (radius < 0.42) {
    const shade = 0.35 + 0.6 * Math.cos(radius * 3.6);
    return [shade, shade * 0.42, shade * 0.2];
  }

  const cx2 = (u - 0.72) * 2.2;
  const radius2 = Math.hypot(cx2, cy);
  if (radius2 < 0.3) {
    const rings = 0.5 + 0.45 * Math.sin(radius2 * 90 + phase);
    return [rings * 0.3, rings * 0.55, rings];
  }

  const sky = 0.18 + 0.55 * (1 - v) + 0.12 * Math.sin(u * 6.283 + phase);
  return [sky * 0.55, sky * 0.72, sky];
}

/** Build one synthetic CFA frame of 0..1023 samples. */
export function buildSampleFrame({ width = 640, height = 480, pattern = "rggb", phase = 0 } = {}) {
  const cells = BAYER_PATTERNS[pattern]?.cells ?? null;
  const samples = new Uint16Array(width * height);
  const span = SAMPLE_WHITE_LEVEL - SAMPLE_BLACK_LEVEL;

  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      const rgb = scenePixel(x, y, width, height, phase);
      const channel = cells ? cells[y & 1][x & 1] : 1;
      const linear = cells
        ? rgb[channel] * ILLUMINANT[channel]
        : 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
      const value = SAMPLE_BLACK_LEVEL + (linear + shotNoise(x, y) * 0.012) * span;
      samples[row + x] = Math.max(0, Math.min(1023, Math.round(value)));
    }
  }
  return samples;
}

/** Build a complete RAW file (optionally several frames) ready to be written out. */
export function buildSampleFile({
  width = 640,
  height = 480,
  pattern = "rggb",
  packing = "mipi10",
  frames = 1,
} = {}) {
  const chunks = [];
  for (let frame = 0; frame < frames; frame += 1) {
    const samples = buildSampleFrame({ width, height, pattern, phase: (frame * Math.PI) / 4 });
    chunks.push(packFrame(samples, { width, height, packing }));
  }

  const bytes = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
  chunks.reduce((offset, chunk) => {
    bytes.set(chunk, offset);
    return offset + chunk.length;
  }, 0);
  return bytes;
}
