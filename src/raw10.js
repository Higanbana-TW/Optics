export const BAYER_PATTERNS = ["RGGB", "BGGR", "GRBG", "GBRG"];

export function packedRowBytes(width) {
  assertPositiveInteger(width, "影像寬度");
  return Math.ceil(width / 4) * 5;
}

export function requiredFileBytes(width, height, stride = packedRowBytes(width), offset = 0) {
  assertPositiveInteger(height, "影像高度");
  assertNonNegativeInteger(offset, "檔頭偏移");
  assertPositiveInteger(stride, "Row stride");

  const rowBytes = packedRowBytes(width);
  if (stride < rowBytes) {
    throw new Error(`Row stride 不可小於單列封包大小 ${rowBytes} bytes`);
  }
  return offset + (height - 1) * stride + rowBytes;
}

export function unpackRaw10(input, width, height, options = {}) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const offset = options.offset ?? 0;
  const stride = options.stride ?? packedRowBytes(width);
  const needed = requiredFileBytes(width, height, stride, offset);

  if (bytes.byteLength < needed) {
    throw new Error(
      `檔案大小不足：設定需要至少 ${needed.toLocaleString()} bytes，實際只有 ${bytes.byteLength.toLocaleString()} bytes`,
    );
  }

  const pixels = new Uint16Array(width * height);
  for (let y = 0; y < height; y += 1) {
    const rowStart = offset + y * stride;
    let x = 0;
    let source = rowStart;

    while (x < width) {
      const count = Math.min(4, width - x);
      const lowBits = bytes[source + 4];
      for (let index = 0; index < count; index += 1) {
        pixels[y * width + x + index] =
          (bytes[source + index] << 2) | ((lowBits >> (index * 2)) & 0x03);
      }
      x += count;
      source += 5;
    }
  }
  return pixels;
}

export function renderRaw10(pixels, width, height, options = {}) {
  if (!(pixels instanceof Uint16Array) || pixels.length !== width * height) {
    throw new Error("RAW 像素數量與設定的影像尺寸不符");
  }

  const pattern = options.pattern ?? "RGGB";
  const blackLevel = numberInRange(options.blackLevel ?? 64, 0, 1022, "黑階");
  const whiteLevel = numberInRange(options.whiteLevel ?? 1023, 1, 1023, "白階");
  const gamma = numberInRange(options.gamma ?? 2.2, 0.1, 5, "Gamma");
  const exposure = numberInRange(options.exposure ?? 1, 0.05, 16, "曝光");
  const gains = options.gains ?? { r: 1, g: 1, b: 1 };

  if (whiteLevel <= blackLevel) {
    throw new Error("白階必須大於黑階");
  }
  if (pattern !== "MONO" && !BAYER_PATTERNS.includes(pattern)) {
    throw new Error(`不支援的 Bayer 排列：${pattern}`);
  }

  const rgba = new Uint8ClampedArray(width * height * 4);
  const range = whiteLevel - blackLevel;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const pixelIndex = y * width + x;
      const outputIndex = pixelIndex * 4;

      if (pattern === "MONO") {
        const value = toneMap(pixels[pixelIndex], blackLevel, range, exposure, gamma);
        rgba[outputIndex] = value;
        rgba[outputIndex + 1] = value;
        rgba[outputIndex + 2] = value;
      } else {
        const red = interpolateChannel(pixels, width, height, x, y, pattern, "R");
        const green = interpolateChannel(pixels, width, height, x, y, pattern, "G");
        const blue = interpolateChannel(pixels, width, height, x, y, pattern, "B");
        rgba[outputIndex] = toneMap(red * gains.r, blackLevel, range, exposure, gamma);
        rgba[outputIndex + 1] = toneMap(green * gains.g, blackLevel, range, exposure, gamma);
        rgba[outputIndex + 2] = toneMap(blue * gains.b, blackLevel, range, exposure, gamma);
      }
      rgba[outputIndex + 3] = 255;
    }
  }
  return rgba;
}

