from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from map_builder.blocking_grid import BlockingGrid
from map_builder.layer_data import MapLayerData
from map_builder.map_grid import MapGrid
from map_builder.tileset import TileCell

LAYER_NAME_KEY = "LAYER_NAME"
LAYER_ORDER_KEY = "LAYER_ORDER"
TILESET_PATH_KEY = "TILESET_PATH"
TILE_SIZE_KEY = "TILE_SIZE"
MAP_WIDTH_KEY = "MAP_WIDTH"
MAP_HEIGHT_KEY = "MAP_HEIGHT"
UNIT_COORD_GRID_KEY = "UNIT_COORD_GRID"
BLOCKING_GRID_KEY = "BLOCKING_GRID"


def save_layer_file(path: str | Path, layer: MapLayerData) -> Path:
    output_path = Path(path)
    output_path.write_text(format_layer_file(layer), encoding="utf-8")
    return output_path


def format_layer_file(layer: MapLayerData) -> str:
    lines = [
        f"{LAYER_NAME_KEY} = {layer.name!r}",
        f"{LAYER_ORDER_KEY} = {layer.layer_order}",
        f"{TILESET_PATH_KEY} = {layer.tileset_path!r}",
        f"{TILE_SIZE_KEY} = {layer.tile_size}",
        f"{MAP_WIDTH_KEY} = {layer.width}",
        f"{MAP_HEIGHT_KEY} = {layer.height}",
        "",
        format_unit_coord_grid(layer.map_grid.as_rows()).rstrip(),
        "",
        format_blocking_grid(layer.blocking_grid.as_rows()).rstrip(),
        "",
    ]
    return "\n".join(lines)


def format_unit_coord_grid(rows: Sequence[Sequence[TileCell]]) -> str:
    if not rows:
        msg = "Grid must contain at least one row."
        raise ValueError(msg)

    column_count = len(rows[0])
    if column_count == 0:
        msg = "Grid rows must contain at least one column."
        raise ValueError(msg)

    lines = [f"{UNIT_COORD_GRID_KEY} = ("]
    for row in rows:
        if len(row) != column_count:
            msg = "Grid must be rectangular with equal column counts in each row."
            raise ValueError(msg)
        row_items = ", ".join(_format_tile_cell(cell) for cell in row)
        lines.append(f"    ({row_items}),")
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def format_blocking_grid(rows: Sequence[Sequence[bool]]) -> str:
    if not rows:
        msg = "Blocking grid must contain at least one row."
        raise ValueError(msg)

    column_count = len(rows[0])
    if column_count == 0:
        msg = "Blocking grid rows must contain at least one column."
        raise ValueError(msg)

    lines = [f"{BLOCKING_GRID_KEY} = ("]
    for row in rows:
        if len(row) != column_count:
            msg = "Blocking grid must be rectangular with equal column counts in each row."
            raise ValueError(msg)
        if any(not isinstance(cell, bool) for cell in row):
            msg = "Blocking grid cells must be booleans."
            raise ValueError(msg)
        row_items = ", ".join("True" if cell else "False" for cell in row)
        lines.append(f"    ({row_items}),")
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def _format_tile_cell(cell: TileCell) -> str:
    if cell is None:
        return "None"
    return f"({cell[0]}, {cell[1]})"


def load_layer_file(path: str | Path) -> MapLayerData:
    source_path = Path(path)
    source = source_path.read_text(encoding="utf-8")
    assignments = _parse_python_assignments(source)

    tileset_path = _require_str(assignments, TILESET_PATH_KEY)
    layer_order = _optional_int(assignments, LAYER_ORDER_KEY, default=0, minimum=0, maximum=1000)
    tile_size = _optional_int(assignments, TILE_SIZE_KEY, default=16, minimum=1, maximum=256)
    layer_name = assignments.get(LAYER_NAME_KEY, source_path.stem)
    if not isinstance(layer_name, str):
        msg = f"{LAYER_NAME_KEY} must be a string when provided."
        raise ValueError(msg)

    rows = _require_rows(assignments, UNIT_COORD_GRID_KEY)
    map_grid = MapGrid.from_rows(rows)

    declared_width = _optional_int(
        assignments,
        MAP_WIDTH_KEY,
        default=map_grid.columns,
        minimum=1,
        maximum=10000,
    )
    declared_height = _optional_int(
        assignments,
        MAP_HEIGHT_KEY,
        default=map_grid.rows,
        minimum=1,
        maximum=10000,
    )

    if declared_width != map_grid.columns or declared_height != map_grid.rows:
        msg = "Declared MAP_WIDTH/MAP_HEIGHT do not match UNIT_COORD_GRID dimensions."
        raise ValueError(msg)

    blocking_rows = _optional_blocking_rows(
        assignments,
        BLOCKING_GRID_KEY,
        width=map_grid.columns,
        height=map_grid.rows,
    )
    blocking_grid = BlockingGrid.from_rows(blocking_rows)

    return MapLayerData(
        name=layer_name,
        layer_order=layer_order,
        tileset_path=tileset_path,
        tile_size=tile_size,
        map_grid=map_grid,
        blocking_grid=blocking_grid,
    )


