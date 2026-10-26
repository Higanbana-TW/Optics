from __future__ import annotations

import logging
import queue
import sys
import threading

import numpy as np

from live_captions.asr.whisper_engine import WHISPER_BASE_EN_BYTES, explain_load_error, make_whisper
from live_captions.captions.format import format_caption
from live_captions.audio.process import UtteranceSegmenter, offer_drop_oldest, resample_linear
from live_captions.audio.select import OpenedSource, list_audio_report, listening_status
from live_captions.config import AppConfig, load_settings, save_settings
from live_captions.errors import AudioUnavailable, CaptionsError
from live_captions.paths import directory_size, model_dir
from live_captions.pipeline import CaptionPipeline, caption_from_transcript
from live_captions.translate.factory import build_translator
from live_captions.ui.bridge import UiBridge

log = logging.getLogger(__name__)


def ensure_startup_loopback(settings, settings_path) -> str:
    """Every launch listens to meeting playback. A saved microphone does not stick."""
    stale_mic = settings_path.is_file() and load_settings(settings_path).audio == "mic"
    settings.audio = "loopback"
    if stale_mic:
        save_settings(settings_path, settings)
    return "loopback"


def open_requested_source(prefer: str, open_loopback, open_mic) -> OpenedSource:
    """Open loopback or, only when asked, the microphone. Never fall back."""
    if prefer == "mic":
        try:
            return OpenedSource(open_mic(), "mic", "")
        except AudioUnavailable:
            raise
        except Exception as exc:
            raise AudioUnavailable("無法開啟麥克風。") from exc
    try:
        return OpenedSource(open_loopback(), "loopback", "")
    except AudioUnavailable:
        raise
    except Exception as exc:
        raise AudioUnavailable(f"無法開啟系統音訊：{exc}") from exc


def _loopback_device(loopback_name: str | None):
    if sys.platform != "win32":
        raise AudioUnavailable("WASAPI 系統迴路只支援 Windows。")
    from live_captions.audio.wasapi import WasapiLoopbackSource

    return WasapiLoopbackSource(name_contains=loopback_name)


def _microphone_device():
    from live_captions.audio.microphone import MicrophoneSource

    return MicrophoneSource()

DEMO_LINES = (
    "Hello everyone, thanks for joining the meeting.",
    "Let's start by reviewing the project timeline.",
    "Could you share your screen and walk us through the document?",
    "I will send the meeting notes after this call.",
)


class CaptionService:
    def __init__(
        self,
        config: AppConfig,
        translator,
        asr,
        bridge: UiBridge,
        *,
        demo: bool,
        audio_mode: str,
    ) -> None:
        self.config = config
        self.translator = translator
        self.asr = asr
        self.bridge = bridge
        self.demo = demo
        self.mode = audio_mode
        self.pipeline = CaptionPipeline(translator)
        self.stop = threading.Event()
        self.restart = threading.Event()
        self.listen_status = "正在啟動…"
        self._source = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._worker, name="caption-worker", daemon=True)
        self._thread.start()

    def stop_service(self) -> None:
        self.stop.set()
        self.restart.set()
        source = self._source
        if source is not None:
            source.close()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)

    def set_audio(self, mode: str) -> None:
        self.mode = mode
        self.restart.set()

    def _worker(self) -> None:
        try:
            if self.stop.is_set():
                return
            if not self.demo:
                self.bridge.publish_status("正在載入語音模型…（第一次會下載約 139 MB）")
                try:
                    self.asr.load()
                except Exception as exc:
                    message = (
                        str(exc)
                        if isinstance(exc, CaptionsError)
                        else explain_load_error(exc, platform_name=sys.platform)
                    )
                    self.bridge.publish_status(message)
                    return
                if self.stop.is_set():
                    return
            self.bridge.publish_status("正在準備翻譯模型…（第一次會下載約 68 MB）")
            try:
                self.translator.warmup(on_status=self.bridge.publish_status)
            except Exception as exc:
                message = str(exc) if isinstance(exc, CaptionsError) else f"翻譯模型無法載入：{exc}"
                self.bridge.publish_status(message)
                return
            if self.stop.is_set():
                return
            if self.demo:
                self._demo_loop()
            else:
                self._audio_session()
        except Exception as exc:
            log.exception("caption worker failed")
            self.bridge.publish_status(f"發生錯誤：{exc}")

    def _demo_loop(self) -> None:
        self.listen_status = "示範句子"
        self.bridge.publish_status(self.listen_status)
        index = 0
        while not self.stop.is_set():
            line = DEMO_LINES[index % len(DEMO_LINES)]
            index += 1
            self._publish_transcript(line)
            if self.stop.wait(4):
                return

    def _audio_session(self) -> None:
        utterances: queue.Queue = queue.Queue(maxsize=2)

        def capture() -> None:
            try:
                self._capture(utterances)
            finally:
                utterances.put(None)

        capture_thread = threading.Thread(target=capture, name="caption-audio", daemon=True)
        capture_thread.start()
        try:
            while not self.stop.is_set():
                try:
                    item = utterances.get(timeout=0.3)
                except queue.Empty:
                    continue
                if item is None:
                    return
                self._transcribe_utterance(item)
        finally:
            self.stop.set()
            source = self._source
            if source is not None:
                source.close()
            capture_thread.join(timeout=3)

    def _capture(self, utterances: queue.Queue) -> None:
        segmenter = UtteranceSegmenter(threshold=self.config.vad_threshold)
        while not self.stop.is_set():
            self.restart.clear()
            try:
                opened = open_requested_source(
                    self.mode,
                    lambda: _loopback_device(self.config.loopback_name),
                    _microphone_device,
                )
            except CaptionsError as exc:
                self.bridge.publish_status(str(exc))
                if self.stop.wait(3):
                    return
                continue
            self._source = opened.source
            device_name = str(getattr(opened.source, "device_name", "") or "")
            self.listen_status = listening_status(opened.mode, device_name)
            self.bridge.publish_status(self.listen_status)
            log.info("audio mode=%s device=%s", opened.mode, device_name)
            try:
                for chunk in opened.source.frames(self.stop, self.restart):
                    samples = resample_linear(chunk, int(opened.source.sample_rate), 16000)
                    for utterance in segmenter.push(samples):
                        offer_drop_oldest(utterances, utterance)
            except Exception as exc:
                if not (self.stop.is_set() or self.restart.is_set()):
                    log.exception("audio capture failed")
                    self.bridge.publish_status(f"音訊中斷：{exc}")
            finally:
                for utterance in segmenter.flush():
                    offer_drop_oldest(utterances, utterance)
                source = self._source
                self._source = None
                if source is not None:
                    source.close()
            if self.stop.is_set():
                return
            segmenter = UtteranceSegmenter(threshold=self.config.vad_threshold)

    def _transcribe_utterance(self, audio: np.ndarray) -> None:
        try:
            text = self.asr.transcribe(audio)
        except Exception as exc:
            log.exception("speech recognition failed")
            self.bridge.publish_status(f"語音辨識失敗：{exc}")
            return
        self._publish_transcript(text)

    def _publish_transcript(self, text: str) -> None:
        state, error = caption_from_transcript(self.pipeline, text)
        if error:
            self.bridge.publish_status(error)
            return
        if state is None:
            return
        log.debug("caption %s | %s", state.english, state.traditional)
        self.bridge.publish_caption(state)
        self.bridge.publish_status(self.listen_status)


