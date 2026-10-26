from __future__ import annotations

from live_captions.audio.process import pcm16_bytes_to_mono_f32
from live_captions.audio.select import pick_loopback
from live_captions.errors import AudioUnavailable


def _import_pyaudio():
    try:
        import pyaudiowpatch as pyaudio
    except ImportError as exc:
        raise AudioUnavailable(
            "缺少 pyaudiowpatch。請在 Windows 上執行 pip install -r requirements.txt。"
        ) from exc
    return pyaudio


def list_loopback_lines() -> list[str]:
    pyaudio = _import_pyaudio()
    lines: list[str] = []
    with pyaudio.PyAudio() as audio:
        try:
            devices = list(audio.get_loopback_device_info_generator())
        except Exception as exc:
            raise AudioUnavailable(f"無法列出 WASAPI 迴路：{exc}") from exc
    for device in devices:
        lines.append(f"系統迴路 {device['index']}: {device['name']}")
    return lines


def resolve_loopback_device(audio, *, name_contains: str | None = None) -> dict:
    if not name_contains:
        getter = getattr(audio, "get_default_wasapi_loopback", None)
        if getter is not None:
            try:
                return getter()
            except Exception:
                pass
    try:
        devices = list(audio.get_loopback_device_info_generator())
    except Exception as exc:
        raise AudioUnavailable(f"WASAPI 迴路無法使用：{exc}") from exc
    default_name = ""
    try:
        pyaudio = _import_pyaudio()
        wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
        default_name = str(default_out.get("name", ""))
    except Exception:
        default_name = ""
    return pick_loopback(
        devices,
        default_output_name=default_name,
        preferred_substring=name_contains,
    )


class WasapiLoopbackSource:
    """Capture the default playback device, which is what Teams sends to the speakers."""

    def __init__(self, name_contains: str | None = None) -> None:
        pyaudio = _import_pyaudio()
        self._pa = pyaudio.PyAudio()
        self._stream = None
        try:
            device = resolve_loopback_device(self._pa, name_contains=name_contains)
            self.sample_rate = int(device["defaultSampleRate"])
            self.channels = max(1, int(device["maxInputChannels"]))
            self.device_name = str(device["name"])
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                frames_per_buffer=1024,
                input=True,
                input_device_index=int(device["index"]),
            )
        except AudioUnavailable:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise AudioUnavailable(f"無法開啟系統音訊：{exc}") from exc

    def frames(self, stop, restart):
        stream = self._stream
        if stream is None:
            return
        while not stop.is_set() and not restart.is_set():
            try:
                raw = stream.read(1024, exception_on_overflow=False)
            except Exception:
                if stop.is_set() or restart.is_set():
                    return
                raise
            yield pcm16_bytes_to_mono_f32(raw, self.channels)

    def close(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        audio = getattr(self, "_pa", None)
        self._pa = None
        if audio is not None:
            try:
                audio.terminate()
            except Exception:
                pass
