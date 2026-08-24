#!/usr/bin/env node
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { basename, dirname, extname, join, resolve } from "node:path";
import { deflateSync } from "node:zlib";
import jpeg from "jpeg-js";

import {
  BAYER_PATTERNS,
  DEMOSAIC_MODES,
  PACKINGS,
  TONE_CURVES,
  bytesPerRow,
  frameByteLength,
  frameCount,
  guessDimensions,
  parseDimensionsFromName,
  parsePatternFromName,
} from "../src/raw10/format.js";
import { DEFAULT_OPTIONS, processRaw } from "../src/raw10/process.js";
import { encodeBmp, encodePng, rgbToRgba } from "../src/raw10/encode.js";

const FORMATS = { png: "png", jpg: "jpg", jpeg: "jpg", bmp: "bmp" };

const USAGE = `10-bit MIPI RAW 轉圖檔工具

用法:
  node tools/raw10-convert.mjs <輸入檔...> --width W --height H [選項]

必要參數:
  -w, --width <n>        影像寬度（像素）
  -h, --height <n>       影像高度（像素）
                         若檔名含有 1920x1080 之類的字樣可自動判斷

輸出:
  -o, --out <file>       單一輸出檔（副檔名決定格式）
  -d, --outdir <dir>     輸出資料夾（沿用輸入檔名）
  -f, --format <fmt>     png | jpg | bmp（預設 png）
  -q, --quality <1-100>  JPEG 品質（預設 92）

RAW 格式:
  -p, --pattern <p>      ${Object.keys(BAYER_PATTERNS).join(" | ")}（預設 rggb）
      --packing <p>      ${Object.keys(PACKINGS).join(" | ")}（預設 mipi10）
      --align <lsb|msb>  未打包 16-bit 時資料靠齊方式（預設 lsb）
      --stride <n>       每列位元組數，0 為自動（處理硬體 padding）
      --offset <n>       跳過檔頭位元組數（預設 0）
      --frame <n|all>    多張連拍時要輸出的影格（預設 0）

影像處理:
      --black <n>        黑階（預設 ${DEFAULT_OPTIONS.blackLevel}）
      --white <n>        白階（預設 ${DEFAULT_OPTIONS.whiteLevel}）
      --gains <r,g,b>    白平衡增益（預設 1,1,1）
      --ev <n>           曝光補償，單位 stop（預設 0）
      --tone <t>         ${Object.keys(TONE_CURVES).join(" | ")}（預設 srgb）
      --gamma <n>        tone=gamma 時的 gamma 值（預設 2.2）
      --demosaic <m>     ${Object.keys(DEMOSAIC_MODES).join(" | ")}（預設 bilinear）
  -a, --auto             自動估算黑白階與灰界白平衡

其他:
      --info             只印出檔案資訊與可能的解析度，不做轉換
      --json             以 JSON 格式輸出結果摘要
      --help             顯示本說明

範例:
  node tools/raw10-convert.mjs capture.raw -w 1920 -h 1080 -p bggr -o capture.png
  node tools/raw10-convert.mjs frames/*.raw -w 1280 -h 720 --auto -f jpg -d out/
  node tools/raw10-convert.mjs burst.raw10 -w 640 -h 480 --frame all -d out/
`;

const NUMERIC_FLAGS = new Set([
  "width",
  "height",
  "stride",
  "offset",
  "black",
  "white",
  "ev",
  "gamma",
  "quality",
]);

const ALIASES = {
  w: "width",
  h: "height",
  o: "out",
  d: "outdir",
  f: "format",
  q: "quality",
  p: "pattern",
  a: "auto",
};

export function parseArgs(argv) {
  const options = { inputs: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("-") || token === "-") {
      options.inputs.push(token);
      continue;
    }
    const raw = token.replace(/^--?/, "");
    const [namePart, inlineValue] = raw.split("=");
    const name = ALIASES[namePart] ?? namePart;

    if (name === "help" || name === "auto" || name === "json" || name === "info") {
      options[name] = true;
      continue;
    }
    const value = inlineValue ?? argv[++i];
    if (value === undefined) throw new Error(`選項 --${name} 缺少數值`);
    options[name] = NUMERIC_FLAGS.has(name) ? Number(value) : value;
    if (NUMERIC_FLAGS.has(name) && Number.isNaN(options[name])) {
      throw new Error(`選項 --${name} 需要數字，收到「${value}」`);
    }
  }
  return options;
}

