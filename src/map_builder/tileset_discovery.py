from __future__ import annotations

from pathlib import Path

SUPPORTED_TILESET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def discover_tilesets(tileset_root: Path) -> list[Path]:
    if not tileset_root.exists() or not tileset_root.is_dir():
        return []

    results = []
    for path in tileset_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_TILESET_EXTENSIONS:
            continue
        results.append(path.resolve())

    return sorted(results, key=lambda path: str(path).lower())
