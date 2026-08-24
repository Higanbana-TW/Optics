import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import jpeg from "jpeg-js";

import { packFrame } from "../src/raw10/unpack.js";
import { main, parseArgs } from "../tools/raw10-convert.mjs";

const WIDTH = 640;
const HEIGHT = 480;
const FRAMES = 3;

let workDir;
let rawPath;

function buildFrames() {
  const chunks = [];
  for (let frame = 0; frame < FRAMES; frame += 1) {
    const samples = new Uint16Array(WIDTH * HEIGHT);
    for (let y = 0; y < HEIGHT; y += 1) {
      for (let x = 0; x < WIDTH; x += 1) {
        samples[y * WIDTH + x] = 64 + ((x * 8 + y * 4 + frame * 90) % 900);
      }
    }
    chunks.push(packFrame(samples, { width: WIDTH, height: HEIGHT, packing: "mipi10" }));
  }
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const bytes = new Uint8Array(total);
  chunks.reduce((offset, chunk) => {
    bytes.set(chunk, offset);
    return offset + chunk.length;
  }, 0);
  return bytes;
}

function pngSize(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

/** Run the CLI while keeping its logging out of the test report. */
async function runCli(args) {
  const log = console.log;
  const error = console.error;
  const output = [];
  console.log = (...parts) => output.push(parts.join(" "));
  console.error = (...parts) => output.push(parts.join(" "));
  try {
    const code = await main(args);
    return { code, output: output.join("\n") };
  } finally {
    console.log = log;
    console.error = error;
  }
}

before(async () => {
  workDir = await mkdtemp(join(tmpdir(), "raw10-cli-"));
  rawPath = join(workDir, `burst_${WIDTH}x${HEIGHT}_rggb.raw10`);
  await writeFile(rawPath, buildFrames());
});

after(async () => {
  await rm(workDir, { recursive: true, force: true });
});

describe("command line arguments", () => {
  it("understands aliases, inline values and flags", () => {
    const options = parseArgs(["a.raw", "-w", "640", "--height=480", "--auto", "-f", "jpg", "b.raw"]);
    assert.deepEqual(options.inputs, ["a.raw", "b.raw"]);
    assert.equal(options.width, 640);
    assert.equal(options.height, 480);
    assert.equal(options.auto, true);
    assert.equal(options.format, "jpg");
  });

  it("rejects non-numeric sizes", () => {
    assert.throws(() => parseArgs(["a.raw", "--width", "wide"]), /需要數字/);
  });
});

describe("raw10-convert CLI", () => {
  it("writes a PNG with the requested dimensions", async () => {
    const outPath = join(workDir, "frame.png");
    const { code } = await runCli([rawPath, "-w", String(WIDTH), "-h", String(HEIGHT), "-o", outPath]);
    assert.equal(code, 0);
    const bytes = new Uint8Array(await readFile(outPath));
    assert.deepEqual(Array.from(bytes.subarray(0, 4)), [0x89, 0x50, 0x4e, 0x47]);
    assert.deepEqual(pngSize(bytes), { width: WIDTH, height: HEIGHT });
  });

  it("writes a decodable JPEG", async () => {
    const outPath = join(workDir, "frame.jpg");
    const { code } = await runCli([rawPath, "-o", outPath, "--auto", "-q", "90"]);
    assert.equal(code, 0);
    const decoded = jpeg.decode(await readFile(outPath));
    assert.equal(decoded.width, WIDTH);
    assert.equal(decoded.height, HEIGHT);
  });

  it("writes a BMP whose header matches the image", async () => {
    const outPath = join(workDir, "frame.bmp");
    const { code } = await runCli([rawPath, "-o", outPath, "-f", "bmp"]);
    assert.equal(code, 0);
    const bytes = new Uint8Array(await readFile(outPath));
    const view = new DataView(bytes.buffer);
    assert.equal(bytes[0], 0x42);
    assert.equal(view.getInt32(18, true), WIDTH);
    assert.equal(view.getInt32(22, true), HEIGHT);
  });

  it("takes the resolution from the file name", async () => {
    const outDir = join(workDir, "named");
    const { code } = await runCli([rawPath, "-d", outDir]);
    assert.equal(code, 0);
    const files = await readdir(outDir);
    assert.deepEqual(files, [`burst_${WIDTH}x${HEIGHT}_rggb.png`]);
  });

  it("exports every frame of a burst", async () => {
    const outDir = join(workDir, "all");
    const { code } = await runCli([rawPath, "--frame", "all", "-d", outDir, "-f", "bmp"]);
    assert.equal(code, 0);
    const files = (await readdir(outDir)).sort();
    assert.equal(files.length, FRAMES);
    assert.ok(files[0].endsWith("_0000.bmp"));
  });

  it("halves the output size when binning", async () => {
    const outPath = join(workDir, "binned.png");
    const { code } = await runCli([rawPath, "-o", outPath, "--demosaic", "binning"]);
    assert.equal(code, 0);
    assert.deepEqual(pngSize(new Uint8Array(await readFile(outPath))), {
      width: WIDTH / 2,
      height: HEIGHT / 2,
    });
  });

  it("reports file information without converting", async () => {
    const { code, output } = await runCli([rawPath, "--info"]);
    assert.equal(code, 0);
    assert.match(output, new RegExp(`${WIDTH}x${HEIGHT}`));
    assert.match(output, /3 張影格/);
  });

  it("fails clearly when the size is unknown", async () => {
    const plainPath = join(workDir, "unknown.raw");
    await writeFile(plainPath, await readFile(rawPath));
    const { code, output } = await runCli([plainPath]);
    assert.equal(code, 1);
    assert.match(output, /請以 --width 與 --height 指定影像尺寸/);
  });
});
