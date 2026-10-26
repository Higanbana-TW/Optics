import hashlib
import queue
import struct
import zipfile

import numpy as np
import pytest

from live_captions.audio.process import (
    UtteranceSegmenter,
    offer_drop_oldest,
    pcm16_bytes_to_mono_f32,
    resample_linear,
)
from live_captions.audio.select import listening_status, pick_loopback, select_audio_source
from live_captions.config import Settings, save_settings
from live_captions.runtime import ensure_startup_loopback, open_requested_source
from live_captions.errors import AudioUnavailable, CaptionsError
from live_captions.translate.local_mt import EN_ZH_SHA256, EN_ZH_SIZE, safe_extract, sha256_file, split_for_translation
from live_captions.ui.bridge import UiBridge
from live_captions.ui.hotkeys import GlobalHotkeys
from live_captions.ui.win32 import WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TRANSPARENT, next_exstyle
from live_captions.asr.whisper_engine import WhisperEngine, explain_load_error, resolve_whisper_runtime
from live_captions.pipeline import CaptionState


def _frames(count: int, amplitude: float, frame: int = 480) -> np.ndarray:
    size = frame * count
    if amplitude == 0:
        return np.zeros(size, dtype=np.float32)
    time = np.arange(size, dtype=np.float32) / 16000
    return (amplitude * np.sin(2 * np.pi * 220 * time)).astype(np.float32)


def _segmenter(**kwargs) -> UtteranceSegmenter:
    params = dict(
        sample_rate=16000,
        frame_ms=30,
        threshold=0.01,
        silence_ms=300,
        min_speech_ms=300,
        max_speech_ms=900,
        preroll_ms=90,
        tail_ms=60,
    )
    params.update(kwargs)
    return UtteranceSegmenter(**params)


def test_pcm16_downmix_and_resample():
    raw = struct.pack("<hh", 32767, -32768)
    mono = pcm16_bytes_to_mono_f32(raw, 1)
    assert mono[0] == pytest.approx(32767 / 32768)
    assert mono[1] == pytest.approx(-1.0)
    stereo = pcm16_bytes_to_mono_f32(struct.pack("<hh", 32767, 0), 2)
    assert stereo[0] == pytest.approx(0.5, abs=1e-3)

    averaged = resample_linear(np.array([1, 1, 1, 3, 3, 3], dtype=np.float32), 48000, 16000)
    assert averaged.tolist() == pytest.approx([1, 3])
    identity = np.array([0.25, -0.5], dtype=np.float32)
    assert resample_linear(identity, 16000, 16000) is identity
    assert resample_linear(np.zeros(0, dtype=np.float32), 48000, 16000).size == 0
    stretched = resample_linear(np.ones(44100, dtype=np.float32), 44100, 16000)
    assert abs(stretched.size - 16000) <= 1
    assert np.allclose(stretched, 1, atol=1e-5)


def test_segmenter_emits_one_utterance_and_drops_a_short_blip():
    segmenter = _segmenter()
    assert segmenter.push(_frames(20, 0)) == []
    assert segmenter.flush() == []
    assert segmenter.push(np.concatenate([_frames(8, 0.2), _frames(12, 0)])) == []

    outputs = segmenter.push(np.concatenate([_frames(4, 0), _frames(15, 0.2), _frames(12, 0)]))
    assert len(outputs) == 1
    assert outputs[0].size == 19 * 480


def test_segmenter_splits_a_long_utterance_and_a_second_phrase():
    segmenter = _segmenter()
    outputs = segmenter.push(_frames(50, 0.2))
    assert len(outputs) == 1
    assert outputs[0].size == 30 * 480
    flushed = segmenter.flush()
    assert len(flushed) == 1
    assert flushed[0].size == 20 * 480

    pair = _segmenter().push(
        np.concatenate(
            [_frames(15, 0.2), _frames(12, 0), _frames(15, 0.2), _frames(12, 0)]
        )
    )
    assert len(pair) == 2


