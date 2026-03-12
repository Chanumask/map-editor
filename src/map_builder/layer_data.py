from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from map_builder.blocking_grid import BlockingGrid
from map_builder.map_grid import MapGrid
from map_builder.tileset import TileCoord, Tileset


@dataclass(slots=True)
class MapLayerData:
    name: str
    layer_order: int
    tileset_path: str
    tile_size: int
    map_grid: MapGrid
    blocking_grid: BlockingGrid

    def __post_init__(self) -> None:
        if self.layer_order < 0:
            msg = "layer_order must be >= 0."
            raise ValueError(msg)
        if self.map_grid.columns != self.blocking_grid.columns:
            msg = "map_grid and blocking_grid must share the same width."
            raise ValueError(msg)
        if self.map_grid.rows != self.blocking_grid.rows:
            msg = "map_grid and blocking_grid must share the same height."
            raise ValueError(msg)

    @property
    def width(self) -> int:
        return self.map_grid.columns

    @property
    def height(self) -> int:
        return self.map_grid.rows


@dataclass(slots=True)
class LoadedBackgroundLayer:
    source_path: Path
    layer_data: MapLayerData
    resolved_tileset_path: Path
    tileset: Tileset
    tile_cache: dict[TileCoord, pygame.Surface]