export function calculateAutoWhiteBalance(pixels, width, height, pattern) {
  if (!BAYER_PATTERNS.includes(pattern)) return { r: 1, g: 1, b: 1 };

  const totals = { R: 0, G: 0, B: 0 };
  const counts = { R: 0, G: 0, B: 0 };
  const step = Math.max(1, Math.floor(Math.sqrt((width * height) / 250000)));

  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const channel = colorAt(x, y, pattern);
      totals[channel] += pixels[y * width + x];
      counts[channel] += 1;
    }
  }

  const means = {
    R: totals.R / Math.max(1, counts.R),
    G: totals.G / Math.max(1, counts.G),
    B: totals.B / Math.max(1, counts.B),
  };
  return {
    r: clamp(means.G / Math.max(1, means.R), 0.25, 4),
    g: 1,
    b: clamp(means.G / Math.max(1, means.B), 0.25, 4),
  };
}

export function encodeBmp(rgba, width, height) {
  const rowSize = Math.ceil((width * 3) / 4) * 4;
  const pixelBytes = rowSize * height;
  const buffer = new ArrayBuffer(54 + pixelBytes);
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);

  bytes[0] = 0x42;
  bytes[1] = 0x4d;
  view.setUint32(2, buffer.byteLength, true);
  view.setUint32(10, 54, true);
  view.setUint32(14, 40, true);
  view.setInt32(18, width, true);
  view.setInt32(22, height, true);
  view.setUint16(26, 1, true);
  view.setUint16(28, 24, true);
  view.setUint32(34, pixelBytes, true);
  view.setInt32(38, 2835, true);
  view.setInt32(42, 2835, true);

  for (let y = 0; y < height; y += 1) {
    const sourceRow = (height - 1 - y) * width * 4;
    const targetRow = 54 + y * rowSize;
    for (let x = 0; x < width; x += 1) {
      const source = sourceRow + x * 4;
      const target = targetRow + x * 3;
      bytes[target] = rgba[source + 2];
      bytes[target + 1] = rgba[source + 1];
      bytes[target + 2] = rgba[source];
    }
  }
  return new Blob([buffer], { type: "image/bmp" });
}

function interpolateChannel(pixels, width, height, x, y, pattern, target) {
  if (colorAt(x, y, pattern) === target) return pixels[y * width + x];

  let total = 0;
  let count = 0;
  for (let radius = 1; radius <= 2 && count === 0; radius += 1) {
    const minY = Math.max(0, y - radius);
    const maxY = Math.min(height - 1, y + radius);
    const minX = Math.max(0, x - radius);
    const maxX = Math.min(width - 1, x + radius);

    for (let sampleY = minY; sampleY <= maxY; sampleY += 1) {
      for (let sampleX = minX; sampleX <= maxX; sampleX += 1) {
        if (
          Math.max(Math.abs(sampleX - x), Math.abs(sampleY - y)) === radius &&
          colorAt(sampleX, sampleY, pattern) === target
        ) {
          total += pixels[sampleY * width + sampleX];
          count += 1;
        }
      }
    }
  }
  return count ? total / count : pixels[y * width + x];
}

function colorAt(x, y, pattern) {
  return pattern[(y & 1) * 2 + (x & 1)];
}

function toneMap(value, blackLevel, range, exposure, gamma) {
  const normalized = clamp(((value - blackLevel) / range) * exposure, 0, 1);
  return Math.round(Math.pow(normalized, 1 / gamma) * 255);
}

function numberInRange(value, min, max, name) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < min || number > max) {
    throw new Error(`${name}必須介於 ${min} 和 ${max} 之間`);
  }
  return number;
}

function assertPositiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`${name}必須是正整數`);
}

function assertNonNegativeInteger(value, name) {
  if (!Number.isInteger(value) || value < 0) throw new Error(`${name}必須是非負整數`);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