def test_quieter_threshold_hears_a_soft_tone():
    quiet = np.concatenate([_frames(15, 0.008), _frames(12, 0)])
    assert _segmenter(threshold=0.01).push(quiet) == []
    assert len(_segmenter(threshold=0.004).push(quiet)) == 1


def test_queue_drops_the_oldest_utterance():
    items: queue.Queue = queue.Queue(maxsize=1)
    offer_drop_oldest(items, "old")
    offer_drop_oldest(items, "new")
    assert items.get_nowait() == "new"


def test_loopback_failure_does_not_open_the_microphone():
    def fail_loopback():
        raise OSError("no wasapi")

    def mic():
        raise AssertionError("microphone opened")

    with pytest.raises(AudioUnavailable, match="無法開啟系統音訊"):
        select_audio_source("loopback", fail_loopback, mic)
    with pytest.raises(AudioUnavailable, match="找不到預設播放裝置"):
        select_audio_source("loopback", lambda: (_ for _ in ()).throw(AudioUnavailable("找不到預設播放裝置的 WASAPI 迴路。")), mic)

    opened = select_audio_source("mic", lambda: (_ for _ in ()).throw(AssertionError("loopback")), lambda: "m")
    assert opened.mode == "mic"
    assert opened.source == "m"
    assert opened.notice == ""


