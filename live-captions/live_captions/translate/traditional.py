from __future__ import annotations

from live_captions.errors import CaptionsError


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


class TraditionalConverter:
    """Map Chinese into Taiwan Traditional with OpenCC s2twp.

    The converter always runs. Shared-shape simplified words such as 信息,
    程序, and 打印 do not change under a plain simplified-to-traditional map,
    but s2twp turns them into 資訊, 程式, and 列印. Already-Taiwanese sentences
    usually stay put. A few dictionary phrases are localized again, for
    example 文件 may become 檔案 and 連接 may become 連線.
    """

    def __init__(self) -> None:
        try:
            from opencc import OpenCC
        except ImportError as exc:
            raise CaptionsError(
                "缺少 OpenCC。請在 live-captions 目錄執行 pip install -r requirements.txt。"
            ) from exc
        self._s2twp = OpenCC("s2twp")

    def to_taiwan(self, text: str) -> str:
        if not text or not has_cjk(text):
            return text
        return self._s2twp.convert(text)
