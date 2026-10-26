# -*- mode: python ; coding: utf-8 -*-
"""Windows onedir build for LiveCaptions.exe.

Run on windows-latest. Speech and translation models are not collected;
the app downloads them on first launch.
"""

import os

from PyInstaller.utils.hooks import collect_all

root = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = []
binaries = []
hiddenimports = [
    "live_captions",
    "live_captions.cli",
    "numpy",
    "httpx",
    "httpcore",
    "certifi",
    "h11",
    "anyio",
    "huggingface_hub",
    "tokenizers",
    "tqdm",
    "yaml",
    "opencc",
    "pyaudiowpatch",
    "sounddevice",
]

# Qt, OpenCC dictionaries, CTranslate2, and the audio libraries must travel
# with the exe. Model weights are intentionally absent.
for package in (
    "PySide6",
    "shiboken6",
    "opencc",
    "certifi",
    "ctranslate2",
    "faster_whisper",
    "av",
    "sounddevice",
    "pyaudiowpatch",
    "sentencepiece",
    "onnxruntime",
    "huggingface_hub",
    "tokenizers",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(SPECPATH, "livecaptions_entry.py")],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPECPATH, "rthook_qt.py")],
    excludes=["torch", "tensorflow", "pandas", "matplotlib", "tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LiveCaptions",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LiveCaptions",
)
