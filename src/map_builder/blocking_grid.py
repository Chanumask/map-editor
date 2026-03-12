from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(slots=True)
class BlockingGrid:
    columns: int
    rows: int
    default_blocked: bool = False
    _cells: list[list[bool]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._cells = [
            [self.default_blocked for _ in range(self.columns)] for _ in range(self.rows)
        ]

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Sequence[bool]],
        *,
        default_blocked: bool = False,
    ) -> BlockingGrid:
        if not rows:
            msg = "Blocking rows must contain at least one row."
            raise ValueError(msg)
        column_count = len(rows[0])
        if column_count == 0:
            msg = "Blocking rows must contain at least one column."
            raise ValueError(msg)
        if any(len(row) != column_count for row in rows):
            msg = "Blocking rows must be rectangular."
            raise ValueError(msg)
        if any(not isinstance(cell, bool) for row in rows for cell in row):
            msg = "Blocking rows must contain booleans."
            raise ValueError(msg)

        grid = cls(columns=column_count, rows=len(rows), default_blocked=default_blocked)
        for row_index, row in enumerate(rows):
            for column_index, blocked in enumerate(row):
                grid.set(column_index, row_index, blocked)
        return grid

    def in_bounds(self, column: int, row: int) -> bool:
        return 0 <= column < self.columns and 0 <= row < self.rows

    def get(self, column: int, row: int) -> bool:
        if not self.in_bounds(column, row):
            msg = f"Blocking cell ({column}, {row}) is outside of map bounds."
            raise IndexError(msg)
        return self._cells[row][column]

    def set(self, column: int, row: int, blocked: bool) -> None:
        if not self.in_bounds(column, row):
            return
        self._cells[row][column] = blocked

    def toggle(self, column: int, row: int) -> None:
        if not self.in_bounds(column, row):
            return
        self._cells[row][column] = not self._cells[row][column]

    def fill(self, blocked: bool) -> None:
        for row_index in range(self.rows):
            for column_index in range(self.columns):
                self._cells[row_index][column_index] = blocked

    def blocked_count(self) -> int:
        return sum(1 for row in self._cells for blocked in row if blocked)

    def as_rows(self) -> tuple[tuple[bool, ...], ...]:
        return tuple(tuple(cell for cell in row) for row in self._cells)
