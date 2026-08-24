import { BAYER_PATTERNS, RAW_MAX } from "./format.js";
import { unpackFrame } from "./unpack.js";

export const DEFAULT_OPTIONS = {
  width: 0,
  height: 0,
  packing: "mipi10",
  align: "lsb",
  stride: 0,
  offset: 0,
  pattern: "rggb",
  blackLevel: 64,
  whiteLevel: RAW_MAX,
  gains: [1, 1, 1],
  exposure: 0,
  tone: "srgb",
  gamma: 2.2,
  demosaic: "bilinear",
  auto: false,
};

const LUT_SIZE = 4096;

function buildToneLut(tone, gamma) {
  const lut = new Uint8Array(LUT_SIZE);
  const safeGamma = gamma > 0 ? gamma : 2.2;
  for (let i = 0; i < LUT_SIZE; i += 1) {
    const value = i / (LUT_SIZE - 1);
    let mapped;
    if (tone === "linear") mapped = value;
    else if (tone === "gamma") mapped = value ** (1 / safeGamma);
    else mapped = value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055;
    lut[i] = Math.round(255 * Math.min(1, Math.max(0, mapped)));
  }
  return lut;
}

function applyLut(lut, value) {
  if (!(value > 0)) return lut[0];
  if (value >= 1) return lut[LUT_SIZE - 1];
  return lut[(value * (LUT_SIZE - 1)) | 0];
}

/**
 * Collect per-channel statistics so black level, white balance and exposure can
 * be estimated from the frame itself (grey-world white balance plus percentile
 * based black/white points).
 */
export function analyzeSamples(samples, { width, height, pattern = "rggb" }) {
  const cells = BAYER_PATTERNS[pattern]?.cells ?? null;
  const histogram = new Uint32Array(RAW_MAX + 1);
  const sums = [0, 0, 0];
  const counts = [0, 0, 0];

  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    const cellRow = cells ? cells[y & 1] : null;
    for (let x = 0; x < width; x += 1) {
      const value = samples[row + x];
      histogram[value] += 1;
      const channel = cellRow ? cellRow[x & 1] : 1;
      sums[channel] += value;
      counts[channel] += 1;
    }
  }

  const total = width * height;
  const percentile = (fraction) => {
    const target = total * fraction;
    let seen = 0;
    for (let value = 0; value <= RAW_MAX; value += 1) {
      seen += histogram[value];
      if (seen >= target) return value;
    }
    return RAW_MAX;
  };

  const channelMeans = sums.map((sum, i) => (counts[i] ? sum / counts[i] : 0));
  const dimmestChannel = Math.min(...channelMeans.filter((mean, i) => counts[i] > 0));
  // A flat frame can push the dark percentile above a channel mean, which would
  // wipe that channel out; keep the black point below the dimmest channel.
  const blackLevel = Math.min(percentile(0.002), Math.max(0, Math.floor(dimmestChannel) - 1));
  const whiteLevel = Math.max(blackLevel + 1, percentile(0.998));
  const means = channelMeans.map((mean) => Math.max(1e-6, mean - blackLevel));
  const reference = means[1] || Math.max(means[0], means[2]) || 1;
  const gains = cells
    ? means.map((mean) => (mean > 1e-6 ? clampGain(reference / mean) : 1))
    : [1, 1, 1];

  return { blackLevel, whiteLevel, gains, means, histogram };
}

function clampGain(gain) {
  return Math.min(8, Math.max(0.125, Number(gain.toFixed(3))));
}

function normalizeSamples(samples, { blackLevel, whiteLevel, gains, exposure, width, height, pattern }) {
  const cells = BAYER_PATTERNS[pattern]?.cells ?? null;
  const range = Math.max(1, whiteLevel - blackLevel);
  const boost = 2 ** exposure;
  const scaled = [
    ((gains?.[0] ?? 1) * boost) / range,
    ((gains?.[1] ?? 1) * boost) / range,
    ((gains?.[2] ?? 1) * boost) / range,
  ];
  const out = new Float32Array(width * height);

  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    const cellRow = cells ? cells[y & 1] : null;
    for (let x = 0; x < width; x += 1) {
      const channel = cellRow ? cellRow[x & 1] : 1;
      out[row + x] = (samples[row + x] - blackLevel) * scaled[channel];
    }
  }
  return out;
}

function mirrorIndex(index, size) {
  if (index < 0) return -index;
  if (index >= size) return 2 * size - 2 - index;
  return index;
}

function buildMirrorTable(size) {
  const previous = new Int32Array(size);
  const next = new Int32Array(size);
  for (let i = 0; i < size; i += 1) {
    previous[i] = mirrorIndex(i - 1, size);
    next[i] = mirrorIndex(i + 1, size);
  }
  return { previous, next };
}

