export const COLOR_RED = 0;
export const COLOR_GREEN = 1;
export const COLOR_BLUE = 2;

// cells[y & 1][x & 1] gives the colour of the CFA sample at that position.
export const BAYER_PATTERNS = {
  rggb: { label: "RGGB", cells: [[COLOR_RED, COLOR_GREEN], [COLOR_GREEN, COLOR_BLUE]] },
  bggr: { label: "BGGR", cells: [[COLOR_BLUE, COLOR_GREEN], [COLOR_GREEN, COLOR_RED]] },
  grbg: { label: "GRBG", cells: [[COLOR_GREEN, COLOR_RED], [COLOR_BLUE, COLOR_GREEN]] },
  gbrg: { label: "GBRG", cells: [[COLOR_GREEN, COLOR_BLUE], [COLOR_RED, COLOR_GREEN]] },
  mono: { label: "MONO", cells: null },
};

export const PACKINGS = {
  mipi10: { label: "MIPI RAW10 packed (5 bytes / 4 px)", packed: true },
  mipi10lsbrev: { label: "MIPI RAW10 packed, reversed LSB order", packed: true },
  raw16le: { label: "Unpacked 16-bit little endian", packed: false },
  raw16be: { label: "Unpacked 16-bit big endian", packed: false },
};

export const TONE_CURVES = { srgb: "sRGB", gamma: "Gamma", linear: "Linear" };

export const DEMOSAIC_MODES = { bilinear: "Bilinear", binning: "2x2 binning", none: "None (grayscale)" };

export const RAW_MAX = 1023;

export function isPacked(packing) {
  return PACKINGS[packing]?.packed ?? true;
}

/** Bytes occupied by one image row, ignoring any extra hardware padding. */
export function bytesPerRow(width, packing) {
  if (!isPacked(packing)) return width * 2;
  // MIPI packs four pixels into five bytes; partial groups are padded out.
  return Math.ceil(width / 4) * 5;
}

export function frameByteLength(width, height, packing, stride = 0) {
  const rowBytes = stride > 0 ? stride : bytesPerRow(width, packing);
  return rowBytes * height;
}

export function frameCount(byteLength, width, height, packing, stride = 0, offset = 0) {
  const frameBytes = frameByteLength(width, height, packing, stride);
  if (frameBytes <= 0) return 0;
  return Math.max(0, Math.floor((byteLength - offset) / frameBytes));
}

const COMMON_WIDTHS = [
  320, 640, 720, 800, 960, 1024, 1280, 1288, 1296, 1440, 1600, 1620, 1632, 1920, 1928, 1936, 2048,
  2160, 2312, 2328, 2560, 2592, 2688, 3264, 3280, 3840, 4000, 4032, 4056, 4096, 4208, 4224, 5184,
  5344, 5472, 6528, 8000, 8192,
];

const PREFERRED_RATIOS = [4 / 3, 16 / 9, 3 / 2, 5 / 4, 1, 16 / 10];

const MAX_GUESSED_FRAMES = 8;

/**
 * Suggest width/height pairs whose frame size divides the file exactly, also
 * considering that the dump may hold several frames back to back. Sorted so
 * that the most photographic aspect ratios come first.
 */
export function guessDimensions(byteLength, packing = "mipi10", limit = 12) {
  const seen = new Set();
  const candidates = [];

  for (let frames = 1; frames <= MAX_GUESSED_FRAMES; frames += 1) {
    if (byteLength % frames !== 0) continue;
    const frameBytes = byteLength / frames;

    for (const width of COMMON_WIDTHS) {
      const rowBytes = bytesPerRow(width, packing);
      if (frameBytes % rowBytes !== 0) continue;
      const height = frameBytes / rowBytes;
      if (height < 64 || height > 12000) continue;
      const ratio = width / height;
      if (ratio < 0.4 || ratio > 4) continue;
      const key = `${width}x${height}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const ratioError = Math.min(...PREFERRED_RATIOS.map((r) => Math.abs(ratio - r) / r));
      candidates.push({ width, height, frames, ratioError });
    }
  }

  candidates.sort((a, b) => a.ratioError - b.ratioError || a.frames - b.frames || b.width - a.width);
  return candidates.slice(0, limit).map(({ width, height, frames }) => ({ width, height, frames }));
}

/** Pull "1920x1080" style hints out of a file name. */
export function parseDimensionsFromName(name = "") {
  const match = /(\d{3,5})\s*[x×*_-]\s*(\d{3,5})/i.exec(name);
  if (!match) return null;
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (!width || !height) return null;
  return { width, height };
}

export function parsePatternFromName(name = "") {
  const match = /(?:^|[^a-z0-9])(rggb|bggr|grbg|gbrg)(?:[^a-z0-9]|$)/i.exec(name);
  return match ? match[1].toLowerCase() : null;
}
