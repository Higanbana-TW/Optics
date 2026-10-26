from __future__ import annotations

import re

# Exact lines Whisper often invents on silence or hold music. Real meeting
# phrases such as "thank you" are intentionally not in this list.
_HALLUCINATIONS = {
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "subtitles by the amara.org community",
}
_NOISE = {"uh", "um", "hmm", "mm", "ah", "oh", "er", "eh"}


def normalize_english(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def prepare_transcript(text: str) -> str | None:
    cleaned = normalize_english(text)
    if not cleaned:
        return None
    folded = cleaned.strip(" .!?,;:\"'").lower()
    if folded in _HALLUCINATIONS or folded in _NOISE:
        return None
    if not re.search(r"[A-Za-z]", cleaned):
        return None
    return cleaned