function demosaicBilinear(values, width, height, cells, lut) {
  const rgb = new Uint8ClampedArray(width * height * 3);
  const { previous: xPrev, next: xNext } = buildMirrorTable(width);
  const { previous: yPrev, next: yNext } = buildMirrorTable(height);

  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    const rowUp = yPrev[y] * width;
    const rowDown = yNext[y] * width;
    const cellRow = cells[y & 1];

    for (let x = 0; x < width; x += 1) {
      const left = xPrev[x];
      const right = xNext[x];
      const centre = values[row + x];
      const channel = cellRow[x & 1];

      let r;
      let g;
      let b;

      if (channel === 1) {
        g = centre;
        const horizontal = (values[row + left] + values[row + right]) * 0.5;
        const vertical = (values[rowUp + x] + values[rowDown + x]) * 0.5;
        if (cellRow[(x + 1) & 1] === 0) {
          r = horizontal;
          b = vertical;
        } else {
          r = vertical;
          b = horizontal;
        }
      } else {
        const cross =
          (values[row + left] + values[row + right] + values[rowUp + x] + values[rowDown + x]) * 0.25;
        const diagonal =
          (values[rowUp + left] + values[rowUp + right] + values[rowDown + left] + values[rowDown + right]) *
          0.25;
        g = cross;
        if (channel === 0) {
          r = centre;
          b = diagonal;
        } else {
          b = centre;
          r = diagonal;
        }
      }

      const dst = (row + x) * 3;
      rgb[dst] = applyLut(lut, r);
      rgb[dst + 1] = applyLut(lut, g);
      rgb[dst + 2] = applyLut(lut, b);
    }
  }
  return { width, height, rgb };
}

function demosaicBinning(values, width, height, cells, lut) {
  const outWidth = width >> 1;
  const outHeight = height >> 1;
  const rgb = new Uint8ClampedArray(outWidth * outHeight * 3);

  for (let y = 0; y < outHeight; y += 1) {
    const rowTop = 2 * y * width;
    const rowBottom = rowTop + width;
    for (let x = 0; x < outWidth; x += 1) {
      const left = 2 * x;
      const quad = [
        { value: values[rowTop + left], channel: cells[0][0] },
        { value: values[rowTop + left + 1], channel: cells[0][1] },
        { value: values[rowBottom + left], channel: cells[1][0] },
        { value: values[rowBottom + left + 1], channel: cells[1][1] },
      ];
      const sums = [0, 0, 0];
      const counts = [0, 0, 0];
      for (const { value, channel } of quad) {
        sums[channel] += value;
        counts[channel] += 1;
      }
      const dst = (y * outWidth + x) * 3;
      for (let channel = 0; channel < 3; channel += 1) {
        rgb[dst + channel] = applyLut(lut, counts[channel] ? sums[channel] / counts[channel] : 0);
      }
    }
  }
  return { width: outWidth, height: outHeight, rgb };
}

function toGrayscale(values, width, height, lut) {
  const rgb = new Uint8ClampedArray(width * height * 3);
  for (let i = 0; i < values.length; i += 1) {
    const gray = applyLut(lut, values[i]);
    const dst = i * 3;
    rgb[dst] = gray;
    rgb[dst + 1] = gray;
    rgb[dst + 2] = gray;
  }
  return { width, height, rgb };
}

/**
 * Full RAW10 -> 8-bit RGB pipeline: unpack, level, white balance, demosaic and
 * tone map. Returns interleaved RGB plus the settings that were actually used.
 */
export function processRaw(bytes, userOptions = {}) {
  const options = { ...DEFAULT_OPTIONS, ...userOptions };
  const { width, height } = options;
  const pattern = BAYER_PATTERNS[options.pattern] ? options.pattern : "rggb";
  const samples = unpackFrame(bytes, { ...options, width, height });

  let { blackLevel, whiteLevel, gains } = options;
  let stats = null;
  if (options.auto) {
    stats = analyzeSamples(samples, { width, height, pattern });
    blackLevel = stats.blackLevel;
    whiteLevel = stats.whiteLevel;
    gains = stats.gains;
  }

  const values = normalizeSamples(samples, {
    blackLevel,
    whiteLevel,
    gains,
    exposure: options.exposure,
    width,
    height,
    pattern,
  });

  const lut = buildToneLut(options.tone, options.gamma);
  const cells = BAYER_PATTERNS[pattern].cells;

  let image;
  if (!cells || options.demosaic === "none") image = toGrayscale(values, width, height, lut);
  else if (options.demosaic === "binning") image = demosaicBinning(values, width, height, cells, lut);
  else image = demosaicBilinear(values, width, height, cells, lut);

  return {
    ...image,
    samples,
    stats,
    settings: { ...options, pattern, blackLevel, whiteLevel, gains },
  };
}

export { buildToneLut, normalizeSamples };
