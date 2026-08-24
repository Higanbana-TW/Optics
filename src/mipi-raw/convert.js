/** 10-bit MIPI CSI-2 RAW unpacking, Bayer demosaic, and BMP encoding. */

export const MAX_10BIT = 1023;
export const BAYER_PATTERNS = ["RGGB", "GRBG", "GBRG", "BGGR"];

const LAYOUTS = {
  RGGB: [
    [0, 1],
    [1, 2],
  ],
  GRBG: [
    [1, 0],
    [2, 1],
  ],
  GBRG: [
    [1, 2],
    [0, 1],
  ],
  BGGR: [
    [2, 1],
    [1, 0],
  ],
};

export const COMMON_RESOLUTIONS = [
  [320, 240],
  [640, 480],
  [800, 600],
  [1024, 768],
  [1280, 720],
  [1280, 800],
  [1280, 960],
  [1440, 1080],
  [1600, 1200],
  [1632, 1224],
  [1920, 1080],
  [1920, 1200],
  [2048, 1536],
  [2304, 1296],
  [2304, 1536],
  [2304, 1728],
  [2560, 1440],
  [2592, 1944],
  [3264, 1836],
  [3264, 2448],
  [3280, 2464],
  [3840, 2160],
  [4000, 3000],
  [4032, 2268],
  [4032, 3024],
  [4056, 3040],
  [4096, 2160],
  [4096, 3072],
  [4208, 3120],
  [4624, 2604],
  [4624, 3472],
  [4656, 3496],
  [5344, 4016],
  [8000, 6000],
  [9152, 6944],
  [9248, 6944],
];

const ASPECTS = [
  [16, 9],
  [16, 10],
  [4, 3],
  [3, 2],
  [5, 4],
  [1, 1],
  [21, 9],
];

export function packedRowBytes(width) {
  if (width % 4 !== 0) {
    throw new Error("MIPI RAW10 寬度必須是 4 的倍數");
  }
  return (width * 5) / 4;
}

export function packRaw10Mipi(pixels, width, height) {
  const rowBytes = packedRowBytes(width);
  const out = new Uint8Array(rowBytes * height);
  let di = 0;
  for (let y = 0; y < height; y++) {
    const row = y * width;
    for (let x = 0; x < width; x += 4) {
      const p0 = pixels[row + x];
      const p1 = pixels[row + x + 1];
      const p2 = pixels[row + x + 2];
      const p3 = pixels[row + x + 3];
      out[di] = (p0 >> 2) & 0xff;
      out[di + 1] = (p1 >> 2) & 0xff;
      out[di + 2] = (p2 >> 2) & 0xff;
      out[di + 3] = (p3 >> 2) & 0xff;
      out[di + 4] =
        (p0 & 0x03) | ((p1 & 0x03) << 2) | ((p2 & 0x03) << 4) | ((p3 & 0x03) << 6);
      di += 5;
    }
  }
  return out;
}

export function unpackRaw10Mipi(data, width, height, { offset = 0, stride } = {}) {
  const rowBytes = packedRowBytes(width);
  const rowStride = stride ?? rowBytes;
  if (rowStride < rowBytes) {
    throw new Error(`列跨距 ${rowStride} 小於 RAW10 列長 ${rowBytes}`);
  }
  const needed = offset + rowStride * height;
  if (data.byteLength < needed) {
    throw new Error(`檔案資料不足：需要 ${needed} bytes，實際 ${data.byteLength} bytes`);
  }

  const src = data instanceof Uint8Array ? data : new Uint8Array(data);
  const pixels = new Uint16Array(width * height);
  let pi = 0;
  for (let y = 0; y < height; y++) {
    let si = offset + y * rowStride;
    for (let x = 0; x < width; x += 4) {
      const b0 = src[si];
      const b1 = src[si + 1];
      const b2 = src[si + 2];
      const b3 = src[si + 3];
      const b4 = src[si + 4];
      pixels[pi] = (b0 << 2) | (b4 & 0x03);
      pixels[pi + 1] = (b1 << 2) | ((b4 >> 2) & 0x03);
      pixels[pi + 2] = (b2 << 2) | ((b4 >> 4) & 0x03);
      pixels[pi + 3] = (b3 << 2) | ((b4 >> 6) & 0x03);
      pi += 4;
      si += 5;
    }
  }
  return pixels;
}

