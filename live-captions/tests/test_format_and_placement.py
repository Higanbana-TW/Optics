from live_captions.captions.format import caption_history_text, font_sizes, format_caption
from live_captions.captions.placement import Rect, default_bar_rect, resolve_bar_rect
from live_captions.captions.transcript import prepare_transcript


def test_short_caption_keeps_both_languages():
    caption = format_caption("Hello everyone.", "大家好。")
    assert caption.english == "Hello everyone."
    assert caption.traditional == "大家好。"


def test_whitespace_is_collapsed_before_display():
    caption = format_caption("Hello   \n everyone.", "大家  好。")
    assert caption.english == "Hello everyone."
    assert caption.traditional == "大家好。"
    mixed = format_caption("Open the API.", "請看 API 文件")
    assert mixed.traditional == "請看 API 文件"


def test_empty_caption_stays_empty():
    caption = format_caption("   ", " \n ")
    assert caption.english == ""
    assert caption.traditional == ""


def test_long_english_keeps_the_latest_lines():
    text = " ".join(["alpha"] * 40)
    caption = format_caption(text, "測試", max_en_lines=2, max_en_chars=20, max_zh_chars=10)
    assert caption.english.startswith("…")
    assert caption.english.count("\n") == 1
    assert caption.english.splitlines()[-1].endswith("alpha")
    assert "測試" == caption.traditional


def test_long_chinese_keeps_the_latest_characters():
    caption = format_caption("Hello", "甲" * 30, max_zh_lines=2, max_zh_chars=8)
    assert caption.traditional.startswith("…")
    # Two newest lines are 8 and 6 characters; the ellipsis is added in front.
    assert caption.traditional.count("甲") == 14
    assert caption.traditional.count("\n") == 1


def test_font_sizes_stay_readable():
    assert font_sizes(0) == (14, 16)
    assert font_sizes(16) == (22, 24)
    assert font_sizes(-6) == (11, 13)
    assert font_sizes(100) == font_sizes(16)


def test_history_keeps_the_whole_session():
    text = caption_history_text(
        [
            ("one", "一"),
            ("two", "二"),
            ("three", "三"),
            ("four", "四"),
            ("five", "五"),
        ]
    )
    assert text.index("one") < text.index("二") < text.index("five")
    assert "三" in text and "四" in text


def test_default_bar_sits_near_the_bottom_center():
    area = Rect(0, 0, 1920, 1080)
    bar = default_bar_rect(area)
    assert bar.width == 980
    assert bar.x == (1920 - 980) // 2
    assert bar.y == 1080 - 150 - 48
    assert bar == resolve_bar_rect(None, None, None, area, [area])


def test_narrow_screen_keeps_a_minimum_width():
    area = Rect(0, 0, 600, 800)
    bar = default_bar_rect(area)
    assert bar.width == 520
    assert bar.x == 40


def test_saved_position_is_kept_when_it_is_on_screen():
    area = Rect(0, 0, 1920, 1080)
    rect = resolve_bar_rect(100, 200, 800, area, [area])
    assert (rect.x, rect.y, rect.width) == (100, 200, 800)


def test_offscreen_saved_position_falls_back():
    area = Rect(0, 0, 1920, 1080)
    assert resolve_bar_rect(-4000, -4000, 800, area, [area]) == default_bar_rect(area)


def test_transcript_filter_drops_fillers_and_known_hallucinations():
    assert prepare_transcript("  Hello   everyone. ") == "Hello everyone."
    assert prepare_transcript("um") is None
    assert prepare_transcript("Thanks for watching!") is None
    assert prepare_transcript("Thank you.") == "Thank you."
    assert prepare_transcript("...") is None
