from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from live_captions.errors import ConfigError
from live_captions.paths import app_dir, data_dir

AUDIO_ALIASES = {"loopback": "loopback", "mic": "mic", "microphone": "mic"}
TRANSLATORS = {"local", "deepl", "openai", "libre"}


def clamp_alpha(value: int) -> int:
    return max(80, min(242, value))


def parse_audio(value: str) -> str:
    key = value.strip().lower()
    if key not in AUDIO_ALIASES:
        raise ConfigError("音訊來源請設為 loopback 或 mic。")
    return AUDIO_ALIASES[key]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _env_int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = _clean(env.get(name))
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必須是整數。") from exc
    if value < low or value > high:
        raise ConfigError(f"{name} 請設在 {low} 到 {high}。")
    return value


@dataclass(frozen=True)
class AppConfig:
    audio: str = "loopback"
    translator: str = "local"
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"
    whisper_compute: str | None = None
    cpu_threads: int = 4
    vad_threshold: float = 0.01
    loopback_name: str | None = None
    bar_alpha: int = 214
    deepl_key: str | None = None
    openai_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    libre_url: str | None = None
    libre_key: str | None = None


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    source = os.environ if env is None else env
    translator = (_clean(source.get("CAPTIONS_TRANSLATOR")) or "local").lower()
    if translator not in TRANSLATORS:
        raise ConfigError("CAPTIONS_TRANSLATOR 請設為 local、deepl、openai 或 libre。")
    device = (_clean(source.get("CAPTIONS_WHISPER_DEVICE")) or "cpu").lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise ConfigError("CAPTIONS_WHISPER_DEVICE 請設為 cpu、cuda 或 auto。")
    try:
        vad = float(_clean(source.get("CAPTIONS_VAD_THRESHOLD")) or "0.01")
    except ValueError as exc:
        raise ConfigError("CAPTIONS_VAD_THRESHOLD 必須是數字。") from exc
    if not 0 < vad <= 1:
        raise ConfigError("CAPTIONS_VAD_THRESHOLD 請設在 0 到 1 之間。")
    alpha = _env_int(source, "CAPTIONS_BAR_ALPHA", 214, 0, 255)
    return AppConfig(
        audio=parse_audio(_clean(source.get("CAPTIONS_AUDIO")) or "loopback"),
        translator=translator,
        whisper_model=_clean(source.get("CAPTIONS_WHISPER_MODEL")) or "base.en",
        whisper_device=device,
        whisper_compute=_clean(source.get("CAPTIONS_WHISPER_COMPUTE")),
        cpu_threads=_env_int(source, "CAPTIONS_CPU_THREADS", 4, 1, 32),
        vad_threshold=vad,
        loopback_name=_clean(source.get("CAPTIONS_LOOPBACK_NAME")),
        bar_alpha=clamp_alpha(alpha),
        deepl_key=_clean(source.get("DEEPL_API_KEY")),
        openai_key=_clean(source.get("OPENAI_API_KEY")),
        openai_model=_clean(source.get("OPENAI_MODEL")) or "gpt-4.1-mini",
        openai_base_url=_clean(source.get("OPENAI_BASE_URL")) or "https://api.openai.com/v1",
        libre_url=_clean(source.get("LIBRETRANSLATE_URL")),
        libre_key=_clean(source.get("LIBRETRANSLATE_API_KEY")),
    )


def public_summary(config: AppConfig) -> str:
    def flag(value: str | None) -> str:
        return "set" if value else "unset"

    return (
        f"audio={config.audio} translator={config.translator} "
        f"whisper={config.whisper_model} device={config.whisper_device} "
        f"deepl={flag(config.deepl_key)} openai={flag(config.openai_key)} "
        f"libre={'set' if config.libre_url else 'unset'}"
    )


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.lower().startswith("export "):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def env_file() -> Path:
    return app_dir() / ".env"


@dataclass
class Settings:
    audio: str = "loopback"
    click_through: bool = False
    font_delta: int = 0
    x: int | None = None
    y: int | None = None
    width: int | None = None


def load_settings(path: Path) -> Settings:
    if not path.is_file():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    audio = data.get("audio", "loopback")
    if audio not in {"loopback", "mic"}:
        audio = "loopback"
    font_delta = data.get("font_delta", 0)
    if not isinstance(font_delta, int):
        font_delta = 0

    def as_int(name: str) -> int | None:
        value = data.get(name)
        return value if isinstance(value, int) else None

    return Settings(
        audio=audio,
        click_through=bool(data.get("click_through", False)),
        font_delta=font_delta,
        x=as_int("x"),
        y=as_int("y"),
        width=as_int("width"),
    )


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "audio": settings.audio,
        "click_through": settings.click_through,
        "font_delta": settings.font_delta,
        "x": settings.x,
        "y": settings.y,
        "width": settings.width,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_audio(
    *,
    cli: str | None,
    settings: Settings,
    settings_existed: bool,
    env_audio: str,
) -> str:
    if cli in {"loopback", "mic"}:
        return cli
    if settings_existed and settings.audio in {"loopback", "mic"}:
        return settings.audio
    return env_audio


def configure_logging(verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(data_dir() / "captions.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


def windows_banner() -> str:
    if sys.platform == "win32":
        return "拖曳字幕列可移動。Ctrl+Alt+C 點擊穿透，Ctrl+Alt+H 隱藏，Ctrl+Alt+A 切換音訊，Ctrl+Alt+Q 結束。"
    return "WASAPI 系統迴路與全域熱鍵只在 Windows 上有效。"
