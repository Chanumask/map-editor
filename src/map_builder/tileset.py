from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame

TileCoord = tuple[int, int]
TileCell = TileCoord | None


@dataclass(frozen=True, slots=True)
class Tile:
    coord: TileCoord
    surface: pygame.Surface


@dataclass(slots=True)
class Tileset:
    path: Path
    tile_size: int
    tiles: list[Tile]
    columns: int
    rows: int
    ignored_width_px: int = 0
    ignored_height_px: int = 0
    _lookup: dict[TileCoord, pygame.Surface] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lookup = {tile.coord: tile.surface for tile in self.tiles}

    @classmethod
    def load(cls, path: str | Path, tile_size: int) -> Tileset:
        if tile_size <= 0:
            msg = "Tile size must be a positive integer."
            raise ValueError(msg)

        file_path = Path(path)
        loaded = pygame.image.load(str(file_path))
        try:
            image = loaded.convert_alpha()
        except pygame.error:
            image = loaded.convert()

        width, height = image.get_size()
        columns = width // tile_size
        rows = height // tile_size
        ignored_width_px = width % tile_size
        ignored_height_px = height % tile_size

        if columns == 0 or rows == 0:
            msg = f"Tileset image is too small for tile size {tile_size}."
            raise ValueError(msg)

        tiles: list[Tile] = []
        for row in range(rows):
            for column in range(columns):
                rect = pygame.Rect(
                    column * tile_size,
                    row * tile_size,
                    tile_size,
                    tile_size,
                )
                surface = image.subsurface(rect).copy()
                tiles.append(Tile(coord=(column, row), surface=surface))

        return cls(
            path=file_path,
            tile_size=tile_size,
            tiles=tiles,
            columns=columns,
            rows=rows,
            ignored_width_px=ignored_width_px,
            ignored_height_px=ignored_height_px,
        )

    def get_tile_surface(self, coord: TileCoord) -> pygame.Surface | None:
        return self._lookup.get(coord)
