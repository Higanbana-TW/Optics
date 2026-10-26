import json

from live_captions.cli import main
from live_captions.config import (
    load_config,
    load_dotenv,
    load_settings,
    resolve_audio,
    save_settings,
    Settings,
)
from live_captions.errors import ConfigError
import pytest


def test_settings_roundtrip_has_no_secret_fields(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(
        path,
        Settings(audio="mic", click_through=True, font_delta=2, x=10, y=20, width=800),
    )
    text = path.read_text(encoding="utf-8")
    assert "key" not in text.lower()
    assert "secret" not in text.lower()
    loaded = load_settings(path)
    assert loaded.audio == "mic"
    assert loaded.click_through is True
    assert loaded.font_delta == 2
    assert (loaded.x, loaded.y, loaded.width) == (10, 20, 800)


def test_corrupt_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{", encoding="utf-8")
    assert load_settings(path) == Settings()
    path.write_text(json.dumps(["nope"]), encoding="utf-8")
    assert load_settings(path) == Settings()


def test_dotenv_does_not_override_existing_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "from-env")
    monkeypatch.delenv("CAPTIONS_AUDIO", raising=False)
    path = tmp_path / ".env"
    path.write_text('DEEPL_API_KEY="from-file"\nCAPTIONS_AUDIO=mic\n# comment\n', encoding="utf-8")
    load_dotenv(path)
    assert __import__("os").environ["DEEPL_API_KEY"] == "from-env"
    assert __import__("os").environ["CAPTIONS_AUDIO"] == "mic"


def test_audio_cli_beats_saved_settings():
    saved = Settings(audio="mic")
    assert resolve_audio(cli="loopback", settings=saved, settings_existed=True, env_audio="mic") == "loopback"
    assert resolve_audio(cli=None, settings=saved, settings_existed=True, env_audio="loopback") == "mic"
    assert resolve_audio(cli=None, settings=saved, settings_existed=False, env_audio="loopback") == "loopback"


def test_invalid_audio_and_alpha_are_rejected_or_clamped():
    with pytest.raises(ConfigError):
        load_config({"CAPTIONS_AUDIO": "speakers"})
    config = load_config({"CAPTIONS_BAR_ALPHA": "10", "CAPTIONS_AUDIO": "microphone"})
    assert config.bar_alpha == 80
    assert config.audio == "mic"
    assert load_config({"CAPTIONS_BAR_ALPHA": "200"}).bar_alpha == 200
    assert load_config({"CAPTIONS_BAR_ALPHA": "255"}).bar_alpha == 242
    with pytest.raises(ConfigError):
        load_config({"CAPTIONS_BAR_ALPHA": "300"})


def test_convert_command_prints_taiwan_traditional(capsys):
    assert main(["--convert", "软件和网络"]) == 0
    output = capsys.readouterr().out
    assert "軟體" in output
    assert "網路" in output


def test_headless_without_a_source_is_rejected(capsys):
    assert main(["--headless"]) == 2
    assert "請加上" in capsys.readouterr().err
