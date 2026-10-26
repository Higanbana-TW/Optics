from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FormattedCaption:
    english: str
    traditional: str


def collapse_space(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    # Drop spaces that a translator inserts between Chinese characters.
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def wrap_words(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars")
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        if not word:
            continue
        if not current:
            current = word
            continue
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def wrap_chars(text: str, max_chars: int) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars")
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def tail_lines(lines: list[str], max_lines: int) -> str:
    if max_lines < 1:
        raise ValueError("max_lines")
    if not lines:
        return ""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[-max_lines :]
    kept[0] = "…" + kept[0]
    return "\n".join(kept)


def format_caption(
    english: str,
    traditional: str,
    *,
    max_en_lines: int = 2,
    max_en_chars: int = 84,
    max_zh_lines: int = 2,
    max_zh_chars: int = 28,
) -> FormattedCaption:
    english = collapse_space(english)
    traditional = collapse_space(traditional)
    english_text = tail_lines(wrap_words(english, max_en_chars), max_en_lines) if english else ""
    chinese_text = (
        tail_lines(wrap_chars(traditional, max_zh_chars), max_zh_lines) if traditional else ""
    )
    return FormattedCaption(english=english_text, traditional=chinese_text)


def font_sizes(delta: int) -> tuple[int, int]:
    """English and Traditional Chinese point sizes.

    Chinese stays only a little larger than English. A much larger Chinese
    face was pushing the second line out of the bar.
    """
    delta = max(-6, min(16, delta))
    english = max(11, 14 + delta // 2)
    chinese = max(12, 16 + delta // 2)
    return english, chinese


def caption_history_text(lines: list[tuple[str, str]], *, limit: int = 3) -> str:
    """Older bilingual lines, oldest first. The current line is not included."""
    if limit < 1:
        raise ValueError("limit")
    blocks: list[str] = []
    for english, traditional in lines[-limit:]:
        parts = [collapse_space(part) for part in (english, traditional)]
        parts = [part for part in parts if part]
        if parts:
            blocks.append("\n".join(parts))
    return "\n\n".join(blocks)
