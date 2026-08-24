import "./style.css";
import "./raw10.css";

import {
  bytesPerRow,
  frameCount,
  guessDimensions,
  parseDimensionsFromName,
  parsePatternFromName,
} from "./raw10/format.js";
import { DEFAULT_OPTIONS, processRaw } from "./raw10/process.js";
import { encodeBmp, rgbToRgba } from "./raw10/encode.js";
import { buildSampleFile } from "./raw10/sample.js";

const $ = (selector) => document.querySelector(selector);

const previewStage = $("#previewStage");
const canvas = $("#previewCanvas");
const context = canvas.getContext("2d");
const loadingState = $("#loadingState");
const toast = $("#toast");
const sourceLabel = $("#sourceLabel");
const statusDot = $(".status-dot");
const previewInfo = $("#previewInfo");
const fileNameLabel = $("#fileName");
const fileMetaLabel = $("#fileMeta");
const fileInput = $("#fileInput");
const sizeGuesses = $("#sizeGuesses");
const sizeChips = $("#sizeChips");
const frameField = $("#frameField");
const frameSelect = $("#frameSelect");
const qualityRange = $("#qualityRange");
const qualityValue = $("#qualityValue");
const exposureRange = $("#exposureRange");
const exposureValue = $("#exposureValue");
const gammaField = $("#gammaField");
const alignField = $("#alignField");

const controls = {
  width: $("#widthInput"),
  height: $("#heightInput"),
  stride: $("#strideInput"),
  offset: $("#offsetInput"),
  packing: $("#packingSelect"),
  align: $("#alignSelect"),
  pattern: $("#patternSelect"),
  demosaic: $("#demosaicSelect"),
  black: $("#blackInput"),
  white: $("#whiteInput"),
  gainR: $("#gainR"),
  gainG: $("#gainG"),
  gainB: $("#gainB"),
  tone: $("#toneSelect"),
  gamma: $("#gammaInput"),
};

const MIME_TYPES = { png: "image/png", jpg: "image/jpeg", bmp: "image/bmp" };

let fileBytes = null;
let fileLabel = "";
let currentImage = null;
let renderTimer = null;
let toastTimer = null;

function showToast(message, type = "") {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast ${type}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3600);
}

function formatBytes(value) {
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}

function baseName(name) {
  return name.replace(/\.[^./\\]+$/, "") || "raw10";
}

function readSettings() {
  const frameIndex = Number(frameSelect.value || 0);
  const width = Math.max(2, Math.round(Number(controls.width.value) || 0));
  const height = Math.max(2, Math.round(Number(controls.height.value) || 0));
  const packing = controls.packing.value;
  const stride = Math.max(0, Math.round(Number(controls.stride.value) || 0));
  const rowBytes = stride > 0 ? stride : bytesPerRow(width, packing);

  return {
    ...DEFAULT_OPTIONS,
    width,
    height,
    packing,
    align: controls.align.value,
    stride,
    offset: Math.max(0, Math.round(Number(controls.offset.value) || 0)) + frameIndex * rowBytes * height,
    pattern: controls.pattern.value,
    demosaic: controls.demosaic.value,
    blackLevel: Number(controls.black.value) || 0,
    whiteLevel: Number(controls.white.value) || 1023,
    gains: [Number(controls.gainR.value) || 1, Number(controls.gainG.value) || 1, Number(controls.gainB.value) || 1],
    exposure: Number(exposureRange.value) || 0,
    tone: controls.tone.value,
    gamma: Number(controls.gamma.value) || 2.2,
  };
}

function applySettings(settings) {
  controls.black.value = Math.round(settings.blackLevel);
  controls.white.value = Math.round(settings.whiteLevel);
  controls.gainR.value = Number(settings.gains[0]).toFixed(2);
  controls.gainG.value = Number(settings.gains[1]).toFixed(2);
  controls.gainB.value = Number(settings.gains[2]).toFixed(2);
}

function syncDependentFields() {
  const packed = controls.packing.value.startsWith("mipi");
  alignField.hidden = packed;
  gammaField.hidden = controls.tone.value !== "gamma";
  exposureValue.textContent = `${Number(exposureRange.value) >= 0 ? "+" : ""}${Number(exposureRange.value).toFixed(1)} EV`;
  qualityValue.textContent = qualityRange.value;
}

