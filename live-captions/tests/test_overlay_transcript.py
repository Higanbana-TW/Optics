import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from live_captions.config import Settings
from live_captions.pipeline import CaptionState
from live_captions.ui.overlay import CaptionWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _wheel(widget, delta: int) -> None:
    local = QPointF(widget.rect().center())
    event = QWheelEvent(
        local,
        QPointF(widget.mapToGlobal(widget.rect().center())),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_scrollable_window_keeps_the_whole_session_and_writes_it(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPTIONS_TRANSCRIPT_DIR", str(tmp_path))
    window = CaptionWindow(Settings(), tmp_path / "settings.json", bar_alpha=210)
    window.on_quit_requested = lambda: None
    window.show()
    qapp.processEvents()

    opening = "alpha-start english"
    for index in range(8):
        window.set_caption(
            CaptionState(
                f"{opening} sentence {index} " + ("meeting notes " * 12),
                f"開頭繁體 {index} " + ("會議字幕 " * 12),
            )
        )
    qapp.processEvents()

    text = window.view.toPlainText()
    assert text.index(opening) < text.index("sentence 7")
    assert text.index("開頭繁體 0") < text.index("開頭繁體 7")
    assert len(window._lines) == 8
    assert window.view.height() <= 360
    assert window.view.document().size().height() > window.view.height()

    bar = window.view.verticalScrollBar()
    assert bar.maximum() > 40
    window._scroll_to_bottom()
    assert bar.value() >= bar.maximum() - 16
    _wheel(window.view.viewport(), 240)
    qapp.processEvents()
    assert bar.value() < bar.maximum() - 16

    bar.setValue(0)
    window.set_caption(CaptionState("omega-end english", "結尾繁體"))
    qapp.processEvents()
    assert bar.value() <= 16
    text = window.view.toPlainText()
    assert text.index(opening) < text.index("omega-end english")
    assert "結尾繁體" in text

    point = window.view.viewport().mapTo(window, window.view.viewport().rect().center())
    hit = window.childAt(point)
    assert hit is not None
    assert not hit.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not window.view.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    window.request_quit()
    window.close()
    qapp.processEvents()
    files = list(tmp_path.glob("Optics-captions-*.txt"))
    assert len(files) == 1
    saved = files[0].open(encoding="utf-8-sig", newline="").read()
    assert saved.index(opening) < saved.index("開頭繁體 0") < saved.index("omega-end english")
    assert saved.index("omega-end english") < saved.index("結尾繁體")
    assert "\r\n" in saved
    window.deleteLater()
    qapp.processEvents()


def test_closing_without_captions_writes_nothing(qapp, tmp_path, monkeypatch):
    folder = tmp_path / "empty"
    folder.mkdir()
    monkeypatch.setenv("CAPTIONS_TRANSCRIPT_DIR", str(folder))
    window = CaptionWindow(Settings(), tmp_path / "settings.json", bar_alpha=210)
    window.on_quit_requested = lambda: None
    window.request_quit()
    window.close()
    qapp.processEvents()
    assert list(folder.iterdir()) == []
    window.deleteLater()
    qapp.processEvents()