export function unpackU16(data, width, height, { offset = 0, stride, littleEndian = true, msbAligned = false } = {}) {
  const rowBytes = width * 2;
  const rowStride = stride ?? rowBytes;
  if (rowStride < rowBytes) {
    throw new Error(`列跨距 ${rowStride} 小於 16-bit 列長 ${rowBytes}`);
  }
  const needed = offset + rowStride * height;
  if (data.byteLength < needed) {
    throw new Error(`檔案資料不足：需要 ${needed} bytes，實際 ${data.byteLength} bytes`);
  }

  const view = new DataView(data.buffer ?? data, (data.byteOffset ?? 0) + offset);
  const pixels = new Uint16Array(width * height);
  for (let y = 0; y < height; y++) {
    const rowOffset = y * rowStride;
    for (let x = 0; x < width; x++) {
      let value = view.getUint16(rowOffset + x * 2, littleEndian);
      if (msbAligned) value >>= 6;
      pixels[y * width + x] = value & MAX_10BIT;
    }
  }
  return pixels;
}

function clamp(value, lo, hi) {
  return value < lo ? lo : value > hi ? hi : value;
}

function sample(raw, width, height, x, y) {
  return raw[clamp(y, 0, height - 1) * width + clamp(x, 0, width - 1)];
}

export function mosaicBayer(rgb, width, height, pattern = "RGGB") {
  const layout = LAYOUTS[pattern];
  if (!layout) throw new Error(`不支援的 Bayer 排列：${pattern}`);
  const raw = new Uint16Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const channel = layout[y & 1][x & 1];
      raw[y * width + x] = rgb[(y * width + x) * 3 + channel];
    }
  }
  return raw;
}

export function demosaicBilinear(raw, width, height, pattern = "RGGB") {
  const layout = LAYOUTS[pattern];
  if (!layout) throw new Error(`不支援的 Bayer 排列：${pattern}`);

  let redRow = 0;
  let blueRow = 1;
  for (let row = 0; row < 2; row++) {
    for (let col = 0; col < 2; col++) {
      if (layout[row][col] === 0) redRow = row;
      if (layout[row][col] === 2) blueRow = row;
    }
  }

  const rgb = new Float32Array(width * height * 3);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const channel = layout[y & 1][x & 1];
      const center = sample(raw, width, height, x, y);
      let r = 0;
      let g = 0;
      let b = 0;

      if (channel === 1) {
        g = center;
        if ((y & 1) === redRow) {
          r = (sample(raw, width, height, x - 1, y) + sample(raw, width, height, x + 1, y)) * 0.5;
          b = (sample(raw, width, height, x, y - 1) + sample(raw, width, height, x, y + 1)) * 0.5;
        } else {
          b = (sample(raw, width, height, x - 1, y) + sample(raw, width, height, x + 1, y)) * 0.5;
          r = (sample(raw, width, height, x, y - 1) + sample(raw, width, height, x, y + 1)) * 0.5;
        }
      } else if (channel === 0) {
        r = center;
        g =
          (sample(raw, width, height, x - 1, y) +
            sample(raw, width, height, x + 1, y) +
            sample(raw, width, height, x, y - 1) +
            sample(raw, width, height, x, y + 1)) *
          0.25;
        b =
          (sample(raw, width, height, x - 1, y - 1) +
            sample(raw, width, height, x + 1, y - 1) +
            sample(raw, width, height, x - 1, y + 1) +
            sample(raw, width, height, x + 1, y + 1)) *
          0.25;
      } else {
        b = center;
        g =
          (sample(raw, width, height, x - 1, y) +
            sample(raw, width, height, x + 1, y) +
            sample(raw, width, height, x, y - 1) +
            sample(raw, width, height, x, y + 1)) *
          0.25;
        r =
          (sample(raw, width, height, x - 1, y - 1) +
            sample(raw, width, height, x + 1, y - 1) +
            sample(raw, width, height, x - 1, y + 1) +
            sample(raw, width, height, x + 1, y + 1)) *
          0.25;
      }

      const i = (y * width + x) * 3;
      rgb[i] = r;
      rgb[i + 1] = g;
      rgb[i + 2] = b;
    }
  }
  return rgb;
}

export function applyBlackLevel(raw, blackLevel) {
  if (!blackLevel) return raw;
  const out = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    const value = raw[i] - blackLevel;
    out[i] = value < 0 ? 0 : value;
  }
  return out;
}

export function applyWhiteBalance(rgb, gains) {
  const out = new Float32Array(rgb.length);
  let gr = 1;
  let gg = 1;
  let gb = 1;
  if (!gains) {
    let rSum = 0;
    let gSum = 0;
    let bSum = 0;
    let rCount = 0;
    let gCount = 0;
    let bCount = 0;
    for (let i = 0; i < rgb.length; i += 3) {
      if (rgb[i] > 0) {
        rSum += rgb[i];
        rCount += 1;
      }
      if (rgb[i + 1] > 0) {
        gSum += rgb[i + 1];
        gCount += 1;
      }
      if (rgb[i + 2] > 0) {
        bSum += rgb[i + 2];
        bCount += 1;
      }
    }
    const rMean = rCount ? rSum / rCount : 1;
    const gMean = gCount ? gSum / gCount : 1;
    const bMean = bCount ? bSum / bCount : 1;
    gr = gMean / Math.max(rMean, 1e-6);
    gg = 1;
    gb = gMean / Math.max(bMean, 1e-6);
  } else {
    [gr, gg, gb] = gains;
  }
  for (let i = 0; i < rgb.length; i += 3) {
    out[i] = rgb[i] * gr;
    out[i + 1] = rgb[i + 1] * gg;
    out[i + 2] = rgb[i + 2] * gb;
  }
  return out;
}

