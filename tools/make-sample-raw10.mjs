#!/usr/bin/env node
import { writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { BAYER_PATTERNS, PACKINGS } from "../src/raw10/format.js";
import { buildSampleFile } from "../src/raw10/sample.js";

const USAGE = `產生測試用的 10-bit MIPI RAW 檔（合成畫面）

用法:
  node tools/make-sample-raw10.mjs [選項]

選項:
  -w, --width <n>     寬度（預設 640）
  -h, --height <n>    高度（預設 480）
  -p, --pattern <p>   ${Object.keys(BAYER_PATTERNS).join(" | ")}（預設 rggb）
      --packing <p>   ${Object.keys(PACKINGS).join(" | ")}（預設 mipi10）
      --frames <n>    連續影格數（預設 1）
  -o, --out <file>    輸出檔名（預設 samples/sample_<w>x<h>_<pattern>.raw10）
`;

function parseArgs(argv) {
  const aliases = { w: "width", h: "height", p: "pattern", o: "out" };
  const numeric = new Set(["width", "height", "frames"]);
  const options = {};
  for (let i = 0; i < argv.length; i += 1) {
    const raw = argv[i].replace(/^--?/, "");
    const [namePart, inlineValue] = raw.split("=");
    const name = aliases[namePart] ?? namePart;
    if (name === "help") {
      options.help = true;
      continue;
    }
    const value = inlineValue ?? argv[++i];
    options[name] = numeric.has(name) ? Number(value) : value;
  }
  return options;
}

async function main(argv) {
  const options = parseArgs(argv);
  if (options.help) {
    console.log(USAGE);
    return 0;
  }

  const width = options.width || 640;
  const height = options.height || 480;
  const pattern = (options.pattern || "rggb").toLowerCase();
  const packing = options.packing || "mipi10";
  const frames = Math.max(1, options.frames || 1);

  if (!BAYER_PATTERNS[pattern]) {
    console.error(`未知的 Bayer 排列：${pattern}`);
    return 1;
  }
  if (!PACKINGS[packing]) {
    console.error(`未知的封裝格式：${packing}`);
    return 1;
  }

  const bytes = buildSampleFile({ width, height, pattern, packing, frames });
  const outPath = resolve(options.out || `samples/sample_${width}x${height}_${pattern}.raw10`);
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, bytes);
  console.log(`✓ ${outPath}（${width}x${height}，${pattern}，${packing}，${frames} 張影格，${bytes.length} bytes）`);
  return 0;
}

main(process.argv.slice(2)).then((code) => {
  process.exitCode = code;
});
