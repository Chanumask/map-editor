# Map Layer Integration Specification (Main Game)

## Purpose

This specification defines how the main game must load and interpret map layer files exported by `map-builder`.

Use this as the integration source of truth.

## 1. Map Layer File Format

Each exported map layer is a Python file containing variable assignments.

### Required fields

- `LAYER_NAME: str`
- `LAYER_ORDER: int`
- `TILESET_PATH: str`
- `TILE_SIZE: int`
- `MAP_WIDTH: int`
- `MAP_HEIGHT: int`
- `UNIT_COORD_GRID: tuple[tuple[tuple[int, int] | None, ...], ...]`
- `BLOCKING_GRID: tuple[tuple[bool, ...], ...]`

### Optional fields

- `MAP_ID: str` (optional)
- `TILESET_NAME: str` (optional)

### Field definitions

#### `LAYER_NAME`

Human-readable layer id (for example `"base"`, `"hazards"`, `"details"`).

#### `LAYER_ORDER`

Deterministic render order for this layer.

Examples:

- `LAYER_ORDER = 0` base
- `LAYER_ORDER = 1` hazards
- `LAYER_ORDER = 2` details

The game loader **must sort layers by `LAYER_ORDER` ascending before rendering**.

#### `TILESET_PATH`

Path to the tileset image used to render this layer.

#### `TILE_SIZE`

Source tile size in pixels for slicing the tileset image.

#### `MAP_WIDTH` / `MAP_HEIGHT`

Layer dimensions in tiles.

#### `UNIT_COORD_GRID`

Main tile coordinate grid.

Structure:

- Outer tuple = rows (`MAP_HEIGHT` rows)
- Each row = tuple of cells (`MAP_WIDTH` cells)
- Each cell = `(tileset_x, tileset_y)` or `None`

Coordinate meaning in tileset grid:

- `(0, 0)` = top-left tile in the tileset
- `(1, 0)` = tile to the right
- `(0, 1)` = first tile in second row

Empty-cell meaning:

- `None` = no tile at this cell for this layer (transparent)
- Lower layers should remain visible through `None` cells

#### `BLOCKING_GRID`

Per-cell walk-blocking data for this layer.

Structure:

- Outer tuple = rows (`MAP_HEIGHT` rows)
- Each row = tuple of booleans (`MAP_WIDTH` cells)
- Each cell = `True` (blocking) or `False` (walkable)

Semantics:

- Blocking is authored per placed map cell (not globally per tileset coordinate).
- During runtime composition, game systems can combine blocking across loaded layers.
- `None` tile cells may still be blocking (`True`) when authors need invisible blockers.

#### `MAP_ID` (optional)

Map identifier for debugging/validation.

#### `TILESET_NAME` (optional)

Human-readable tileset id for debugging/validation.

## 2. Tile Sizing Rules (Source vs Render)

The game must distinguish between:

- `TILE_SIZE`: source slicing size from layer file
- `RENDER_TILE_SIZE`: runtime in-game tile render size (game-side setting/config)

Required behavior:

1. Slice tilesets using `TILE_SIZE`.
2. Render sliced tiles at `RENDER_TILE_SIZE`.
3. Compute world positions using `RENDER_TILE_SIZE`.

World mapping:

- `world_x = col_index * RENDER_TILE_SIZE`
- `world_y = row_index * RENDER_TILE_SIZE`

If `RENDER_TILE_SIZE != TILE_SIZE`, tiles are scaled at render time.

## 3. Layered Map Model

`map-builder` produces one file per layer.

Examples:

- `base_a5_layer.py`
- `hazards_a1_layer.py`
- `details_b_layer.py`

Each layer references its own tileset and tile size.
Each layer also stores per-cell blocking metadata.

Final composed map = stack of layers sorted by `LAYER_ORDER`.

## 4. Expected Folder Structure

Recommended structure in the main game repo:

```text
assets/
  maps/
    ashland_map/
      base_a5_layer.py
      hazards_a1_layer.py
      details_b_layer.py
```

Rules:

- One folder = one map
- Each file in folder = one layer

## 5. Loader Safety Rule (Required)

The game loader must **not** blindly import arbitrary Python modules for map files.

Instead, it must parse layer files as data and extract only these variables:

- `LAYER_NAME`
- `LAYER_ORDER`
- `TILESET_PATH`
- `TILE_SIZE`
- `MAP_WIDTH`
- `MAP_HEIGHT`
- `UNIT_COORD_GRID`
- `BLOCKING_GRID`
- `MAP_ID` (optional)
- `TILESET_NAME` (optional)

All other variables must be ignored.

## 6. Game-Side Loading and Rendering Pipeline

For each layer file:

1. Parse allowed variables (safe data extraction, no arbitrary execution).
2. Validate schema and grid shape.
3. Load tileset image from `TILESET_PATH`.
4. Slice tileset using `TILE_SIZE`.
5. Store layer data + sliced tileset reference.

