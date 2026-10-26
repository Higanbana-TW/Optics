from __future__ import annotations

import queue
import sys
from pathlib import Path

from live_captions.captions.format import caption_history_text, collapse_space, font_sizes
from live_captions.captions.placement import Rect, resolve_bar_rect
from live_captions.config import Settings, save_settings
from live_captions.pipeline import CaptionState
from live_captions.ui.bridge import UiBridge
from live_captions.ui.hotkeys import (
    HOTKEY_AUDIO,
    HOTKEY_CLICK_THROUGH,
    HOTKEY_HIDE,
    HOTKEY_QUIT,
)
from live_captions.ui.win32 import apply_windows_overlay

try:
    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtGui import QAction, QColor, QCursor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QLabel,
        QMenu,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only when the GUI dependency is missing
    raise ImportError(
        "無法載入介面元件（PySide6）。請在 live-captions 目錄執行 pip install -r requirements.txt。"
    ) from exc


def _apply_family(font: QFont) -> None:
    families = ["Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "Segoe UI"]
    if hasattr(font, "setFamilies"):
        font.setFamilies(families)
    else:
        font.setFamily(families[0])


def build_tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(8, 10, 14, 230))
    painter.setPen(QColor(255, 255, 255, 50))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setPen(QColor("white"))
    font = QFont()
    font.setPointSize(18)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "字")
    painter.end()
    return QIcon(pixmap)


