from __future__ import annotations

import queue
import sys
from pathlib import Path

from live_captions.captions.format import collapse_space, font_sizes
from live_captions.captions.session_log import write_session_transcript
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
    from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
    from PySide6.QtGui import (
        QAction,
        QColor,
        QCursor,
        QFont,
        QGuiApplication,
        QIcon,
        QPainter,
        QPalette,
        QPixmap,
        QTextCharFormat,
        QTextCursor,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QLabel,
        QMenu,
        QSystemTrayIcon,
        QTextEdit,
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
        self._lines: list[CaptionState] = []
        self._anchor_bottom: int | None = None
        self._transcript_written = False
        self._build()
        self._apply_fonts()
        self._place()
        self._render_status()
        timer = QTimer(self)
        timer.timeout.connect(self._poll)
        timer.start(50)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._write_session_file)
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
        outer.addWidget(self.frame)
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(22, 12, 22, 14)
        layout.setSpacing(2)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.view = QTextEdit()
        self.view.setObjectName("transcript")
        self.view.setReadOnly(True)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setAcceptRichText(False)
        self.view.setUndoRedoEnabled(False)
        self.view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.view.viewport().setAutoFillBackground(False)
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.view.viewport().installEventFilter(self)
        self.frame.installEventFilter(self)
        self.frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.frame.customContextMenuRequested.connect(
            lambda pos: self.menu.exec(self.frame.mapToGlobal(pos))
        )
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(
            lambda pos: self.menu.exec(self.view.mapToGlobal(pos))
        )
        palette = self.view.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        palette.setColor(QPalette.ColorRole.Text, QColor(230, 232, 236))
        self.view.setPalette(palette)
        self.view.hide()
        layout.addWidget(self.status)
        layout.addWidget(self.view)
        self.setStyleSheet(
            f"""
            #bar {{
                background-color: rgba(8, 10, 14, {self.bar_alpha});
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 36);
            }}
            QLabel {{ background: transparent; }}
            #status {{ color: rgba(186, 214, 255, 230); }}
            #transcript {{
                background: transparent;
                border: none;
                color: rgba(230, 232, 236, 230);
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 90);
                border-radius: 4px;
                min-height: 24px;
            }}
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
        follow = self._following_bottom()
        scroll_value = self.view.verticalScrollBar().value()
        english_size, _chinese_size = font_sizes(self.settings.font_delta)
        font = QFont()
        _apply_family(font)
        font.setPointSize(english_size)
        self.view.setFont(font)
        self._refresh_transcript(follow=follow)
        self._apply_status_style()
        self._fit_to_text()
        if follow:
            self._scroll_to_bottom()
        else:
            self.view.verticalScrollBar().setValue(scroll_value)

    def _apply_status_style(self) -> None:
        font = QFont()
        _apply_family(font)
        font.setPointSize(16 if not self._has_caption else 11)
        self.status.setFont(font)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_to_text()
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
        if state == self._current:
            return
        english = collapse_space(state.english)
        traditional = collapse_space(state.traditional)
        if not english and not traditional:
            return
        follow = self._following_bottom()
        self._current = CaptionState(english=english, traditional=traditional)
        self._lines.append(self._current)
        self._append_block(self._current, follow=False)
        self._has_caption = True
        self.view.show()
        self._apply_status_style()
        self._fit_to_text()
        if follow:
            self._scroll_to_bottom()

    def _following_bottom(self) -> bool:
        if not self._lines or not self.view.isVisible():
            return True
        bar = self.view.verticalScrollBar()
        return bar.maximum() == 0 or bar.value() >= bar.maximum() - 16

    def _scroll_to_bottom(self) -> None:
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _append_block(self, state: CaptionState, *, follow: bool) -> None:
        english_size, chinese_size = font_sizes(self.settings.font_delta)
        cursor = QTextCursor(self.view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.view.document().characterCount() > 1:
            cursor.insertBlock()
            cursor.insertBlock()
        if state.english:
            english_format = QTextCharFormat()
            english_format.setFontPointSize(english_size)
            english_format.setForeground(QColor(230, 232, 236))
            cursor.insertText(state.english, english_format)
        if state.english and state.traditional:
            cursor.insertBlock()
        if state.traditional:
            chinese_format = QTextCharFormat()
            chinese_format.setFontPointSize(chinese_size)
            chinese_format.setForeground(QColor(255, 255, 255))
            cursor.insertText(state.traditional, chinese_format)
        if follow:
            self._scroll_to_bottom()

    def _refresh_transcript(self, *, follow: bool = True) -> None:
        lines = list(self._lines)
        self.view.clear()
        for state in lines:
            self._append_block(state, follow=False)
        if lines:
            self.view.show()
            if follow:
                self._scroll_to_bottom()

    def _write_session_file(self) -> None:
        if self._transcript_written:
            return
        self._transcript_written = True
        try:
            path = write_session_transcript([(item.english, item.traditional) for item in self._lines])
        except OSError as exc:
            print(f"字幕無法存檔：{exc}", flush=True)
            return
        if path is not None:
            print(f"字幕已存檔：{path}", flush=True)

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
        self._write_session_file()
        if self.on_quit_requested is not None:
            self.on_quit_requested()
        else:
            QApplication.quit()

    def contextMenuEvent(self, event) -> None:
        self.menu.exec(event.globalPosition().toPoint())

    def eventFilter(self, watched, event) -> bool:
        on_bar = watched is self.view.viewport() or watched is self.frame
        if on_bar and not self.settings.click_through:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if (
                event.type() == QEvent.Type.MouseMove
                and self._drag_offset is not None
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._drag_offset is not None:
                    self._drag_offset = None
                    self._remember_geometry()
                return True
        if event.type() == QEvent.Type.Wheel and watched is self.view.viewport():
            return False
        return super().eventFilter(watched, event)

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
        status_height = 0
        if self.status.isVisible() and self.status.text().strip():
            status_height = max(1, self.status.heightForWidth(text_width))
            self.status.setMinimumHeight(status_height)
            self.status.setMaximumHeight(max(status_height, self.status.sizeHint().height()))
        else:
            self.status.setMinimumHeight(0)
            self.status.setMaximumHeight(16777215)
        view_height = 0
        if self._lines and not self.view.isHidden():
            self.view.document().setTextWidth(text_width)
            document_height = int(self.view.document().size().height()) + 10
            screen_cap = 320
            screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
            if screen is not None:
                screen_cap = max(180, min(360, int(screen.availableGeometry().height() * 0.42)))
            view_height = min(screen_cap, max(72, document_height))
            self.view.setFixedHeight(view_height)
        heights = [height for height in (status_height, view_height) if height]
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
        self._write_session_file()
        super().closeEvent(event)
