from __future__ import annotations

import numpy as np

from live_captions.config import AppConfig
from live_captions.errors import CaptionsError

# Published Hugging Face storage for Systran/faster-whisper-base.en (usedStorage).
WHISPER_BASE_EN_BYTES = 145_216_508
WHISPER_SMALL_EN_BYTES = 483_545_366


def resolve_whisper_runtime(
    device: str,
    compute: str | None,
    *,
    cuda_devices: int,
) -> tuple[str, str]:
    requested = device.lower()
    if requested == "auto":
        requested = "cuda" if cuda_devices > 0 else "cpu"
    if requested not in {"cpu", "cuda"}:
        raise CaptionsError("CAPTIONS_WHISPER_DEVICE 請設為 cpu、cuda 或 auto。")
    if compute:
        return requested, compute
    if requested == "cuda":
        return requested, "int8_float16"
    return requested, "int8"


def explain_load_error(exc: BaseException, *, platform_name: str) -> str:
    text = str(exc)
    if platform_name == "win32" and any(token in text for token in ("DLL", "dll", "WinError")):
        return (
            "語音模型無法載入。請安裝 Microsoft Visual C++ 2015–2022 Redistributable（x64）後再試。"
            f"原始錯誤：{text}"
        )
    return f"語音模型無法載入：{text}"


def detect_cuda_devices() -> int:
    try:
        import ctranslate2
    except Exception:
        return 0
    try:
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


class WhisperEngine:
    def __init__(self, model_name: str, device: str, compute_type: str, cpu_threads: int) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = max(1, cpu_threads)
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise CaptionsError(
                "缺少 faster-whisper。請在 live-captions 目錄執行 pip install -r requirements.txt。"
            ) from exc
        try:
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
        except Exception as exc:
            raise CaptionsError(explain_load_error(exc, platform_name=__import__("sys").platform)) from exc

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size < 4000:
            return ""
        if self._model is None:
            self.load()
        samples = np.ascontiguousarray(audio, dtype=np.float32)
        segments, _info = self._model.transcribe(
            samples,
            language="en",
            task="transcribe",
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=False,
            no_speech_threshold=0.6,
        )
        parts: list[str] = []
        for segment in segments:
            if float(getattr(segment, "no_speech_prob", 0.0) or 0.0) > 0.6:
                continue
            text = str(getattr(segment, "text", "") or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts)


def make_whisper(config: AppConfig, *, cuda_devices: int | None = None) -> WhisperEngine:
    if cuda_devices is None:
        cuda_devices = detect_cuda_devices() if config.whisper_device == "auto" else 0
    device, compute = resolve_whisper_runtime(
        config.whisper_device,
        config.whisper_compute,
        cuda_devices=cuda_devices,
    )
    return WhisperEngine(config.whisper_model, device, compute, config.cpu_threads)
