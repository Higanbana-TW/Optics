from __future__ import annotations

from dataclasses import dataclass

from live_captions.captions.polish import clean_mt_text, finish_subtitle
from live_captions.captions.transcript import prepare_transcript
from live_captions.translate.traditional import TraditionalConverter


@dataclass(frozen=True)
class CaptionState:
    english: str = ""
    traditional: str = ""


class CaptionPipeline:
    """Publish English and Taiwan Traditional Chinese in one update."""

    def __init__(self, translator, converter: TraditionalConverter | None = None):
        self.translator = translator
        self.converter = converter or TraditionalConverter()
        self.state = CaptionState()

    def apply_transcript(self, text: str) -> CaptionState | None:
        cleaned = prepare_transcript(text)
        if cleaned is None or cleaned == self.state.english:
            return None
        raw = self.translator.translate(cleaned)
        if raw is None or not str(raw).strip():
            return None
        traditional = finish_subtitle(cleaned, self.converter.to_taiwan(clean_mt_text(str(raw))))
        if not traditional:
            return None
        self.state = CaptionState(english=cleaned, traditional=traditional)
        return self.state


def caption_from_transcript(pipeline: CaptionPipeline, text: str) -> tuple[CaptionState | None, str]:
    try:
        return pipeline.apply_transcript(text), ""
    except Exception as exc:
        return None, f"翻譯失敗：{exc}"