class CaptionWindow(QWidget):
    def __init__(self, settings: Settings, settings_path: Path, bar_alpha: int) -> None:
        super().__init__()
        self.settings = settings
        self.settings_path = settings_path
        self.bar_alpha = bar_alpha
        self.bridge = UiBridge()
        self.hotkey_queue: queue.Queue[int] = queue.Queue()
        self.on_audio_change = None
        self.on_quit_requested = None
        self._drag_offset: QPoint | None = None
        self._has_caption = False
        self._status_text = "正在啟動…"
        self._current: CaptionState | None = None
        self._recent: list[CaptionState] = []
        self._anchor_bottom: int | None = None
        self._build()
        self._apply_fonts()
        self._place()
        self._render_status()
        timer = QTimer(self)
        timer.timeout.connect(self._poll)
        timer.start(50)
        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._sync_win32)
        if sys.platform == "win32":
            self._topmost_timer.start(1500)

    def _build(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if sys.platform == "win32":
            flags |= Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Optic 即時字幕")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        self.frame = QFrame()
        self.frame.setObjectName("bar")
        self.frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        outer.addWidget(self.frame)
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(22, 12, 22, 14)
        layout.setSpacing(2)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.history = QLabel()
        self.history.setObjectName("history")
        self.history.setWordWrap(True)
        self.history.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.english = QLabel()
        self.english.setObjectName("english")
        self.english.setWordWrap(True)
        self.english.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.chinese = QLabel()
        self.chinese.setObjectName("chinese")
        self.chinese.setWordWrap(True)
        self.chinese.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for label in (self.status, self.history, self.english, self.chinese):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(label)
        self.history.hide()
        self.english.hide()
        self.chinese.hide()
        self.setStyleSheet(
            f"""
            #bar {{
                background-color: rgba(8, 10, 14, {self.bar_alpha});
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 36);
            }}
            QLabel {{ background: transparent; }}
            #history {{ color: rgba(210, 214, 220, 168); }}
            #english {{ color: rgba(230, 232, 236, 230); }}
            #chinese {{ color: #ffffff; }}
            #status {{ color: rgba(186, 214, 255, 230); }}
            """
        )
        self._build_tray()

    def _build_tray(self) -> None:
        self.menu = QMenu(self)
        self.action_show = QAction("顯示字幕", self)
        self.action_audio_loopback = QAction("音訊：系統播放", self)
        self.action_audio_mic = QAction("音訊：麥克風", self)
        self.action_click = QAction("點擊穿透", self)
        self.action_larger = QAction("字體放大", self)
        self.action_smaller = QAction("字體縮小", self)
        self.action_quit = QAction("結束", self)
        self.action_audio_loopback.setCheckable(True)
        self.action_audio_mic.setCheckable(True)
        self.action_click.setCheckable(True)
        self.action_show.triggered.connect(self.toggle_visible)
        self.action_audio_loopback.triggered.connect(lambda: self.set_audio("loopback"))
        self.action_audio_mic.triggered.connect(lambda: self.set_audio("mic"))
        self.action_click.triggered.connect(lambda checked: self.set_click_through(bool(checked)))
        self.action_larger.triggered.connect(lambda: self.change_font(1))
        self.action_smaller.triggered.connect(lambda: self.change_font(-1))
        self.action_quit.triggered.connect(self.request_quit)
        for action in (
            self.action_show,
            self.action_audio_loopback,
            self.action_audio_mic,
            self.action_click,
            self.action_larger,
            self.action_smaller,
            self.action_quit,
        ):
            self.menu.addAction(action)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(build_tray_icon(), self)
            self.tray.setToolTip("Optic 即時字幕")
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()
        self._sync_menu()

    def _place(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            self.setFixedWidth(880)
            if self._anchor_bottom is None:
                self._anchor_bottom = self.y() + self.height()
            self._fit_to_text()
            return
        area = screen.availableGeometry()
        work = Rect(area.x(), area.y(), area.width(), area.height())
        screens = []
        for item in QGuiApplication.screens():
            geo = item.availableGeometry()
            screens.append(Rect(geo.x(), geo.y(), geo.width(), geo.height()))
        rect = resolve_bar_rect(self.settings.x, self.settings.y, self.settings.width, work, screens or [work])
        self.setFixedWidth(rect.width)
        self.move(rect.x, rect.y)
        self._anchor_bottom = rect.y + rect.height
        self._fit_to_text()

    def _apply_fonts(self) -> None:
        english_size, chinese_size = font_sizes(self.settings.font_delta)
        english = QFont()
        _apply_family(english)
        english.setPointSize(english_size)
        self.english.setFont(english)
        history = QFont()
        _apply_family(history)
        history.setPointSize(max(11, english_size - 1))
        self.history.setFont(history)
        chinese = QFont()
        _apply_family(chinese)
        chinese.setPointSize(chinese_size)
        chinese.setWeight(QFont.Weight.Normal)
        self.chinese.setFont(chinese)
        self._apply_status_style()
        self._fit_to_text()

    def _apply_status_style(self) -> None:
        font = QFont()
        _apply_family(font)
        font.setPointSize(16 if not self._has_caption else 11)
        self.status.setFont(font)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_win32()

    def _sync_win32(self) -> None:
        apply_windows_overlay(int(self.winId()), click_through=self.settings.click_through)

    def _poll(self) -> None:
        while True:
            try:
                hotkey_id = self.hotkey_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_hotkey(hotkey_id)
        status = self.bridge.drain_statuses()
        if status is not None:
            self._status_text = status
            self._render_status()
        for state in self.bridge.drain_captions():
            self.set_caption(state)

    def _handle_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == HOTKEY_CLICK_THROUGH:
            self.set_click_through(not self.settings.click_through)
        elif hotkey_id == HOTKEY_HIDE:
            self.toggle_visible()
        elif hotkey_id == HOTKEY_AUDIO:
            self.toggle_audio()
        elif hotkey_id == HOTKEY_QUIT:
            self.request_quit()

    def set_caption(self, state: CaptionState) -> None:
        if self._current is not None and state != self._current:
            self._recent.append(self._current)
            del self._recent[:-3]
        self._current = state
        history = caption_history_text(
            [(item.english, item.traditional) for item in self._recent],
            limit=3,
        )
        self._set_wrapped(self.history, history)
        self._set_wrapped(self.english, collapse_space(state.english))
        self._set_wrapped(self.chinese, collapse_space(state.traditional))
        self._has_caption = bool(state.english.strip() or state.traditional.strip())
        self._apply_status_style()
        self._fit_to_text()

    def _set_wrapped(self, label, text: str) -> None:
        label.setText(text)
        label.setVisible(bool(text.strip()))

    def _render_status(self) -> None:
        text = self._status_text
        if self.settings.click_through:
            text = f"點擊穿透 · {text}" if text else "點擊穿透 · Ctrl+Alt+C 關閉"
        self.status.setText(text)
        self._fit_to_text()

    def set_click_through(self, enabled: bool) -> None:
        self.settings.click_through = enabled
        self._save()
        self._sync_menu()
        self._sync_win32()
        self._render_status()

    def set_audio(self, mode: str) -> None:
        if mode not in {"loopback", "mic"} or mode == self.settings.audio:
            self._sync_menu()
            return
        self.settings.audio = mode
        self._save()
        self._sync_menu()
        if self.on_audio_change is not None:
            self.on_audio_change(mode)

    def toggle_audio(self) -> None:
        self.set_audio("mic" if self.settings.audio == "loopback" else "loopback")

    def change_font(self, step: int) -> None:
        self.settings.font_delta = max(-6, min(16, self.settings.font_delta + step))
        self._apply_fonts()
        self._save()

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
            self.action_show.setText("顯示字幕")
        else:
            self.show()
            self.raise_()
            self._sync_win32()
            self.action_show.setText("隱藏字幕")

    def _sync_menu(self) -> None:
        self.action_audio_loopback.setChecked(self.settings.audio == "loopback")
        self.action_audio_mic.setChecked(self.settings.audio == "mic")
        self.action_click.setChecked(self.settings.click_through)
        self.action_show.setText("隱藏字幕" if self.isVisible() else "顯示字幕")

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def request_quit(self) -> None:
        self._remember_geometry()
        if self.on_quit_requested is not None:
            self.on_quit_requested()
        else:
            QApplication.quit()

    def contextMenuEvent(self, event) -> None:
        self.menu.exec(event.globalPosition().toPoint())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.settings.click_through:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._remember_geometry()
        super().mouseReleaseEvent(event)

    def _text_width(self) -> int:
        outer = self.layout().contentsMargins()
        inner = self.frame.layout().contentsMargins()
        return max(160, self.width() - outer.left() - outer.right() - inner.left() - inner.right())

    def _fit_to_text(self) -> None:
        if self.width() < 200 or self.layout() is None or self.frame.layout() is None:
            return
        text_width = self._text_width()
        labels = (self.status, self.history, self.english, self.chinese)
        heights: list[int] = []
        for label in labels:
            if not label.isVisible() or not label.text().strip():
                label.setMinimumHeight(0)
                label.setMaximumHeight(16777215)
                continue
            height = max(1, label.heightForWidth(text_width))
            label.setMinimumHeight(height)
            label.setMaximumHeight(max(height, label.sizeHint().height()))
            heights.append(height)
        if not heights:
            return
        outer = self.layout().contentsMargins()
        inner = self.frame.layout().contentsMargins()
        spacing = self.frame.layout().spacing()
        total = (
            outer.top()
            + outer.bottom()
            + inner.top()
            + inner.bottom()
            + sum(heights)
            + spacing * (len(heights) - 1)
            + 6
        )
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else None
        if area is not None:
            total = min(total, max(120, int(area.height() * 0.55)))
        geo = self.geometry()
        bottom = self._anchor_bottom if self._anchor_bottom is not None else geo.y() + max(geo.height(), total)
        y = bottom - total
        if area is not None:
            if y < area.top():
                y = area.top()
            if y + total > area.bottom() + 1:
                y = max(area.top(), area.bottom() + 1 - total)
        self.setFixedHeight(total)
        if geo.x() != self.x() or y != self.y():
            self.move(geo.x(), y)
        self._anchor_bottom = y + total

    def _remember_geometry(self) -> None:
        geo = self.geometry()
        self._anchor_bottom = geo.y() + geo.height()
        self.settings.x = geo.x()
        self.settings.y = geo.y()
        self.settings.width = geo.width()
        self._save()

    def _save(self) -> None:
        save_settings(self.settings_path, self.settings)

    def closeEvent(self, event) -> None:
        self._remember_geometry()
        super().closeEvent(event)
