from __future__ import annotations

from pathlib import Path

import pygame

from map_builder.blocking_grid import BlockingGrid
from map_builder.brush import TilePatch
from map_builder.layer_data import LoadedBackgroundLayer, MapLayerData
from map_builder.layer_file import load_layer_file, save_layer_file
from map_builder.map_grid import EMPTY_TILE, MAP_COLUMNS, MAP_ROWS, MapGrid
from map_builder.tileset import TileCoord, Tileset
from map_builder.tileset_discovery import SUPPORTED_TILESET_EXTENSIONS, discover_tilesets
from map_builder.tools import Tool

FPS = 60

WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 720

UI_PADDING = 14
TOP_BAR_HEIGHT = 260

LEFT_PANEL_MIN_WIDTH = 360
LEFT_PANEL_MAX_WIDTH = 560
LEFT_PANEL_RATIO = 0.32

MAP_CELL_SIZE = 16

PALETTE_GAP = 0
PALETTE_MIN_TILE_SIZE = 8
PALETTE_MAX_TILE_SIZE = 40
PALETTE_HEIGHT_RATIO = 0.90
STATUS_SECTION_HEIGHT = 44

BACKGROUND_LAYER_ALPHA = 170

BG_COLOR = (32, 35, 39)
PANEL_COLOR = (44, 48, 54)
PANEL_BORDER_COLOR = (68, 74, 82)
BUTTON_COLOR = (79, 137, 224)
BUTTON_HOVER_COLOR = (95, 153, 240)
BUTTON_ACTIVE_COLOR = (244, 175, 73)
BUTTON_TEXT_COLOR = (242, 246, 252)
INPUT_BG_COLOR = (24, 27, 31)
INPUT_BORDER_COLOR = (110, 116, 126)
INPUT_ACTIVE_BORDER_COLOR = (130, 180, 250)
TEXT_COLOR = (226, 231, 239)
MUTED_TEXT_COLOR = (190, 197, 208)
MAP_GRID_COLOR = (77, 84, 93)
CHECKER_LIGHT = (63, 68, 75)
CHECKER_DARK = (56, 61, 68)
OUT_OF_BOUNDS_CELL = (49, 53, 59)
SELECTION_COLOR = (250, 216, 115)
CANVAS_SELECTION_COLOR = (113, 204, 156)
CLIPBOARD_COLOR = (113, 158, 224)
BLOCKING_OVERLAY_FILL = (220, 65, 65, 110)
BLOCKING_OVERLAY_LINE = (255, 220, 220, 200)
SECTION_BG_COLOR = (39, 43, 50)
SECTION_BORDER_COLOR = (86, 93, 104)


class MapBuilderApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Map Builder")

        display_info = pygame.display.Info()
        display_width = display_info.current_w or 1440
        display_height = display_info.current_h or 900
        self.window_width = max(WINDOW_MIN_WIDTH, display_width)
        self.window_height = max(WINDOW_MIN_HEIGHT, display_height)

        self.screen = pygame.display.set_mode(
            (self.window_width, self.window_height),
            pygame.RESIZABLE,
        )
        self.clock = pygame.time.Clock()

        self.ui_font = pygame.font.Font(None, 22)
        self.small_font = pygame.font.Font(None, 18)
        self.label_font = pygame.font.Font(None, 17)
        self.header_font = pygame.font.Font(None, 21)
        self.status_font = pygame.font.Font(None, 16)
        self.header_font.set_bold(True)

        default_grid = MapGrid(columns=MAP_COLUMNS, rows=MAP_ROWS, default_coord=EMPTY_TILE)
        default_blocking_grid = BlockingGrid(
            columns=MAP_COLUMNS,
            rows=MAP_ROWS,
            default_blocked=False,
        )
        self.active_layer = MapLayerData(
            name="active_layer",
            layer_order=0,
            tileset_path="",
            tile_size=16,
            map_grid=default_grid,
            blocking_grid=default_blocking_grid,
        )
        self.tileset: Tileset | None = None

        self.background_layers: list[LoadedBackgroundLayer] = []
        self.tileset_cache: dict[tuple[str, int], Tileset] = {}

        self.last_saved_layer_path: Path | None = None
        self.last_saved_layer_dir: Path = Path.cwd() / "layers"
        self.last_saved_layer_filename: str | None = None
        self.last_saved_layer_dir.mkdir(parents=True, exist_ok=True)

        self.map_view_column_offset = 0
        self.map_view_row_offset = 0

        self.selected_tile_coord: TileCoord = (0, 0)
        self.active_brush = TilePatch.from_single((0, 0))
        self.clipboard_patch: TilePatch | None = None

        self.active_tool = Tool.PAINT
        self.active_input: str | None = None

        self.tile_size_text = "16"
        self.tileset_root = Path.cwd() / "tilesets"
        self.tileset_root.mkdir(parents=True, exist_ok=True)
        self.available_tilesets: list[Path] = []
        self.selected_tileset_index: int | None = None
        self.tileset_dropdown_open = False
        self.tileset_dropdown_scroll = 0
        self.tileset_dropdown_item_height = 24
        self.tileset_dropdown_max_visible = 8
        self.output_path_text = "layers/active_layer.py"
        self.layer_file_path_text = ""
        self.map_width_text = str(self.map_grid.columns)
        self.map_height_text = str(self.map_grid.rows)
        self.status_message = (
            "Select a tileset from the dropdown, then paint/save layers and load them as BG."
        )

        self.palette_scroll = 0
        self.map_painting = False
        self.map_erasing = False
        self.map_blocking = False
        self.map_block_target_state: bool | None = None
        self.map_unblocking = False

        self.tileset_selecting = False
        self.tileset_selection_anchor: tuple[int, int] | None = None
        self.tileset_selection_current: tuple[int, int] | None = None
        self.tileset_patch_bounds: tuple[int, int, int, int] | None = None

        self.canvas_selecting = False
        self.canvas_selection_anchor: tuple[int, int] | None = None
        self.canvas_selection_current: tuple[int, int] | None = None
        self.canvas_selection_bounds: tuple[int, int, int, int] | None = None

        self.map_tile_cache: dict[TileCoord, pygame.Surface] = {}
        self.palette_tile_cache: dict[tuple[TileCoord, int], pygame.Surface] = {}
        self.blocking_overlay_surface = self._create_blocking_overlay_surface()

        self._update_layout()
        self._refresh_tileset_options(preserve_selection=False)

    @property
    def map_grid(self) -> MapGrid:
        return self.active_layer.map_grid

    @map_grid.setter
    def map_grid(self, grid: MapGrid) -> None:
        self.active_layer.map_grid = grid

    @property
    def blocking_grid(self) -> BlockingGrid:
        return self.active_layer.blocking_grid

    @blocking_grid.setter
    def blocking_grid(self, grid: BlockingGrid) -> None:
        self.active_layer.blocking_grid = grid

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self._handle_window_resize(event.w, event.h)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_button_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._handle_mouse_button_up(event)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self._handle_mouse_wheel(event)
                elif event.type == pygame.KEYDOWN:
                    self._handle_key_down(event)
                elif event.type == pygame.DROPFILE:
                    self._handle_drop_file(event.file)

            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def _handle_window_resize(self, width: int, height: int) -> None:
        self.window_width = max(WINDOW_MIN_WIDTH, width)
        self.window_height = max(WINDOW_MIN_HEIGHT, height)
        self.screen = pygame.display.set_mode(
            (self.window_width, self.window_height),
            pygame.RESIZABLE,
        )
        self._update_layout()
        self._clamp_map_view_offsets()

    def _update_layout(self) -> None:
        self.left_panel_width = max(
            LEFT_PANEL_MIN_WIDTH,
            min(int(self.window_width * LEFT_PANEL_RATIO), LEFT_PANEL_MAX_WIDTH),
        )

        self.map_left = self.left_panel_width + UI_PADDING
        self.map_top = TOP_BAR_HEIGHT + UI_PADDING
        self.map_view_width = self.window_width - self.map_left - UI_PADDING
        self.map_view_height = self.window_height - self.map_top - UI_PADDING

        x = UI_PADDING
        y = UI_PADDING
        inner_width = self.left_panel_width - (UI_PADDING * 2)

        row_0_y = y
        row_1_y = y + 54
        row_2_y = y + 98
        row_3_y = y + 142
        row_4_y = y + 178
        row_5_y = y + 216

        self.load_button_rect = pygame.Rect(x, row_0_y, 120, 32)
        self.save_button_rect = pygame.Rect(x + 128, row_0_y, 120, 32)
        tile_width = max(56, inner_width - 256)
        self.tile_size_input_rect = pygame.Rect(x + 256, row_0_y, tile_width, 32)

        self.tileset_dropdown_rect = pygame.Rect(x, row_1_y, inner_width - 88, 28)
        self.tileset_refresh_rect = pygame.Rect(
            self.tileset_dropdown_rect.right + 6,
            row_1_y,
            82,
            28,
        )
        self.output_path_input_rect = pygame.Rect(x, row_2_y, inner_width, 28)
        self.layer_file_path_input_rect = pygame.Rect(x, row_3_y, inner_width, 28)

        self.new_active_layer_rect = pygame.Rect(x, row_4_y, 100, 30)
        self.load_active_layer_rect = pygame.Rect(x + 108, row_4_y, 100, 30)
        self.load_bg_rect = pygame.Rect(x + 216, row_4_y, inner_width - 216, 30)
        self.clear_canvas_rect = pygame.Rect(x, row_5_y, 120, 30)
        self.clear_backgrounds_rect = pygame.Rect(x + 128, row_5_y, inner_width - 128, 30)

        self.left_io_section_rect = pygame.Rect(
            x - 6,
            y - 8,
            inner_width + 12,
            self.layer_file_path_input_rect.bottom - y + 18,
        )
        self.left_actions_section_rect = pygame.Rect(
            x - 6,
            self.new_active_layer_rect.y - 10,
            inner_width + 12,
            self.clear_backgrounds_rect.bottom - self.new_active_layer_rect.y + 18,
        )
        palette_available_height = self.window_height - TOP_BAR_HEIGHT - (UI_PADDING * 2)
        palette_height = max(120, int(palette_available_height * PALETTE_HEIGHT_RATIO))
        palette_y = self.window_height - UI_PADDING - palette_height
        self.palette_rect = pygame.Rect(
            UI_PADDING,
            palette_y,
            self.left_panel_width - (UI_PADDING * 2),
            palette_height,
        )
        status_top = self.clear_backgrounds_rect.bottom + 8
        status_bottom = self.palette_rect.y - 8
        status_height = min(STATUS_SECTION_HEIGHT, max(0, status_bottom - status_top))
        self.left_status_section_rect = pygame.Rect(
            x - 6,
            status_top,
            inner_width + 12,
            status_height,
        )
        self.left_status_y = self.left_status_section_rect.y + 10
        if self.tileset is None:
            self.palette_scroll = 0
        else:
            self.palette_scroll = max(0, min(self.palette_scroll, self._max_palette_scroll()))

        tool_y = 24
        tool_h = 32
        tx = self.map_left
        gap = 8
        tool_x = tx + 12
        self.paint_tool_rect = pygame.Rect(tool_x, tool_y, 74, tool_h)
        self.fill_background_rect = pygame.Rect(
            self.paint_tool_rect.right + gap, tool_y, 84, tool_h
        )
        self.tileset_patch_tool_rect = pygame.Rect(
            self.fill_background_rect.right + gap,
            tool_y,
            122,
            tool_h,
        )
        self.canvas_copy_tool_rect = pygame.Rect(
            self.tileset_patch_tool_rect.right + gap,
            tool_y,
            132,
            tool_h,
        )
        self.paste_tool_rect = pygame.Rect(
            self.canvas_copy_tool_rect.right + gap, tool_y, 68, tool_h
        )
        self.block_tool_rect = pygame.Rect(self.paste_tool_rect.right + gap, tool_y, 74, tool_h)

        size_y = 70
        self.map_width_input_rect = pygame.Rect(tx + 98, size_y, 62, 30)
        self.map_height_input_rect = pygame.Rect(tx + 184, size_y, 62, 30)
        self.apply_map_size_rect = pygame.Rect(tx + 256, size_y, 106, 30)
        self.top_tools_section_rect = pygame.Rect(
            self.map_left + 8, 8, self.map_view_width - 16, 50
        )
        self.top_info_section_rect = pygame.Rect(
            self.map_left + 8,
            62,
            self.map_view_width - 16,
            TOP_BAR_HEIGHT - 70,
        )

        self.map_rect = pygame.Rect(
            self.map_left,
            self.map_top,
            self.map_view_width,
            self.map_view_height,
        )

    def _handle_mouse_button_down(self, event: pygame.event.Event) -> None:
        if event.button == 1:
            if self._handle_tileset_dropdown_click(event.pos):
                return

            if self._handle_top_control_click(event.pos):
                return

            if self.load_button_rect.collidepoint(event.pos):
                self._load_tileset()
                return

            if self.save_button_rect.collidepoint(event.pos):
                self._save_active_layer()
                return

            if self.new_active_layer_rect.collidepoint(event.pos):
                self._new_active_layer()
                return

            if self.load_active_layer_rect.collidepoint(event.pos):
                self._load_active_layer_from_file()
                return

            if self.load_bg_rect.collidepoint(event.pos):
                self._add_background_layer_from_file()
                return

            if self.clear_canvas_rect.collidepoint(event.pos):
                self._clear_active_canvas()
                return

            if self.clear_backgrounds_rect.collidepoint(event.pos):
                self._clear_background_layers()
                return

            self.active_input = self._input_name_at_position(event.pos)

            if self.palette_rect.collidepoint(event.pos):
                self._handle_palette_mouse_down(event.pos)
                return

            if self.map_rect.collidepoint(event.pos):
                self._handle_map_mouse_down(event.pos)
                return

        if event.button == 3 and self.map_rect.collidepoint(event.pos):
            if self.active_tool == Tool.PAINT:
                self.map_erasing = True
                self._erase_map_cell(event.pos)
            elif self.active_tool == Tool.BLOCK:
                self.map_unblocking = True
                self._set_blocking_at_position(event.pos, blocked=False)

    def _handle_mouse_button_up(self, event: pygame.event.Event) -> None:
        if event.button == 1:
            self.map_painting = False
            self.map_blocking = False
            self.map_block_target_state = None

            if self.tileset_selecting:
                self._finalize_tileset_patch_selection()

            if self.canvas_selecting:
                self._finalize_canvas_selection_copy()

        if event.button == 3:
            self.map_erasing = False
            self.map_unblocking = False

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.map_painting and event.buttons[0] and self.active_tool == Tool.PAINT:
            self._paint_brush_at_position(event.pos)

        if self.map_erasing and event.buttons[2] and self.active_tool == Tool.PAINT:
            self._erase_map_cell(event.pos)

        if self.map_blocking and event.buttons[0] and self.active_tool == Tool.BLOCK:
            if self.map_block_target_state is not None:
                self._set_blocking_at_position(event.pos, blocked=self.map_block_target_state)

        if self.map_unblocking and event.buttons[2] and self.active_tool == Tool.BLOCK:
            self._set_blocking_at_position(event.pos, blocked=False)

        if self.tileset_selecting:
            cell = self._palette_cell_at_position(event.pos, clamp=True)
            if cell is not None:
                self.tileset_selection_current = cell

        if self.canvas_selecting:
            cell = self._map_cell_at_position(event.pos, clamp=True)
            if cell is not None:
                self.canvas_selection_current = cell

    def _handle_mouse_wheel(self, event: pygame.event.Event) -> None:
        mouse_position = pygame.mouse.get_pos()

        if self.tileset_dropdown_open:
            list_rect = self._tileset_dropdown_list_rect()
            if self.tileset_dropdown_rect.collidepoint(mouse_position) or (
                list_rect is not None and list_rect.collidepoint(mouse_position)
            ):
                self.tileset_dropdown_scroll -= event.y
                self.tileset_dropdown_scroll = max(
                    0,
                    min(self.tileset_dropdown_scroll, self._max_tileset_dropdown_scroll()),
                )
                return

        if self.tileset is not None and self.palette_rect.collidepoint(mouse_position):
            self.palette_scroll -= event.y * 30
            self.palette_scroll = max(0, min(self.palette_scroll, self._max_palette_scroll()))
            return

        if self.map_rect.collidepoint(mouse_position):
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self._pan_map(-event.y * 2, 0)
            else:
                self._pan_map(0, -event.y * 2)

    def _handle_key_down(self, event: pygame.event.Event) -> None:
        if self.active_input is not None:
            self._handle_text_input_key(event)
            return

        if event.key == pygame.K_LEFT:
            self._pan_map(-1, 0)
        elif event.key == pygame.K_RIGHT:
            self._pan_map(1, 0)
        elif event.key == pygame.K_UP:
            self._pan_map(0, -1)
        elif event.key == pygame.K_DOWN:
            self._pan_map(0, 1)

    def _handle_text_input_key(self, event: pygame.event.Event) -> None:
        if self.active_input is None:
            return

        if event.key in {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE}:
            self.active_input = None
            return

        current_value = self._get_input_value(self.active_input)
        if event.key == pygame.K_BACKSPACE:
            self._set_input_value(self.active_input, current_value[:-1])
            return

        if not event.unicode or not event.unicode.isprintable():
            return

        if self.active_input in {"tile_size", "map_width", "map_height"}:
            if event.unicode.isdigit() and len(current_value) < 4:
                self._set_input_value(self.active_input, current_value + event.unicode)
            return

        if len(current_value) < 260:
            self._set_input_value(self.active_input, current_value + event.unicode)

    def _handle_drop_file(self, file_path: str) -> None:
        dropped_path = Path(file_path).expanduser()
        if not dropped_path.exists():
            self.status_message = f"Dropped file not found: {dropped_path}"
            return

        if dropped_path.suffix.lower() not in SUPPORTED_TILESET_EXTENSIONS:
            self.status_message = (
                f"Unsupported dropped file type: {dropped_path.suffix or '<none>'}."
            )
            return

        resolved_path = dropped_path.resolve()
        self._select_tileset_path(resolved_path, add_if_missing=True)
        self.tileset_dropdown_open = False
        self._load_tileset()

    def _handle_tileset_dropdown_click(self, position: tuple[int, int]) -> bool:
        if self.tileset_refresh_rect.collidepoint(position):
            self._refresh_tileset_options(preserve_selection=True)
            self.tileset_dropdown_open = False
            count = len(self.available_tilesets)
            if count == 0:
                self.status_message = f"No tilesets found under {self.tileset_root}."
            else:
                self.status_message = f"Refreshed tilesets: {count} found."
            return True

        if self.tileset_dropdown_rect.collidepoint(position):
            self.active_input = None
            if not self.available_tilesets:
                self.status_message = f"No tilesets found under {self.tileset_root}."
                return True
            self.tileset_dropdown_open = not self.tileset_dropdown_open
            return True

        if not self.tileset_dropdown_open:
            return False

        option_index = self._tileset_option_index_at_position(position)
        if option_index is not None:
            self.selected_tileset_index = option_index
            self.tileset_dropdown_open = False
            self.active_input = None
            self._load_tileset()
            return True

        list_rect = self._tileset_dropdown_list_rect()
        if list_rect is None or not list_rect.collidepoint(position):
            self.tileset_dropdown_open = False
        return False

    def _handle_top_control_click(self, position: tuple[int, int]) -> bool:
        if self.paint_tool_rect.collidepoint(position):
            self.active_tool = Tool.PAINT
            self.status_message = "Paint tool active."
            return True

        if self.fill_background_rect.collidepoint(position):
            self._fill_active_layer_with_selected_tile()
            return True

        if self.tileset_patch_tool_rect.collidepoint(position):
            self.active_tool = Tool.TILESET_PATCH
            self.status_message = "Tileset patch selection active. Drag in the tileset panel."
            return True

        if self.canvas_copy_tool_rect.collidepoint(position):
            self.active_tool = Tool.CANVAS_SELECT
            self.status_message = "Canvas select/copy active. Drag on map to copy a region."
            return True

        if self.paste_tool_rect.collidepoint(position):
            self.active_tool = Tool.PASTE
            if self.clipboard_patch is None:
                self.status_message = "Paste tool active. Clipboard is empty."
            else:
                self.status_message = "Paste tool active. Click map to paste clipboard patch."
            return True

        if self.block_tool_rect.collidepoint(position):
            self.active_tool = Tool.BLOCK
            self.status_message = "Block tool active. Left-click toggles, right-click clears."
            return True

        if self.apply_map_size_rect.collidepoint(position):
            self._apply_canvas_resize()
            return True

        return False

    def _load_tileset(self) -> None:
        selected_path = self._selected_tileset_path()
        if selected_path is None:
            if self.available_tilesets:
                self.status_message = "Select a tileset from the dropdown first."
            else:
                self.status_message = f"No tilesets found under {self.tileset_root}."
            return

        self._load_tileset_from_path(selected_path)

    def _load_tileset_from_path(self, selected_path: Path) -> bool:
        tile_size = self._parse_positive_int(self.tile_size_text, minimum=1, maximum=256)
        if tile_size is None:
            self.status_message = "Tile size must be an integer from 1 to 256."
            return False

        resolved_path = selected_path.resolve()
        try:
            tileset = Tileset.load(resolved_path, tile_size)
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to load tileset: {exc}"
            return False

        self._select_tileset_path(resolved_path, add_if_missing=True)
        self.tileset = tileset
        self.active_layer.tileset_path = str(self._path_for_export(resolved_path))
        self.active_layer.tile_size = tile_size

        self.palette_scroll = 0
        self.palette_tile_cache.clear()
        self._rebuild_active_map_tile_cache()
        self._set_single_tile_brush((0, 0), announce=False)

        remainder_note = ""
        if tileset.ignored_width_px or tileset.ignored_height_px:
            remainder_note = (
                f" Ignored remainder: {tileset.ignored_width_px}px width, "
                f"{tileset.ignored_height_px}px height."
            )
        self.status_message = (
            f"Loaded active tileset {resolved_path.name}: {tileset.columns}x{tileset.rows} tiles."
            f"{remainder_note}"
        )
        return True

    def _save_active_layer(self) -> None:
        if self.tileset is None:
            self.status_message = "Load an active tileset before saving a layer file."
            return

        selected_path = self._normalize_user_path(self.output_path_text)
        if not selected_path:
            self.status_message = "Output path is empty."
            return

        output_path = self._resolve_output_path(selected_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        layer_to_save = MapLayerData(
            name=output_path.stem,
            layer_order=self.active_layer.layer_order,
            tileset_path=self.active_layer.tileset_path,
            tile_size=self.active_layer.tile_size,
            map_grid=self.map_grid,
            blocking_grid=self.blocking_grid,
        )

        try:
            save_layer_file(output_path, layer_to_save)
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to save layer: {exc}"
            return

        self.active_layer.name = layer_to_save.name
        self.output_path_text = str(self._path_for_display(output_path))
        self._set_last_saved_layer(output_path)
        self.status_message = (
            f"Saved active layer to {output_path}. Load BG now defaults to this file."
        )

    def _set_last_saved_layer(self, output_path: Path) -> None:
        self.last_saved_layer_path = output_path
        self.last_saved_layer_dir = output_path.parent
        self.last_saved_layer_filename = output_path.name
        self.layer_file_path_text = str(self._path_for_display(output_path))

    def _resolve_layer_source_path(self) -> Path | None:
        selected_path = self._normalize_user_path(self.layer_file_path_text)
        if selected_path:
            return self._resolve_path_for_read(selected_path)
        if self.last_saved_layer_path is not None:
            source_path = self.last_saved_layer_path
            self.layer_file_path_text = str(self._path_for_display(source_path))
            return source_path
        return None

    def _new_active_layer(self) -> None:
        new_grid = MapGrid(
            columns=self.map_grid.columns,
            rows=self.map_grid.rows,
            default_coord=EMPTY_TILE,
        )
        new_blocking_grid = BlockingGrid(
            columns=self.blocking_grid.columns,
            rows=self.blocking_grid.rows,
            default_blocked=False,
        )
        self.map_grid = new_grid
        self.blocking_grid = new_blocking_grid
        self.canvas_selection_bounds = None
        self.canvas_selection_anchor = None
        self.canvas_selection_current = None
        self._clamp_map_view_offsets()
        self.status_message = "Started new blank active layer."

    def _load_active_layer_from_file(self) -> None:
        source_path = self._resolve_layer_source_path()
        if source_path is None:
            self.status_message = (
                "No layer path set yet. Save a layer first or enter a layer file path."
            )
            return

        if not source_path.exists():
            self.status_message = f"Layer file does not exist: {source_path}"
            return

        try:
            layer_data = load_layer_file(source_path)
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to load layer file: {exc}"
            return

        try:
            resolved_tileset_path = self._resolve_tileset_path_from_layer(
                layer_data.tileset_path,
                source_path,
            )
            self._select_tileset_path(resolved_tileset_path, add_if_missing=True)
            self.tile_size_text = str(layer_data.tile_size)
            loaded = self._load_tileset_from_path(resolved_tileset_path)
            if not loaded:
                return
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to load active layer tileset: {exc}"
            return

        layer_data.tileset_path = str(self._path_for_export(resolved_tileset_path))
        self.active_layer = layer_data
        self.map_width_text = str(self.map_grid.columns)
        self.map_height_text = str(self.map_grid.rows)
        self.output_path_text = str(self._path_for_display(source_path))
        self.layer_file_path_text = str(self._path_for_display(source_path))
        self.canvas_selection_bounds = None
        self.canvas_selection_anchor = None
        self.canvas_selection_current = None
        self._clamp_map_view_offsets()
        self._rebuild_active_map_tile_cache()
        self._set_single_tile_brush((0, 0), announce=False)

        self.status_message = (
            f"Loaded active layer '{self.active_layer.name}' from {source_path.name} for editing."
        )

    def _add_background_layer_from_file(self) -> None:
        source_path = self._resolve_layer_source_path()
        if source_path is None:
            self.status_message = (
                "No layer path set yet. Save a layer first or enter a layer file path."
            )
            return

        if not source_path.exists():
            self.status_message = f"Layer file does not exist: {source_path}"
            return

        try:
            layer_data = load_layer_file(source_path)
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to load layer file: {exc}"
            return

        try:
            resolved_tileset_path = self._resolve_tileset_path_from_layer(
                layer_data.tileset_path,
                source_path,
            )
            background_tileset = self._get_or_load_tileset(
                resolved_tileset_path,
                layer_data.tile_size,
            )
        except Exception as exc:  # noqa: BLE001
            self.status_message = f"Failed to load background tileset: {exc}"
            return

        tile_cache = self._build_tile_cache(background_tileset, alpha=BACKGROUND_LAYER_ALPHA)
        background_layer = LoadedBackgroundLayer(
            source_path=source_path,
            layer_data=layer_data,
            resolved_tileset_path=resolved_tileset_path,
            tileset=background_tileset,
            tile_cache=tile_cache,
        )
        self.background_layers.append(background_layer)
        self.layer_file_path_text = str(self._path_for_display(source_path))

        size_note = ""
        if layer_data.width != self.map_grid.columns or layer_data.height != self.map_grid.rows:
            size_note = " Size differs from active layer; rendering is clipped to active bounds."

        self.status_message = (
            f"Loaded background layer '{layer_data.name}' from {source_path.name}."
            f" Total backgrounds: {len(self.background_layers)}.{size_note}"
        )

    def _clear_background_layers(self) -> None:
        count = len(self.background_layers)
        self.background_layers.clear()
        self.status_message = f"Cleared {count} background layer(s)."

    def _clear_active_canvas(self) -> None:
        self.map_grid.fill(EMPTY_TILE)
        self.blocking_grid.fill(False)
        self.canvas_selection_bounds = None
        self.canvas_selection_anchor = None
        self.canvas_selection_current = None
        self.status_message = "Cleared active layer canvas and blocking grid."

    def _fill_active_layer_with_selected_tile(self) -> None:
        self.map_grid.fill(self.selected_tile_coord)
        self.status_message = f"Filled active layer with tile {self.selected_tile_coord}."

    def _apply_canvas_resize(self) -> None:
        width = self._parse_positive_int(self.map_width_text, minimum=1, maximum=5000)
        height = self._parse_positive_int(self.map_height_text, minimum=1, maximum=5000)
        if width is None or height is None:
            self.status_message = "Map size must be two integers between 1 and 5000."
            return

        if width == self.map_grid.columns and height == self.map_grid.rows:
            self.status_message = f"Map size unchanged at {width}x{height}."
            return

        old_grid = self.map_grid
        old_blocking_grid = self.blocking_grid
        new_grid = MapGrid(columns=width, rows=height, default_coord=EMPTY_TILE)
        new_blocking_grid = BlockingGrid(columns=width, rows=height, default_blocked=False)

        copy_columns = min(old_grid.columns, new_grid.columns)
        copy_rows = min(old_grid.rows, new_grid.rows)
        for row in range(copy_rows):
            for column in range(copy_columns):
                new_grid.paint(column, row, old_grid.get(column, row))
                new_blocking_grid.set(column, row, old_blocking_grid.get(column, row))

        self.map_grid = new_grid
        self.blocking_grid = new_blocking_grid
        self.map_width_text = str(width)
        self.map_height_text = str(height)
        self.canvas_selection_bounds = None
        self.canvas_selection_anchor = None
        self.canvas_selection_current = None
        self._clamp_map_view_offsets()

        self.status_message = (
            f"Resized active layer to {width}x{height}. "
            "Existing tile and blocking data were preserved where overlapping."
        )

    def _set_single_tile_brush(self, coord: TileCoord, *, announce: bool = True) -> None:
        self.selected_tile_coord = coord
        self.active_brush = TilePatch.from_single(coord)
        self.tileset_patch_bounds = (coord[0], coord[1], coord[0], coord[1])
        if announce:
            self.status_message = f"Selected tile {coord}."

    def _handle_palette_mouse_down(self, position: tuple[int, int]) -> None:
        if self.tileset is None:
            return

        cell = self._palette_cell_at_position(position)
        if cell is None:
            return

        if self.active_tool == Tool.TILESET_PATCH:
            self.tileset_selecting = True
            self.tileset_selection_anchor = cell
            self.tileset_selection_current = cell
            return

        self._set_single_tile_brush(cell)

    def _handle_map_mouse_down(self, position: tuple[int, int]) -> None:
        if self.active_tool == Tool.PAINT:
            self.map_painting = True
            self._paint_brush_at_position(position)
            return

        if self.active_tool == Tool.CANVAS_SELECT:
            cell = self._map_cell_at_position(position)
            if cell is None:
                return
            self.canvas_selecting = True
            self.canvas_selection_anchor = cell
            self.canvas_selection_current = cell
            return

        if self.active_tool == Tool.PASTE:
            self._paste_clipboard_at_position(position)
            return

        if self.active_tool == Tool.BLOCK:
            cell = self._map_cell_at_position(position)
            if cell is None:
                return
            next_blocked = not self.blocking_grid.get(cell[0], cell[1])
            self.blocking_grid.set(cell[0], cell[1], next_blocked)
            self.map_blocking = True
            self.map_block_target_state = next_blocked

    def _finalize_tileset_patch_selection(self) -> None:
        self.tileset_selecting = False
        if self.tileset_selection_anchor is None or self.tileset_selection_current is None:
            return

        left, top, right, bottom = self._normalize_bounds(
            self.tileset_selection_anchor,
            self.tileset_selection_current,
        )
        self.tileset_selection_anchor = None
        self.tileset_selection_current = None

        patch_rows = []
        for row in range(top, bottom + 1):
            patch_rows.append(tuple((column, row) for column in range(left, right + 1)))

        patch = TilePatch(rows=tuple(patch_rows))
        self.active_brush = patch
        self.selected_tile_coord = patch.top_left
        self.tileset_patch_bounds = (left, top, right, bottom)
        self.active_tool = Tool.PAINT
        self.status_message = (
            f"Selected tileset patch {patch.width}x{patch.height} from ({left}, {top}). "
            "Paint tool active."
        )

    def _finalize_canvas_selection_copy(self) -> None:
        self.canvas_selecting = False
        if self.canvas_selection_anchor is None or self.canvas_selection_current is None:
            return

        left, top, right, bottom = self._normalize_bounds(
            self.canvas_selection_anchor,
            self.canvas_selection_current,
        )
        self.canvas_selection_anchor = None
        self.canvas_selection_current = None

        patch = self.map_grid.copy_patch(left, top, right, bottom)
        self.clipboard_patch = patch
        self.canvas_selection_bounds = (left, top, right, bottom)
        self.status_message = (
            f"Copied active-layer patch {patch.width}x{patch.height} to clipboard."
        )

    def _paint_brush_at_position(self, position: tuple[int, int]) -> None:
        cell = self._map_cell_at_position(position)
        if cell is None:
            return
        self.map_grid.paste_patch(cell[0], cell[1], self.active_brush)

    def _paste_clipboard_at_position(self, position: tuple[int, int]) -> None:
        if self.clipboard_patch is None:
            self.status_message = "Clipboard is empty. Copy a canvas region first."
            return

        cell = self._map_cell_at_position(position)
        if cell is None:
            return

        clipped = self.map_grid.paste_patch(cell[0], cell[1], self.clipboard_patch)
        if clipped:
            self.status_message = (
                "Pasted clipboard patch into active layer (clipped at map bounds)."
            )
        else:
            self.status_message = "Pasted clipboard patch into active layer."

    def _erase_map_cell(self, position: tuple[int, int]) -> None:
        cell = self._map_cell_at_position(position)
        if cell is None:
            return
        self.map_grid.paint(cell[0], cell[1], EMPTY_TILE)

    def _set_blocking_at_position(self, position: tuple[int, int], *, blocked: bool) -> None:
        cell = self._map_cell_at_position(position)
        if cell is None:
            return
        self.blocking_grid.set(cell[0], cell[1], blocked)

    def _palette_cell_at_position(
        self,
        position: tuple[int, int],
        *,
        clamp: bool = False,
    ) -> tuple[int, int] | None:
        if self.tileset is None:
            return None

        tile_size = self._palette_tile_size()
        inner_left = self.palette_rect.x + UI_PADDING
        inner_top = self.palette_rect.y + UI_PADDING

        local_x = position[0] - inner_left
        local_y = position[1] - inner_top + self.palette_scroll

        slot_size = tile_size + PALETTE_GAP
        column = local_x // slot_size
        row = local_y // slot_size

        if clamp:
            column = max(0, min(column, self.tileset.columns - 1))
            row = max(0, min(row, self.tileset.rows - 1))
            return (column, row)

        if local_x < 0 or local_y < 0:
            return None
        if column < 0 or row < 0:
            return None
        if column >= self.tileset.columns or row >= self.tileset.rows:
            return None

        if local_x % slot_size >= tile_size or local_y % slot_size >= tile_size:
            return None

        return (column, row)

    def _map_cell_at_position(
        self,
        position: tuple[int, int],
        *,
        clamp: bool = False,
    ) -> tuple[int, int] | None:
        visible_columns = self._visible_map_columns()
        visible_rows = self._visible_map_rows()

        if not clamp and not self.map_rect.collidepoint(position):
            return None

        relative_x = position[0] - self.map_rect.x
        relative_y = position[1] - self.map_rect.y
        view_column = relative_x // MAP_CELL_SIZE
        view_row = relative_y // MAP_CELL_SIZE

        if clamp:
            view_column = max(0, min(view_column, visible_columns - 1))
            view_row = max(0, min(view_row, visible_rows - 1))
        else:
            if view_column < 0 or view_row < 0:
                return None
            if view_column >= visible_columns or view_row >= visible_rows:
                return None

        column = self.map_view_column_offset + view_column
        row = self.map_view_row_offset + view_row

        if clamp:
            column = max(0, min(column, self.map_grid.columns - 1))
            row = max(0, min(row, self.map_grid.rows - 1))
            return (column, row)

        if not self.map_grid.in_bounds(column, row):
            return None

        return (column, row)

    def _draw(self) -> None:
        self.screen.fill(BG_COLOR)
        self._draw_left_panel()
        self._draw_top_tool_bar()
        self._draw_map_canvas()

    def _draw_left_panel(self) -> None:
        panel_rect = pygame.Rect(0, 0, self.left_panel_width, self.window_height)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect)
        pygame.draw.line(
            self.screen,
            PANEL_BORDER_COLOR,
            (self.left_panel_width, 0),
            (self.left_panel_width, self.window_height),
            width=2,
        )

        panel_title = self.header_font.render("Layer Controls", True, TEXT_COLOR)
        self.screen.blit(panel_title, (UI_PADDING, 2))

        self._draw_section_box(self.left_io_section_rect, "Tileset / Layer File")
        self._draw_section_box(self.left_actions_section_rect, "Layer Actions")
        self._draw_section_box(self.left_status_section_rect, "Status")

        self._draw_button(self.load_button_rect, "Load Tileset", is_active=False)
        self._draw_button(self.save_button_rect, "Save Layer", is_active=False)

        tile_label = self.label_font.render("Tile Size", True, TEXT_COLOR)
        self.screen.blit(
            tile_label,
            (self.tile_size_input_rect.x, self.tile_size_input_rect.y - 14),
        )
        self._draw_input_field(
            self.tile_size_input_rect,
            self.tile_size_text,
            self.active_input == "tile_size",
            align_right=False,
        )

        self._draw_tileset_dropdown()
        self._draw_labeled_input(
            "Save Path",
            self.output_path_input_rect,
            self.output_path_text,
            self.active_input == "output_path",
        )
        self._draw_labeled_input(
            "Layer Path (Active/BG)",
            self.layer_file_path_input_rect,
            self.layer_file_path_text,
            self.active_input == "layer_file_path",
        )

        self._draw_button(self.new_active_layer_rect, "New Active", is_active=False)
        self._draw_button(self.load_active_layer_rect, "Load Active", is_active=False)
        self._draw_button(self.load_bg_rect, "Load BG", is_active=False)
        self._draw_button(self.clear_canvas_rect, "Clear Canvas", is_active=False)
        self._draw_button(self.clear_backgrounds_rect, "Clear BG", is_active=False)

        status_rect = self.left_status_section_rect.inflate(-10, -10)
        pygame.draw.rect(self.screen, INPUT_BG_COLOR, status_rect, border_radius=4)
        pygame.draw.rect(self.screen, INPUT_BORDER_COLOR, status_rect, width=1, border_radius=4)
        status_text = self._fit_text_to_width(
            self.status_message,
            status_rect.width - 8,
            font=self.status_font,
        )
        status_surface = self.status_font.render(
            status_text,
            True,
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(
            status_surface,
            (
                status_rect.x + 4,
                status_rect.y + (status_rect.height - status_surface.get_height()) // 2,
            ),
        )

        pygame.draw.rect(self.screen, INPUT_BG_COLOR, self.palette_rect)
        pygame.draw.rect(self.screen, PANEL_BORDER_COLOR, self.palette_rect, width=1)
        palette_label = self.label_font.render("Tileset Preview (Scroll)", True, TEXT_COLOR)
        self.screen.blit(palette_label, (self.palette_rect.x, self.palette_rect.y - 18))

        if self.tileset is None:
            hint = self.ui_font.render("No active tileset loaded.", True, MUTED_TEXT_COLOR)
            self.screen.blit(hint, (self.palette_rect.x + 14, self.palette_rect.y + 14))
            return

        tile_size = self._palette_tile_size()
        inner_left = self.palette_rect.x + UI_PADDING
        inner_top = self.palette_rect.y + UI_PADDING

        for row in range(self.tileset.rows):
            for column in range(self.tileset.columns):
                coord = (column, row)
                cell_rect = pygame.Rect(
                    inner_left + column * (tile_size + PALETTE_GAP),
                    inner_top + row * (tile_size + PALETTE_GAP) - self.palette_scroll,
                    tile_size,
                    tile_size,
                )
                if (
                    cell_rect.bottom < self.palette_rect.top
                    or cell_rect.top > self.palette_rect.bottom
                ):
                    continue

                pygame.draw.rect(self.screen, PANEL_COLOR, cell_rect)
                tile_surface = self._get_palette_tile_surface(coord, tile_size)
                if tile_surface is not None:
                    self.screen.blit(tile_surface, cell_rect.topleft)
                pygame.draw.rect(self.screen, MAP_GRID_COLOR, cell_rect, width=1)

        highlight = self._current_tileset_highlight_bounds()
        if highlight is not None:
            left, top, right, bottom = highlight
            selection_rect = pygame.Rect(
                inner_left + left * (tile_size + PALETTE_GAP),
                inner_top + top * (tile_size + PALETTE_GAP) - self.palette_scroll,
                (right - left + 1) * tile_size,
                (bottom - top + 1) * tile_size,
            )
            pygame.draw.rect(self.screen, SELECTION_COLOR, selection_rect, width=2)

        self._draw_palette_scrollbar()
        self._draw_tileset_dropdown_overlay()

    def _draw_top_tool_bar(self) -> None:
        tools_bg = pygame.Rect(self.map_left, 0, self.map_view_width, TOP_BAR_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, tools_bg)
        pygame.draw.line(
            self.screen,
            PANEL_BORDER_COLOR,
            (self.map_left, TOP_BAR_HEIGHT),
            (self.map_left + self.map_view_width, TOP_BAR_HEIGHT),
            width=2,
        )
        self._draw_section_box(self.top_tools_section_rect, "Tools")
        self._draw_section_box(self.top_info_section_rect, "Layer / Map Info")

        self._draw_button(
            self.paint_tool_rect,
            Tool.PAINT.label,
            is_active=self.active_tool == Tool.PAINT,
        )
        self._draw_button(self.fill_background_rect, "Fill Active", is_active=False)
        self._draw_button(
            self.tileset_patch_tool_rect,
            Tool.TILESET_PATCH.label,
            is_active=self.active_tool == Tool.TILESET_PATCH,
        )
        self._draw_button(
            self.canvas_copy_tool_rect,
            Tool.CANVAS_SELECT.label,
            is_active=self.active_tool == Tool.CANVAS_SELECT,
        )
        self._draw_button(
            self.paste_tool_rect,
            Tool.PASTE.label,
            is_active=self.active_tool == Tool.PASTE,
        )
        self._draw_button(
            self.block_tool_rect,
            Tool.BLOCK.label,
            is_active=self.active_tool == Tool.BLOCK,
        )

        map_size_label = self.label_font.render("Map W x H", True, TEXT_COLOR)
        self.screen.blit(map_size_label, (self.map_left + 16, 78))

        self._draw_input_field(
            self.map_width_input_rect,
            self.map_width_text,
            self.active_input == "map_width",
            align_right=False,
        )
        x_label = self.small_font.render("x", True, TEXT_COLOR)
        self.screen.blit(x_label, (self.map_width_input_rect.right + 9, 87))
        self._draw_input_field(
            self.map_height_input_rect,
            self.map_height_text,
            self.active_input == "map_height",
            align_right=False,
        )
        self._draw_button(self.apply_map_size_rect, "Apply Size", is_active=False)

        brush_text = f"Brush: {self.active_brush.width}x{self.active_brush.height}"
        brush_surface = self.small_font.render(brush_text, True, TEXT_COLOR)
        self.screen.blit(brush_surface, (self.map_left + 392, 78))

        if self.clipboard_patch is None:
            clipboard_text = "Clipboard: empty"
        else:
            clipboard_text = (
                f"Clipboard: {self.clipboard_patch.width}x{self.clipboard_patch.height}"
            )
        clipboard_surface = self.small_font.render(clipboard_text, True, TEXT_COLOR)
        self.screen.blit(clipboard_surface, (self.map_left + 552, 78))

        blocked_count = self.blocking_grid.blocked_count()
        blocked_surface = self.small_font.render(f"Blocked: {blocked_count}", True, TEXT_COLOR)
        blocked_x = self.map_left + self.map_view_width - blocked_surface.get_width() - 18
        self.screen.blit(blocked_surface, (blocked_x, 78))

        active_tileset_name = Path(self.active_layer.tileset_path).name or "<none>"
        active_text = (
            f"Active layer: {self.active_layer.name} (order {self.active_layer.layer_order}) | "
            f"tileset: {active_tileset_name} | size: {self.map_grid.columns}x{self.map_grid.rows}"
        )
        active_surface = self.small_font.render(
            self._fit_text_to_width(active_text, self.map_view_width - 32),
            True,
            TEXT_COLOR,
        )
        self.screen.blit(active_surface, (self.map_left + 16, 122))

        if self.last_saved_layer_path is None:
            last_save_text = "Last save (default BG): none yet"
        else:
            display_path = self._path_for_display(self.last_saved_layer_path)
            last_save_text = f"Last save (default BG): {display_path}"
        last_save_surface = self.small_font.render(
            self._fit_text_to_width(last_save_text, self.map_view_width - 32),
            True,
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(last_save_surface, (self.map_left + 16, 148))

        bg_names = ", ".join(layer.layer_data.name for layer in self.background_layers)
        if not bg_names:
            bg_text = "Background layers: none"
        else:
            bg_text = f"Background layers ({len(self.background_layers)}): {bg_names}"
        bg_surface = self.small_font.render(
            self._fit_text_to_width(bg_text, self.map_view_width - 32),
            True,
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(bg_surface, (self.map_left + 16, 174))

    def _draw_map_canvas(self) -> None:
        map_bg_rect = self.map_rect.inflate(4, 4)
        pygame.draw.rect(self.screen, PANEL_BORDER_COLOR, map_bg_rect)
        pygame.draw.rect(self.screen, INPUT_BG_COLOR, self.map_rect)

        visible_columns = self._visible_map_columns()
        visible_rows = self._visible_map_rows()

        for view_row in range(visible_rows):
            for view_column in range(visible_columns):
                map_column = self.map_view_column_offset + view_column
                map_row = self.map_view_row_offset + view_row

                cell_rect = pygame.Rect(
                    self.map_rect.x + view_column * MAP_CELL_SIZE,
                    self.map_rect.y + view_row * MAP_CELL_SIZE,
                    MAP_CELL_SIZE,
                    MAP_CELL_SIZE,
                )

                if not self.map_grid.in_bounds(map_column, map_row):
                    pygame.draw.rect(self.screen, OUT_OF_BOUNDS_CELL, cell_rect)
                    pygame.draw.rect(self.screen, MAP_GRID_COLOR, cell_rect, width=1)
                    continue

                checker_color = CHECKER_LIGHT if (map_column + map_row) % 2 == 0 else CHECKER_DARK
                pygame.draw.rect(self.screen, checker_color, cell_rect)

                for layer in self.background_layers:
                    if not layer.layer_data.map_grid.in_bounds(map_column, map_row):
                        continue
                    bg_coord = layer.layer_data.map_grid.get(map_column, map_row)
                    if bg_coord is None:
                        continue
                    bg_surface = layer.tile_cache.get(bg_coord)
                    if bg_surface is not None:
                        self.screen.blit(bg_surface, cell_rect.topleft)

                active_coord = self.map_grid.get(map_column, map_row)
                if active_coord is not None:
                    active_surface = self.map_tile_cache.get(active_coord)
                    if active_surface is not None:
                        self.screen.blit(active_surface, cell_rect.topleft)

                if self.blocking_grid.get(map_column, map_row):
                    self.screen.blit(self.blocking_overlay_surface, cell_rect.topleft)

                pygame.draw.rect(self.screen, MAP_GRID_COLOR, cell_rect, width=1)

        if self.canvas_selection_bounds is not None:
            self._draw_map_selection_box(self.canvas_selection_bounds, CANVAS_SELECTION_COLOR)

        if self.canvas_selecting and self.canvas_selection_anchor and self.canvas_selection_current:
            live_bounds = self._normalize_bounds(
                self.canvas_selection_anchor,
                self.canvas_selection_current,
            )
            self._draw_map_selection_box(live_bounds, CLIPBOARD_COLOR)

    def _draw_map_selection_box(
        self,
        bounds: tuple[int, int, int, int],
        color: tuple[int, int, int],
    ) -> None:
        left, top, right, bottom = bounds

        visible_left = self.map_view_column_offset
        visible_top = self.map_view_row_offset
        visible_right = min(
            self.map_grid.columns - 1,
            self.map_view_column_offset + self._visible_map_columns() - 1,
        )
        visible_bottom = min(
            self.map_grid.rows - 1,
            self.map_view_row_offset + self._visible_map_rows() - 1,
        )

        draw_left = max(left, visible_left)
        draw_top = max(top, visible_top)
        draw_right = min(right, visible_right)
        draw_bottom = min(bottom, visible_bottom)

        if draw_left > draw_right or draw_top > draw_bottom:
            return

        rect = pygame.Rect(
            self.map_rect.x + (draw_left - self.map_view_column_offset) * MAP_CELL_SIZE,
            self.map_rect.y + (draw_top - self.map_view_row_offset) * MAP_CELL_SIZE,
            (draw_right - draw_left + 1) * MAP_CELL_SIZE,
            (draw_bottom - draw_top + 1) * MAP_CELL_SIZE,
        )
        pygame.draw.rect(self.screen, color, rect, width=2)

    def _draw_palette_scrollbar(self) -> None:
        if self.tileset is None:
            return

        max_scroll = self._max_palette_scroll()
        if max_scroll <= 0:
            return

        track = pygame.Rect(
            self.palette_rect.right - 8,
            self.palette_rect.y + 4,
            5,
            self.palette_rect.height - 8,
        )
        pygame.draw.rect(self.screen, PANEL_BORDER_COLOR, track, border_radius=3)

        visible_ratio = self.palette_rect.height / (self.palette_rect.height + max_scroll)
        thumb_height = max(24, int(track.height * visible_ratio))
        travel = max(1, track.height - thumb_height)
        thumb_y = track.y + int((self.palette_scroll / max_scroll) * travel)
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_height)
        pygame.draw.rect(self.screen, BUTTON_COLOR, thumb, border_radius=3)

    def _draw_button(self, rect: pygame.Rect, text: str, *, is_active: bool) -> None:
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        color = BUTTON_ACTIVE_COLOR if is_active else BUTTON_COLOR
        if hovered and not is_active:
            color = BUTTON_HOVER_COLOR

        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, PANEL_BORDER_COLOR, rect, width=1, border_radius=5)
        label = self.small_font.render(text, True, BUTTON_TEXT_COLOR)
        self.screen.blit(
            label,
            (
                rect.x + (rect.width - label.get_width()) // 2,
                rect.y + (rect.height - label.get_height()) // 2,
            ),
        )

    def _draw_section_box(self, rect: pygame.Rect, title: str) -> None:
        pygame.draw.rect(self.screen, SECTION_BG_COLOR, rect, border_radius=6)
        pygame.draw.rect(self.screen, SECTION_BORDER_COLOR, rect, width=1, border_radius=6)
        title_surface = self.label_font.render(title, True, TEXT_COLOR)
        title_x = rect.x + 10
        title_y = rect.y - 8
        title_bg = pygame.Rect(
            title_x - 4,
            title_y - 1,
            title_surface.get_width() + 8,
            title_surface.get_height() + 2,
        )
        pygame.draw.rect(self.screen, PANEL_COLOR, title_bg, border_radius=4)
        self.screen.blit(title_surface, (title_x, title_y))

    def _draw_tileset_dropdown(self) -> None:
        label_surface = self.label_font.render("Tileset", True, TEXT_COLOR)
        self.screen.blit(
            label_surface,
            (self.tileset_dropdown_rect.x, self.tileset_dropdown_rect.y - 13),
        )

        pygame.draw.rect(self.screen, INPUT_BG_COLOR, self.tileset_dropdown_rect)
        border_color = (
            INPUT_ACTIVE_BORDER_COLOR if self.tileset_dropdown_open else INPUT_BORDER_COLOR
        )
        pygame.draw.rect(self.screen, border_color, self.tileset_dropdown_rect, width=2)

        selected_label = self._selected_tileset_label()
        clipped = self._fit_text_to_width(selected_label, self.tileset_dropdown_rect.width - 26)
        text_surface = self.small_font.render(clipped, True, TEXT_COLOR)
        text_y = (
            self.tileset_dropdown_rect.y
            + (self.tileset_dropdown_rect.height - text_surface.get_height()) // 2
        )
        self.screen.blit(text_surface, (self.tileset_dropdown_rect.x + 5, text_y))

        arrow = "v" if not self.tileset_dropdown_open else "^"
        arrow_surface = self.small_font.render(arrow, True, MUTED_TEXT_COLOR)
        self.screen.blit(
            arrow_surface,
            (
                self.tileset_dropdown_rect.right - 14,
                self.tileset_dropdown_rect.y
                + (self.tileset_dropdown_rect.height - arrow_surface.get_height()) // 2,
            ),
        )

        self._draw_button(self.tileset_refresh_rect, "Refresh", is_active=False)

    def _draw_tileset_dropdown_overlay(self) -> None:
        list_rect = self._tileset_dropdown_list_rect()
        if list_rect is None:
            return

        pygame.draw.rect(self.screen, INPUT_BG_COLOR, list_rect)
        pygame.draw.rect(self.screen, INPUT_ACTIVE_BORDER_COLOR, list_rect, width=2)

        mouse_position = pygame.mouse.get_pos()
        start = self.tileset_dropdown_scroll
        end = min(
            len(self.available_tilesets),
            start + self._tileset_dropdown_visible_count(),
        )
        for index in range(start, end):
            row = index - start
            item_rect = pygame.Rect(
                list_rect.x + 1,
                list_rect.y + row * self.tileset_dropdown_item_height + 1,
                list_rect.width - 2,
                self.tileset_dropdown_item_height,
            )

            if index == self.selected_tileset_index:
                pygame.draw.rect(self.screen, BUTTON_ACTIVE_COLOR, item_rect)
            elif item_rect.collidepoint(mouse_position):
                pygame.draw.rect(self.screen, BUTTON_HOVER_COLOR, item_rect)

            item_label = self._fit_text_to_width(
                self._tileset_label_for_path(self.available_tilesets[index]),
                item_rect.width - 8,
            )
            item_surface = self.small_font.render(item_label, True, BUTTON_TEXT_COLOR)
            self.screen.blit(
                item_surface,
                (
                    item_rect.x + 4,
                    item_rect.y + (item_rect.height - item_surface.get_height()) // 2,
                ),
            )

    def _draw_labeled_input(
        self,
        label: str,
        rect: pygame.Rect,
        value: str,
        is_active: bool,
        *,
        align_right: bool = False,
    ) -> None:
        label_surface = self.label_font.render(label, True, TEXT_COLOR)
        self.screen.blit(label_surface, (rect.x, rect.y - 13))
        self._draw_input_field(rect, value, is_active, align_right=align_right)

    def _draw_input_field(
        self,
        rect: pygame.Rect,
        value: str,
        is_active: bool,
        *,
        align_right: bool,
    ) -> None:
        pygame.draw.rect(self.screen, INPUT_BG_COLOR, rect)
        border_color = INPUT_ACTIVE_BORDER_COLOR if is_active else INPUT_BORDER_COLOR
        pygame.draw.rect(self.screen, border_color, rect, width=2)

        clipped_value = self._fit_text_to_width(value, rect.width - 10)
        text_surface = self.small_font.render(clipped_value, True, TEXT_COLOR)
        x_pos = rect.x + 5
        if align_right and text_surface.get_width() < rect.width - 10:
            x_pos = rect.right - text_surface.get_width() - 5
        y_pos = rect.y + (rect.height - text_surface.get_height()) // 2
        self.screen.blit(text_surface, (x_pos, y_pos))

    def _normalize_bounds(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        return (
            min(start[0], end[0]),
            min(start[1], end[1]),
            max(start[0], end[0]),
            max(start[1], end[1]),
        )

    def _visible_map_columns(self) -> int:
        return max(1, self.map_rect.width // MAP_CELL_SIZE)

    def _visible_map_rows(self) -> int:
        return max(1, self.map_rect.height // MAP_CELL_SIZE)

    def _max_map_view_column_offset(self) -> int:
        return max(0, self.map_grid.columns - self._visible_map_columns())

    def _max_map_view_row_offset(self) -> int:
        return max(0, self.map_grid.rows - self._visible_map_rows())

    def _clamp_map_view_offsets(self) -> None:
        self.map_view_column_offset = max(
            0,
            min(self.map_view_column_offset, self._max_map_view_column_offset()),
        )
        self.map_view_row_offset = max(
            0,
            min(self.map_view_row_offset, self._max_map_view_row_offset()),
        )

    def _pan_map(self, delta_columns: int, delta_rows: int) -> None:
        self.map_view_column_offset += delta_columns
        self.map_view_row_offset += delta_rows
        self._clamp_map_view_offsets()

    def _input_name_at_position(self, position: tuple[int, int]) -> str | None:
        if self.tile_size_input_rect.collidepoint(position):
            return "tile_size"
        if self.output_path_input_rect.collidepoint(position):
            return "output_path"
        if self.layer_file_path_input_rect.collidepoint(position):
            return "layer_file_path"
        if self.map_width_input_rect.collidepoint(position):
            return "map_width"
        if self.map_height_input_rect.collidepoint(position):
            return "map_height"
        return None

    def _get_input_value(self, input_name: str) -> str:
        if input_name == "tile_size":
            return self.tile_size_text
        if input_name == "output_path":
            return self.output_path_text
        if input_name == "layer_file_path":
            return self.layer_file_path_text
        if input_name == "map_width":
            return self.map_width_text
        if input_name == "map_height":
            return self.map_height_text
        return ""

    def _set_input_value(self, input_name: str, value: str) -> None:
        if input_name == "tile_size":
            self.tile_size_text = value
        elif input_name == "output_path":
            self.output_path_text = value
        elif input_name == "layer_file_path":
            self.layer_file_path_text = value
        elif input_name == "map_width":
            self.map_width_text = value
        elif input_name == "map_height":
            self.map_height_text = value

    def _refresh_tileset_options(self, *, preserve_selection: bool) -> None:
        previous_path = self._selected_tileset_path() if preserve_selection else None
        discovered = discover_tilesets(self.tileset_root)
        self.available_tilesets = discovered
        self.selected_tileset_index = None
        self.tileset_dropdown_scroll = 0

        preferred_paths: list[Path] = []
        if previous_path is not None:
            preferred_paths.append(previous_path.resolve())
        if self.active_layer.tileset_path:
            preferred_paths.append(self._resolve_path_for_read(self.active_layer.tileset_path))
        preferred_paths.append((self.tileset_root / "tf_A5_ashlands_2.png").resolve())

        for path in preferred_paths:
            if self._select_tileset_path(path, add_if_missing=False):
                return

        if self.available_tilesets:
            self.selected_tileset_index = 0

    def _selected_tileset_path(self) -> Path | None:
        if self.selected_tileset_index is None:
            return None
        if self.selected_tileset_index < 0:
            return None
        if self.selected_tileset_index >= len(self.available_tilesets):
            return None
        return self.available_tilesets[self.selected_tileset_index]

    def _select_tileset_path(self, path: Path, *, add_if_missing: bool) -> bool:
        resolved_path = path.resolve()
        for index, available in enumerate(self.available_tilesets):
            if available == resolved_path:
                self.selected_tileset_index = index
                return True

        if add_if_missing:
            self.available_tilesets.append(resolved_path)
            self.available_tilesets.sort(key=lambda p: str(p).lower())
            for index, available in enumerate(self.available_tilesets):
                if available == resolved_path:
                    self.selected_tileset_index = index
                    return True

        return False

    def _tileset_label_for_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return str(path)

    def _selected_tileset_label(self) -> str:
        selected_path = self._selected_tileset_path()
        if selected_path is not None:
            return self._tileset_label_for_path(selected_path)
        if self.available_tilesets:
            return "Choose tileset..."
        return f"No tilesets in {self.tileset_root}"

    def _tileset_dropdown_visible_count(self) -> int:
        if not self.available_tilesets:
            return 0
        return min(self.tileset_dropdown_max_visible, len(self.available_tilesets))

    def _max_tileset_dropdown_scroll(self) -> int:
        visible_count = self._tileset_dropdown_visible_count()
        if visible_count <= 0:
            return 0
        return max(0, len(self.available_tilesets) - visible_count)

    def _tileset_dropdown_list_rect(self) -> pygame.Rect | None:
        if not self.tileset_dropdown_open or not self.available_tilesets:
            return None

        visible_count = self._tileset_dropdown_visible_count()
        return pygame.Rect(
            self.tileset_dropdown_rect.x,
            self.tileset_dropdown_rect.bottom + 2,
            self.tileset_dropdown_rect.width,
            visible_count * self.tileset_dropdown_item_height + 2,
        )

    def _tileset_option_index_at_position(self, position: tuple[int, int]) -> int | None:
        list_rect = self._tileset_dropdown_list_rect()
        if list_rect is None or not list_rect.collidepoint(position):
            return None

        local_y = position[1] - list_rect.y - 1
        if local_y < 0:
            return None
        row = local_y // self.tileset_dropdown_item_height
        index = self.tileset_dropdown_scroll + row
        if index < 0 or index >= len(self.available_tilesets):
            return None
        return index

    def _parse_positive_int(
        self,
        value: str,
        *,
        minimum: int,
        maximum: int,
    ) -> int | None:
        if not value or not value.isdigit():
            return None
        parsed = int(value)
        if parsed < minimum or parsed > maximum:
            return None
        return parsed

    def _normalize_user_path(self, raw_path: str) -> str:
        path_text = raw_path.strip()
        if len(path_text) >= 2 and path_text[0] == path_text[-1] and path_text[0] in {'"', "'"}:
            path_text = path_text[1:-1]
        return path_text

    def _resolve_path_for_read(self, path_text: str, *, base_dir: Path | None = None) -> Path:
        candidate = Path(path_text).expanduser()
        if candidate.is_absolute():
            return candidate

        if base_dir is not None:
            base_candidate = (base_dir / candidate).expanduser()
            if base_candidate.exists():
                return base_candidate.resolve()

        return (Path.cwd() / candidate).resolve()

    def _resolve_output_path(self, path_text: str) -> Path:
        output_path = Path(path_text).expanduser()
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()
        if output_path.suffix == "":
            output_path = output_path.with_suffix(".py")
        return output_path

    def _path_for_export(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            return resolved.relative_to(Path.cwd())
        except ValueError:
            return resolved

    def _path_for_display(self, path: Path) -> Path:
        return self._path_for_export(path)

    def _resolve_tileset_path_from_layer(self, tileset_path: str, layer_path: Path) -> Path:
        return self._resolve_path_for_read(tileset_path, base_dir=layer_path.parent)

    def _fit_text_to_width(
        self,
        value: str,
        width: int,
        *,
        font: pygame.font.Font | None = None,
    ) -> str:
        target_font = self.small_font if font is None else font
        if target_font.size(value)[0] <= width:
            return value

        prefix = "..."
        trimmed = value
        while trimmed and target_font.size(prefix + trimmed)[0] > width:
            trimmed = trimmed[1:]
        return prefix + trimmed

    def _rebuild_active_map_tile_cache(self) -> None:
        self.map_tile_cache.clear()
        if self.tileset is None:
            return
        self.map_tile_cache.update(self._build_tile_cache(self.tileset, alpha=None))

    def _build_tile_cache(
        self,
        tileset: Tileset,
        *,
        alpha: int | None,
    ) -> dict[TileCoord, pygame.Surface]:
        cache: dict[TileCoord, pygame.Surface] = {}
        for tile in tileset.tiles:
            surface = tile.surface
            if surface.get_width() == MAP_CELL_SIZE and surface.get_height() == MAP_CELL_SIZE:
                scaled = surface.copy()
            else:
                # Use nearest-neighbor scaling to keep pixel-art tiles crisp.
                scaled = pygame.transform.scale(surface, (MAP_CELL_SIZE, MAP_CELL_SIZE))
            if alpha is not None:
                scaled.set_alpha(alpha)
            cache[tile.coord] = scaled
        return cache

    def _create_blocking_overlay_surface(self) -> pygame.Surface:
        overlay = pygame.Surface((MAP_CELL_SIZE, MAP_CELL_SIZE), pygame.SRCALPHA)
        overlay.fill(BLOCKING_OVERLAY_FILL)
        pygame.draw.line(
            overlay,
            BLOCKING_OVERLAY_LINE,
            (2, 2),
            (MAP_CELL_SIZE - 3, MAP_CELL_SIZE - 3),
            width=2,
        )
        pygame.draw.line(
            overlay,
            BLOCKING_OVERLAY_LINE,
            (MAP_CELL_SIZE - 3, 2),
            (2, MAP_CELL_SIZE - 3),
            width=2,
        )
        return overlay

    def _get_or_load_tileset(self, path: Path, tile_size: int) -> Tileset:
        key = (str(path), tile_size)
        cached = self.tileset_cache.get(key)
        if cached is not None:
            return cached

        loaded = Tileset.load(path, tile_size)
        self.tileset_cache[key] = loaded
        return loaded

    def _get_palette_tile_surface(self, coord: TileCoord, tile_size: int) -> pygame.Surface | None:
        if self.tileset is None:
            return None

        cache_key = (coord, tile_size)
        cached = self.palette_tile_cache.get(cache_key)
        if cached is not None:
            return cached

        source = self.tileset.get_tile_surface(coord)
        if source is None:
            return None

        if source.get_width() == tile_size and source.get_height() == tile_size:
            scaled = source.copy()
        else:
            # Keep tiles sharp by using nearest-neighbor scaling for palette previews.
            scaled = pygame.transform.scale(source, (tile_size, tile_size))

        self.palette_tile_cache[cache_key] = scaled
        return scaled

    def _palette_tile_size(self) -> int:
        if self.tileset is None:
            return PALETTE_MAX_TILE_SIZE

        available_width = self.palette_rect.width - (UI_PADDING * 2)
        if self.tileset.columns <= 0:
            return PALETTE_MAX_TILE_SIZE

        max_size = max(1, available_width // self.tileset.columns)
        max_size = min(PALETTE_MAX_TILE_SIZE, max_size)

        base_size = self.tileset.tile_size
        if max_size >= base_size:
            factor = max(1, max_size // base_size)
            return base_size * factor

        return max(PALETTE_MIN_TILE_SIZE, max_size)

    def _max_palette_scroll(self) -> int:
        if self.tileset is None:
            return 0

        tile_size = self._palette_tile_size()
        content_height = (self.tileset.rows * (tile_size + PALETTE_GAP)) + (UI_PADDING * 2)
        return max(0, content_height - self.palette_rect.height)

    def _current_tileset_highlight_bounds(self) -> tuple[int, int, int, int] | None:
        if (
            self.tileset_selecting
            and self.tileset_selection_anchor
            and self.tileset_selection_current
        ):
            return self._normalize_bounds(
                self.tileset_selection_anchor,
                self.tileset_selection_current,
            )
        return self.tileset_patch_bounds
