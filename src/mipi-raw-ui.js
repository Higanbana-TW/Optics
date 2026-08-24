import "./style.css";
import "./mipi-raw.css";
import {
  encodeBmp,
  expectedFrameBytes,
  guessLayouts,
  makeSampleRaw10,
  packedRowBytes,
  rawToRgb,
  readRawPixels,
  rgbToImageData,
} from "./mipi-raw/convert.js";

const $ = (selector) => document.querySelector(selector);

const fileInput = $("#fileInput");
const dropZone = $("#dropZone");
const preview = $("#preview");
const previewWrap = $("#previewWrap");
const emptyPreview = $("#emptyPreview");
const fileMeta = $("#fileMeta");
const guessSelect = $("#guessSelect");
const widthInput = $("#width");
const heightInput = $("#height");
const formatSelect = $("#format");
const bayerSelect = $("#bayer");
const offsetInput = $("#offset");
const strideInput = $("#stride");
const frameInput = $("#frame");
const blackLevelInput = $("#blackLevel");
const wbSelect = $("#whiteBalance");
const toneSelect = $("#tone");
const jpegQuality = $("#jpegQuality");
const toast = $("#toast");
const statusDot = $(".status-dot");
const sourceLabel = $("#sourceLabel");
const convertButton = $("#convertButton");
const helpDialog = $("#helpDialog");

let fileBytes = null;
let fileName = "sample.raw";
let lastRgb = null;
let lastSize = { width: 0, height: 0 };
let toastTimer = null;

function showToast(message, type = "") {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast ${type}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3600);
}

