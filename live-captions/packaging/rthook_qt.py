"""Point a frozen build at the Qt plugins collected beside the executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _plugin_root() -> Path | None:
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        roots.append(Path(sys.executable).resolve().parent / "_internal")
    for root in roots:
        for plugins in (root / "PySide6" / "plugins", root / "PySide6" / "Qt" / "plugins"):
            if plugins.is_dir():
                return plugins
    return None


plugins = _plugin_root()
if plugins is not None:
    os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins / "platforms"))
