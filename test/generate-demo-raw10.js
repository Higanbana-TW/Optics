import { writeFile } from "node:fs/promises";

const width = 320;
const height = 200;
const output = process.argv[2] ?? "/tmp/raw10-demo.raw";
const packed = new Uint8Array((width / 4) * 5 * height);

function sceneColor(x, y) {
  const gradient = x / (width - 1);
  let color = [
    90 + 620 * gradient,
    130 + 500 * (y / (height - 1)),
    700 - 500 * gradient,
  ];

  if (x > 35 && x < 135 && y > 45 && y < 155) color = [900, 180, 120];
  if (x > 110 && x < 210 && y > 30 && y < 140) color = [130, 850, 300];
  if (x > 190 && x < 290 && y > 55 && y < 165) color = [140, 260, 930];
  return color.map((value) => Math.round(Math.min(1023, value)));
}

function bayerValue(x, y) {
  const [red, green, blue] = sceneColor(x, y);
  const channel = "RGGB"[(y & 1) * 2 + (x & 1)];
  return channel === "R" ? red : channel === "G" ? green : blue;
}

for (let y = 0; y < height; y += 1) {
  for (let x = 0; x < width; x += 4) {
    const values = [0, 1, 2, 3].map((offset) => bayerValue(x + offset, y));
    const target = y * (width / 4) * 5 + (x / 4) * 5;
    for (let index = 0; index < 4; index += 1) packed[target + index] = values[index] >> 2;
    packed[target + 4] =
      (values[0] & 3) |
      ((values[1] & 3) << 2) |
      ((values[2] & 3) << 4) |
      ((values[3] & 3) << 6);
  }
}

await writeFile(output, packed);
console.log(`Generated ${output}: ${width}x${height}, RGGB, ${packed.byteLength} bytes`);
