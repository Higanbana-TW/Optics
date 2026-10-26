from __future__ import annotations

import queue
from collections import deque

import numpy as np


def pcm16_bytes_to_mono_f32(data: bytes, channels: int) -> np.ndarray:
    if channels < 1:
        raise ValueError("channels")
    audio = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if channels == 1:
        return audio
    usable = (audio.size // channels) * channels
    if usable == 0:
        return np.zeros(0, dtype=np.float32)
    return audio[:usable].reshape(-1, channels).mean(axis=1).astype(np.float32)


def resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate <= 0 or dst_rate <= 0:
        raise ValueError("sample rate must be positive")
    if (
        src_rate == dst_rate
        and isinstance(samples, np.ndarray)
        and samples.dtype == np.float32
        and samples.ndim == 1
        and samples.flags.c_contiguous
    ):
        return samples
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if audio.size == 0 or src_rate == dst_rate:
        return audio
    if src_rate % dst_rate == 0:
        factor = src_rate // dst_rate
        usable = (audio.size // factor) * factor
        if usable == 0:
            return np.zeros(0, dtype=np.float32)
        return audio[:usable].reshape(-1, factor).mean(axis=1).astype(np.float32)
    dst_count = max(1, int(round(audio.size * dst_rate / src_rate)))
    src_x = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
    dst_x = np.linspace(0.0, 1.0, num=dst_count, endpoint=False)
    return np.interp(dst_x, src_x, audio).astype(np.float32)


def offer_drop_oldest(items: queue.Queue, item: object) -> None:
    while True:
        try:
            items.put_nowait(item)
            return
        except queue.Full:
            try:
                items.get_nowait()
            except queue.Empty:
                continue


def _rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))


class UtteranceSegmenter:
    """Energy gate that emits one utterance after a short silence."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        threshold: float = 0.01,
        silence_ms: int = 600,
        min_speech_ms: int = 300,
        max_speech_ms: int = 12000,
        preroll_ms: int = 300,
        tail_ms: int = 200,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_size = max(1, int(sample_rate * frame_ms / 1000))
        self.threshold = threshold
        self.silence_frames_needed = max(1, int(silence_ms / frame_ms))
        self.min_speech_frames = max(1, int(min_speech_ms / frame_ms))
        self.max_speech_frames = max(self.min_speech_frames + 1, int(max_speech_ms / frame_ms))
        self.tail_frames = max(0, int(tail_ms / frame_ms))
        self._pending = np.zeros(0, dtype=np.float32)
        self._preroll: deque[np.ndarray] = deque(maxlen=max(0, int(preroll_ms / frame_ms)))
        self._speech: list[np.ndarray] = []
        self._in_speech = False
        self._voiced_count = 0
        self._silence_count = 0

    def push(self, samples: np.ndarray) -> list[np.ndarray]:
        if samples.size == 0:
            return []
        data = np.concatenate((self._pending, np.asarray(samples, dtype=np.float32).reshape(-1)))
        outputs: list[np.ndarray] = []
        offset = 0
        frame = self.frame_size
        while offset + frame <= data.size:
            uttered = self._consume(data[offset : offset + frame])
            offset += frame
            if uttered is not None:
                outputs.append(uttered)
        self._pending = data[offset:].copy()
        return outputs

    def flush(self) -> list[np.ndarray]:
        outputs: list[np.ndarray] = []
        if self._pending.size:
            pad = self.frame_size - self._pending.size
            frame = self._pending if pad == 0 else np.concatenate(
                (self._pending, np.zeros(pad, dtype=np.float32))
            )
            self._pending = np.zeros(0, dtype=np.float32)
            uttered = self._consume(frame)
            if uttered is not None:
                outputs.append(uttered)
        if self._in_speech and self._speech and self._voiced_count >= self.min_speech_frames:
            outputs.append(np.concatenate(self._speech))
        self._reset_speech()
        return outputs

    def _consume(self, frame: np.ndarray) -> np.ndarray | None:
        voiced = _rms(frame) >= self.threshold
        piece = frame.copy()
        if not self._in_speech:
            self._preroll.append(piece)
            if not voiced:
                return None
            self._in_speech = True
            self._speech = list(self._preroll)
            self._preroll.clear()
            self._voiced_count = sum(1 for item in self._speech if _rms(item) >= self.threshold)
            self._silence_count = 0
        else:
            self._speech.append(piece)
            if voiced:
                self._voiced_count += 1
                self._silence_count = 0
            else:
                self._silence_count += 1
        if len(self._speech) >= self.max_speech_frames:
            uttered = self._emit_all()
            self._in_speech = True
            return uttered
        if self._silence_count >= self.silence_frames_needed:
            return self._emit_with_tail()
        return None

    def _emit_all(self) -> np.ndarray | None:
        frames = self._speech
        voiced = self._voiced_count
        self._reset_speech()
        if voiced < self.min_speech_frames or not frames:
            return None
        return np.concatenate(frames)

    def _emit_with_tail(self) -> np.ndarray | None:
        frames = list(self._speech)
        voiced = self._voiced_count
        trailing = self._silence_count
        self._reset_speech()
        if voiced < self.min_speech_frames:
            return None
        if trailing > self.tail_frames:
            drop = trailing - self.tail_frames
            frames = frames[:-drop] if drop else frames
        if not frames:
            return None
        return np.concatenate(frames)

    def _reset_speech(self) -> None:
        self._speech = []
        self._in_speech = False
        self._voiced_count = 0
        self._silence_count = 0
