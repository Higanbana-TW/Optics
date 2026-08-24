import "./style.css";
import {
  BAYER_PATTERNS,
  demosaicRaw10,
  encodeBmp,
  expectedRaw10Bytes,
  packedRowBytes,
  unpackRaw10,
} from "./raw10.js";

const $ = (selector) => document.querySelector(selector);
const fileInput = $("#fileInput");
const dropZone = $("#dropZone");
const form = $("#settingsForm");
const canvas = $("#previewCanvas");
const previewEmpty = $("#previewEmpty");
const processing = $("#processing");
const fileName = $("#fileName");
const fileMeta = $("#fileMeta");
const status = $("#status");
const convertButton = $("#convertButton");
const downloadButton = $("#downloadButton");
const strideInput = $("#stride");
const widthInput = $("#width");
const heightInput = $("#height");

let selectedFile = null;
let outputBlob = null;
let outputExtension = "";

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function setStatus(message, type = "") {
  status.textContent = message;
  status.className = `status-message ${type}`.trim();
}

function resetOutput() {
  outputBlob = null;
  downloadButton.disabled = true;
  canvas.classList.add("hidden");
  previewEmpty.classList.remove("hidden");
}

function selectFile(file) {
  if (!file) return;
  selectedFile = file;
  fileName.textContent = file.name;
  fileMeta.textContent = `${formatBytes(file.size)} · 本機處理，不會上傳`;
  dropZone.classList.add("has-file");
  convertButton.disabled = false;
  resetOutput();
  updateSizeHint();
  setStatus("檔案已就緒，請確認影像參數");
}

function currentDimensions() {
  const width = Number(widthInput.value);
  const height = Number(heightInput.value);
  const minimumStride = Number.isInteger(width) && width > 0 ? packedRowBytes(width) : 0;
  const stride = strideInput.value === "" ? minimumStride : Number(strideInput.value);
  return { width, height, stride, minimumStride };
}

function updateSizeHint() {
  try {
    const { width, height, stride, minimumStride } = currentDimensions();
    $("#strideHint").textContent = minimumStride ? `最小 ${minimumStride} bytes；留空自動計算` : "依影像寬度自動計算";
    const expected = expectedRaw10Bytes(width, height, stride);
    $("#expectedSize").textContent = `預期 RAW 大小 ${formatBytes(expected)}`;
    if (selectedFile && selectedFile.size < expected) {
      setStatus(`檔案不足 ${formatBytes(expected)}，請檢查寬、高或 stride`, "error");
    }
  } catch {
    $("#expectedSize").textContent = "輸入尺寸後顯示預期檔案大小";
  }
}

async function canvasToBlob(type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("瀏覽器無法建立輸出影像"))), type, quality);
  });
}

async function convert() {
  if (!selectedFile || !form.reportValidity()) return;

  convertButton.disabled = true;
  downloadButton.disabled = true;
  processing.classList.remove("hidden");
  setStatus("正在解包 RAW10 與 Bayer 去馬賽克…");

  await new Promise((resolve) => window.setTimeout(resolve, 20));

  try {
    const { width, height, stride } = currentDimensions();
    const pattern = $("#bayer").value;
    const blackLevel = Number($("#blackLevel").value);
    const whiteLevel = Number($("#whiteLevel").value);
    const bytes = new Uint8Array(await selectedFile.arrayBuffer());
    const pixels = unpackRaw10(bytes, width, height, stride);
    const rgba = demosaicRaw10(pixels, width, height, { pattern, blackLevel, whiteLevel });

    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").putImageData(new ImageData(rgba, width, height), 0, 0);

    const format = document.querySelector('input[name="format"]:checked').value;
    if (format === "bmp") {
      outputBlob = encodeBmp(rgba, width, height);
      outputExtension = "bmp";
    } else {
      const mimeType = format === "jpg" ? "image/jpeg" : "image/png";
      outputBlob = await canvasToBlob(mimeType, format === "jpg" ? 0.92 : undefined);
      outputExtension = format;
    }

    canvas.classList.remove("hidden");
    previewEmpty.classList.add("hidden");
    downloadButton.disabled = false;
    const extraBytes = bytes.byteLength - expectedRaw10Bytes(width, height, stride);
    setStatus(
      `完成：${width} × ${height} · ${pattern} · ${outputExtension.toUpperCase()}${extraBytes > 0 ? `（忽略尾端 ${formatBytes(extraBytes)}）` : ""}`,
      "success",
    );
  } catch (error) {
    resetOutput();
    setStatus(error instanceof Error ? error.message : "轉換失敗", "error");
  } finally {
    processing.classList.add("hidden");
    convertButton.disabled = false;
  }
}

function download() {
  if (!outputBlob || !selectedFile) return;
  const url = URL.createObjectURL(outputBlob);
  const link = document.createElement("a");
  const baseName = selectedFile.name.replace(/\.[^.]+$/, "") || "raw10";
  link.href = url;
  link.download = `${baseName}.${outputExtension}`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

if (!BAYER_PATTERNS.includes($("#bayer").value)) {
  $("#bayer").value = "RGGB";
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  selectFile(event.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
form.addEventListener("submit", (event) => {
  event.preventDefault();
  convert();
});
downloadButton.addEventListener("click", download);
[widthInput, heightInput, strideInput].forEach((input) => input.addEventListener("input", updateSizeHint));
document.querySelectorAll('input[name="format"]').forEach((input) => input.addEventListener("change", resetOutput));

updateSizeHint();
