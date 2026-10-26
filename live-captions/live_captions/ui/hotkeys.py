from __future__ import annotations

import ctypes
import queue
import sys
import threading
from ctypes import wintypes

HOTKEY_CLICK_THROUGH = 1
HOTKEY_HIDE = 2
HOTKEY_AUDIO = 3
HOTKEY_QUIT = 4

_MOD = 0x0002 | 0x0001 | 0x4000  # Ctrl + Alt, no autorepeat
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_BINDINGS = (
    (HOTKEY_CLICK_THROUGH, ord("C"), "Ctrl+Alt+C"),
    (HOTKEY_HIDE, ord("H"), "Ctrl+Alt+H"),
    (HOTKEY_AUDIO, ord("A"), "Ctrl+Alt+A"),
    (HOTKEY_QUIT, ord("Q"), "Ctrl+Alt+Q"),
)


class GlobalHotkeys:
    """Register Ctrl+Alt hotkeys on Windows. On other systems this is a no-op."""

    def __init__(self, sink: queue.Queue) -> None:
        self.sink = sink
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    def start(self) -> None:
        if sys.platform != "win32" or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="caption-hotkeys", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        thread_id = self._thread_id
        if thread_id:
            ctypes.windll.user32.PostThreadMessageW(thread_id, _WM_QUIT, 0, 0)
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        registered: list[int] = []
        for hotkey_id, virtual_key, label in _BINDINGS:
            if user32.RegisterHotKey(None, hotkey_id, _MOD, virtual_key):
                registered.append(hotkey_id)
            else:
                print(f"無法註冊熱鍵 {label}", flush=True)
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        user32.GetMessageW.restype = ctypes.c_int
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) != 0:
            if message.message == _WM_HOTKEY:
                self.sink.put(int(message.wParam))
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)