function updateFrameOptions() {
  if (!fileBytes) return;
  const width = Number(controls.width.value) || 0;
  const height = Number(controls.height.value) || 0;
  const stride = Number(controls.stride.value) || 0;
  const offset = Number(controls.offset.value) || 0;
  const total = frameCount(fileBytes.length, width, height, controls.packing.value, stride, offset);

  if (total <= 1) {
    frameField.hidden = true;
    frameSelect.innerHTML = "";
    return;
  }

  const previous = Number(frameSelect.value || 0);
  frameSelect.innerHTML = "";
  for (let i = 0; i < total; i += 1) {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = `第 ${i + 1} / ${total} 張`;
    frameSelect.append(option);
  }
  frameSelect.value = String(Math.min(previous, total - 1));
  frameField.hidden = false;
}

function renderSizeChips() {
  if (!fileBytes) return;
  const guesses = guessDimensions(fileBytes.length, controls.packing.value, 8);
  sizeChips.innerHTML = "";
  if (!guesses.length) {
    sizeGuesses.hidden = true;
    return;
  }

  for (const { width, height } of guesses) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = `${width}×${height}`;
    chip.classList.toggle(
      "active",
      Number(controls.width.value) === width && Number(controls.height.value) === height,
    );
    chip.addEventListener("click", () => {
      controls.width.value = String(width);
      controls.height.value = String(height);
      updateFrameOptions();
      renderSizeChips();
      scheduleRender({ auto: true });
    });
    sizeChips.append(chip);
  }
  sizeGuesses.hidden = false;
}

function drawImage(image) {
  canvas.width = image.width;
  canvas.height = image.height;
  const imageData = new ImageData(rgbToRgba(image.rgb, image.width, image.height), image.width, image.height);
  context.putImageData(imageData, 0, 0);
  previewStage.classList.add("has-image");
}

async function render({ auto = false } = {}) {
  if (!fileBytes) return;
  const settings = readSettings();
  const pixels = settings.width * settings.height;
  if (!(pixels > 0) || pixels > 120e6) {
    showToast("影像尺寸不合理，請重新確認寬高", "error");
    return;
  }

  const rowBytes = settings.stride > 0 ? settings.stride : bytesPerRow(settings.width, settings.packing);
  const needed = settings.offset + rowBytes * settings.height;
  if (needed > fileBytes.length) {
    showToast(
      `資料不足：此設定需要 ${formatBytes(needed)}，檔案只有 ${formatBytes(fileBytes.length)}`,
      "error",
    );
  }

  const heavy = pixels > 2e6;
  if (heavy) loadingState.classList.remove("hidden");
  await new Promise((resolve) => requestAnimationFrame(resolve));

  try {
    const start = performance.now();
    const image = processRaw(fileBytes, { ...settings, auto });
    const elapsed = performance.now() - start;
    currentImage = image;
    drawImage(image);
    if (auto) applySettings(image.settings);
    previewInfo.textContent = `${image.width} × ${image.height} · ${settings.pattern.toUpperCase()} · ${elapsed.toFixed(0)} ms`;
  } catch (error) {
    showToast(`轉換失敗：${error.message}`, "error");
  } finally {
    loadingState.classList.add("hidden");
  }
}

function scheduleRender(options = {}) {
  window.clearTimeout(renderTimer);
  renderTimer = window.setTimeout(() => render(options), 120);
}

function setFile(bytes, name) {
  fileBytes = bytes;
  fileLabel = name;

  const named = parseDimensionsFromName(name);
  const guesses = guessDimensions(bytes.length, controls.packing.value, 8);
  const dimensions = named ?? guesses[0];
  if (dimensions) {
    controls.width.value = String(dimensions.width);
    controls.height.value = String(dimensions.height);
  }
  const pattern = parsePatternFromName(name);
  if (pattern) controls.pattern.value = pattern;

  controls.offset.value = "0";
  frameSelect.innerHTML = "";
  updateFrameOptions();
  renderSizeChips();

  sourceLabel.textContent = name;
  statusDot.classList.add("active");
  fileNameLabel.textContent = name;
  fileMetaLabel.textContent = `${formatBytes(bytes.length)} · ${bytes.length.toLocaleString("en-US")} bytes${
    dimensions ? "" : " · 請手動輸入寬高"
  }`;

  render({ auto: true });
}

