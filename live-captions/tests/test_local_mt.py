from pathlib import Path

import pytest

from live_captions.paths import model_dir
from live_captions.pipeline import CaptionPipeline
from live_captions.translate.local_mt import LocalEnZhTranslator, _find_model_root
from live_captions.translate.traditional import TraditionalConverter


def _installed_model() -> Path | None:
    return _find_model_root(model_dir())


@pytest.mark.skipif(_installed_model() is None, reason="local English-Chinese model is not installed")
def test_local_model_output_is_traditional_chinese():
    translator = LocalEnZhTranslator()
    translator.warmup()
    pipeline = CaptionPipeline(translator, TraditionalConverter())
    state = pipeline.apply_transcript(
        "Please install the software, connect to the network, and play the video."
    )
    assert state is not None
    assert any("\u4e00" <= char <= "\u9fff" for char in state.traditional)
    assert state.traditional != state.english
    assert pipeline.converter.to_taiwan(state.traditional) == state.traditional
    print(f"LOCAL_MT {state.english} => {state.traditional}")