export function toneMapToU8(rgb, mode = "shift") {
  const out = new Uint8Array(rgb.length);
  if (mode === "shift") {
    const scale = 255 / MAX_10BIT;
    for (let i = 0; i < rgb.length; i++) {
      const value = rgb[i] * scale;
      out[i] = value < 0 ? 0 : value > 255 ? 255 : value;
    }
    return out;
  }

  let lo = Infinity;
  let hi = -Infinity;
  if (mode === "percentile") {
    const sampleCount = Math.min(rgb.length, 200000);
    const step = Math.max(1, Math.floor(rgb.length / sampleCount));
    const samples = [];
    for (let i = 0; i < rgb.length; i += step) samples.push(rgb[i]);
    samples.sort((a, b) => a - b);
    lo = samples[Math.floor(samples.length * 0.01)];
    hi = samples[Math.min(samples.length - 1, Math.floor(samples.length * 0.995))];
  } else {
    for (let i = 0; i < rgb.length; i++) {
      const value = rgb[i];
      if (value < lo) lo = value;
      if (value > hi) hi = value;
    }
  }

  const scale = hi <= lo ? 0 : 255 / (hi - lo);
  for (let i = 0; i < rgb.length; i++) {
    const value = (rgb[i] - lo) * scale;
    out[i] = value < 0 ? 0 : value > 255 ? 255 : value;
  }
  return out;
}

export function rawToRgb(rawPixels, width, height, options = {}) {
  const {
    bayer = "RGGB",
    blackLevel = 0,
    whiteBalance = "auto",
    tone = "shift",
  } = options;
  const linear = applyBlackLevel(rawPixels, blackLevel);
  let rgb;
  if (bayer === "mono") {
    rgb = new Float32Array(width * height * 3);
    for (let i = 0; i < linear.length; i++) {
      const value = linear[i];
      rgb[i * 3] = value;
      rgb[i * 3 + 1] = value;
      rgb[i * 3 + 2] = value;
    }
  } else {
    rgb = demosaicBilinear(linear, width, height, bayer);
  }

  let gains = [1, 1, 1];
  if (whiteBalance === "auto" && bayer !== "mono") gains = null;
  else if (Array.isArray(whiteBalance)) gains = whiteBalance;
  rgb = applyWhiteBalance(rgb, gains);
  return toneMapToU8(rgb, tone);
}

export function expectedFrameBytes(width, height, fmt, stride) {
  if (fmt === "mipi10") {
    return (stride ?? packedRowBytes(width)) * height;
  }
  return (stride ?? width * 2) * height;
}

export function guessLayouts(fileSize, offset = 0) {
  const payload = fileSize - offset;
  if (payload <= 0) return [];
  const ranked = [];

  const add = (width, height, format, stride, score) => {
    if (width < 8 || height < 8 || stride <= 0) return;
    const frame = stride * height;
    if (frame <= 0 || payload < frame) return;
    const frames = payload % frame === 0 ? payload / frame : 1;
    if (payload % frame !== 0 && payload - frame > 65536) return;
    ranked.push({ width, height, format, stride, frames, score });
  };

  for (const [width, height] of COMMON_RESOLUTIONS) {
    if (width % 4 === 0) add(width, height, "mipi10", packedRowBytes(width), 100);
    add(width, height, "u16le", width * 2, 80);
  }

  if ((payload * 8) % 10 === 0) {
    const pixels = (payload * 8) / 10;
    for (const [aw, ah] of ASPECTS) {
      let width = Math.round(Math.sqrt((pixels * aw) / ah));
      width -= width % 4;
      if (width > 0 && pixels % width === 0) {
        const height = pixels / width;
        add(width, height, "mipi10", packedRowBytes(width), 60);
      }
    }
  }

  if (payload % 2 === 0) {
    const pixels = payload / 2;
    for (const [aw, ah] of ASPECTS) {
      const width = Math.round(Math.sqrt((pixels * aw) / ah));
      if (width > 0 && pixels % width === 0) {
        add(width, pixels / width, "u16le", width * 2, 40);
      }
    }
  }

  const unique = new Map();
  for (const item of ranked) {
    const key = `${item.width}x${item.height}-${item.format}-${item.stride}-${item.frames}`;
    const prev = unique.get(key);
    if (!prev || item.score > prev.score) unique.set(key, item);
  }
  return [...unique.values()].sort((a, b) => b.score - a.score || b.width * b.height - a.width * a.height);
}

