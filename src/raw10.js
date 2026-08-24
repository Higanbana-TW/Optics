export const BAYER_PATTERNS = ["RGGB", "BGGR", "GRBG", "GBRG"];

export function packedRowBytes(width) {
  if (!Number.isInteger(width) || width <= 0) {
    throw new Error("影像寬度必須是正整數");
  }
  return Math.ceil(width / 4) * 5;
}

export function expectedRaw10Bytes(width, height, stride = packedRowBytes(width)) {
  if (!Number.isInteger(height) || height <= 0) {
    throw new Error("影像高度必須是正整數");
  }
  if (!Number.isInteger(stride) || stride < packedRowBytes(width)) {
    throw new Error(`Row stride 不可小於 ${packedRowBytes(width)} bytes`);
  }
  return stride * height;
}

export function unpackRaw10(bytes, width, height, stride = packedRowBytes(width)) {
  const requiredBytes = expectedRaw10Bytes(width, height, stride);
  if (!(bytes instanceof Uint8Array)) {
    throw new TypeError("RAW10 資料必須是 Uint8Array");
  }
  if (bytes.byteLength < requiredBytes) {
    throw new Error(`檔案太小：需要 ${requiredBytes} bytes，實際只有 ${bytes.byteLength} bytes`);
  }

  const pixels = new Uint16Array(width * height);

  for (let y = 0; y < height; y += 1) {
    const rowOffset = y * stride;
    for (let x = 0; x < width; x += 4) {
      const source = rowOffset + Math.floor(x / 4) * 5;
      const lowBits = bytes[source + 4];
      const pixelsInGroup = Math.min(4, width - x);

      for (let index = 0; index < pixelsInGroup; index += 1) {
        pixels[y * width + x + index] =
          (bytes[source + index] << 2) | ((lowBits >> (index * 2)) & 0x03);
      }
    }
  }

  return pixels;
}

function colorAt(pattern, x, y) {
  return pattern[(y & 1) * 2 + (x & 1)];
}

function sampleChannel(pixels, width, height, pattern, x, y, channel) {
  if (colorAt(pattern, x, y) === channel) {
    return pixels[y * width + x];
  }

  let total = 0;
  let count = 0;

  for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
    const sampleY = y + offsetY;
    if (sampleY < 0 || sampleY >= height) continue;

    for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
      const sampleX = x + offsetX;
      if (sampleX < 0 || sampleX >= width || (offsetX === 0 && offsetY === 0)) continue;
      if (colorAt(pattern, sampleX, sampleY) !== channel) continue;

      total += pixels[sampleY * width + sampleX];
      count += 1;
    }
  }

  return count ? total / count : pixels[y * width + x];
}

export function demosaicRaw10(
  pixels,
  width,
  height,
  { pattern = "RGGB", blackLevel = 64, whiteLevel = 1023 } = {},
) {
  if (!(pixels instanceof Uint16Array) || pixels.length !== width * height) {
    throw new Error("像素資料尺寸與寬高不符");
  }
  if (!BAYER_PATTERNS.includes(pattern)) {
    throw new Error(`不支援的 Bayer 排列：${pattern}`);
  }
  if (!Number.isFinite(blackLevel) || !Number.isFinite(whiteLevel) || whiteLevel <= blackLevel) {
    throw new Error("白電平必須大於黑電平");
  }

  const rgba = new Uint8ClampedArray(width * height * 4);
  const scale = 255 / (whiteLevel - blackLevel);
  const normalize = (value) => Math.round(Math.max(0, Math.min(255, (value - blackLevel) * scale)));

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const output = (y * width + x) * 4;
      rgba[output] = normalize(sampleChannel(pixels, width, height, pattern, x, y, "R"));
      rgba[output + 1] = normalize(sampleChannel(pixels, width, height, pattern, x, y, "G"));
      rgba[output + 2] = normalize(sampleChannel(pixels, width, height, pattern, x, y, "B"));
      rgba[output + 3] = 255;
    }
  }

  return rgba;
}

export function encodeBmp(rgba, width, height) {
  if (!(rgba instanceof Uint8ClampedArray) || rgba.length !== width * height * 4) {
    throw new Error("RGBA 資料尺寸與寬高不符");
  }

  const headerSize = 54;
  const pixelBytes = width * height * 4;
  const buffer = new ArrayBuffer(headerSize + pixelBytes);
  const view = new DataView(buffer);
  const output = new Uint8Array(buffer);

  output[0] = 0x42;
  output[1] = 0x4d;
  view.setUint32(2, buffer.byteLength, true);
  view.setUint32(10, headerSize, true);
  view.setUint32(14, 40, true);
  view.setInt32(18, width, true);
  view.setInt32(22, height, true);
  view.setUint16(26, 1, true);
  view.setUint16(28, 32, true);
  view.setUint32(34, pixelBytes, true);

  for (let y = 0; y < height; y += 1) {
    const bmpY = height - 1 - y;
    for (let x = 0; x < width; x += 1) {
      const source = (y * width + x) * 4;
      const target = headerSize + (bmpY * width + x) * 4;
      output[target] = rgba[source + 2];
      output[target + 1] = rgba[source + 1];
      output[target + 2] = rgba[source];
      output[target + 3] = 255;
    }
  }

  return new Blob([buffer], { type: "image/bmp" });
}
