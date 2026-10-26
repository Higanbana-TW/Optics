from datetime import datetime

from live_captions.captions.session_log import (
    format_session_transcript,
    transcript_filename,
    write_session_transcript,
)


def test_transcript_filename_uses_local_date_and_time():
    when = datetime(2026, 10, 26, 19, 19, 5)
    assert transcript_filename(when) == "Optics-captions-2026-10-26_191905.txt"


def test_session_file_keeps_every_bilingual_line(tmp_path):
    lines = [("one", "一"), ("two", "二"), ("three", "三"), ("four", "四"), ("five", "五")]
    assert "one" in format_session_transcript(lines)
    path = write_session_transcript(
        lines,
        directory=tmp_path,
        when=datetime(2026, 10, 26, 19, 19, 5),
    )
    assert path is not None
    assert path.parent == tmp_path
    assert path.name == "Optics-captions-2026-10-26_191905.txt"
    text = path.open(encoding="utf-8-sig", newline="").read()
    assert text.index("one") < text.index("一") < text.index("five") < text.index("五")
    assert "\r\n" in text
    assert b"\r\r\n" not in path.read_bytes()


def test_empty_session_does_not_write_a_file(tmp_path):
    assert write_session_transcript([], directory=tmp_path) is None
    assert write_session_transcript([("  ", "\n")], directory=tmp_path) is None
    assert list(tmp_path.iterdir()) == []
