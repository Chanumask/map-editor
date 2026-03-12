from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from map_builder.tileset import TileCell, TileCoord


@dataclass(frozen=True, slots=True)
class TilePatch:
    rows: tuple[tuple[TileCell, ...], ...]

    def __post_init__(self) -> None:
        if not self.rows:
            msg = "TilePatch must contain at least one row."
            raise ValueError(msg)
        first_width = len(self.rows[0])
        if first_width == 0:
            msg = "TilePatch rows must not be empty."
            raise ValueError(msg)
        if any(len(row) != first_width for row in self.rows):
            msg = "TilePatch must be rectangular."
            raise ValueError(msg)

    @classmethod
    def from_single(cls, coord: TileCoord) -> TilePatch:
        return cls(rows=((coord,),))

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def top_left(self) -> TileCell:
        return self.rows[0][0]

    def iter_cells(self) -> Iterator[tuple[int, int, TileCell]]:
        for row_index, row in enumerate(self.rows):
            for column_index, coord in enumerate(row):
                yield column_index, row_index, coord