function fillGuesses(bytesLength) {
  const offset = Number(offsetInput.value) || 0;
  const guesses = guessLayouts(bytesLength, offset);
  guessSelect.innerHTML = "";
  if (!guesses.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "無法自動猜測，請手動輸入寬高";
    guessSelect.append(option);
    return guesses;
  }
  for (const [index, item] of guesses.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${item.width} × ${item.height} · ${item.format} · ${item.frames} 影格`;
    guessSelect.append(option);
  }
  applyGuess(guesses[0]);
  return guesses;
}

function applyGuess(item) {
  widthInput.value = item.width;
  heightInput.value = item.height;
  formatSelect.value = item.format;
  if (!strideInput.value) strideInput.placeholder = String(item.stride);
}

function setSource(name, bytes) {
  fileBytes = bytes;
  fileName = name;
  sourceLabel.textContent = name;
  statusDot.classList.add("active");
  fileMeta.textContent = `${name} · ${(bytes.byteLength / 1024).toFixed(1)} KB`;
  fillGuesses(bytes.byteLength);
  convertCurrent();
}

async function loadFile(file) {
  if (!file) return;
  const buffer = await file.arrayBuffer();
  setSource(file.name, new Uint8Array(buffer));
  showToast(`已載入 ${file.name}`);
}

function currentOptions() {
  const width = Number(widthInput.value);
  const height = Number(heightInput.value);
  const fmt = formatSelect.value;
  const offset = Number(offsetInput.value) || 0;
  const strideValue = Number(strideInput.value);
  const stride = strideValue > 0 ? strideValue : undefined;
  const frame = Number(frameInput.value) || 0;
  return { width, height, fmt, offset, stride, frame };
}

function convertCurrent() {
  if (!fileBytes) {
    showToast("請先載入 RAW 檔，或產生示範畫面", "error");
    return null;
  }
  const { width, height, fmt, offset, stride, frame } = currentOptions();
  if (!width || !height) {
    showToast("請輸入寬度與高度", "error");
    return null;
  }
  try {
    if (fmt === "mipi10") packedRowBytes(width);
    const needed = offset + expectedFrameBytes(width, height, fmt, stride) * (frame + 1);
    if (fileBytes.byteLength < needed) {
      throw new Error(`資料不足：目前設定需要 ${needed} bytes`);
    }
    const pixels = readRawPixels(fileBytes, width, height, fmt, { offset, stride, frame });
    const rgb = rawToRgb(pixels, width, height, {
      bayer: bayerSelect.value,
      blackLevel: Number(blackLevelInput.value) || 0,
      whiteBalance: wbSelect.value === "off" ? [1, 1, 1] : "auto",
      tone: toneSelect.value,
    });
    lastRgb = rgb;
    lastSize = { width, height };
    drawPreview(rgb, width, height);
    emptyPreview.classList.add("hidden");
    previewWrap.classList.add("has-image");
    convertButton.disabled = false;
    document.querySelectorAll("[data-save]").forEach((button) => {
      button.disabled = false;
    });
    showToast(`已轉換 ${width} × ${height}`);
    return rgb;
  } catch (error) {
    showToast(error.message, "error");
    return null;
  }
}

function drawPreview(rgb, width, height) {
  const maxEdge = 1600;
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  const drawW = Math.max(1, Math.round(width * scale));
  const drawH = Math.max(1, Math.round(height * scale));
  preview.width = drawW;
  preview.height = drawH;
  const ctx = preview.getContext("2d");
  if (scale === 1) {
    ctx.putImageData(rgbToImageData(rgb, width, height), 0, 0);
    return;
  }
  const full = document.createElement("canvas");
  full.width = width;
  full.height = height;
  full.getContext("2d").putImageData(rgbToImageData(rgb, width, height), 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(full, 0, 0, drawW, drawH);
}

function stemName() {
  return fileName.replace(/\.[^.]+$/, "") || "mipi-raw";
}

function canvasBlob(mime, quality) {
  const { width, height } = lastSize;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").putImageData(rgbToImageData(lastRgb, width, height), 0, 0);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) reject(new Error("瀏覽器無法編碼這個格式"));
      else resolve(blob);
    }, mime, quality);
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function saveAs(kind) {
  if (!lastRgb && !convertCurrent()) return;
  const name = stemName();
  try {
    if (kind === "bmp") {
      downloadBlob(encodeBmp(lastRgb, lastSize.width, lastSize.height), `${name}.bmp`);
    } else if (kind === "png") {
      downloadBlob(await canvasBlob("image/png"), `${name}.png`);
    } else {
      const quality = Number(jpegQuality.value) / 100;
      downloadBlob(await canvasBlob("image/jpeg", quality), `${name}.jpg`);
    }
    showToast(`已下載 ${name}.${kind === "jpeg" ? "jpg" : kind}`);
  } catch (error) {
    showToast(error.message, "error");
  }
}

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragover");
  loadFile(event.dataTransfer.files[0]);
});
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => loadFile(fileInput.files[0]));

guessSelect.addEventListener("change", () => {
  if (!fileBytes) return;
  const guesses = guessLayouts(fileBytes.byteLength, Number(offsetInput.value) || 0);
  const item = guesses[Number(guessSelect.value)];
  if (item) {
    applyGuess(item);
    convertCurrent();
  }
});

$("#openFileButton").addEventListener("click", () => fileInput.click());
$("#sampleButton").addEventListener("click", () => {
  bayerSelect.value = "RGGB";
  const bytes = makeSampleRaw10(640, 480, "RGGB");
  setSource("sample_640x480_rggb.raw", bytes);
});
convertButton.addEventListener("click", convertCurrent);
document.querySelectorAll("[data-save]").forEach((button) => {
  button.addEventListener("click", () => saveAs(button.dataset.save));
});
$("#helpButton").addEventListener("click", () => helpDialog.showModal());
$("#helpCloseButton").addEventListener("click", () => helpDialog.close());

["width", "height", "format", "bayer", "offset", "stride", "frame", "blackLevel", "whiteBalance", "tone"].forEach((id) => {
  $(`#${id}`).addEventListener("change", () => {
    if (fileBytes) convertCurrent();
  });
});