function parseGains(text) {
  if (!text) return DEFAULT_OPTIONS.gains;
  const parts = String(text)
    .split(/[,:/\s]+/)
    .filter(Boolean)
    .map(Number);
  if (parts.length !== 3 || parts.some((value) => !Number.isFinite(value) || value <= 0)) {
    throw new Error(`--gains 需要三個正數，例如 --gains 1.9,1,1.6（收到「${text}」）`);
  }
  return parts;
}

function resolveFormat(options, outPath) {
  const explicit = options.format && FORMATS[String(options.format).toLowerCase()];
  if (explicit) return explicit;
  const ext = extname(outPath || "").slice(1).toLowerCase();
  return FORMATS[ext] ?? "png";
}

function encodeImage(image, format, quality) {
  if (format === "bmp") return encodeBmp(image.rgb, image.width, image.height);
  if (format === "jpg") {
    const rgba = rgbToRgba(image.rgb, image.width, image.height);
    return jpeg.encode({ data: Buffer.from(rgba.buffer), width: image.width, height: image.height }, quality)
      .data;
  }
  return encodePng(image.rgb, image.width, image.height, deflateSync);
}

function buildRawOptions(options, dimensions) {
  return {
    ...DEFAULT_OPTIONS,
    width: dimensions.width,
    height: dimensions.height,
    packing: options.packing ?? DEFAULT_OPTIONS.packing,
    align: options.align ?? DEFAULT_OPTIONS.align,
    stride: options.stride ?? 0,
    pattern: (options.pattern ?? dimensions.pattern ?? DEFAULT_OPTIONS.pattern).toLowerCase(),
    blackLevel: options.black ?? DEFAULT_OPTIONS.blackLevel,
    whiteLevel: options.white ?? DEFAULT_OPTIONS.whiteLevel,
    gains: parseGains(options.gains),
    exposure: options.ev ?? 0,
    tone: options.tone ?? DEFAULT_OPTIONS.tone,
    gamma: options.gamma ?? DEFAULT_OPTIONS.gamma,
    demosaic: options.demosaic ?? DEFAULT_OPTIONS.demosaic,
    auto: Boolean(options.auto),
  };
}

function resolveDimensions(options, inputPath, byteLength, packing) {
  let width = options.width;
  let height = options.height;
  const fromName = parseDimensionsFromName(basename(inputPath));
  if ((!width || !height) && fromName) {
    width = width || fromName.width;
    height = height || fromName.height;
  }
  if (!width || !height) {
    const guesses = guessDimensions(byteLength, packing);
    const hint = guesses.length
      ? `\n可能的解析度：${guesses.map((g) => `${g.width}x${g.height}`).join("、")}`
      : "";
    throw new Error(`請以 --width 與 --height 指定影像尺寸。${hint}`);
  }
  return { width, height, pattern: parsePatternFromName(basename(inputPath)) };
}

function describeFile(inputPath, bytes, packing, dimensions) {
  const info = {
    file: inputPath,
    bytes: bytes.length,
    packing,
    guesses: guessDimensions(bytes.length, packing).map((g) =>
      g.frames > 1 ? `${g.width}x${g.height}（${g.frames} 張影格）` : `${g.width}x${g.height}`,
    ),
  };
  if (dimensions) {
    info.width = dimensions.width;
    info.height = dimensions.height;
    info.bytesPerRow = bytesPerRow(dimensions.width, packing);
    info.frameBytes = frameByteLength(dimensions.width, dimensions.height, packing);
    info.frames = frameCount(bytes.length, dimensions.width, dimensions.height, packing);
  }
  return info;
}

