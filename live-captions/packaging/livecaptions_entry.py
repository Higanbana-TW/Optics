"""Double-click entry for LiveCaptions.exe.

PyInstaller freezes this script. The Python package is still started with
``python -m live_captions``.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
from pathlib import Path


def _ensure_stdio() -> None:
    """A windowed executable starts with stdout and stderr set to None."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = Path(sys.executable).resolve().parent / "LiveCaptions.log"
    handle = open(log_path, "a", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle


def main() -> None:
    multiprocessing.freeze_support()
    _ensure_stdio()
    try:
        from live_captions.cli import main as cli_main

        raise SystemExit(cli_main())
    except SystemExit:
        raise
    except Exception:
        text = traceback.format_exc()
        log_path: Path | None
        try:
            log_path = Path(sys.executable).resolve().parent / "LiveCaptions-error.log"
            log_path.write_text(text, encoding="utf-8")
        except OSError:
            log_path = None
        if sys.platform == "win32" and os.environ.get("CAPTIONS_NO_ERROR_DIALOG") != "1":
            try:
                import ctypes

                detail = f"\n\n{log_path}" if log_path is not None else ""
                ctypes.windll.user32.MessageBoxW(
                    None,
                    "字幕程式啟動失敗。" + detail,
                    "Optic 即時字幕",
                    0x10,
                )
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
