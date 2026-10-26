from __future__ import annotations

import queue

from live_captions.pipeline import CaptionState


class UiBridge:
    def __init__(self) -> None:
        self.captions: queue.Queue[CaptionState] = queue.Queue()
        self.statuses: queue.Queue[str] = queue.Queue()

    def publish_caption(self, state: CaptionState) -> None:
        self.captions.put(state)

    def publish_status(self, text: str) -> None:
        self.statuses.put(text)

    def drain_captions(self) -> CaptionState | None:
        latest = None
        while True:
            try:
                latest = self.captions.get_nowait()
            except queue.Empty:
                return latest

    def drain_statuses(self) -> str | None:
        latest = None
        while True:
            try:
                latest = self.statuses.get_nowait()
            except queue.Empty:
                return latest
