from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from map_builder.brush import TilePatch
from map_builder.tileset import TileCell

MAP_COLUMNS = 50
MAP_ROWS = 38
EMPTY_TILE: TileCell = None


@dataclass(slots=True)
class MapGrid:
    columns: int = MAP_COLUMNS
    rows: int = MAP_ROWS
    default_coord: TileCell = EMPTY_TILE
    _cells: list[list[TileCell]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._cells = [[self.default_coord for _ in range(self.columns)] for _ in range(self.rows)]

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Sequence[TileCell]],
        *,
        default_coord: TileCell = EMPTY_TILE,
    ) -> MapGrid:
        if not rows:
            msg = "Rows must contain at least one row."
            raise ValueError(msg)
        column_count = len(rows[0])
        if column_count == 0:
            msg = "Rows must contain at least one column."
            raise ValueError(msg)
        if any(len(row) != column_count for row in rows):
            msg = "Rows must be rectangular."
            raise ValueError(msg)

        grid = cls(columns=column_count, rows=len(rows), default_coord=default_coord)
        for row_index, row in enumerate(rows):
            for column_index, coord in enumerate(row):
                grid.paint(column_index, row_index, coord)
        return grid

    def in_bounds(self, column: int, row: int) -> bool:
        return 0 <= column < self.columns and 0 <= row < self.rows

    def paint(self, column: int, row: int, coord: TileCell) -> None:
        if not self.in_bounds(column, row):
            return
        self._cells[row][column] = coord

    def fill(self, coord: TileCell) -> None:
        for row_index in range(self.rows):
            for column_index in range(self.columns):
                self._cells[row_index][column_index] = coord

    def get(self, column: int, row: int) -> TileCell:
        if not self.in_bounds(column, row):
            msg = f"Cell ({column}, {row}) is outside of map bounds."
            raise IndexError(msg)
        return self._cells[row][column]

    def copy_patch(
        self,
        start_column: int,
        start_row: int,
        end_column: int,
        end_row: int,
    ) -> TilePatch:
        left = min(start_column, end_column)
        right = max(start_column, end_column)
        top = min(start_row, end_row)
        bottom = max(start_row, end_row)

        if not self.in_bounds(left, top) or not self.in_bounds(right, bottom):
            msg = "Copy selection bounds are outside of map bounds."
            raise ValueError(msg)

        rows = []
        for row_index in range(top, bottom + 1):
            rows.append(tuple(self._cells[row_index][left : right + 1]))
        return TilePatch(rows=tuple(rows))

    def paste_patch(self, target_column: int, target_row: int, patch: TilePatch) -> bool:
        clipped = False
        for offset_x, offset_y, coord in patch.iter_cells():
            column = target_column + offset_x
            row = target_row + offset_y
            if self.in_bounds(column, row):
                self._cells[row][column] = coord
            else:
                clipped = True
        return clipped

    def as_rows(self) -> tuple[tuple[TileCell, ...], ...]:
        return tuple(tuple(cell for cell in row) for row in self._cells)