function outputPathFor(options, inputPath, format, frameIndex, multiFrame) {
  const base = basename(inputPath, extname(inputPath));
  const suffix = multiFrame ? `_${String(frameIndex).padStart(4, "0")}` : "";
  if (options.out && !multiFrame) return resolve(options.out);
  const directory = options.outdir ? resolve(options.outdir) : dirname(resolve(inputPath));
  return join(directory, `${base}${suffix}.${format}`);
}

async function convertFile(inputPath, options) {
  const bytes = new Uint8Array(await readFile(inputPath));
  const packing = options.packing ?? DEFAULT_OPTIONS.packing;

  let dimensions = null;
  try {
    dimensions = resolveDimensions(options, inputPath, bytes.length, packing);
  } catch (error) {
    if (!options.info) throw error;
  }

  if (options.info) return { info: describeFile(inputPath, bytes, packing, dimensions) };

  const rawOptions = buildRawOptions(options, dimensions);
  const stride = rawOptions.stride > 0 ? rawOptions.stride : bytesPerRow(rawOptions.width, packing);
  const frameBytes = stride * rawOptions.height;
  const baseOffset = options.offset ?? 0;
  const available = Math.max(1, frameCount(bytes.length, rawOptions.width, rawOptions.height, packing, stride, baseOffset));

  const allFrames = String(options.frame ?? "0").toLowerCase() === "all";
  const frames = allFrames ? Array.from({ length: available }, (_, i) => i) : [Number(options.frame ?? 0) || 0];
  const format = resolveFormat(options, options.out);
  const quality = Math.min(100, Math.max(1, options.quality ?? 92));
  const results = [];

  for (const frameIndex of frames) {
    const offset = baseOffset + frameIndex * frameBytes;
    if (offset + frameBytes > bytes.length && frameIndex > 0) {
      throw new Error(`影格 ${frameIndex} 超出檔案範圍（檔案僅有 ${available} 張影格）`);
    }
    const image = processRaw(bytes, { ...rawOptions, offset });
    const encoded = encodeImage(image, format, quality);
    const outPath = outputPathFor(options, inputPath, format, frameIndex, frames.length > 1);
    await mkdir(dirname(outPath), { recursive: true });
    await writeFile(outPath, encoded);
    results.push({
      input: inputPath,
      output: outPath,
      frame: frameIndex,
      width: image.width,
      height: image.height,
      format,
      bytes: encoded.length,
      settings: {
        pattern: image.settings.pattern,
        packing,
        blackLevel: image.settings.blackLevel,
        whiteLevel: image.settings.whiteLevel,
        gains: image.settings.gains,
        exposure: image.settings.exposure,
        tone: image.settings.tone,
        demosaic: image.settings.demosaic,
      },
    });
  }
  return { results };
}

export async function main(argv) {
  let options;
  try {
    options = parseArgs(argv);
  } catch (error) {
    console.error(`錯誤：${error.message}`);
    return 1;
  }

  if (options.help || options.inputs.length === 0) {
    console.log(USAGE);
    return options.help ? 0 : 1;
  }

  const summary = [];
  const infos = [];
  for (const input of options.inputs) {
    try {
      const { results, info } = await convertFile(input, options);
      if (info) {
        infos.push(info);
        if (!options.json) {
          console.log(`${info.file}：${info.bytes} bytes（${info.packing}）`);
          if (info.width) {
            console.log(`  尺寸 ${info.width}x${info.height}，每列 ${info.bytesPerRow} bytes，共 ${info.frames} 張影格`);
          }
          if (info.guesses.length) console.log(`  可能的解析度：${info.guesses.join("、")}`);
        }
        continue;
      }
      summary.push(...results);
      if (!options.json) {
        for (const item of results) {
          console.log(`✓ ${item.input} → ${item.output}（${item.width}x${item.height}，${item.format}）`);
        }
      }
    } catch (error) {
      console.error(`✗ ${input}：${error.message}`);
      return 1;
    }
  }

  if (options.json) console.log(JSON.stringify(options.info ? infos : summary, null, 2));
  return 0;
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname);
if (invokedDirectly) {
  main(process.argv.slice(2)).then((code) => {
    process.exitCode = code;
  });
}
