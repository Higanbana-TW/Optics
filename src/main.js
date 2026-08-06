import Hls from "hls.js";
import "./style.css";

const $ = (selector) => document.querySelector(selector);
const video = $("#video");
const videoStage = $("#videoStage");
const emptyState = $("#emptyState");
const loadingState = $("#loadingState");
const sourceLabel = $("#sourceLabel");
const statusDot = $(".status-dot");
const seekBar = $("#seekBar");
const volumeBar = $("#volumeBar");
const currentTime = $("#currentTime");
const durationLabel = $("#duration");
const playIcon = $(".play-icon");
const pauseIcon = $(".pause-icon");
const volumeIcon = $(".volume-icon");
const mutedIcon = $(".muted-icon");
const bufferBar = $("#bufferBar");
const streamDialog = $("#streamDialog");
const helpDialog = $("#helpDialog");
const streamUrl = $("#streamUrl");
const fileInput = $("#fileInput");
const toast = $("#toast");

let hls = null;
let objectUrl = null;
let toastTimer = null;
let speedIndex = 0;
const playbackSpeeds = [1, 1.25, 1.5, 1.75, 2, 0.5, 0.75];
const demoStream = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8";

function formatTime(value) {
  if (!Number.isFinite(value)) return video.duration === Infinity ? "LIVE" : "00:00";
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = Math.floor(value % 60);
  return `${hours ? `${String(hours).padStart(2, "0")}:` : ""}${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function showToast(message, type = "") {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast ${type}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3400);
}

function setLoading(isLoading) {
  loadingState.classList.toggle("hidden", !isLoading);
}

function resetSource() {
  if (hls) {
    hls.destroy();
    hls = null;
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  video.pause();
  video.removeAttribute("src");
  video.load();
  seekBar.value = 0;
  seekBar.style.setProperty("--range-progress", "0%");
  bufferBar.style.width = "0";
}

async function startPlayback() {
  try {
    await video.play();
  } catch {
    showToast("媒體已載入，按下播放鍵即可開始");
  }
}

function markSourceReady(label) {
  sourceLabel.textContent = label;
  statusDot.classList.add("active");
  emptyState.classList.add("hidden");
  videoStage.classList.add("has-media");
}

function openFilePicker() {
  fileInput.click();
}

function loadFile(file) {
  if (!file) return;
  if (!file.type.startsWith("video/") && !file.type.startsWith("audio/")) {
    showToast("請選擇影音檔案", "error");
    return;
  }
  resetSource();
  objectUrl = URL.createObjectURL(file);
  video.src = objectUrl;
  markSourceReady(file.name);
  setLoading(true);
  startPlayback();
}

function isHlsUrl(url) {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".m3u8");
  } catch {
    return false;
  }
}

function loadStream(url) {
  const cleanUrl = url.trim();
  if (!cleanUrl) return;

  resetSource();
  markSourceReady(new URL(cleanUrl).hostname);
  setLoading(true);

  if (isHlsUrl(cleanUrl) && Hls.isSupported()) {
    hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
      backBufferLength: 60,
    });
    hls.loadSource(cleanUrl);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, startPlayback);
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (!data.fatal) return;
      setLoading(false);
      if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
        hls.recoverMediaError();
      } else {
        showToast("無法讀取串流，請確認網址與 CORS 設定", "error");
        hls.destroy();
        hls = null;
      }
    });
    return;
  }

  if (isHlsUrl(cleanUrl) && video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = cleanUrl;
    startPlayback();
    return;
  }

  video.src = cleanUrl;
  startPlayback();
}

function togglePlayback() {
  if (!video.currentSrc) {
    showToast("請先開啟影音來源");
    return;
  }
  if (video.paused) startPlayback();
  else video.pause();
}

function seekBy(seconds) {
  if (!Number.isFinite(video.duration)) return;
  video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
}

function toggleMute() {
  video.muted = !video.muted;
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else videoStage.requestFullscreen().catch(() => showToast("瀏覽器無法進入全螢幕", "error"));
}

function captureFrame() {
  if (!video.currentSrc || video.readyState < 2) {
    showToast("目前沒有可擷取的畫面", "error");
    return;
  }
  if (!video.videoWidth || !video.videoHeight) {
    showToast("音訊檔案沒有可擷取的畫面", "error");
    return;
  }

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");

  try {
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        showToast("擷取失敗，來源可能禁止跨網域存取", "error");
        return;
      }
      const link = document.createElement("a");
      const captureUrl = URL.createObjectURL(blob);
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      link.href = captureUrl;
      link.download = `optic-capture-${stamp}.png`;
      link.click();
      URL.revokeObjectURL(captureUrl);
      showToast(`已擷取 ${canvas.width} × ${canvas.height} 原始畫面`);
    }, "image/png");
  } catch {
    showToast("來源未允許 CORS，瀏覽器無法擷取畫面", "error");
  }
}

function openStreamDialog() {
  streamDialog.showModal();
  window.setTimeout(() => streamUrl.focus(), 50);
}

["#openFileButton", "#fileCard"].forEach((selector) => $(selector).addEventListener("click", openFilePicker));
["#openStreamButton", "#streamCard"].forEach((selector) => $(selector).addEventListener("click", openStreamDialog));
["#captureButton", "#captureCard"].forEach((selector) => $(selector).addEventListener("click", captureFrame));

$("#playButton").addEventListener("click", togglePlayback);
$("#backButton").addEventListener("click", () => seekBy(-10));
$("#forwardButton").addEventListener("click", () => seekBy(10));
$("#muteButton").addEventListener("click", toggleMute);
$("#fullscreenButton").addEventListener("click", toggleFullscreen);
$("#helpButton").addEventListener("click", () => helpDialog.showModal());
$("#helpCloseButton").addEventListener("click", () => helpDialog.close());

$("#speedButton").addEventListener("click", (event) => {
  speedIndex = (speedIndex + 1) % playbackSpeeds.length;
  video.playbackRate = playbackSpeeds[speedIndex];
  event.currentTarget.textContent = `${playbackSpeeds[speedIndex]}×`;
});

fileInput.addEventListener("change", () => loadFile(fileInput.files[0]));

$("#streamForm").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!streamUrl.reportValidity()) return;
  const url = streamUrl.value;
  streamDialog.close();
  loadStream(url);
});

$("#demoStreamButton").addEventListener("click", () => {
  streamUrl.value = demoStream;
  streamDialog.close();
  loadStream(demoStream);
});

video.addEventListener("click", togglePlayback);
video.addEventListener("dblclick", toggleFullscreen);
video.addEventListener("play", () => {
  playIcon.classList.add("hidden");
  pauseIcon.classList.remove("hidden");
  $("#playButton").setAttribute("aria-label", "暫停");
});
video.addEventListener("pause", () => {
  playIcon.classList.remove("hidden");
  pauseIcon.classList.add("hidden");
  $("#playButton").setAttribute("aria-label", "播放");
});
video.addEventListener("loadedmetadata", () => {
  durationLabel.textContent = formatTime(video.duration);
});
video.addEventListener("loadeddata", () => setLoading(false));
video.addEventListener("canplay", () => setLoading(false));
video.addEventListener("waiting", () => setLoading(true));
video.addEventListener("playing", () => setLoading(false));
video.addEventListener("error", () => {
  setLoading(false);
  showToast("媒體載入失敗，請檢查格式、網址或跨網域設定", "error");
});

video.addEventListener("timeupdate", () => {
  currentTime.textContent = formatTime(video.currentTime);
  if (Number.isFinite(video.duration) && video.duration > 0) {
    const progress = (video.currentTime / video.duration) * 100;
    seekBar.value = Math.round(progress * 10);
    seekBar.style.setProperty("--range-progress", `${progress}%`);
  }
});

video.addEventListener("progress", () => {
  if (!video.buffered.length || !Number.isFinite(video.duration)) return;
  bufferBar.style.width = `${(video.buffered.end(video.buffered.length - 1) / video.duration) * 100}%`;
});

video.addEventListener("volumechange", () => {
  const isMuted = video.muted || video.volume === 0;
  volumeIcon.classList.toggle("hidden", isMuted);
  mutedIcon.classList.toggle("hidden", !isMuted);
  volumeBar.value = video.muted ? 0 : video.volume;
  volumeBar.style.setProperty("--range-progress", `${volumeBar.value * 100}%`);
});

seekBar.addEventListener("input", () => {
  if (!Number.isFinite(video.duration)) return;
  const progress = Number(seekBar.value) / 1000;
  video.currentTime = progress * video.duration;
  seekBar.style.setProperty("--range-progress", `${progress * 100}%`);
});

volumeBar.addEventListener("input", () => {
  video.muted = false;
  video.volume = Number(volumeBar.value);
});

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input")) return;
  const key = event.key.toLowerCase();
  if (event.code === "Space") {
    event.preventDefault();
    togglePlayback();
  } else if (event.key === "ArrowLeft") seekBy(-10);
  else if (event.key === "ArrowRight") seekBy(10);
  else if (key === "c") captureFrame();
  else if (key === "f") toggleFullscreen();
  else if (key === "m") toggleMute();
});

videoStage.addEventListener("dragover", (event) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});
videoStage.addEventListener("drop", (event) => {
  event.preventDefault();
  loadFile(event.dataTransfer.files[0]);
});

volumeBar.style.setProperty("--range-progress", "100%");
