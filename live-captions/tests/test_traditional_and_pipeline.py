import httpx
import pytest

from live_captions.config import load_config, public_summary
from live_captions.errors import CaptionsError, ConfigError
from live_captions.captions.polish import clean_mt_text, finish_subtitle
from live_captions.pipeline import CaptionPipeline, CaptionState, caption_from_transcript
from live_captions.translate.engines import (
    DeepLTranslator,
    LibreTranslator,
    OpenAITranslator,
    deepl_endpoint,
    http_error,
)
from live_captions.translate.factory import build_translator
from live_captions.translate.traditional import TraditionalConverter


@pytest.fixture(scope="module")
def converter():
    return TraditionalConverter()


def test_simplified_technical_words_become_taiwan_traditional(converter):
    assert converter.to_taiwan("软件") == "軟體"
    assert converter.to_taiwan("软件") != "軟件"
    assert converter.to_taiwan("网络") == "網路"
    assert converter.to_taiwan("视频") == "影片"
    assert converter.to_taiwan("服务器") == "伺服器"
    assert converter.to_taiwan("默认设置") == "預設設定"


def test_shared_shape_simplified_words_are_converted(converter):
    assert converter.to_taiwan("信息") == "資訊"
    assert converter.to_taiwan("打印") == "列印"
    assert converter.to_taiwan("程序") == "程式"


def test_meeting_sentence_is_taiwan_traditional(converter):
    assert converter.to_taiwan("请安装软件，连接网络并播放视频。") == "請安裝軟體，連線網路並播放影片。"


def test_existing_taiwan_sentence_stays_readable(converter):
    text = "大家好，我們開始會議。"
    assert converter.to_taiwan(text) == text


def test_conversion_is_idempotent(converter):
    samples = [
        "请安装软件，连接网络并播放视频。",
        "大家好，我們開始會議。今天討論軟體架構與網路安全。",
        "我們會把文件放在伺服器上。",
    ]
    for sample in samples:
        once = converter.to_taiwan(sample)
        assert converter.to_taiwan(once) == once


def test_opencc_phrase_file_becomes_dang_an(converter):
    # s2twp localizes 文件 to 檔案. Lock the dictionary behavior.
    assert converter.to_taiwan("我們會把文件放在伺服器上。") == "我們會把檔案放在伺服器上。"


def test_sentencepiece_marker_and_ascii_punctuation_are_cleaned():
    assert clean_mt_text("▁請安裝軟體,連線網路,播放影片.") == "請安裝軟體，連線網路，播放影片。"
    assert clean_mt_text("Hello, API_KEY.") == "Hello, API_KEY."
    assert finish_subtitle("Hello everyone.", "大家好") == "大家好。"
    assert finish_subtitle("Hello everyone.", "大家好。") == "大家好。"
    assert finish_subtitle("Are you there?", "你在嗎") == "你在嗎？"


def test_english_and_empty_text_are_unchanged(converter):
    assert converter.to_taiwan("Hello, please open the API.") == "Hello, please open the API."
    assert converter.to_taiwan("") == ""


def test_pipeline_publishes_english_and_traditional_together(converter):
    class FakeTranslator:
        def __init__(self):
            self.calls = 0

        def translate(self, text: str) -> str:
            self.calls += 1
            assert text == "Hello everyone."
            return "大家好，请安装软件并检查网络。"

    translator = FakeTranslator()
    pipeline = CaptionPipeline(translator, converter)
    state = pipeline.apply_transcript("  Hello   everyone. ")
    assert state == CaptionState(
        english="Hello everyone.",
        traditional="大家好，請安裝軟體並檢查網路。",
    )
    assert pipeline.apply_transcript("Hello everyone.") is None
    assert translator.calls == 1


def test_failed_translation_keeps_the_previous_caption(converter):
    class Scripted:
        def __init__(self):
            self.calls = 0

        def translate(self, text: str) -> str:
            self.calls += 1
            if self.calls == 1:
                return "你好"
            raise RuntimeError("boom")

    pipeline = CaptionPipeline(Scripted(), converter)
    first, error = caption_from_transcript(pipeline, "Hello everyone")
    assert error == ""
    assert first is not None
    second, error = caption_from_transcript(pipeline, "How are you doing today")
    assert second is None
    assert "翻譯失敗" in error
    assert "boom" in error
    assert pipeline.state == first


def test_blank_translation_does_not_clear_caption(converter):
    class Blank:
        def translate(self, text: str) -> str:
            return "   "

    pipeline = CaptionPipeline(Blank(), converter)
    pipeline.state = CaptionState("Hello", "你好")
    assert pipeline.apply_transcript("Good morning everyone") is None
    assert pipeline.state == CaptionState("Hello", "你好")


def test_deepl_endpoint_and_request_shape():
    assert deepl_endpoint("secret-key:fx") == "https://api-free.deepl.com/v2/translate"
    assert deepl_endpoint("secret-key") == "https://api.deepl.com/v2/translate"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/translate"
        assert request.headers["Authorization"] == "DeepL-Auth-Key secret-key:fx"
        body = request.read().decode()
        assert "ZH-HANT" in body
        assert "Hello" in body
        return httpx.Response(200, json={"translations": [{"text": "软件"}]})

    engine = DeepLTranslator("secret-key:fx", httpx.Client(transport=httpx.MockTransport(handler)))
    assert engine.translate("Hello") == "软件"


def test_api_errors_do_not_include_the_key():
    key = "secret-key-value:fx"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="denied " + key)

    engine = DeepLTranslator(key, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(CaptionsError) as raised:
        engine.translate("Hello")
    assert key not in str(raised.value)
    assert "403" in str(raised.value)
    assert "額度已用完" in str(http_error("DeepL", 456))


def test_openai_and_libre_parse_simplified_text():
    def openai_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " 视频 "}}]},
        )

    openai = OpenAITranslator(
        "sk-test",
        "gpt-4.1-mini",
        "https://example.test/v1",
        httpx.Client(transport=httpx.MockTransport(openai_handler)),
    )
    assert openai.translate("Play the video") == "视频"

    def libre_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/translate"
        return httpx.Response(200, json={"translatedText": "网络"})

    libre = LibreTranslator("https://translate.example", client=httpx.Client(transport=httpx.MockTransport(libre_handler)))
    assert libre.translate("network") == "网络"


def test_local_translator_is_the_default_even_when_an_api_key_exists():
    config = load_config({"OPENAI_API_KEY": "sk-super-secret", "DEEPL_API_KEY": "deepl-secret"})
    assert config.translator == "local"
    summary = public_summary(config)
    assert "sk-super-secret" not in summary
    assert "deepl-secret" not in summary
    assert "openai=set" in summary
    assert isinstance(build_translator(config).__class__.__name__, str)
    assert build_translator(config).__class__.__name__ == "LocalEnZhTranslator"


def test_selecting_deepl_without_a_key_fails_clearly():
    config = load_config({"CAPTIONS_TRANSLATOR": "deepl"})
    with pytest.raises(ConfigError, match="DEEPL_API_KEY"):
        build_translator(config)
