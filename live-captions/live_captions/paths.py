from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    override = os.environ.get("CAPTIONS_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        path = root / "OpticsLiveCaptions"
    else:
        path = Path.home() / ".optics-live-captions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    override = os.environ.get("CAPTIONS_CACHE_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = root / "OpticsLiveCaptions"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        path = root / "optics-live-captions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_dir() -> Path:
    return cache_dir() / "models" / "translate-en-zh"


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total