def run_headless_lines(config: AppConfig, lines: tuple[str, ...] | list[str]) -> int:
    translator = build_translator(config)
    translator.warmup(on_status=print)
    pipeline = CaptionPipeline(translator)
    produced = 0
    for line in lines:
        state, error = caption_from_transcript(pipeline, line)
        if error:
            print(error, file=sys.stderr)
            return 2
        if state is None:
            continue
        formatted = format_caption(state.english, state.traditional)
        print(formatted.english)
        print(formatted.traditional)
        print()
        produced += 1
    if produced == 0:
        print("沒有產生字幕。", file=sys.stderr)
        return 2
    return 0


def run_setup(config: AppConfig) -> int:
    translator = build_translator(config)
    if config.translator == "local":
        print("準備本機翻譯模型…", flush=True)
        translator.warmup(on_status=print)
        root = model_dir()
        print(f"翻譯模型：{directory_size(root)} bytes，位置 {root}", flush=True)
    else:
        print("翻譯引擎不是本機模型，略過翻譯模型下載。", flush=True)
    print(f"準備語音模型 {config.whisper_model}…", flush=True)
    print(f"base.en 公開大小為 {WHISPER_BASE_EN_BYTES} bytes。", flush=True)
    engine = make_whisper(config)
    engine.load()
    print(f"語音模型已載入：{config.whisper_model}（{engine.device}, {engine.compute_type}）", flush=True)
    return 0


def run_app(config: AppConfig, settings, settings_path, *, demo: bool) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "無法載入介面元件（PySide6）。請在 live-captions 目錄執行 pip install -r requirements.txt。",
            file=sys.stderr,
        )
        return 1
    import ctypes

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Higanbana.Optics.LiveCaptions")
        except Exception:
            pass
    app = QApplication([])
    app.setApplicationName("Optic 即時字幕")
    app.setQuitOnLastWindowClosed(False)
    from live_captions.ui.hotkeys import GlobalHotkeys
    from live_captions.ui.overlay import CaptionWindow

    audio_mode = ensure_startup_loopback(settings, settings_path)
    window = CaptionWindow(settings, settings_path, config.bar_alpha)
    translator = build_translator(config)
    service = CaptionService(
        config,
        translator,
        make_whisper(config),
        window.bridge,
        demo=demo,
        audio_mode=audio_mode,
    )
    window.on_audio_change = service.set_audio

    def quit_app() -> None:
        service.stop_service()
        app.quit()

    window.on_quit_requested = quit_app
    hotkeys = GlobalHotkeys(window.hotkey_queue)
    hotkeys.start()
    window.show()
    service.start()
    code = app.exec()
    hotkeys.stop()
    service.stop_service()
    return int(code)


def list_audio() -> int:
    print(list_audio_report())
    return 0