After all layers are parsed:

6. Validate cross-layer dimensions.
7. Sort layers by `LAYER_ORDER` ascending.
8. Render sorted layers bottom-to-top.

Per cell render rule:

1. Read `(tileset_x, tileset_y)` from `UNIT_COORD_GRID[row][col]`.
2. If the cell is `None`, skip draw for this layer/cell.
3. Otherwise resolve tile from sliced tileset.
4. Draw at `(col * RENDER_TILE_SIZE, row * RENDER_TILE_SIZE)`.

Per cell blocking rule:

1. Read `blocked = BLOCKING_GRID[row][col]`.
2. Use this flag when building the final collision/navigation map (commonly OR-combined across layers).

## 7. Validation Rules (Required)

Fail map load with explicit error messages if any check fails.

### Per-layer checks

- Required fields exist and have correct types.
- `TILESET_PATH` exists.
- `TILE_SIZE > 0`.
- `MAP_WIDTH > 0`, `MAP_HEIGHT > 0`.
- `UNIT_COORD_GRID` has exactly `MAP_HEIGHT` rows.
- Each row has exactly `MAP_WIDTH` cells.
- Each cell is either `None` or exactly two integers `(x, y)`.
- For non-`None` cells, `(x, y)` is inside sliced tileset bounds.
- `BLOCKING_GRID` has exactly `MAP_HEIGHT` rows.
- Each `BLOCKING_GRID` row has exactly `MAP_WIDTH` booleans.

### Cross-layer checks

- All layers in map share identical `MAP_WIDTH`.
- All layers in map share identical `MAP_HEIGHT`.
- `LAYER_ORDER` values must be unique within one map.

## 8. Rendering Order in Frame

Recommended high-level order:

1. Map layers (sorted by `LAYER_ORDER`)
2. Entities
3. Projectiles/effects
4. Player
5. HUD/UI

Map layers must render below gameplay elements.

## 9. Coordinate System

Map grid:

- Origin `(0, 0)` = top-left map cell
- X grows right
- Y grows down

Tileset grid (inside `(x, y)` tuples):

- Origin `(0, 0)` = top-left tileset tile
- X grows right
- Y grows down

Diagram:

```text
Map grid:
(0,0) -> +x
  |
  v
 +y

Tileset grid:
(0,0) (1,0) (2,0) ...
(0,1) (1,1) (2,1) ...
...
```

## 10. Complete Example Layer File

```python
LAYER_NAME = "base"
LAYER_ORDER = 0
MAP_ID = "ashland_map"
TILESET_NAME = "A5_Ashland"
TILESET_PATH = "assets/tilesets/ashland/tf_A5_ashlands_2.png"
TILE_SIZE = 16
MAP_WIDTH = 4
MAP_HEIGHT = 2

UNIT_COORD_GRID = (
    ((2, 0), None, (3, 0), (3, 0)),
    (None, (3, 0), (3, 0), (4, 0)),
)

BLOCKING_GRID = (
    (False, False, False, False),
    (False, True, False, False),
)
```

How this renders:

- Slice `TILESET_PATH` by `TILE_SIZE=16`.
- Skip `None` cells (transparent in this layer).
- Resolve non-`None` cell coordinates to source tiles.
- Draw each non-`None` tile at map-space cell position using `RENDER_TILE_SIZE`.

## 11. Intended Workflow

1. Create base layer in `map-builder`
2. Save layer file
3. Load it as background
4. Switch tileset
5. Create second layer
6. Repeat for details layer(s)
7. Place layer files in game map folder
8. Game loader reads all layer files and composes final map by `LAYER_ORDER`

## 12. Instructions for Game Map Loader Implementation

1. Locate map folder (for example `assets/maps/<map_id>/`).
2. Enumerate candidate layer files (`*.py`).
3. For each file:
- parse safe variables only (see section 5)
- validate required fields and grid shape
- resolve/load `TILESET_PATH`
- slice tileset with `TILE_SIZE`
4. Validate cross-layer constraints:
- same width/height
- unique `LAYER_ORDER`
5. Sort layers by `LAYER_ORDER` ascending.
6. Build in-memory map object:
- map dimensions
- ordered layers
- per-layer tileset data
- per-layer coordinate grid
 - per-layer blocking grid
7. Render layers bottom-to-top using `RENDER_TILE_SIZE`.
8. Render gameplay entities and UI above map layers.
9. On any failure, abort map load and emit file+field-specific error.

## Compatibility Notes

- This spec requires `LAYER_ORDER` for deterministic layer stacking.
- Loader should default `BLOCKING_GRID` to all `False` when older files omit it.
- Older files that contain only `(x, y)` cells in `UNIT_COORD_GRID` remain valid.