def _parse_python_assignments(source: str) -> dict[str, Any]:
    module = ast.parse(source)
    values: dict[str, Any] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        try:
            values[name] = ast.literal_eval(node.value)
        except Exception as exc:  # noqa: BLE001
            msg = f"Could not parse assignment for {name}: {exc}"
            raise ValueError(msg) from exc
    return values


def _require_str(assignments: dict[str, Any], key: str) -> str:
    value = assignments.get(key)
    if not isinstance(value, str):
        msg = f"{key} must be a string."
        raise ValueError(msg)
    return value


def _optional_int(
    assignments: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = assignments.get(key, default)
    if not isinstance(value, int):
        msg = f"{key} must be an integer."
        raise ValueError(msg)
    if value < minimum or value > maximum:
        msg = f"{key} must be between {minimum} and {maximum}."
        raise ValueError(msg)
    return value


def _require_rows(assignments: dict[str, Any], key: str) -> tuple[tuple[TileCell, ...], ...]:
    value = assignments.get(key)
    if not isinstance(value, (tuple, list)):
        msg = f"{key} must be a sequence of rows."
        raise ValueError(msg)
    if not value:
        msg = f"{key} must contain at least one row."
        raise ValueError(msg)

    rows: list[tuple[TileCell, ...]] = []
    expected_width: int | None = None
    for row_index, row in enumerate(value):
        if not isinstance(row, (tuple, list)):
            msg = f"Row {row_index} in {key} must be a sequence."
            raise ValueError(msg)
        parsed_row: list[TileCell] = []
        for cell_index, cell in enumerate(row):
            if cell is None:
                parsed_row.append(None)
                continue
            if (
                not isinstance(cell, (tuple, list))
                or len(cell) != 2
                or not isinstance(cell[0], int)
                or not isinstance(cell[1], int)
            ):
                msg = f"Cell ({row_index}, {cell_index}) in {key} must be (x, y) or None."
                raise ValueError(msg)
            parsed_row.append((cell[0], cell[1]))

        if expected_width is None:
            expected_width = len(parsed_row)
            if expected_width == 0:
                msg = f"{key} rows must contain at least one column."
                raise ValueError(msg)
        elif len(parsed_row) != expected_width:
            msg = f"{key} must be rectangular with equal row lengths."
            raise ValueError(msg)

        rows.append(tuple(parsed_row))

    return tuple(rows)


def _optional_blocking_rows(
    assignments: dict[str, Any],
    key: str,
    *,
    width: int,
    height: int,
) -> tuple[tuple[bool, ...], ...]:
    value = assignments.get(key)
    if value is None:
        return tuple(tuple(False for _ in range(width)) for _ in range(height))

    if not isinstance(value, (tuple, list)):
        msg = f"{key} must be a sequence of rows."
        raise ValueError(msg)
    if len(value) != height:
        msg = f"{key} must contain exactly {height} rows."
        raise ValueError(msg)

    rows: list[tuple[bool, ...]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, (tuple, list)):
            msg = f"Row {row_index} in {key} must be a sequence."
            raise ValueError(msg)
        if len(row) != width:
            msg = f"Row {row_index} in {key} must contain exactly {width} columns."
            raise ValueError(msg)
        if any(not isinstance(cell, bool) for cell in row):
            msg = f"Row {row_index} in {key} must contain only booleans."
            raise ValueError(msg)
        rows.append(tuple(row))
    return tuple(rows)
