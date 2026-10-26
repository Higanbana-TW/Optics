from __future__ import annotations

import ctypes
import sys

# Extended style bits for a layered, non-activating, optionally click-through window.
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def next_exstyle(style: int, *, click_through: bool) -> int:
    style |= WS_EX_LAYERED | WS_EX_NOACTIVATE
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    return style


def apply_windows_overlay(hwnd: int, *, click_through: bool) -> None:
    if sys.platform != "win32" or not hwnd:
        return
    user32 = ctypes.windll.user32
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.GetWindowLongPtrW.restype = ctypes.c_void_p
        user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        current = int(user32.GetWindowLongPtrW(hwnd, -20) or 0)
        updated = next_exstyle(current, click_through=click_through)
        user32.SetWindowLongPtrW(hwnd, -20, ctypes.c_void_p(updated))
    else:
        current = int(user32.GetWindowLongW(hwnd, -20) or 0)
        updated = next_exstyle(current, click_through=click_through)
        user32.SetWindowLongW(hwnd, -20, updated)
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )
