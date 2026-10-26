from __future__ import annotations

import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path

import httpx

from live_captions.errors import CaptionsError
from live_captions.paths import model_dir

EN_ZH_URL = "https://argos-net.com/v1/translate-en_zh-1_9.argosmodel"
EN_ZH_SHA256 = "433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab"
EN_ZH_SIZE = 70_743_021
_USER_AGENT = "OpticsLiveCaptions/1.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in archive.infolist():
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in Path(name).parts:
            raise CaptionsError(f"翻譯模型包含不安全的路徑：{name}")
        target = (dest / name).resolve()
        if target != dest and dest not in target.parents:
            raise CaptionsError(f"翻譯模型包含不安全的路徑：{name}")
    archive.extractall(dest)


def _find_model_root(path: Path) -> Path | None:
    if (path / "metadata.json").is_file() and (path / "model" / "model.bin").is_file():
        return path
    if not path.is_dir():
        return None
    for child in path.iterdir():
        if child.is_dir() and (child / "metadata.json").is_file() and (child / "model" / "model.bin").is_file():
            return child
    return None


def _download(url: str, dest: Path, on_status=None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".part")
    if on_status:
        on_status("正在下載翻譯模型…（約 68 MB）")
    timeout = httpx.Timeout(30.0, read=60.0)
    written = 0
    next_report = 8 * 1024 * 1024
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout, headers={"User-Agent": _USER_AGENT}) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
                written += len(chunk)
                if written >= next_report:
                    print(f"翻譯模型已下載 {written // (1024 * 1024)} MB", flush=True)
                    next_report += 8 * 1024 * 1024
    temporary.replace(dest)


def ensure_local_model(cache: Path | None = None, on_status=None) -> Path:
    cache = cache or model_dir()
    ready = _find_model_root(cache)
    if ready is not None:
        return ready
    cache.parent.mkdir(parents=True, exist_ok=True)
    archive_path = cache.parent / "translate-en_zh-1_9.argosmodel"
    if not archive_path.is_file() or sha256_file(archive_path) != EN_ZH_SHA256:
        try:
            _download(EN_ZH_URL, archive_path, on_status=on_status)
        except httpx.HTTPError as exc:
            raise CaptionsError(f"翻譯模型下載失敗：{exc}") from exc
        digest = sha256_file(archive_path)
        if digest != EN_ZH_SHA256:
            archive_path.unlink(missing_ok=True)
            raise CaptionsError("翻譯模型下載後的檢查碼不符，已刪除檔案。")
    staging = cache.parent / "translate-en-zh-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        safe_extract(archive, staging)
    root = _find_model_root(staging)
    if root is None:
        raise CaptionsError("翻譯模型壓縮檔裡沒有 metadata.json。")
    if cache.exists():
        shutil.rmtree(cache)
    shutil.move(str(root), str(cache))
    shutil.rmtree(staging, ignore_errors=True)
    archive_path.unlink(missing_ok=True)
    installed = _find_model_root(cache)
    if installed is None:
        raise CaptionsError("翻譯模型安裝後找不到模型檔。")
    return installed


def split_for_translation(text: str, limit: int = 180) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    pieces = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    chunks: list[str] = []
    for piece in pieces:
        if len(piece) <= limit:
            chunks.append(piece)
            continue
        for start in range(0, len(piece), limit):
            chunks.append(piece[start : start + limit])
    return chunks


class LocalEnZhTranslator:
    """Offline English to Simplified Chinese via the Argos OPUS-MT package.

    The package is loaded with CTranslate2 and SentencePiece. spaCy and Stanza
    are not installed; caption lines are short enough to split on punctuation.
    Callers run OpenCC s2twp on the result before display.
    """

    def __init__(self, cache: Path | None = None, cpu_threads: int = 4) -> None:
        self.cache = cache
        self.cpu_threads = max(1, cpu_threads)
        self._translator = None
        self._processor = None

    def warmup(self, on_status=None) -> None:
        if self._translator is not None:
            return
        root = ensure_local_model(self.cache, on_status=on_status)
        self._load(root)

    def _load(self, root: Path) -> None:
        try:
            import ctranslate2
            import sentencepiece as spm
        except ImportError as exc:
            raise CaptionsError(
                "缺少翻譯元件。請在 live-captions 目錄執行 pip install -r requirements.txt。"
            ) from exc
        model_path = root / "sentencepiece.model"
        if not model_path.is_file():
            raise CaptionsError("翻譯模型沒有 sentencepiece.model。")
        processor = spm.SentencePieceProcessor(model_file=str(model_path))
        last_error: Exception | None = None
        device = os.environ.get("CAPTIONS_MT_DEVICE", "cpu").strip().lower() or "cpu"
        compute_types = ("int8", "default") if device == "cpu" else ("int8_float16", "default")
        translator = None
        for compute_type in compute_types:
            try:
                translator = ctranslate2.Translator(
                    str(root / "model"),
                    device=device,
                    compute_type=compute_type,
                    inter_threads=1,
                    intra_threads=self.cpu_threads,
                )
                break
            except Exception as exc:
                last_error = exc
                translator = None
        if translator is None:
            raise CaptionsError(f"翻譯模型無法載入：{last_error}")
        self._processor = processor
        self._translator = translator

    def translate(self, text: str) -> str:
        self.warmup()
        chunks = split_for_translation(text)
        if not chunks:
            return ""
        assert self._processor is not None
        assert self._translator is not None
        tokenized = [self._processor.encode(chunk, out_type=str) for chunk in chunks]
        results = self._translator.translate_batch(
            tokenized,
            beam_size=2,
            num_hypotheses=1,
            replace_unknowns=True,
            max_decoding_length=128,
            length_penalty=0.2,
        )
        parts: list[str] = []
        for result in results:
            tokens = result.hypotheses[0]
            try:
                value = self._processor.decode_pieces(tokens)
            except Exception:
                value = "".join(tokens).replace("▁", " ")
            cleaned = value.strip()
            if cleaned:
                parts.append(cleaned)
        return "".join(parts).strip()
