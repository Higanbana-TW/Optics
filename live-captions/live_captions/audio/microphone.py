from __future__ import annotations

import numpy as np

from live_captions.errors import AudioUnavailable


def _import_sounddevice():
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise AudioUnavailable(
            "缺少 sounddevice。請在 live-captions 目錄執行 pip install -r requirements.txt。"
        ) from exc
    return sd


def list_input_lines() -> list[str]:
    sd = _import_sounddevice()
    try:
        devices = sd.query_devices()
    except Exception as exc:
        raise AudioUnavailable(f"無法列出麥克風：{exc}") from exc
    default = None
    try:
        default_pair = sd.default.device
        if isinstance(default_pair, (list, tuple)) and default_pair:
            default = default_pair[0]
    except Exception:
        default = None
    lines: list[str] = []
    for index, device in enumerate(devices):
        if int(device["max_input_channels"]) <= 0:
            continue
        mark = "（預設）" if index == default else ""
        lines.append(f"麥克風 {index}: {device['name']}{mark}")
    return lines


class MicrophoneSource:
    def __init__(self) -> None:
        sd = _import_sounddevice()
        self._sd = sd
        try:
            info = sd.query_devices(kind="input")
        except Exception as exc:
            raise AudioUnavailable("找不到麥克風。") from exc
        self.sample_rate = int(info.get("default_samplerate") or 48000)
        self.device_name = str(info.get("name") or "麥克風")
        self._stream = None

    def frames(self, stop, restart):
        block = 1024
        stream = None
        try:
            stream = self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block,
            )
            stream.start()
        except Exception as exc:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            raise AudioUnavailable("無法開啟麥克風。") from exc
        self._stream = stream
        try:
            while not stop.is_set() and not restart.is_set():
                try:
                    data, _overflow = stream.read(block)
                except Exception:
                    if stop.is_set() or restart.is_set():
                        return
                    raise
                yield np.asarray(data, dtype=np.float32).reshape(-1).copy()
        finally:
            self.close()

    def close(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        for method in ("abort", "stop", "close"):
            action = getattr(stream, method, None)
            if action is None:
                continue
            try:
                action()
            except Exception:
                pass