async function loadFile(file) {
  if (!file) return;
  try {
    const buffer = await file.arrayBuffer();
    setFile(new Uint8Array(buffer), file.name);
  } catch (error) {
    showToast(`無法讀取檔案：${error.message}`, "error");
  }
}

function loadDemo() {
  const width = 1280;
  const height = 960;
  const bytes = buildSampleFile({ width, height, pattern: "rggb", packing: "mipi10", frames: 3 });
  controls.packing.value = "mipi10";
  setFile(bytes, `demo_${width}x${height}_rggb.raw10`);
  showToast("已載入合成示範檔（3 張影格）");
}

function toBlob(format, quality) {
  if (format === "bmp") {
    return Promise.resolve(
      new Blob([encodeBmp(currentImage.rgb, currentImage.width, currentImage.height)], {
        type: MIME_TYPES.bmp,
      }),
    );
  }
  return new Promise((resolve) => canvas.toBlob(resolve, MIME_TYPES[format], quality));
}

async function exportImage(format) {
  if (!currentImage) {
    showToast("請先載入 RAW 檔", "error");
    return;
  }
  const quality = Number(qualityRange.value) / 100;
  const blob = await toBlob(format, quality);
  if (!blob) {
    showToast("輸出失敗，請再試一次", "error");
    return;
  }

  const frameSuffix = frameField.hidden ? "" : `_f${String(frameSelect.value).padStart(3, "0")}`;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${baseName(fileLabel)}${frameSuffix}_${currentImage.width}x${currentImage.height}.${format}`;
  link.click();
  URL.revokeObjectURL(url);
  showToast(`已輸出 ${format.toUpperCase()}（${formatBytes(blob.size)}）`);
}

function resetSettings() {
  controls.stride.value = "0";
  controls.offset.value = "0";
  controls.black.value = String(DEFAULT_OPTIONS.blackLevel);
  controls.white.value = String(DEFAULT_OPTIONS.whiteLevel);
  controls.gainR.value = "1";
  controls.gainG.value = "1";
  controls.gainB.value = "1";
  controls.tone.value = DEFAULT_OPTIONS.tone;
  controls.gamma.value = String(DEFAULT_OPTIONS.gamma);
  controls.demosaic.value = DEFAULT_OPTIONS.demosaic;
  exposureRange.value = "0";
  syncDependentFields();
  updateFrameOptions();
  render();
}

for (const control of Object.values(controls)) {
  control.addEventListener("change", () => {
    syncDependentFields();
    if (control === controls.packing) renderSizeChips();
    if ([controls.width, controls.height, controls.stride, controls.offset, controls.packing].includes(control)) {
      updateFrameOptions();
      renderSizeChips();
    }
    scheduleRender();
  });
  control.addEventListener("input", () => scheduleRender());
}

exposureRange.addEventListener("input", () => {
  syncDependentFields();
  scheduleRender();
});
qualityRange.addEventListener("input", syncDependentFields);
frameSelect.addEventListener("change", () => render());

$("#openFileButton").addEventListener("click", () => fileInput.click());
$("#demoButton").addEventListener("click", loadDemo);
$("#autoButton").addEventListener("click", () => render({ auto: true }));
$("#resetButton").addEventListener("click", resetSettings);
fileInput.addEventListener("change", () => loadFile(fileInput.files[0]));

$("#zoomButton").addEventListener("click", (event) => {
  const actual = previewStage.classList.toggle("actual");
  event.currentTarget.textContent = actual ? "符合視窗" : "1:1 檢視";
});

for (const button of document.querySelectorAll("[data-export]")) {
  button.addEventListener("click", () => exportImage(button.dataset.export));
}

previewStage.addEventListener("dragover", (event) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
  previewStage.classList.add("dragging");
});
previewStage.addEventListener("dragleave", () => previewStage.classList.remove("dragging"));
previewStage.addEventListener("drop", (event) => {
  event.preventDefault();
  previewStage.classList.remove("dragging");
  loadFile(event.dataTransfer.files[0]);
});

syncDependentFields();
