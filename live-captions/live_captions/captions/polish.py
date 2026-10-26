from __future__ import annotations

import re

_CJK = r"\u4e00-\u9fff"
_TERMINAL = "。！？…」』.!?"


def clean_mt_text(text: str) -> str:
    """Remove SentencePiece markers and use Chinese punctuation between CJK."""
    text = text.replace("\u2581", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(rf"(?<=[{_CJK}]),(?=\s*[{_CJK}])", "，", text)
    text = re.sub(rf"(?<=[{_CJK}])\?(?=\s|$)", "？", text)
    text = re.sub(rf"(?<=[{_CJK}])!(?=\s|$)", "！", text)
    text = re.sub(rf"(?<=[{_CJK}])\.(?=\s|$)", "。", text)
    return text


def finish_subtitle(english: str, traditional: str) -> str:
    traditional = traditional.strip()
    if not traditional or traditional[-1] in _TERMINAL:
        return traditional
    if english.endswith("?"):
        return traditional + "？"
    if english.endswith("!"):
        return traditional + "！"
    if english.endswith("."):
        return traditional + "。"
    return traditional
