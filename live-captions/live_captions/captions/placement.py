from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


def default_bar_rect(work_area: Rect) -> Rect:
    width = min(980, max(520, int(work_area.width * 0.72)))
    height = 150
    x = work_area.x + max(0, (work_area.width - width) // 2)
    y = work_area.y + max(0, work_area.height - height - 48)
    return Rect(x, y, width, height)


def placement_is_visible(rect: Rect, screens: list[Rect]) -> bool:
    anchor_x = rect.x + rect.width // 2
    anchor_y = rect.y + min(24, max(0, rect.height - 1))
    return any(
        screen.x <= anchor_x < screen.x + screen.width
        and screen.y <= anchor_y < screen.y + screen.height
        for screen in screens
    )


def resolve_bar_rect(
    saved_x: int | None,
    saved_y: int | None,
    saved_width: int | None,
    work_area: Rect,
    screens: list[Rect],
) -> Rect:
    default = default_bar_rect(work_area)
    if saved_x is None or saved_y is None:
        return default
    width = saved_width if isinstance(saved_width, int) else default.width
    width = max(520, min(1200, width))
    rect = Rect(saved_x, saved_y, width, default.height)
    if not placement_is_visible(rect, screens):
        return default
    return rect