def test_startup_rewrites_a_saved_microphone_and_a_failed_loopback_stays_loopback(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(audio="mic", x=12, y=34, width=800)
    save_settings(path, settings)
    assert ensure_startup_loopback(settings, path) == "loopback"
    assert settings.audio == "loopback"
    saved = path.read_text(encoding="utf-8")
    assert '"audio": "loopback"' in saved
    assert '"x": 12' in saved

    def mic():
        raise AssertionError("microphone opened")

    with pytest.raises(AudioUnavailable, match="無法開啟系統音訊"):
        open_requested_source("loopback", lambda: (_ for _ in ()).throw(OSError("wasapi")), mic)
    opened = open_requested_source("loopback", lambda: type("Src", (), {"device_name": "Speakers (Realtek)"})(), mic)
    assert opened.mode == "loopback"
    assert listening_status(opened.mode, opened.source.device_name) == "聆聽系統音訊 · Speakers (Realtek)"


def test_named_loopback_does_not_silently_switch_to_the_microphone():
    def missing():
        raise AudioUnavailable("找不到名稱包含「Headset」的系統播放裝置。")

    with pytest.raises(AudioUnavailable, match="Headset"):
        select_audio_source("loopback", missing, lambda: "mic")


def test_pick_loopback_matches_the_default_playback_name():
    devices = [
        {"name": "Speakers (Realtek)", "isLoopbackDevice": False, "index": 1},
        {"name": "Speakers (Realtek) [Loopback]", "isLoopbackDevice": True, "index": 5},
        {"name": "Headphones [Loopback]", "isLoopbackDevice": True, "index": 6},
    ]
    chosen = pick_loopback(devices, default_output_name="Speakers (Realtek)", preferred_substring=None)
    assert chosen["index"] == 5
    chosen = pick_loopback(devices, default_output_name="Speakers (Realtek)", preferred_substring="head")
    assert chosen["index"] == 6
    with pytest.raises(AudioUnavailable):
        pick_loopback(devices, default_output_name="Speakers (Realtek)", preferred_substring="missing")


def test_listening_status_names_the_loopback_device():
    assert listening_status("loopback", "") == "聆聽系統音訊"
    assert listening_status("loopback", "Speakers (Realtek)") == "聆聽系統音訊 · Speakers (Realtek)"
    status = listening_status("mic", "N" * 50)
    assert status.startswith("聆聽麥克風 · ")
    assert status.endswith("…")


def test_click_through_style_bit_can_be_cleared():
    enabled = next_exstyle(0, click_through=True)
    assert enabled & WS_EX_TRANSPARENT
    assert enabled & WS_EX_LAYERED
    assert enabled & WS_EX_NOACTIVATE
    disabled = next_exstyle(enabled, click_through=False)
    assert not disabled & WS_EX_TRANSPARENT
    assert disabled & WS_EX_LAYERED
    assert disabled & WS_EX_NOACTIVATE


def test_hotkeys_do_not_start_a_thread_off_windows():
    if __import__("sys").platform == "win32":
        return
    hotkeys = GlobalHotkeys(queue.Queue())
    hotkeys.start()
    hotkeys.stop()


def test_bridge_keeps_every_caption_and_the_latest_status():
    bridge = UiBridge()
    bridge.publish_caption(CaptionState("one", "一"))
    bridge.publish_caption(CaptionState("two", "二"))
    bridge.publish_status("先")
    bridge.publish_status("後")
    assert bridge.drain_captions() == [
        CaptionState("one", "一"),
        CaptionState("two", "二"),
    ]
    assert bridge.drain_statuses() == "後"
    assert bridge.drain_captions() == []


def test_model_package_hash_is_pinned_and_zip_paths_are_rejected(tmp_path):
    assert len(EN_ZH_SHA256) == 64
    assert int(EN_ZH_SHA256, 16)
    assert EN_ZH_SIZE == 70_743_021
    payload = tmp_path / "blob.bin"
    payload.write_bytes(b"abc")
    assert sha256_file(payload) == hashlib.sha256(b"abc").hexdigest()

    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../evil.txt", "nope")
    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(CaptionsError, match="不安全"):
            safe_extract(archive, tmp_path / "out")

    good_path = tmp_path / "good.zip"
    with zipfile.ZipFile(good_path, "w") as archive:
        archive.writestr("translate/metadata.json", "{}")
    with zipfile.ZipFile(good_path) as archive:
        safe_extract(archive, tmp_path / "good")
    assert (tmp_path / "good" / "translate" / "metadata.json").is_file()


def test_translation_chunks_long_text_on_sentence_boundaries():
    chunks = split_for_translation("Hello there. This is the second sentence!")
    assert chunks == ["Hello there.", "This is the second sentence!"]
    long = "a" * 400
    pieces = split_for_translation(long, limit=180)
    assert "".join(pieces) == long
    assert max(len(piece) for piece in pieces) <= 180


def test_whisper_wrapper_skips_non_speech_and_short_audio():
    class Segment:
        def __init__(self, text, no_speech_prob):
            self.text = text
            self.no_speech_prob = no_speech_prob

    class Model:
        def transcribe(self, audio, **kwargs):
            assert kwargs["language"] == "en"
            assert kwargs["condition_on_previous_text"] is False
            assert kwargs["vad_filter"] is False
            return [Segment(" Hello everyone. ", 0.1), Segment(" noise ", 0.95)], None

    engine = WhisperEngine("base.en", "cpu", "int8", 1)
    engine._model = Model()
    assert engine.transcribe(np.ones(16000, dtype=np.float32)) == "Hello everyone."
    assert engine.transcribe(np.zeros(100, dtype=np.float32)) == ""


def test_whisper_device_selection_and_windows_dll_hint():
    assert resolve_whisper_runtime("auto", None, cuda_devices=0) == ("cpu", "int8")
    assert resolve_whisper_runtime("auto", None, cuda_devices=2) == ("cuda", "int8_float16")
    assert resolve_whisper_runtime("cpu", "int8", cuda_devices=4) == ("cpu", "int8")
    message = explain_load_error(OSError("DLL load failed"), platform_name="win32")
    assert "Visual C++" in message
    linux_message = explain_load_error(OSError("DLL load failed"), platform_name="linux")
    assert "Visual C++" not in linux_message
    assert "DLL load failed" in linux_message
