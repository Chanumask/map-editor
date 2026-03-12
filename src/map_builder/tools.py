from __future__ import annotations

from enum import StrEnum


class Tool(StrEnum):
    PAINT = "paint"
    BLOCK = "block"
    TILESET_PATCH = "tileset_patch"
    CANVAS_SELECT = "canvas_select"
    PASTE = "paste"

    @property
    def label(self) -> str:
        if self is Tool.PAINT:
            return "Paint"
        if self is Tool.BLOCK:
            return "Block"
        if self is Tool.TILESET_PATCH:
            return "Tileset Patch Select"
        if self is Tool.CANVAS_SELECT:
            return "Canvas Select / Copy"
        return "Paste"
