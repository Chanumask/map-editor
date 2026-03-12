# map-builder

Simple internal 2D tile map editor for building coordinate-grid map layers for a Python/pygame game project.

## Project Structure

- `src/map_builder/app.py`: editor UI, tool handling, active/background layer state.
- `src/map_builder/layer_data.py`: layer model objects.
- `src/map_builder/layer_file.py`: layer file save/load and validation.
- `src/map_builder/tileset.py`: tileset image loading and slicing.
- `src/map_builder/tileset_discovery.py`: tileset file discovery for the dropdown.
- `src/map_builder/map_grid.py`: map grid editing model.
- `src/map_builder/blocking_grid.py`: per-cell blocking flags for each layer.
- `src/map_builder/brush.py` + `src/map_builder/tools.py`: brush and tool definitions.
- `tilesets/`: tileset image files (subfolders supported, discovered recursively).
- `layers/`: saved layer files (one file per layer).

## Layer Model

- One saved file = one map layer.
- Each layer file stores `LAYER_NAME`, `LAYER_ORDER`, `TILESET_PATH`, `TILE_SIZE`, `MAP_WIDTH`, `MAP_HEIGHT`, `UNIT_COORD_GRID`, and `BLOCKING_GRID`.
- `UNIT_COORD_GRID` cells are `(x, y)` or `None` (`None` means no tile / transparent cell).
- One active editable layer sits on top.
- Multiple saved layer files can be loaded as non-editable background/reference layers.

## Features

- Full-display, resizable editor window (starts at current display size).
- Sharper, less cramped layout for controls, palette, and map canvas.
- Tileset dropdown selector auto-populated from `tilesets/` recursively (+ `Refresh`).
- Load existing layer files directly into the active editable layer (`Load Active`).
- Save active layer and immediately reuse it as default source for `Load BG`.
- Clear active layer content quickly (`Clear Canvas` clears tiles + blocking).
- Multiple background layers rendered behind active layer.
- Active-layer tools: paint, fill active layer, block/unblock, tileset patch select + stamp, canvas select/copy + paste.
- Runtime map resize (`Map W x H` + `Apply Size`).
- Viewport panning for large maps: arrow keys, mouse wheel over map (`Shift+Wheel` horizontal).

## Requirements

- Python 3.12+
- `uv`

## Setup

```bash
uv sync
```

## Run

```bash
uv run map-builder
```

## Lint / Format

```bash
uv run ruff check .
uv run ruff format --check .
```

## Workflow (Fast Iteration)

1. Pick an active tileset from the `Tileset` dropdown (optionally click `Refresh`), then click `Load Tileset`.
2. Paint and edit the active layer.
3. Save (`Save layer path` + `Save Layer`).
4. Use `Load Active` to reopen a saved layer for direct editing, or click `Load BG`.
   - The editor auto-defaults to the most recently saved layer file.
   - No retyping required for common save/load iteration.
5. Switch tileset, click `New Active`, continue authoring next layer.
6. Repeat and stack more background layers.

## Output Layer File Example

```python
LAYER_NAME = "base_a5_layer"
LAYER_ORDER = 0
TILESET_PATH = "tilesets/<group>/<tileset_file>.png"
TILE_SIZE = 16
MAP_WIDTH = 50
MAP_HEIGHT = 38

UNIT_COORD_GRID = (
    ((0, 0), None, ...),
    ...
)

BLOCKING_GRID = (
    (False, False, ...),
    ...
)
```

## Notes

- Background layers are view-only and cannot be edited directly.
- All paint/copy/paste/block operations affect only the active editable layer.
- Block tool behavior: left-click toggles the clicked cell (drag continues that state), right-click clears.
- Empty tile cells use `None` and render as transparent (lower layers remain visible).
- Empty cell + blocking is allowed and exported as `None` in `UNIT_COORD_GRID` with `True` in `BLOCKING_GRID`.
- If a background layer has different dimensions, rendering clips to active map bounds.
- Pixel-art tiles are scaled with nearest-neighbor scaling for crisp rendering.
