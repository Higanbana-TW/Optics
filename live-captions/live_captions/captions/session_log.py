"""One bilingual text file for each caption session."""

from __future__ import annotations

import ctypes
import os
import sys
from datetime import datetime
from pathlib import Path

from live_captions.captions.format import collapse_space


def documents_dir() -> Path:
    """The user's Documents folder. CAPTIONS_TRANSCRIPT_DIR overrides it."""
    override = os.environ.get("CAPTIONS_TRANSCRIPT_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        path = _windows_documents_dir()
    else:
        path = Path.home() / "Documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def transcript_filename(when: datetime) -> str:
    return when.strftime("Optics-captions-%Y-%m-%d_%H%M%S.txt")


def format_session_transcript(lines: list[tuple[str, str]]) -> str:
    """Every bilingual line, oldest first. Nothing is dropped."""
    blocks: list[str] = []
    for english, traditional in lines:
        parts = [collapse_space(part) for part in (english, traditional)]
        parts = [part for part in parts if part]
        if parts:
            blocks.append("\n".join(parts))
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def write_session_transcript(
    lines: list[tuple[str, str]],
    *,
    directory: Path | None = None,
    when: datetime | None = None,
) -> Path | None:
    text = format_session_transcript(lines)
    if not text.strip():
        return None
    when = when or datetime.now()
    folder = directory or documents_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / transcript_filename(when)
    suffix = path.suffix
    stem = path.stem
    number = 2
    while path.exists():
        path = folder / f"{stem}-{number}{suffix}"
        number += 1
    # newline="\r\n" writes CRLF on Linux and Windows. The default text mode
    # would turn an already-converted CRLF into CRCRLF on Windows.
    with path.open("w", encoding="utf-8-sig", newline="\r\n") as handle:
        handle.write(text)
    return path


def _windows_documents_dir() -> Path:
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    folder_id = GUID(
        0xFDD39AD0,
        0x238F,
        0x46AF,
        (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
    )
    pointer = ctypes.c_wchar_p()
    try:
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id),
            0,
            None,
            ctypes.byref(pointer),
        )
    except Exception:
        return Path.home() / "Documents"
    if result != 0 or not pointer.value:
        return Path.home() / "Documents"
    path = Path(pointer.value)
    try:
        ctypes.windll.ole32.CoTaskMemFree(pointer)
    except Exception:
        pass
    return path