export function makeSampleRgb(width = 640, height = 480) {
  const rgb = new Uint16Array(width * height * 3);
  const colors = [
    [MAX_10BIT, 0, 0],
    [0, MAX_10BIT, 0],
    [0, 0, MAX_10BIT],
    [MAX_10BIT, MAX_10BIT, MAX_10BIT],
    [0, MAX_10BIT, MAX_10BIT],
    [MAX_10BIT, 0, MAX_10BIT],
    [MAX_10BIT, MAX_10BIT, 0],
    [MAX_10BIT >> 1, MAX_10BIT >> 1, MAX_10BIT >> 1],
  ];
  const patchH = Math.max(1, Math.floor((height * 2) / 3));
  const patchW = Math.floor(width / colors.length);
  for (let index = 0; index < colors.length; index += 1) {
    const x0 = index * patchW;
    const x1 = index === colors.length - 1 ? width : (index + 1) * patchW;
    const [r, g, b] = colors[index];
    for (let y = 0; y < patchH; y += 1) {
      for (let x = x0; x < x1; x += 1) {
        const i = (y * width + x) * 3;
        rgb[i] = r;
        rgb[i + 1] = g;
        rgb[i + 2] = b;
      }
    }
  }
  for (let x = 0; x < width; x += 1) {
    const value = Math.round((x / Math.max(width - 1, 1)) * MAX_10BIT);
    for (let y = patchH; y < height; y += 1) {
      const i = (y * width + x) * 3;
      rgb[i] = value;
      rgb[i + 1] = value;
      rgb[i + 2] = value;
    }
  }
  return rgb;
}

export function makeSampleRaw10(width = 640, height = 480, pattern = "RGGB") {
  const rgb = makeSampleRgb(width, height);
  const cfa = mosaicBayer(rgb, width, height, pattern);
  return packRaw10Mipi(cfa, width, height);
}

export function encodeBmp(rgb, width, height) {
  const rowSize = Math.ceil((width * 3) / 4) * 4;
  const pixelBytes = rowSize * height;
  const fileSize = 54 + pixelBytes;
  const buffer = new ArrayBuffer(fileSize);
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);

  view.setUint8(0, 0x42);
  view.setUint8(1, 0x4d);
  view.setUint32(2, fileSize, true);
  view.setUint32(10, 54, true);
  view.setUint32(14, 40, true);
  view.setInt32(18, width, true);
  view.setInt32(22, height, true);
  view.setUint16(26, 1, true);
  view.setUint16(28, 24, true);
  view.setUint32(34, pixelBytes, true);

  for (let y = 0; y < height; y += 1) {
    let dest = 54 + (height - 1 - y) * rowSize;
    const srcRow = y * width * 3;
    for (let x = 0; x < width; x += 1) {
      const src = srcRow + x * 3;
      bytes[dest] = rgb[src + 2];
      bytes[dest + 1] = rgb[src + 1];
      bytes[dest + 2] = rgb[src];
      dest += 3;
    }
  }
  return new Blob([buffer], { type: "image/bmp" });
}

export function rgbToImageData(rgb, width, height) {
  const imageData = typeof ImageData === "function" ? new ImageData(width, height) : { data: new Uint8ClampedArray(width * height * 4), width, height };
  const data = imageData.data;
  for (let i = 0, p = 0; i < rgb.length; i += 3, p += 4) {
    data[p] = rgb[i];
    data[p + 1] = rgb[i + 1];
    data[p + 2] = rgb[i + 2];
    data[p + 3] = 255;
  }
  return imageData;
}

export function readRawPixels(data, width, height, fmt, options = {}) {
  const { offset = 0, stride, frame = 0 } = options;
  const frameBytes = expectedFrameBytes(width, height, fmt, stride);
  const start = offset + frame * frameBytes;
  if (fmt === "mipi10") return unpackRaw10Mipi(data, width, height, { offset: start, stride });
  if (fmt === "u16le") return unpackU16(data, width, height, { offset: start, stride, littleEndian: true });
  if (fmt === "u16be") return unpackU16(data, width, height, { offset: start, stride, littleEndian: false });
  if (fmt === "u16msb") {
    return unpackU16(data, width, height, { offset: start, stride, littleEndian: true, msbAligned: true });
  }
  throw new Error(`不支援的封包格式：${fmt}`);
}
