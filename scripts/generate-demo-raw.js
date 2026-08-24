import { writeFile } from "node:fs/promises";

const width = 320;
const height = 240;
const stride = (width / 4) * 5;
const output = new Uint8Array(stride * height);
const pattern = "RGGB";

function sensorValue(x, y) {
  const color = pattern[(y % 2) * 2 + (x % 2)];
  const horizontal = x / (width - 1);
  const vertical = y / (height - 1);
  if (color === "R") return Math.round(80 + horizontal * 900);
  if (color === "G") return Math.round(70 + vertical * 850);
  return Math.round(90 + (1 - horizontal) * 820);
}

for (let y = 0; y < height; y += 1) {
  for (let x = 0; x < width; x += 4) {
    const target = y * stride + (x / 4) * 5;
    let lowBits = 0;
    for (let index = 0; index < 4; index += 1) {
      const value = sensorValue(x + index, y);
      output[target + index] = value >> 2;
      lowBits |= (value & 0x03) << (index * 2);
    }
    output[target + 4] = lowBits;
  }
}

const destination = process.argv[2] ?? "/tmp/raw10-demo-320x240.raw";
await writeFile(destination, output);
console.log(`${destination} (${width}x${height}, ${output.byteLength} bytes)`);
