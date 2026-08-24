import { copyFile, mkdir, stat } from "node:fs/promises";
import { resolve } from "node:path";

const source = resolve("dist/index.html");
const releaseDirectory = resolve("release");
const destination = resolve(releaseDirectory, "RAW10-Lab-Offline.html");

await mkdir(releaseDirectory, { recursive: true });
await copyFile(source, destination);

const { size } = await stat(destination);
console.log(`Standalone file: ${destination} (${size} bytes)`);
