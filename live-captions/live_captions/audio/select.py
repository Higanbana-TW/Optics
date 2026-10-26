from __future__ import annotations

import sys
from dataclasses import dataclass

from live_captions.errors import AudioUnavailable


@dataclass(frozen=True)
class OpenedSource:
    source: object
    mode: str
    notice: str


def select_audio_source(prefer: str, open_loopback, open_mic) -> OpenedSource:
    """Open the requested source. A loopback failure never opens the microphone."""
    if prefer == "mic":
        try:
            return OpenedSource(open_mic(), "mic", "")
        except AudioUnavailable:
            raise
        except Exception as exc:
            raise AudioUnavailable("無法開啟麥克風。") from exc
    try:
        return OpenedSource(open_loopback(), "loopback", "")
    except AudioUnavailable:
        raise
    except Exception as exc:
        raise AudioUnavailable(f"無法開啟系統音訊：{exc}") from exc


def pick_loopback(devices: list[dict], *, default_output_name: str, preferred_substring: str | None) -> dict:
    loopbacks = [device for device in devices if device.get("isLoopbackDevice")]
    if preferred_substring:
        needle = preferred_substring.lower()
        matches = [device for device in loopbacks if needle in str(device.get("name", "")).lower()]
        if not matches:
            raise AudioUnavailable(f"找不到名稱包含「{preferred_substring}」的系統播放裝置。")
        return matches[0]
    if default_output_name:
        for device in loopbacks:
            if default_output_name in str(device.get("name", "")):
                return device
    raise AudioUnavailable("找不到預設播放裝置的 WASAPI 迴路。")


def listening_status(mode: str, device_name: str = "") -> str:
    base = "聆聽系統音訊" if mode == "loopback" else "聆聽麥克風"
    short = device_name.strip()
    if not short:
        return base
    if len(short) > 42:
        short = short[:41] + "…"
    return f"{base} · {short}"


def open_audio_source(prefer: str, *, loopback_name: str | None = None) -> OpenedSource:
    def open_loopback():
        if sys.platform != "win32":
            raise AudioUnavailable("WASAPI 系統迴路只支援 Windows。")
        from live_captions.audio.wasapi import WasapiLoopbackSource

        return WasapiLoopbackSource(name_contains=loopback_name)

    def open_mic():
        from live_captions.audio.microphone import MicrophoneSource

        return MicrophoneSource()

    return select_audio_source(prefer, open_loopback, open_mic)


def list_audio_report() -> str:
    lines: list[str] = []
    if sys.platform != "win32":
        lines.append("系統迴路：只在 Windows 上可用（WASAPI）。")
    else:
        try:
            from live_captions.audio.wasapi import list_loopback_lines

            found = list_loopback_lines()
            lines.extend(found or ["系統迴路：沒有找到 WASAPI 迴路裝置。"])
        except Exception as exc:
            lines.append(f"系統迴路：無法列出（{exc}）。")
    try:
        from live_captions.audio.microphone import list_input_lines

        found = list_input_lines()
        lines.extend(found or ["麥克風：沒有找到輸入裝置。"])
    except Exception as exc:
        lines.append(f"麥克風：無法列出（{exc}）。")
    return "\n".join(lines)
