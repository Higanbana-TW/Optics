import "./style.css";
import {
  BAYER_PATTERNS,
  calculateAutoWhiteBalance,
  encodeBmp,
  packedRowBytes,
  renderRaw10,
  requiredFileBytes,
  unpackRaw10,
} from "./raw10.js";

const $ = (selector) => document.querySelector(selector);
const canvas = $("#previewCanvas");
const context = canvas.getContext("2d");
const fileInput = $("#fileInput");
const dropZone = $("#dropZone");
const convertButton = $("#convertButton");
const downloadButtons = [...document.querySelectorAll("[data-format]")];
const settingsForm = $("#settingsForm");

let sourceFile = null;
let rawPixels = null;
let renderedImage = null;
let toastTimer = null;

function showToast(message, type = "") {
  window.clearTimeout(toastTimer);
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast ${type}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3800);
}

function readSettings() {
  const width = Number($("#width").value);
  const height = Number($("#height").value);
  const tightStride = packedRowBytes(width);
  const strideValue = $("#stride").value.trim();
  const requestedStride = Number(strideValue);
  return {
    width,
    height,
    pattern: $("#pattern").value,
    offset: Number($("#offset").value),
    stride: !strideValue || requestedStride === 0 ? tightStride : requestedStride,
    blackLevel: Number($("#blackLevel").value),
    whiteLevel: Number($("#whiteLevel").value),
    gamma: Number($("#gamma").value),
    exposure: 2 ** Number($("#exposure").value),
    autoWhiteBalance: $("#autoWhiteBalance").checked,
  };
}

function validateSettings(settings) {
  if (!Number.isInteger(settings.width) || settings.width <= 0) throw new Error("請輸入正確的影像寬度");
  if (!Number.isInteger(settings.height) || settings.height <= 0) throw new Error("請輸入正確的影像高度");
  if (!Number.isInteger(settings.offset) || settings.offset < 0) throw new Error("檔頭偏移必須是非負整數");
  if (!Number.isInteger(settings.stride) || settings.stride <= 0) throw new Error("Row stride 必須是正整數");
  requiredFileBytes(settings.width, settings.height, settings.stride, settings.offset);
}

function updateEstimate() {
  try {
    const settings = readSettings();
    validateSettings(settings);
    const tight = packedRowBytes(settings.width);
    const needed = requiredFileBytes(settings.width, settings.height, settings.stride, settings.offset);
    $("#packedBytes").textContent = `${tight.toLocaleString()} B / row`;
    $("#expectedBytes").textContent = `${needed.toLocaleString()} B`;
    $("#fileMatch").textContent = sourceFile
      ? sourceFile.size >= needed
        ? "容量符合"
        : `少 ${(needed - sourceFile.size).toLocaleString()} B`
      : "等待檔案";
    $("#fileMatch").className = sourceFile && sourceFile.size < needed ? "danger" : "";
  } catch {
    $("#packedBytes").textContent = "—";
    $("#expectedBytes").textContent = "—";
    $("#fileMatch").textContent = "設定有誤";
    $("#fileMatch").className = "danger";
  }
}

function setFile(file) {
  if (!file) return;
  sourceFile = file;
  rawPixels = null;
  renderedImage = null;
  $("#fileName").textContent = file.name;
  $("#fileSize").textContent = formatBytes(file.size);
  $("#fileMeta").classList.remove("hidden");
  $("#dropPrompt").classList.add("hidden");
  dropZone.classList.add("has-file");
  convertButton.disabled = false;
  downloadButtons.forEach((button) => {
    button.disabled = true;
  });
  updateEstimate();
}

async function convert() {
  if (!sourceFile) return;
  let settings;
  try {
    settings = readSettings();
    validateSettings(settings);
    setBusy(true);
    await nextFrame();

    const bytes = new Uint8Array(await sourceFile.arrayBuffer());
    rawPixels = unpackRaw10(bytes, settings.width, settings.height, settings);
    const gains =
      settings.autoWhiteBalance && BAYER_PATTERNS.includes(settings.pattern)
        ? calculateAutoWhiteBalance(rawPixels, settings.width, settings.height, settings.pattern)
        : { r: 1, g: 1, b: 1 };

    const rgba = renderRaw10(rawPixels, settings.width, settings.height, { ...settings, gains });
    canvas.width = settings.width;
    canvas.height = settings.height;
    renderedImage = new ImageData(rgba, settings.width, settings.height);
    context.putImageData(renderedImage, 0, 0);

    $("#previewEmpty").classList.add("hidden");
    canvas.classList.remove("hidden");
    $("#resolution").textContent = `${settings.width} × ${settings.height}`;
    $("#previewPattern").textContent = settings.pattern === "MONO" ? "Mono" : `${settings.pattern} Bayer`;
    $("#previewInfo").classList.remove("hidden");
    downloadButtons.forEach((button) => {
      button.disabled = false;
    });
    showToast("RAW10 解析完成，可以下載影像");
  } catch (error) {
    showToast(error.message || "轉換失敗，請檢查輸入設定", "error");
  } finally {
    setBusy(false);
  }
}

async function download(format) {
  if (!renderedImage) return;
  const baseName = sourceFile.name.replace(/\.[^.]+$/, "") || "raw10-image";
  let blob;

  if (format === "bmp") {
    blob = encodeBmp(renderedImage.data, renderedImage.width, renderedImage.height);
  } else {
    const mime = format === "jpg" ? "image/jpeg" : "image/png";
    blob = await canvasToBlob(canvas, mime, format === "jpg" ? 0.94 : undefined);
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${baseName}.${format}`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast(`已建立 ${link.download}`);
}

function setBusy(busy) {
  convertButton.disabled = busy;
  convertButton.classList.toggle("busy", busy);
  convertButton.querySelector("span").textContent = busy ? "解析中…" : "解析並預覽";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
}

function canvasToBlob(target, type, quality) {
  return new Promise((resolve, reject) => {
    target.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("無法建立輸出檔案"))), type, quality);
  });
}

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") fileInput.click();
});
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  setFile(event.dataTransfer.files[0]);
});
settingsForm.addEventListener("input", updateEstimate);
settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  convert();
});
downloadButtons.forEach((button) => button.addEventListener("click", () => download(button.dataset.format)));

$("#exposure").addEventListener("input", (event) => {
  $("#exposureValue").textContent = `${Number(event.target.value) >= 0 ? "+" : ""}${event.target.value} EV`;
});
$("#helpButton").addEventListener("click", () => $("#helpDialog").showModal());
$("#helpCloseButton").addEventListener("click", () => $("#helpDialog").close());

updateEstimate();
