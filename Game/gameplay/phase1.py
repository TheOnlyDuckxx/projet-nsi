# PHASE1.PY
# Gestion de la première phase du jeu (qui a l'origine devait en contenir 3)


# --------------- IMPORTATION DES MODULES ---------------
import pygame
import random
import heapq
import json
import hashlib
import math
import time
from typing import Any, Optional
from Game.ui.iso_render import IsoMapView, get_prop_sprite_name
from world.world_gen import BIOME_CORRUPT, load_world_params_from_preset, WorldGenerator
from Game.world.tiles import get_ground_sprite_name
from Game.species.fauna import PassiveFaunaFactory, PassiveFaunaDefinition
from Game.species.species import Espece, ROLE_CLASS_LABELS
from Game.save.save import SaveManager
from Game.core.utils import resource_path
from Game.ui.hud.bottom_hud import BottomHUD
from Game.ui.hud.game_hud import (
    draw_inspection_panel,
    draw_work_bar,
    handle_inspection_panel_click,
    inspection_panel_contains_point,
)
from Game.ui.hud.left_hud import LeftHUD
from Game.ui.hud.notification import add_notification
from Game.world.fog_of_war import FogOfWar
from Game.gameplay.craft import Craft
from Game.world.day_night import DayNightCycle
from Game.gameplay.event import EventManager
from Game.gameplay.quest_manager import QuestManager
from Game.ui.hud.draggable_window import DraggableWindow
from Game.world.weather import WEATHER_CONDITIONS, WeatherSystem
from Game.world.weather_vfx import WeatherVFXController
from Game.gameplay.tech_tree import TechTreeManager
from Game.gameplay.fauna_spawner import FaunaSpawner
from Game.gameplay.fauna_definitions import (
    fauna_definition_catalog,
    get_fauna_definition as resolve_fauna_definition,
    rabbit_definition,
)
from Game.gameplay.phase1_data import (
    collect_species_stats,
    get_prop_description_entry,
    load_prop_descriptions,
)
from Game.gameplay.phase1_combat import (
    clear_entity_combat_refs,
    combat_attack_interval,
    combat_attack_range,
    combat_damage,
    draw_fauna_health_bar,
    draw_species_health_bar,
    grant_fauna_combat_rewards,
    start_entity_combat,
    stop_entity_combat,
    update_entity_combat,
)

_WATER_BIOME_IDS = {1, 3, 4}
_AUTO_HARVESTABLE_PROP_IDS = {
    10, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 23, 29, 30, 31, 32, 33, 34,
    35, 36, 37, 38, 39, 40,
}
_SPECIES_CORPSE_PROP_ID = 150
_SPECIES_GRAVESTONE_PROP_ID = 151
_FOOD_STOCK_KEYS = ("food", "berries", "meat")
_WATER_STOCK_KEYS = ("water",)
_GARDEN_CYCLE_MINUTES = 4.0
_GARDEN_FOOD_PER_SEED = 3
_DEFAULT_CORRUPTION_CONFIG = {
    "enabled": True,
    "initial_seed_count": 5,
    "min_spawn_distance_from_player": 160,
    "tick_interval_sec": 1.5,
    "spread_attempts_per_tick": 16,
    "infection_chance": 0.35,
    "max_new_tiles_per_tick": 4,
    "speed_multiplier": 1.0,
    "clear_natural_props": True,
    "water_blocks_spread": True,
    "active_on_new_games_only": True,
}
_MINIMAP_BIOME_COLORS: dict[int, tuple[int, int, int]] = {
    1: (24, 72, 150),    # ocean
    3: (34, 92, 180),    # lake
    4: (48, 128, 212),   # river
    10: (78, 140, 70),   # plains
    11: (34, 96, 50),    # forest
    12: (24, 110, 56),   # rainforest
    13: (166, 154, 68),  # savanna
    14: (206, 180, 92),  # desert
    15: (76, 110, 80),   # taiga
    16: (170, 170, 164), # tundra
    17: (226, 230, 234), # snow
    18: (58, 92, 74),    # swamp
    19: (66, 110, 84),   # mangrove
    20: (120, 116, 110), # rock
    21: (138, 134, 126), # alpine
    22: (96, 74, 64),    # volcanic
    23: (96, 82, 126),   # mystic
    24: (132, 42, 42),   # corrupt
}


# --------------- CLASSE PRINCIPALE ---------------
class Phase1:
    """Contient la logique reliant la logique de tout les systemes pour faire fonctionner le gameplay"""

    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False

        self.view = IsoMapView(self.assets, self.screen.get_size())
        self.gen = WorldGenerator(tiles_levels=6, chunk_size=64, cache_chunks=2048)
        self.params = None
        self.world = None
        self.fog=None
        
        # Système jour/nuit
        self.day_night = DayNightCycle(cycle_duration=600)
        self.day_night.set_time(6, 0)
        self.day_night.set_speed(3.0)
        self.event_manager = EventManager()
        self.quest_manager = QuestManager(self)

        #Météo
        self.weather_system = None
        self.weather_vfx = WeatherVFXController()
        self.weather_icons: dict[str, pygame.Surface] = {}
        self._load_weather_icons()
        self.prop_descriptions = self._load_prop_descriptions()
        self.tech_tree = TechTreeManager(
            resource_path("Game/data/tech_tree.json"),
            on_unlock=self._on_tech_unlocked,
        )
        self._last_innovation_day = self.day_night.jour
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._stats_last_day = 0
        self._daily_stats: list[dict] = []
        self._stats_current_day = {}
        self._run_stats = {}
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False
        self._corruption_config = self._load_corruption_config()
        self._corruption_active = False
        self._corruption_timer = 0.0
        self._corruption_rng = random.Random()
        self._corruption_frontier: list[tuple[int, int]] = []
        self._corruption_frontier_set: set[tuple[int, int]] = set()
        self._corruption_infected_count = 0
        self._corruption_speed_multiplier = float(self._corruption_config.get("speed_multiplier", 1.0) or 1.0)
        self._corruption_dry_ticks = 0
        self.world_history: list[dict] = []
        self.class_state: dict = {"main_class": None, "chosen_day": None}
        self._tech_effects = self._default_tech_effects()
        self._tech_runtime = {"belligerant_kill_streak": 0}
        self._tech_effects_dirty = True
        self.horde_state: dict = {
            "active": False,
            "ends_at_minute": 0.0,
            "last_horde_day": -9999.0,
            "aggressive_spawn_multiplier": 3.0,
        }
        self._warehouse_gate_cache: bool | None = None
        self._warehouse_gate_probe_cd = 0.0
        self._warehouse_built_count = 0

        # entités
        self.espece = None
        self.fauna_species: Espece | None = None
        self.fauna_species_by_name = {}
        self.joueur: Optional[Espece] = None
        self.entities: list = []
        self.fauna_spawner = FaunaSpawner(resource_path("Game/data/fauna_spawns.json"))
        self._save_path: str | None = None

        # UI/HUD
        self.bottom_hud: BottomHUD | None = None
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 12)
        self.menu_button_rect = None
        self.end_run_button_rect = None
        self.achievements_button_rect = None
        self._pause_achievements_open = False
        self._pause_ach_scroll = 0
        self._pause_ach_max_scroll = 0
        self._pause_ach_back_rect = None
        self.ui_menu_open = False
        self.right_hud = LeftHUD(self)
        self.minimap_visible = False
        self._minimap_sample_size = 56
        self._minimap_world_span = 420
        self._minimap_world_span_min = 120
        self._minimap_world_span_max = 1200
        self._minimap_display_size = 220
        self._minimap_refresh_interval = 0.30
        self._minimap_refresh_cd = 0.0
        self._minimap_last_center: tuple[int, int] | None = None
        self._minimap_cache_center: tuple[int, int] | None = None
        self._minimap_base_surface: pygame.Surface | None = None
        self._minimap_scaled_surface: pygame.Surface | None = None


        # Transparence des props (activée via touche H)
        self.props_transparency_active = False

        # Sélection actuelle: ("tile",(i,j)) | ("prop",(i,j,pid)) | ("entity",ent)
        self.selected: Optional[tuple] = None
        self.selected_entities: list = []
        self.rename_active = False
        self.rename_value = ""
        self.rename_target = None
        self.rename_max_length = 20
        self.save_message = ""
        self.save_message_timer = 0.0
        self.craft_system = Craft()
        self.selected_craft = None
        self.construction_sites: dict[tuple[int, int], dict] = {}
        self.shared_harvest_jobs: dict[tuple[int, int, str], dict] = {}
        self.warehouse: dict[str, int] = {}
        self.unlocked_crafts: set[str] = set()
        self._init_craft_unlocks()
        self.info_windows: list[DraggableWindow] = []
        self.construction_assign_radius = 12.0
        self.inspect_cursor_path = resource_path("Game/assets/vfx/9.png")
        self.default_cursor_path = resource_path("Game/assets/vfx/1.png")
        self.inspect_mode_active = False

        # Gestion bonheur / décès
        self.happiness = 10.0
        self.happiness_min = -100.0
        self.happiness_max = 100.0
        self.species_death_count = 0
        self.death_event_ready = False
        self.death_response_mode: str | None = None
        self.food_reserve_capacity = 100
        self.food_target_per_individual = 3.0
        self.water_target_per_individual = 4.0
        self._food_consumption_base_per_individual_per_sec = 1.0 / 120.0
        self.food_consumption_per_individual_per_sec = float(self._food_consumption_base_per_individual_per_sec)
        self.water_consumption_per_individual_per_sec = 1.0 / 100.0
        self._group_supply_food_buffer = 0.0
        self._group_supply_water_buffer = 0.0
        self._group_supply_damage_timer = 0.0
        self._supply_cached_population = 1
        self._supply_cached_food_units_per_ind = 0.0
        self._supply_cached_water_units_per_ind = 0.0
        self._supply_cached_food_ratio = 0.0
        self._supply_cached_water_ratio = 0.0
        self._supply_cached_debuff_mult = 1.0

        # Production passive d'eau (structures)
        self._water_collector_tiles: set[tuple[int, int]] = set()
        self._water_collector_water_buffer = 0.0
        self._water_collector_probe_cd = 0.0

        # Production passive de nourriture (jardins)
        self._garden_tiles: set[tuple[int, int]] = set()
        self._garden_growth_buffer = 0.0
        self._garden_probe_cd = 0.0

        # Sources de lumière (feux de camp)
        self._campfire_tiles: set[tuple[int, int]] = set()
        self._campfire_probe_cd = 0.0

        # Repos en tanière (max 1 individu / tanière)
        self._shelter_occupants: dict[tuple[int, int], object] = {}

        # Sélection multi via clic + glisser
        self._drag_select_start: Optional[tuple[int, int]] = None
        self._drag_select_rect: Optional[pygame.Rect] = None
        self._dragging_selection = False
        self._drag_threshold = 6
        self._ui_click_blocked = False
        self._update_frame_id = 0
        self._perf_logs_enabled = True
        self._perf_slow_frame_sec = 0.12
        self._perf_trace_frames = 0

    def _perf_enter_start(self, source: str):
        now = time.perf_counter()
        if self._perf_logs_enabled:
            print(f"[Perf][Phase1] Enter source={source} | +0.000s | total 0.000s")
        return {"start": now, "last": now}

    def _perf_enter_mark(self, perf: dict, label: str):
        if not self._perf_logs_enabled:
            return
        now = time.perf_counter()
        delta = now - perf["last"]
        total = now - perf["start"]
        perf["last"] = now
        print(f"[Perf][Phase1] {label} | +{delta:.3f}s | total {total:.3f}s")

    def _perf_update_settings(self):
        settings = getattr(self.app, "settings", None)
        if settings is None:
            self._perf_logs_enabled = True
            self._perf_slow_frame_sec = 0.12
            return
        self._perf_logs_enabled = bool(settings.get("debug.perf_logs", True))
        slow_ms = settings.get("debug.perf_slow_frame_ms", 120)
        try:
            self._perf_slow_frame_sec = max(0.01, float(slow_ms) / 1000.0)
        except Exception:
            self._perf_slow_frame_sec = 0.12

    def _endgame_debug(self, msg: str):
        settings = getattr(self.app, "settings", None)
        enabled = True if settings is None else bool(settings.get("debug.endgame_logs", True))
        if not enabled:
            return
        print(f"[EndGameDebug] {msg}")

    def _normalize_corruption_config(self, raw: Any) -> dict[str, Any]:
        cfg = dict(_DEFAULT_CORRUPTION_CONFIG)
        if isinstance(raw, dict):
            for key in cfg.keys():
                if key in raw:
                    cfg[key] = raw[key]

        def _to_int(key: str, minimum: int) -> int:
            try:
                return max(minimum, int(cfg.get(key, minimum)))
            except Exception:
                return minimum

        def _to_float(key: str, minimum: float) -> float:
            try:
                return max(minimum, float(cfg.get(key, minimum)))
            except Exception:
                return minimum

        cfg["enabled"] = bool(cfg.get("enabled", True))
        cfg["initial_seed_count"] = _to_int("initial_seed_count", 0)
        cfg["min_spawn_distance_from_player"] = _to_int("min_spawn_distance_from_player", 0)
        cfg["tick_interval_sec"] = _to_float("tick_interval_sec", 0.05)
        cfg["spread_attempts_per_tick"] = _to_int("spread_attempts_per_tick", 1)
        cfg["infection_chance"] = min(1.0, max(0.0, float(cfg.get("infection_chance", 0.35) or 0.35)))
        cfg["max_new_tiles_per_tick"] = _to_int("max_new_tiles_per_tick", 1)
        cfg["speed_multiplier"] = _to_float("speed_multiplier", 0.1)
        cfg["clear_natural_props"] = bool(cfg.get("clear_natural_props", True))
        cfg["water_blocks_spread"] = bool(cfg.get("water_blocks_spread", True))
        cfg["active_on_new_games_only"] = bool(cfg.get("active_on_new_games_only", True))
        return cfg

    def _load_corruption_config(self, path: str = "Game/data/corruption.json") -> dict[str, Any]:
        raw = {}
        try:
            with open(resource_path(path), "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
        except Exception:
            raw = {}
        return self._normalize_corruption_config(raw)

    def _reset_corruption_runtime(self) -> None:
        self._corruption_active = False
        self._corruption_timer = float(self._corruption_config.get("tick_interval_sec", 1.5) or 1.5)
        seed = int(getattr(getattr(self, "world", None), "seed", 0) or 0) ^ 0xC0A512D
        self._corruption_rng = random.Random(seed)
        self._corruption_frontier = []
        self._corruption_frontier_set = set()
        self._corruption_infected_count = 0
        self._corruption_speed_multiplier = float(self._corruption_config.get("speed_multiplier", 1.0) or 1.0)
        self._corruption_dry_ticks = 0

    def disable_corruption_runtime(self) -> None:
        self._reset_corruption_runtime()
        self._corruption_active = False

    def export_corruption_state(self) -> dict[str, Any] | None:
        if getattr(self, "world", None) is None:
            return None
        return {
            "active": bool(self._corruption_active),
            "timer": float(self._corruption_timer),
            "speed_multiplier": float(self._corruption_speed_multiplier),
            "frontier": [(int(x), int(y)) for (x, y) in self._corruption_frontier],
            "infected_count": int(self._corruption_infected_count),
            "dry_ticks": int(self._corruption_dry_ticks),
            "rng_state": self._corruption_rng.getstate(),
        }

    def import_corruption_state(self, data: dict[str, Any] | None) -> None:
        self._reset_corruption_runtime()
        if not isinstance(data, dict):
            self._corruption_active = False
            return

        self._corruption_timer = max(0.0, float(data.get("timer", self._corruption_timer) or self._corruption_timer))
        self._corruption_speed_multiplier = max(
            0.1, float(data.get("speed_multiplier", self._corruption_speed_multiplier) or self._corruption_speed_multiplier)
        )
        self._corruption_infected_count = max(0, int(data.get("infected_count", 0) or 0))
        self._corruption_dry_ticks = max(0, int(data.get("dry_ticks", 0) or 0))

        frontier = data.get("frontier") or []
        for item in frontier:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            self._add_corruption_frontier(int(item[0]), int(item[1]))

        rng_state = data.get("rng_state")
        if rng_state is not None:
            try:
                self._corruption_rng.setstate(rng_state)
            except Exception:
                pass

        if self._corruption_infected_count <= 0:
            self._corruption_infected_count = self._estimate_corruption_infected_count()
        self._corruption_active = bool(data.get("active", False)) and bool(self._corruption_frontier)

    def _estimate_corruption_infected_count(self) -> int:
        world = getattr(self, "world", None)
        if world is None:
            return 0
        overrides = getattr(world, "_biome_overrides", None)
        if isinstance(overrides, dict):
            count = 0
            for bid in overrides.values():
                try:
                    if int(bid) == int(BIOME_CORRUPT):
                        count += 1
                except Exception:
                    continue
            return count
        return 0

    def _norm_world_xy(self, x: int, y: int) -> tuple[int, int]:
        world = self.world
        if world is None:
            return int(x), int(y)
        w = max(1, int(world.width))
        h = max(1, int(world.height))
        nx = int(x) % w
        ny = max(0, min(h - 1, int(y)))
        return nx, ny

    def _add_corruption_frontier(self, x: int, y: int) -> None:
        world = self.world
        if world is None:
            return
        x, y = self._norm_world_xy(x, y)
        key = (x, y)
        if key in self._corruption_frontier_set:
            return
        self._corruption_frontier_set.add(key)
        self._corruption_frontier.append(key)

    def _corruption_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        world = self.world
        if world is None:
            return []
        w = max(1, int(world.width))
        h = max(1, int(world.height))
        x = int(x) % w
        y = max(0, min(h - 1, int(y)))
        out = [((x + 1) % w, y), ((x - 1) % w, y)]
        if y > 0:
            out.append((x, y - 1))
        if y + 1 < h:
            out.append((x, y + 1))
        return out

    def _can_corrupt_tile(self, x: int, y: int) -> bool:
        world = self.world
        if world is None:
            return False
        x, y = self._norm_world_xy(x, y)
        try:
            bid = int(world.get_biome_id(x, y))
        except Exception:
            return False
        if bid == int(BIOME_CORRUPT):
            return False
        if bool(self._corruption_config.get("water_blocks_spread", True)) and bid in _WATER_BIOME_IDS:
            return False
        return True

    def _seed_corruption_for_new_world(self) -> None:
        world = self.world
        self._reset_corruption_runtime()
        if world is None:
            return
        if not bool(self._corruption_config.get("enabled", True)):
            return
        if not hasattr(world, "set_tile_corrupt"):
            return

        seed_count = max(0, int(self._corruption_config.get("initial_seed_count", 0) or 0))
        if seed_count <= 0:
            return

        try:
            spawn_x, spawn_y = world.spawn
        except Exception:
            spawn_x, spawn_y = (world.width // 2, world.height // 2)
        spawn_x, spawn_y = self._norm_world_xy(int(spawn_x), int(spawn_y))
        min_dist = max(0, int(self._corruption_config.get("min_spawn_distance_from_player", 0) or 0))
        min_dist2 = min_dist * min_dist
        clear_props = bool(self._corruption_config.get("clear_natural_props", True))

        attempts = 0
        max_attempts = max(800, seed_count * 400)
        seeded = 0
        width = int(world.width)
        height = int(world.height)
        while seeded < seed_count and attempts < max_attempts:
            attempts += 1
            x = self._corruption_rng.randrange(0, max(1, width))
            y = self._corruption_rng.randrange(0, max(1, height))
            x, y = self._norm_world_xy(x, y)

            dx = abs(x - spawn_x)
            dx = min(dx, width - dx)
            dy = abs(y - spawn_y)
            if (dx * dx + dy * dy) < min_dist2:
                continue
            if not self._can_corrupt_tile(x, y):
                continue
            try:
                ok = bool(world.set_tile_corrupt(x, y, clear_natural_props=clear_props))
            except Exception:
                ok = False
            if not ok:
                continue
            self._add_corruption_frontier(x, y)
            seeded += 1
            self._corruption_infected_count += 1

        self._corruption_active = bool(self._corruption_frontier)

    def _run_corruption_tick(self) -> None:
        world = self.world
        if world is None or not self._corruption_active or not self._corruption_frontier:
            self._corruption_active = False
            return

        chance = min(1.0, max(0.0, float(self._corruption_config.get("infection_chance", 0.35) or 0.35)))
        if chance <= 0.0:
            return
        clear_props = bool(self._corruption_config.get("clear_natural_props", True))
        speed = max(0.1, float(self._corruption_speed_multiplier or 1.0))
        attempts = max(1, int(round(float(self._corruption_config.get("spread_attempts_per_tick", 16) or 16) * speed)))
        max_new = max(1, int(round(float(self._corruption_config.get("max_new_tiles_per_tick", 4) or 4) * speed)))

        new_tiles = 0
        for _ in range(attempts):
            if new_tiles >= max_new or not self._corruption_frontier:
                break
            sx, sy = self._corruption_rng.choice(self._corruption_frontier)
            neighbors = self._corruption_neighbors(sx, sy)
            self._corruption_rng.shuffle(neighbors)
            for nx, ny in neighbors:
                if not self._can_corrupt_tile(nx, ny):
                    continue
                if self._corruption_rng.random() > chance:
                    continue
                try:
                    ok = bool(world.set_tile_corrupt(nx, ny, clear_natural_props=clear_props))
                except Exception:
                    ok = False
                if not ok:
                    continue
                self._add_corruption_frontier(nx, ny)
                self._corruption_infected_count += 1
                new_tiles += 1
                break

        if new_tiles > 0:
            self._corruption_dry_ticks = 0
            return

        self._corruption_dry_ticks += 1
        if self._corruption_dry_ticks < 30:
            return

        has_targets = False
        probe_count = min(64, len(self._corruption_frontier))
        for _ in range(probe_count):
            sx, sy = self._corruption_rng.choice(self._corruption_frontier)
            for nx, ny in self._corruption_neighbors(sx, sy):
                if self._can_corrupt_tile(nx, ny):
                    has_targets = True
                    break
            if has_targets:
                break
        if not has_targets:
            self._corruption_active = False

    def _update_corruption(self, dt: float) -> None:
        if not self._corruption_active:
            return
        interval = max(0.05, float(self._corruption_config.get("tick_interval_sec", 1.5) or 1.5))
        self._corruption_timer -= float(dt)
        ticks = 0
        while self._corruption_timer <= 0.0 and ticks < 8 and self._corruption_active:
            self._corruption_timer += interval
            self._run_corruption_tick()
            ticks += 1

    def _reset_session_state(self):
        """
        Réinitialise tout l'état de la phase afin d'éviter qu'une partie
        précédente ne pollue la suivante (ex : retour menu → nouvelle partie).
        """
        self.paused = False
        self.ui_menu_open = False
        self.world = None
        self.params = None
        self.fog = None

        # Données de progression / entités
        self.espece = None
        self.fauna_species = None
        self.fauna_species_by_name = {}
        self.joueur = None
        self.joueur2 = None
        self.entities = []
        if hasattr(self, "fauna_spawner") and self.fauna_spawner is not None:
            self.fauna_spawner.reset()
        self._save_path = None
        self.warehouse = {}
        self.construction_sites = {}
        self.shared_harvest_jobs = {}
        self.selected = None
        self.selected_entities = []
        self.selected_craft = None
        self.info_windows = []
        self.unlocked_crafts = set()

        # UI / interactions
        self.save_message = ""
        self.save_message_timer = 0.0
        self.menu_button_rect = None
        self.end_run_button_rect = None
        self.achievements_button_rect = None
        self._pause_achievements_open = False
        self._pause_ach_scroll = 0
        self._pause_ach_max_scroll = 0
        self._pause_ach_back_rect = None
        self.inspect_mode_active = False
        self.props_transparency_active = False
        self._drag_select_start = None
        self._drag_select_rect = None
        self._dragging_selection = False
        self._ui_click_blocked = False
        self._update_frame_id = 0

        # Systèmes à remettre à zéro
        self.day_night = DayNightCycle(cycle_duration=600)
        self.day_night.set_time(6, 0)
        self.day_night.set_speed(3.0)
        self.event_manager = EventManager()
        self.quest_manager = QuestManager(self)
        self.right_hud = LeftHUD(self)
        self.bottom_hud = None
        self._set_cursor(self.default_cursor_path)
        self._init_craft_unlocks()
        self.world_history = []
        self.class_state = {"main_class": None, "chosen_day": None}
        self._tech_effects = self._default_tech_effects()
        self._tech_runtime = {"belligerant_kill_streak": 0}
        self._tech_effects_dirty = True
        self.horde_state = {
            "active": False,
            "ends_at_minute": 0.0,
            "last_horde_day": -9999.0,
            "aggressive_spawn_multiplier": 3.0,
        }
        self._warehouse_gate_cache = None
        self._warehouse_gate_probe_cd = 0.0
        self._warehouse_built_count = 0
        self.happiness = 10.0
        self.happiness_min = -100.0
        self.happiness_max = 100.0
        self.species_death_count = 0
        self.death_event_ready = False
        self.death_response_mode = None
        self.food_reserve_capacity = 100
        self.food_target_per_individual = 3.0
        self.water_target_per_individual = 4.0
        self._food_consumption_base_per_individual_per_sec = 1.0 / 120.0
        self.food_consumption_per_individual_per_sec = float(self._food_consumption_base_per_individual_per_sec)
        self.water_consumption_per_individual_per_sec = 1.0 / 100.0
        self._group_supply_food_buffer = 0.0
        self._group_supply_water_buffer = 0.0
        self._group_supply_damage_timer = 0.0
        self._supply_cached_population = 1
        self._supply_cached_food_units_per_ind = 0.0
        self._supply_cached_water_units_per_ind = 0.0
        self._supply_cached_food_ratio = 0.0
        self._supply_cached_water_ratio = 0.0
        self._supply_cached_debuff_mult = 1.0
        self._water_collector_tiles = set()
        self._water_collector_water_buffer = 0.0
        self._water_collector_probe_cd = 0.0
        self._garden_tiles = set()
        self._garden_growth_buffer = 0.0
        self._garden_probe_cd = 0.0
        self._campfire_tiles = set()
        self._campfire_probe_cd = 0.0
        self.weather_system = None
        if self.weather_vfx:
            self.weather_vfx.reset()
        self.tech_tree = TechTreeManager(
            resource_path("Game/data/tech_tree.json"),
            on_unlock=self._on_tech_unlocked,
        )
        self._last_innovation_day = self.day_night.jour
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False
        self._corruption_config = self._load_corruption_config()
        self._reset_corruption_runtime()
        self.minimap_visible = False
        self._minimap_refresh_cd = 0.0
        self._minimap_last_center = None
        self._minimap_cache_center = None
        self._minimap_base_surface = None
        self._minimap_scaled_surface = None

        self._stats_last_day = int(getattr(self.day_night, "jour", 0) or 0)
        self._daily_stats = []
        self._stats_current_day = {
            "animals_killed": 0,
            "resources_collected": 0,
            "births": 0,
            "deaths": 0,
            "population_start": 0,
            "population_end": 0,
        }
        self._run_stats = {
            "animals_killed": 0,
            "resources_by_type": {},
            "total_population": 0,
            "max_population": 0,
            "max_innovation": 0,
        }

    def _bootstrap_run_statistics(self):
        pop = max(0, int(getattr(self.espece, "population", 0) or 0))
        if pop <= 0:
            pop = self._count_living_species_members()
        self._stats_last_day = int(getattr(self.day_night, "jour", 0) or 0)
        self._stats_current_day["population_start"] = max(0, pop)
        self._stats_current_day["population_end"] = max(0, pop)

        if int(self._run_stats.get("total_population", 0) or 0) <= 0:
            self._run_stats["total_population"] = max(0, pop)
        self._run_stats["max_population"] = max(
            int(self._run_stats.get("max_population", 0) or 0),
            max(0, pop),
        )
        current_innov = int(getattr(getattr(self, "tech_tree", None), "innovations", 0) or 0)
        self._run_stats["max_innovation"] = max(
            int(self._run_stats.get("max_innovation", 0) or 0),
            current_innov,
        )

    def _normalize_statistics_state(self):
        run_defaults = {
            "animals_killed": 0,
            "resources_by_type": {},
            "total_population": 0,
            "max_population": 0,
            "max_innovation": 0,
        }
        cur_defaults = {
            "animals_killed": 0,
            "resources_collected": 0,
            "births": 0,
            "deaths": 0,
            "population_start": 0,
            "population_end": 0,
        }

        src_run = dict(getattr(self, "_run_stats", {}) or {})
        self._run_stats = {}
        for key, default in run_defaults.items():
            val = src_run.get(key, default)
            if isinstance(default, dict):
                self._run_stats[key] = dict(val or {})
            else:
                try:
                    self._run_stats[key] = int(val or 0)
                except Exception:
                    self._run_stats[key] = int(default)

        src_cur = dict(getattr(self, "_stats_current_day", {}) or {})
        self._stats_current_day = {}
        for key, default in cur_defaults.items():
            try:
                self._stats_current_day[key] = int(src_cur.get(key, default) or 0)
            except Exception:
                self._stats_current_day[key] = int(default)

        normalized_daily = []
        for row in list(getattr(self, "_daily_stats", []) or []):
            if not isinstance(row, dict):
                continue
            try:
                day = int(row.get("day", 0) or 0)
            except Exception:
                day = 0
            births = int(row.get("births", 0) or 0)
            deaths = int(row.get("deaths", 0) or 0)
            population = int(row.get("population", 0) or 0)
            animals = int(row.get("animals_killed", 0) or 0)
            resources = int(row.get("resources_collected", 0) or 0)
            baseline = max(1, int(row.get("population_start", population) or population))
            birth_rate = float(row.get("birth_rate", births / baseline) or births / baseline)
            death_rate = float(row.get("death_rate", deaths / baseline) or deaths / baseline)
            normalized_daily.append(
                {
                    "day": day,
                    "animals_killed": max(0, animals),
                    "resources_collected": max(0, resources),
                    "population": max(0, population),
                    "births": max(0, births),
                    "deaths": max(0, deaths),
                    "birth_rate": max(0.0, birth_rate),
                    "death_rate": max(0.0, death_rate),
                }
            )
        normalized_daily.sort(key=lambda d: int(d.get("day", 0)))
        self._daily_stats = normalized_daily
        try:
            self._stats_last_day = int(getattr(self, "_stats_last_day", 0) or 0)
        except Exception:
            self._stats_last_day = 0

    def _flush_daily_stats(self, target_day: int, include_partial: bool = False):
        current_day = int(getattr(self.day_night, "jour", 0) or 0)
        if target_day < self._stats_last_day:
            self._stats_last_day = target_day

        while self._stats_last_day < target_day:
            pop_end = max(0, int(getattr(self.espece, "population", 0) or 0))
            if pop_end <= 0:
                pop_end = self._count_living_species_members()
            pop_start = max(0, int(self._stats_current_day.get("population_start", pop_end) or pop_end))
            births = max(0, int(self._stats_current_day.get("births", 0) or 0))
            deaths = max(0, int(self._stats_current_day.get("deaths", 0) or 0))
            baseline = max(1, pop_start)
            self._daily_stats.append(
                {
                    "day": int(self._stats_last_day),
                    "animals_killed": max(0, int(self._stats_current_day.get("animals_killed", 0) or 0)),
                    "resources_collected": max(0, int(self._stats_current_day.get("resources_collected", 0) or 0)),
                    "population": pop_end,
                    "births": births,
                    "deaths": deaths,
                    "birth_rate": births / baseline,
                    "death_rate": deaths / baseline,
                }
            )
            self._stats_last_day += 1
            self._stats_current_day = {
                "animals_killed": 0,
                "resources_collected": 0,
                "births": 0,
                "deaths": 0,
                "population_start": pop_end,
                "population_end": pop_end,
            }

        if include_partial:
            pop_end = max(0, int(getattr(self.espece, "population", 0) or 0))
            if pop_end <= 0:
                pop_end = self._count_living_species_members()
            self._stats_current_day["population_end"] = pop_end
            pop_start = max(0, int(self._stats_current_day.get("population_start", pop_end) or pop_end))
            births = max(0, int(self._stats_current_day.get("births", 0) or 0))
            deaths = max(0, int(self._stats_current_day.get("deaths", 0) or 0))
            baseline = max(1, pop_start)
            partial = {
                "day": int(current_day),
                "animals_killed": max(0, int(self._stats_current_day.get("animals_killed", 0) or 0)),
                "resources_collected": max(0, int(self._stats_current_day.get("resources_collected", 0) or 0)),
                "population": pop_end,
                "births": births,
                "deaths": deaths,
                "birth_rate": births / baseline,
                "death_rate": deaths / baseline,
            }
            if self._daily_stats and int(self._daily_stats[-1].get("day", -1)) == int(current_day):
                self._daily_stats[-1] = partial
            else:
                self._daily_stats.append(partial)

    def _on_species_birth(self, _individu=None):
        """Callback appelé à chaque naissance d'individus"""
        self._stats_current_day["births"] = int(self._stats_current_day.get("births", 0) or 0) + 1
        self._run_stats["total_population"] = int(self._run_stats.get("total_population", 0) or 0) + 1
        current_pop = max(0, int(getattr(self.espece, "population", 0) or 0))
        if current_pop <= 0:
            current_pop = self._count_living_species_members()
        self._run_stats["max_population"] = max(int(self._run_stats.get("max_population", 0) or 0), current_pop)

    @staticmethod
    def _collect_species_stats(species) -> dict:
        return collect_species_stats(species)
    
    def _attach_phase_to_entities(self):
        """Facilite l'accès aux systèmes (A REVOIR)"""
        if getattr(self, "espece", None):
            try:
                self.espece.is_player_species = True
            except Exception:
                pass
        for espece in (getattr(self, "espece", None), getattr(self, "fauna_species", None)):
            if espece and hasattr(espece, "reproduction_system"):
                try:
                    espece.reproduction_system.bind_phase(self)
                except Exception:
                    pass
        for ent in self.entities:
            try:
                ent.phase = self
            except Exception:
                pass
            if (
                getattr(self, "espece", None) is not None
                and getattr(ent, "espece", None) is self.espece
                and hasattr(self.espece, "_apply_main_class_bonus_if_needed")
            ):
                try:
                    self.espece._apply_main_class_bonus_if_needed(ent)
                except Exception:
                    pass
        # Nettoie les fenêtres d'info éventuelles (pour éviter les références périmées)
        self.info_windows = []
        self._set_cursor(self.default_cursor_path)

    def _load_weather_icons(self):
        """Charge les icônes météo disponibles dans le pack d'assets."""
        self.weather_icons = {}
        for condition_id, condition in WEATHER_CONDITIONS.items():
            sprite_key = condition.sprites or condition_id
            sprite = self.assets.get_image(sprite_key)
            if sprite is None:
                continue

            scaled_sprite = pygame.transform.smoothscale(sprite, (40, 40))
            self.weather_icons[condition_id] = scaled_sprite
            self.weather_icons[str(sprite_key)] = scaled_sprite
            self.weather_icons[condition.name] = scaled_sprite

    def _load_prop_descriptions(self, path: str = "Game/data/props_descriptions.json") -> dict:
        return load_prop_descriptions(path)

    def _get_prop_description_entry(self, pid: int):
        return get_prop_description_entry(self.prop_descriptions, pid)

    def _ensure_weather_system(self):
        """Initialise la météo si un monde est présent."""
        if self.weather_system is not None or self.world is None:
            return
        raw_seed = getattr(self.params, "seed", 0) if self.params is not None else 0
        world_seed = getattr(self.world, "seed", None)
        if isinstance(raw_seed, str):
            if isinstance(world_seed, int):
                seed = world_seed
            else:
                digest = hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()
                seed = int(digest[:8], 16)
        else:
            seed = int(raw_seed or 0)
        self.weather_system = WeatherSystem(
            world=self.world,
            day_night_cycle=self.day_night,
            seed=seed,
        )

    def _update_weather_vfx(self, dt: float):
        if self.weather_vfx:
            self.weather_vfx.update(dt, self.weather_system, self.screen.get_size())

    def _draw_weather_effects(self, screen: pygame.Surface):
        if self.weather_vfx:
            self.weather_vfx.draw(screen, self.weather_system)

    def _tech_locked_crafts(self) -> set[str]:
        tech_locked_crafts: set[str] = set()
        if self.tech_tree and getattr(self.tech_tree, "techs", None):
            for tech_data in (self.tech_tree.techs or {}).values():
                if not isinstance(tech_data, dict):
                    continue
                for craft_id in tech_data.get("craft", []) or []:
                    if craft_id:
                        tech_locked_crafts.add(str(craft_id))
        return tech_locked_crafts

    def _init_craft_unlocks(self):
        """Initialise l'ensemble des crafts accessibles par défaut."""
        tech_locked_crafts = self._tech_locked_crafts()

        self.unlocked_crafts = set()
        for cid, craft_def in self.craft_system.crafts.items():
            locked = craft_def.get("locked") or craft_def.get("requires_unlock")
            if cid in tech_locked_crafts:
                locked = True
            if not locked:
                self.unlocked_crafts.add(cid)
        if "Entrepot_primitif" in self.craft_system.crafts:
            self.unlocked_crafts.add("Entrepot_primitif")
        self._warehouse_gate_cache = bool(int(getattr(self, "_warehouse_built_count", 0) or 0) > 0)

    def _default_tech_effects(self) -> dict[str, float | bool]:
        return {
            "global_damage_mult": 1.0,
            "global_defense_bonus": 0.0,
            "global_speed_mult": 1.0,
            "global_attack_interval_mult": 1.0,
            "food_consumption_mult": 1.0,
            "pacifist_mode": False,
            "structures_indestructible": False,
            "believer_scaling_per_unit": 0.0,
            "believer_scaling_cap": 0.0,
            "kill_streak_team_bonus": 0.0,
            "kill_streak_defense_bonus": 0.0,
            "kill_streak_cap": 0.65,
        }

    def _sync_tech_tree_main_class(self) -> None:
        if not self.tech_tree or not hasattr(self.tech_tree, "set_main_class"):
            return
        current = None
        if self.espece is not None:
            current = getattr(self.espece, "main_class", None)
        if not current:
            current = self.class_state.get("main_class")
        self.tech_tree.set_main_class(current)

    def _cancel_hostile_combat_due_to_pacifism(self) -> None:
        for ent in list(getattr(self, "entities", [])):
            if ent is None:
                continue
            if getattr(ent, "ia", {}).get("etat") != "combat":
                continue
            target = getattr(ent, "_combat_target", None)
            if target is None:
                continue
            attacker_player = self._is_player_species_entity(ent)
            target_player = self._is_player_species_entity(target)
            if attacker_player and getattr(target, "is_fauna", False):
                self._stop_entity_combat(ent)
            elif target_player and getattr(ent, "is_fauna", False):
                self._stop_entity_combat(ent)

    def _recompute_tech_effects(self) -> None:
        effects = self._default_tech_effects()
        if not hasattr(self, "_food_consumption_base_per_individual_per_sec"):
            self._food_consumption_base_per_individual_per_sec = float(
                getattr(self, "food_consumption_per_individual_per_sec", 1.0 / 120.0) or (1.0 / 120.0)
            )
        tree = getattr(self, "tech_tree", None)
        if tree is not None:
            for tech_id in sorted(getattr(tree, "unlocked", set()) or set()):
                tech_data = tree.get_tech(tech_id) if hasattr(tree, "get_tech") else {}
                eff = tech_data.get("effets") if isinstance(tech_data, dict) else None
                if not isinstance(eff, dict):
                    continue
                for key, value in eff.items():
                    if key not in effects:
                        continue
                    if key in {"global_damage_mult", "global_speed_mult", "global_attack_interval_mult", "food_consumption_mult"}:
                        try:
                            val = float(value)
                        except Exception:
                            continue
                        if val > 0:
                            effects[key] = float(effects[key]) * val
                    elif key in {"global_defense_bonus", "believer_scaling_per_unit", "kill_streak_team_bonus", "kill_streak_defense_bonus"}:
                        try:
                            effects[key] = float(effects[key]) + float(value)
                        except Exception:
                            continue
                    elif key in {"believer_scaling_cap", "kill_streak_cap"}:
                        try:
                            effects[key] = max(float(effects[key]), float(value))
                        except Exception:
                            continue
                    elif key in {"pacifist_mode", "structures_indestructible"}:
                        effects[key] = bool(effects[key]) or bool(value)

        self._tech_effects = effects
        base_food = float(getattr(self, "_food_consumption_base_per_individual_per_sec", 1.0 / 120.0) or (1.0 / 120.0))
        self.food_consumption_per_individual_per_sec = max(0.0, base_food * max(0.25, float(effects["food_consumption_mult"])))

        if float(effects.get("kill_streak_team_bonus", 0.0) or 0.0) <= 0.0:
            self._tech_runtime["belligerant_kill_streak"] = 0

        if bool(effects.get("pacifist_mode", False)):
            self._cancel_hostile_combat_due_to_pacifism()
        self._tech_effects_dirty = False

    def is_pacifist_mode_active(self) -> bool:
        return bool((getattr(self, "_tech_effects", {}) or {}).get("pacifist_mode", False))

    def is_structure_indestructible_mode_active(self) -> bool:
        return bool((getattr(self, "_tech_effects", {}) or {}).get("structures_indestructible", False))

    def _team_kill_streak_bonus(self) -> float:
        effects = getattr(self, "_tech_effects", {}) or {}
        per_kill = float(effects.get("kill_streak_team_bonus", 0.0) or 0.0)
        if per_kill <= 0.0:
            return 0.0
        cap = max(0.0, float(effects.get("kill_streak_cap", 0.65) or 0.65))
        streak = int((getattr(self, "_tech_runtime", {}) or {}).get("belligerant_kill_streak", 0) or 0)
        return min(cap, per_kill * max(0, streak))

    def _team_kill_streak_defense_bonus(self) -> float:
        effects = getattr(self, "_tech_effects", {}) or {}
        per_kill = float(effects.get("kill_streak_defense_bonus", 0.0) or 0.0)
        if per_kill <= 0.0:
            return 0.0
        cap = max(0.0, float(effects.get("kill_streak_cap", 0.65) or 0.65))
        streak = int((getattr(self, "_tech_runtime", {}) or {}).get("belligerant_kill_streak", 0) or 0)
        # On transforme le cap multiplicatif en cap additif défensif raisonnable.
        cap_def = max(0.0, cap * 10.0)
        return min(cap_def, per_kill * max(0, streak))

    def _croyant_scaling_bonus(self, ent) -> float:
        effects = getattr(self, "_tech_effects", {}) or {}
        per_member = float(effects.get("believer_scaling_per_unit", 0.0) or 0.0)
        if per_member <= 0.0:
            return 0.0
        if ent is None or not self._is_player_species_entity(ent):
            return 0.0
        role = str(getattr(ent, "role_class", "") or "").strip().lower()
        if role != "croyant":
            return 0.0
        believers = int(self.count_living_members_by_class("croyant") or 0)
        cap = max(0.0, float(effects.get("believer_scaling_cap", 0.0) or 0.0))
        return min(cap, believers * per_member)

    def get_entity_attack_multiplier(self, attacker, target=None) -> float:
        if attacker is None or not self._is_player_species_entity(attacker):
            return 1.0
        effects = getattr(self, "_tech_effects", {}) or {}
        mult = max(0.1, float(effects.get("global_damage_mult", 1.0) or 1.0))
        mult *= 1.0 + self._team_kill_streak_bonus()
        croyant_bonus = self._croyant_scaling_bonus(attacker)
        if croyant_bonus > 0.0:
            mult *= 1.0 + croyant_bonus
        return max(0.1, mult)

    def get_entity_defense_bonus(self, ent) -> float:
        if ent is None or not self._is_player_species_entity(ent):
            return 0.0
        effects = getattr(self, "_tech_effects", {}) or {}
        bonus = float(effects.get("global_defense_bonus", 0.0) or 0.0)
        bonus += self._team_kill_streak_defense_bonus()
        croyant_bonus = self._croyant_scaling_bonus(ent)
        if croyant_bonus > 0.0:
            bonus += croyant_bonus * 5.0
        return max(0.0, bonus)

    def get_entity_speed_multiplier(self, ent) -> float:
        if ent is None or not self._is_player_species_entity(ent):
            return 1.0
        effects = getattr(self, "_tech_effects", {}) or {}
        mult = max(0.2, float(effects.get("global_speed_mult", 1.0) or 1.0))
        croyant_bonus = self._croyant_scaling_bonus(ent)
        if croyant_bonus > 0.0:
            mult *= 1.0 + (croyant_bonus * 0.2)
        return max(0.2, mult)

    def is_pacifist_damage_blocked(self, attacker, target) -> bool:
        if not self.is_pacifist_mode_active():
            return False
        if attacker is None or target is None:
            return False
        if self._is_player_side_entity(attacker) and getattr(target, "is_fauna", False):
            return True
        if getattr(attacker, "is_fauna", False) and self._is_player_side_entity(target):
            return True
        return False

    def on_species_enemy_killed(self, attacker, target) -> None:
        if attacker is None or target is None:
            return
        if not self._is_player_species_entity(attacker):
            return
        if not getattr(target, "is_fauna", False):
            return
        effects = getattr(self, "_tech_effects", {}) or {}
        if float(effects.get("kill_streak_team_bonus", 0.0) or 0.0) <= 0.0:
            return
        streak = int((self._tech_runtime or {}).get("belligerant_kill_streak", 0) or 0) + 1
        self._tech_runtime["belligerant_kill_streak"] = streak
        # Évite le spam visuel: feedback fréquent au début puis tous les 5 kills.
        if streak <= 4 or streak % 5 == 0:
            percent = int(round(self._team_kill_streak_bonus() * 100.0))
            add_notification(f"Ferveur belligerante: +{percent}% puissance d'equipe.")

    def _reset_belligerant_kill_streak(self, reason: str | None = None) -> None:
        streak = int((self._tech_runtime or {}).get("belligerant_kill_streak", 0) or 0)
        if streak <= 0:
            return
        self._tech_runtime["belligerant_kill_streak"] = 0
        if reason:
            add_notification(reason)

    def _on_tech_unlocked(self, tech_id: str, tech_data: dict) -> None:
        """Callback appelé quand une technologie est débloquée"""
        for craft_id in tech_data.get("craft", []) or []:
            self.unlock_craft(craft_id)
        name = tech_data.get("nom", tech_id)
        add_notification(f"Technologie débloquée : {name}")
        self._tech_effects_dirty = True
        self._recompute_tech_effects()
        self._run_stats["max_innovation"] = max(
            int(self._run_stats.get("max_innovation", 0) or 0),
            int(getattr(getattr(self, "tech_tree", None), "innovations", 0) or 0),
        )

    def _scan_warehouses_near_entities(self, radius: int = 96) -> int:
        """
        Scan borné autour des entités vivantes pour migration d'anciens saves.
        Évite le scan global de la carte (trop coûteux).
        """
        if not self.world or not getattr(self.world, "overlay", None):
            return 0
        w, h = int(self.world.width), int(self.world.height)
        if w <= 0 or h <= 0:
            return 0

        centers: list[tuple[int, int]] = []
        for ent in self.entities:
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "is_fauna", False):
                continue
            centers.append((int(getattr(ent, "x", 0)), int(getattr(ent, "y", 0))))
            if len(centers) >= 6:
                break
        if not centers:
            try:
                sx, sy = self.world.spawn
                centers.append((int(sx), int(sy)))
            except Exception:
                centers.append((w // 2, h // 2))

        found = 0
        seen: set[tuple[int, int]] = set()
        rad = max(8, int(radius))
        for cx, cy in centers:
            x0 = max(0, cx - rad)
            x1 = min(w - 1, cx + rad)
            y0 = max(0, cy - rad)
            y1 = min(h - 1, cy + rad)
            for j in range(y0, y1 + 1):
                row = self.world.overlay[j]
                for i in range(x0, x1 + 1):
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    cell = row[i]
                    if isinstance(cell, dict):
                        if cell.get("state") == "built" and (
                            cell.get("craft_id") == "Entrepot_primitif" or cell.get("pid") == 102
                        ):
                            found += 1
                    elif isinstance(cell, int) and int(cell) == 102:
                        found += 1
        return found

    def has_built_warehouse(self, force_scan: bool = False) -> bool:
        count = int(getattr(self, "_warehouse_built_count", 0) or 0)
        if force_scan:
            detected = self._scan_warehouses_near_entities()
            self._warehouse_built_count = int(detected)
            count = int(detected)
        built = count > 0
        self._warehouse_gate_cache = bool(built)
        return bool(built)

    def _scan_water_collectors_near_entities(self, radius: int = 42) -> set[tuple[int, int]]:
        """
        Scan borné autour des entités vivantes pour retrouver les récupérateurs d'eau.
        """
        if not self.world or not getattr(self.world, "overlay", None):
            return set()
        w, h = int(self.world.width), int(self.world.height)
        if w <= 0 or h <= 0:
            return set()

        centers: list[tuple[int, int]] = []
        for ent in self.entities:
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "is_fauna", False):
                continue
            centers.append((int(getattr(ent, "x", 0)), int(getattr(ent, "y", 0))))
            if len(centers) >= 6:
                break
        if not centers:
            try:
                sx, sy = self.world.spawn
                centers.append((int(sx), int(sy)))
            except Exception:
                centers.append((w // 2, h // 2))

        out: set[tuple[int, int]] = set()
        seen: set[tuple[int, int]] = set()
        rad = max(8, int(radius))
        for cx, cy in centers:
            x0 = max(0, cx - rad)
            x1 = min(w - 1, cx + rad)
            y0 = max(0, cy - rad)
            y1 = min(h - 1, cy + rad)
            for j in range(y0, y1 + 1):
                row = self.world.overlay[j]
                for i in range(x0, x1 + 1):
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    cell = row[i]
                    if isinstance(cell, dict) and cell.get("state") == "built":
                        if cell.get("craft_id") == "Recuperateur_eau" or int(cell.get("pid", 0) or 0) == 115:
                            out.add((int(i), int(j)))
        return out

    def _scan_gardens_near_entities(self, radius: int = 42) -> set[tuple[int, int]]:
        """
        Scan borné autour des entités vivantes pour retrouver les jardins construits.
        """
        if not self.world or not getattr(self.world, "overlay", None):
            return set()
        w, h = int(self.world.width), int(self.world.height)
        if w <= 0 or h <= 0:
            return set()

        centers: list[tuple[int, int]] = []
        for ent in self.entities:
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "is_fauna", False):
                continue
            centers.append((int(getattr(ent, "x", 0)), int(getattr(ent, "y", 0))))
            if len(centers) >= 6:
                break
        if not centers:
            try:
                sx, sy = self.world.spawn
                centers.append((int(sx), int(sy)))
            except Exception:
                centers.append((w // 2, h // 2))

        out: set[tuple[int, int]] = set()
        seen: set[tuple[int, int]] = set()
        rad = max(8, int(radius))
        for cx, cy in centers:
            x0 = max(0, cx - rad)
            x1 = min(w - 1, cx + rad)
            y0 = max(0, cy - rad)
            y1 = min(h - 1, cy + rad)
            for j in range(y0, y1 + 1):
                row = self.world.overlay[j]
                for i in range(x0, x1 + 1):
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    cell = row[i]
                    if isinstance(cell, dict) and cell.get("state") == "built" and cell.get("craft_id") == "Jardin":
                        out.add((int(i), int(j)))
        return out

    def _scan_campfires_near_entities(self, radius: int = 48) -> set[tuple[int, int]]:
        """
        Scan borné autour des entités vivantes pour retrouver les feux de camp.
        """
        if not self.world or not getattr(self.world, "overlay", None):
            return set()
        w, h = int(self.world.width), int(self.world.height)
        if w <= 0 or h <= 0:
            return set()

        centers: list[tuple[int, int]] = []
        for ent in self.entities:
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "is_fauna", False):
                continue
            centers.append((int(getattr(ent, "x", 0)), int(getattr(ent, "y", 0))))
            if len(centers) >= 6:
                break
        if not centers:
            try:
                sx, sy = self.world.spawn
                centers.append((int(sx), int(sy)))
            except Exception:
                centers.append((w // 2, h // 2))

        out: set[tuple[int, int]] = set()
        seen: set[tuple[int, int]] = set()
        rad = max(8, int(radius))
        for cx, cy in centers:
            x0 = max(0, cx - rad)
            x1 = min(w - 1, cx + rad)
            y0 = max(0, cy - rad)
            y1 = min(h - 1, cy + rad)
            for j in range(y0, y1 + 1):
                row = self.world.overlay[j]
                for i in range(x0, x1 + 1):
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    cell = row[i]
                    if isinstance(cell, dict):
                        pid = int(cell.get("pid", 0) or 0)
                        if pid == 101 or cell.get("craft_id") == "Feu_de_camp":
                            if str(cell.get("state") or "") in ("built", "building"):
                                out.add((int(i), int(j)))
                    elif isinstance(cell, int) and int(cell) == 101:
                        out.add((int(i), int(j)))
        return out

    def _update_campfires(self, dt: float) -> None:
        self._campfire_probe_cd = max(0.0, float(self._campfire_probe_cd) - float(dt))
        if self._campfire_probe_cd <= 0.0 and not self._campfire_tiles:
            self._campfire_tiles = set(self._scan_campfires_near_entities())
            self._campfire_probe_cd = 10.0

        if not self._campfire_tiles or not self.world or not getattr(self.world, "overlay", None):
            return

        to_remove: list[tuple[int, int]] = []
        for i, j in self._campfire_tiles:
            try:
                cell = self.world.overlay[int(j)][int(i)]
            except Exception:
                cell = None
            if isinstance(cell, dict):
                pid = int(cell.get("pid", 0) or 0)
                if pid != 101 and cell.get("craft_id") != "Feu_de_camp":
                    to_remove.append((i, j))
                    continue
                state = str(cell.get("state") or "")
                if state not in ("built", "building"):
                    to_remove.append((i, j))
                    continue
            elif isinstance(cell, int):
                if int(cell) != 101:
                    to_remove.append((i, j))
            else:
                to_remove.append((i, j))

        for key in to_remove:
            self._campfire_tiles.discard(key)

    def _is_valid_living_entity(self, ent) -> bool:
        if ent is None:
            return False
        if getattr(ent, "_dead_processed", False):
            return False
        if getattr(ent, "jauges", {}).get("sante", 0) <= 0:
            return False
        return ent in getattr(self, "entities", [])

    def _leave_shelter(self, ent) -> None:
        if ent is None:
            return
        tile = getattr(ent, "_shelter_tile", None)
        if tile:
            occ = self._shelter_occupants.get(tuple(tile))
            if occ is ent:
                self._shelter_occupants.pop(tuple(tile), None)
        try:
            ent._shelter_tile = None
            ent._shelter_resting = False
        except Exception:
            pass

    def _can_enter_shelter(self, ent, shelter_tile: tuple[int, int]) -> bool:
        if ent is None:
            return False
        if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
            return False
        if getattr(ent, "espece", None) != self.espece:
            return False
        occ = self._shelter_occupants.get(tuple(shelter_tile))
        if occ is None:
            return True
        if occ is ent:
            return True
        return not self._is_valid_living_entity(occ)

    def _enter_shelter(self, ent, shelter_tile: tuple[int, int]) -> bool:
        shelter_tile = (int(shelter_tile[0]), int(shelter_tile[1]))
        if not self._can_enter_shelter(ent, shelter_tile):
            return False

        # Nettoyage occupant invalide
        occ = self._shelter_occupants.get(shelter_tile)
        if occ is not None and occ is not ent and not self._is_valid_living_entity(occ):
            self._shelter_occupants.pop(shelter_tile, None)

        self._shelter_occupants[shelter_tile] = ent
        ent._shelter_tile = shelter_tile
        ent._shelter_resting = True

        # "Va dessus" : place l'individu au centre de la tanière.
        try:
            ent.x = float(shelter_tile[0]) + 0.5
            ent.y = float(shelter_tile[1]) + 0.5
        except Exception:
            pass

        if hasattr(ent, "ia") and isinstance(ent.ia, dict):
            ent.ia["etat"] = "repos"
            ent.ia["objectif"] = ("shelter", shelter_tile)
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None
        ent.move_path = []
        ent._move_from = (float(ent.x), float(ent.y))
        ent._move_to = None
        ent._move_t = 0.0
        return True

    def _update_water_collectors(self, dt: float) -> None:
        # Cooldown de scan pour les saves / si on perd le cache.
        self._water_collector_probe_cd = max(0.0, float(self._water_collector_probe_cd) - float(dt))
        if self._water_collector_probe_cd <= 0.0 and not self._water_collector_tiles:
            self._water_collector_tiles = set(self._scan_water_collectors_near_entities())
            self._water_collector_probe_cd = 8.0

        # Nettoyage: enlève les tuiles qui ne contiennent plus la structure.
        if self._water_collector_tiles and self.world and getattr(self.world, "overlay", None):
            to_remove: list[tuple[int, int]] = []
            for i, j in self._water_collector_tiles:
                try:
                    cell = self.world.overlay[int(j)][int(i)]
                except Exception:
                    cell = None
                if not (isinstance(cell, dict) and cell.get("state") == "built" and cell.get("craft_id") == "Recuperateur_eau"):
                    to_remove.append((i, j))
            for key in to_remove:
                self._water_collector_tiles.discard(key)

        if not self._water_collector_tiles or not self.weather_system:
            return

        cond = getattr(self.weather_system, "current_condition", None)
        cid = str(getattr(cond, "id", "") or "")
        # Pluie légère / forte / orage = collecte active.
        rate_per_min = {"rain": 0.8, "heavy_rain": 1.6, "storm": 2.0}.get(cid, 0.0)
        if rate_per_min <= 0.0:
            return

        dt_minutes = float(dt) / 60.0
        self._water_collector_water_buffer += rate_per_min * len(self._water_collector_tiles) * dt_minutes
        produced = int(self._water_collector_water_buffer)
        if produced <= 0:
            return
        self._water_collector_water_buffer -= float(produced)
        self.warehouse["water"] = int(self.warehouse.get("water", 0) or 0) + int(produced)

    def _update_gardens(self, dt: float) -> None:
        self._garden_probe_cd = max(0.0, float(self._garden_probe_cd) - float(dt))
        if self._garden_probe_cd <= 0.0 and not self._garden_tiles:
            self._garden_tiles = set(self._scan_gardens_near_entities())
            self._garden_probe_cd = 8.0

        if self._garden_tiles and self.world and getattr(self.world, "overlay", None):
            to_remove: list[tuple[int, int]] = []
            for i, j in self._garden_tiles:
                try:
                    cell = self.world.overlay[int(j)][int(i)]
                except Exception:
                    cell = None
                if not (isinstance(cell, dict) and cell.get("state") == "built" and cell.get("craft_id") == "Jardin"):
                    to_remove.append((i, j))
            for key in to_remove:
                self._garden_tiles.discard(key)

        if not self._garden_tiles:
            return

        dt_minutes = float(dt) / 60.0
        self._garden_growth_buffer += len(self._garden_tiles) * dt_minutes
        cycles_ready = int(self._garden_growth_buffer // float(_GARDEN_CYCLE_MINUTES))
        if cycles_ready <= 0:
            return

        seeds_stock = int(self.warehouse.get("seed", 0) or 0)
        if seeds_stock <= 0:
            self._garden_growth_buffer = min(self._garden_growth_buffer, float(_GARDEN_CYCLE_MINUTES))
            return

        cycles_done = min(cycles_ready, seeds_stock)
        if cycles_done <= 0:
            return

        self.warehouse["seed"] = max(0, seeds_stock - cycles_done)
        produced_food = int(cycles_done * int(_GARDEN_FOOD_PER_SEED))
        self.warehouse["food"] = int(self.warehouse.get("food", 0) or 0) + produced_food
        self._garden_growth_buffer -= float(cycles_done) * float(_GARDEN_CYCLE_MINUTES)

    def _refresh_craft_gate_state(self, force: bool = False):
        previous = self._warehouse_gate_cache
        built = self.has_built_warehouse(force_scan=force)
        if not force and previous is not None and bool(previous) == bool(built):
            return
        self._warehouse_gate_cache = bool(built)
        self._warehouse_gate_probe_cd = 0.75
        if self.selected_craft and not self.is_craft_unlocked(self.selected_craft):
            self.selected_craft = None
        if self.bottom_hud:
            self.bottom_hud.refresh_craft_buttons()

    def _has_warehouse_under_construction(self) -> bool:
        if not self.construction_sites:
            return False
        for (i, j) in self.construction_sites.keys():
            cell = self._get_construction_cell(int(i), int(j), generate=False)
            if isinstance(cell, dict) and str(cell.get("state") or "") == "building":
                if str(cell.get("craft_id") or "") == "Entrepot_primitif" or int(cell.get("pid", 0) or 0) == 102:
                    return True
        return False

    def warehouse_exists_or_planned(self, *, force_scan: bool = False) -> bool:
        return bool(self.has_built_warehouse(force_scan=force_scan) or self._has_warehouse_under_construction())

    def _grant_warehouse_starter_stock(self) -> None:
        """
        Donne un petit stock de départ à la construction du premier entrepôt.
        Ne doit être appelé qu'au moment où l'entrepôt est effectivement construit.
        """
        if not isinstance(getattr(self, "warehouse", None), dict):
            self.warehouse = {}
        self.warehouse["berries"] = int(self.warehouse.get("berries", 0) or 0) + 12
        self.warehouse["water"] = int(self.warehouse.get("water", 0) or 0) + 12
        add_notification("Entrepôt approvisionné : +12 berries, +12 water.")

    def unlock_all_non_tech_crafts(self, skip: set[str] | None = None):
        skip = set(skip or set())
        tech_locked = self._tech_locked_crafts()
        for craft_id, craft_def in self.craft_system.crafts.items():
            if craft_id in skip:
                continue
            if craft_id == "Entrepot_primitif":
                self.unlocked_crafts.add(craft_id)
                continue
            if craft_id in tech_locked:
                continue
            if craft_def.get("locked") or craft_def.get("requires_unlock"):
                continue
            self.unlocked_crafts.add(craft_id)
        if self.bottom_hud:
            self.bottom_hud.refresh_craft_buttons()

    def start_tech_research(self, tech_id: str) -> bool:
        """Démarre la recherche d'une technologie si possible, et affiche une notification."""
        if not self.tech_tree:
            return False
        self._sync_tech_tree_main_class()
        ok = self.tech_tree.start_research(tech_id)
        if ok:
            tech = self.tech_tree.get_tech(tech_id)
            add_notification(f"Recherche lancée : {tech.get('nom', tech_id)}")
        return ok

    # ---- Sauvegarde / Chargement (wrappers pour le menu) ----
    @staticmethod
    def save_exists() -> bool:
        return SaveManager.has_any_save()

    def _save_manager(self) -> SaveManager:
        return SaveManager(path=self._save_path)

    def save(self) -> bool:
        if not self._save_path:
            self._save_path = SaveManager.create_new_save_path()
        return self._save_manager().save_phase1(self)

    def load(self) -> bool:
        if not self._save_path:
            self._save_path = SaveManager.latest_save_path()
        if not self._save_path:
            return False
        return self._save_manager().load_phase1(self)

    def _ensure_move_runtime(self, ent):
        """S'assure que l'entité a tout le runtime nécessaire au déplacement."""
        if not hasattr(ent, "move_path"):   ent.move_path = []          # liste de (i,j)
        if not hasattr(ent, "move_speed"):  ent.move_speed = 3.5        # tuiles/s (base)
        if not hasattr(ent, "base_move_speed"): ent.base_move_speed = float(getattr(ent, "move_speed", 3.5) or 3.5)
        if not hasattr(ent, "_move_from"):  ent._move_from = None       # (x,y) float
        if not hasattr(ent, "_move_to"):    ent._move_to = None         # (i,j) int
        if not hasattr(ent, "_move_t"):     ent._move_t = 0.0           # 0..1
        if not hasattr(ent, "_combat_target"): ent._combat_target = None
        if not hasattr(ent, "_combat_attack_cd"): ent._combat_attack_cd = 0.0
        if not hasattr(ent, "_combat_repath_cd"): ent._combat_repath_cd = 0.0
        if not hasattr(ent, "_combat_anchor"): ent._combat_anchor = None
        if not hasattr(ent, "_combat_recent_timer"): ent._combat_recent_timer = 0.0

    def _temperature_debuff_multiplier(self, ent) -> float:
        """
        Retourne un multiplicateur 0.55..1.0 selon la température ambiante.
        Les résistances froid/chaleur réduisent (voire annulent) le malus.
        """
        if ent is None or getattr(ent, "is_egg", False):
            return 1.0
        ws = getattr(self, "weather_system", None)
        if ws is None:
            return 1.0

        try:
            temp = float(ws.get_current_temperature(int(getattr(ent, "x", 0)), int(getattr(ent, "y", 0))))
        except Exception:
            return 1.0

        comfort_low = 12.0
        comfort_high = 26.0

        cold_excess = max(0.0, comfort_low - temp)
        heat_excess = max(0.0, temp - comfort_high)
        if cold_excess <= 1e-6 and heat_excess <= 1e-6:
            return 1.0

        env = getattr(ent, "environnement", {}) or {}
        if cold_excess >= heat_excess:
            res = float(env.get("resistance_froid", 5) or 5)
            excess = cold_excess
        else:
            res = float(env.get("resistance_chaleur", 5) or 5)
            excess = heat_excess

        # Résistances acceptent 0..10 (échelle actuelle) ou 0..100 (mutations anciennes).
        if res > 20.0:
            res01 = max(0.0, min(1.0, res / 100.0))
        else:
            res01 = max(0.0, min(1.0, res / 10.0))

        severity = max(0.0, min(1.5, excess / 20.0))
        effective = severity * (1.0 - res01)
        malus = max(0.0, min(0.45, effective * 0.45))
        return max(0.55, 1.0 - malus)

    def _player_night_vision01(self) -> float:
        ent = getattr(self, "joueur", None)
        if ent is None:
            return 0.0
        sens = getattr(ent, "sens", {}) or {}
        try:
            value = float(sens.get("vision_nocturne", 0) or 0)
        except Exception:
            value = 0.0
        # Supporte 0..10 (nouvelle échelle) ou 0..100 (ancienne).
        if value > 20.0:
            return max(0.0, min(1.0, value / 100.0))
        return max(0.0, min(1.0, value / 10.0))

    def _update_entity_passive_regen(self, ent, dt: float) -> None:
        if getattr(ent, "is_egg", False):
            return
        if not hasattr(ent, "jauges") or not isinstance(ent.jauges, dict):
            return
        hp = float(ent.jauges.get("sante", 0) or 0)
        if hp <= 0:
            return

        max_hp = float(getattr(ent, "max_sante", 100.0) or 100.0)
        if max_hp <= 0:
            max_hp = 100.0
        if hp >= max_hp - 1e-3:
            return

        if float(getattr(ent, "_combat_recent_timer", 0.0) or 0.0) > 0.0:
            return
        if hasattr(ent, "ia") and isinstance(ent.ia, dict) and ent.ia.get("etat") == "combat":
            return

        phys = getattr(ent, "physique", {}) or {}
        env = getattr(ent, "environnement", {}) or {}
        endurance = float(phys.get("endurance", 5) or 5)
        stockage = float(phys.get("stockage_energetique", 5) or 5)
        adapt = float(env.get("adaptabilite", 5) or 5)

        # Régénération lente (HP/s). Branchée sur plusieurs stats.
        regen_per_sec = 0.05 + 0.02 * endurance + 0.008 * stockage + 0.008 * adapt
        regen_per_sec = max(0.0, min(3.0, regen_per_sec))

        if self._is_player_species_entity(ent):
            regen_per_sec *= float(self._supply_debuff_multiplier())
        regen_per_sec *= float(self._temperature_debuff_multiplier(ent))

        # Regen minimum (évite les individus "de base" qui ne regénèrent jamais).
        regen_per_sec = max(0.08, float(regen_per_sec))

        # Tanière : récupération beaucoup plus rapide (max 1 individu/tanière géré ailleurs).
        if getattr(ent, "_shelter_resting", False):
            regen_per_sec = max(0.6, regen_per_sec * 6.0)
            regen_per_sec = min(12.0, regen_per_sec)

        ent.jauges["sante"] = min(max_hp, hp + regen_per_sec * float(dt))

    def _entity_can_walk_on_water(self, ent) -> bool:
        """Helper pour savoir si une entité peut marcher sur l'eau"""
        if ent is None:
            return False
        if getattr(ent, "is_egg", False):
            return False
        espece = getattr(ent, "espece", None)
        if espece is None:
            return False
        return bool(getattr(espece, "is_player_species", False))

    def _is_player_species_entity(self, ent) -> bool:
        """Helper pour vérifier que l'espece appartient au joueur (pour les interactions, IA, etc)"""
        if ent is None:
            return False
        if getattr(ent, "is_egg", False):
            return False
        if ent is getattr(self, "joueur", None) or ent is getattr(self, "joueur2", None):
            return True
        if bool(getattr(ent, "is_player_species", False)):
            return True
        espece = getattr(ent, "espece", None)
        if espece is None:
            return False
        if espece is getattr(self, "espece", None):
            return True
        if hasattr(espece, "espece"):
            espece_parent = getattr(espece, "espece", None)
            if espece_parent is getattr(self, "espece", None):
                return True
            return bool(getattr(espece_parent, "is_player_species", False))
        return bool(getattr(espece, "is_player_species", False))

    def _is_player_side_entity(self, ent) -> bool:
        if self._is_player_species_entity(ent):
            return True
        if ent is None or not getattr(ent, "is_egg", False):
            return False
        return getattr(ent, "espece", None) == getattr(self, "espece", None)

    def _tile_is_water(self, i: int, j: int, generate: bool = True) -> bool:
        w = self.world
        if not w:
            return False
        if i < 0 or j < 0 or i >= w.width or j >= w.height:
            return False

        if hasattr(w, "get_tile_snapshot"):
            snap = w.get_tile_snapshot(i, j, generate=generate)
            if snap is None:
                return False
            _lvl, gid, _overlay, bid = snap
            if int(bid) in _WATER_BIOME_IDS:
                return True
            name = get_ground_sprite_name(gid) if gid is not None else None
            if name and any(token in name.lower() for token in ("water", "ocean", "sea", "lake", "river")):
                return True
            return False

        try:
            if hasattr(w, "get_is_water"):
                return bool(w.get_is_water(i, j))
        except Exception:
            pass
        return False

    def _compute_entity_move_speed(self, ent) -> float:
        base = float(getattr(ent, "base_move_speed", getattr(ent, "move_speed", 3.5)) or 3.5)
        physique = getattr(ent, "physique", {}) or {}
        vitesse = float(physique.get("vitesse", 5) or 5)
        speed_mult = max(0.4, min(2.0, 0.6 + 0.08 * vitesse))  # 5 -> ~1.0
        speed = base * speed_mult

        if self._entity_can_walk_on_water(ent) and self._tile_is_water(int(ent.x), int(ent.y), generate=False):
            swim = float(physique.get("vitesse de nage", physique.get("vitesse_de_nage", 3)) or 3)
            # Ralentissement leger et constant dans l'eau.
            water_mult = max(0.75, min(0.98, 0.85 + (swim - 5.0) * 0.02))
            speed *= water_mult

        if self._is_player_species_entity(ent):
            speed *= self._supply_debuff_multiplier()

        if self.weather_system:
            try:
                speed *= float(self.weather_system.get_movement_multiplier())
            except Exception:
                pass
        speed *= float(self._temperature_debuff_multiplier(ent))
        speed *= float(self.get_entity_speed_multiplier(ent))

        return max(0.2, speed)

    def _clear_entity_combat_refs(self, ent):
        clear_entity_combat_refs(self, ent)

    def _stop_entity_combat(self, ent, stop_motion: bool = True):
        stop_entity_combat(self, ent, stop_motion=stop_motion)

    def _start_entity_combat(self, attacker, target) -> bool:
        if self.is_pacifist_mode_active() and self._is_player_species_entity(attacker) and getattr(target, "is_fauna", False):
            return False
        if getattr(attacker, "_shelter_resting", False):
            self._leave_shelter(attacker)
        if getattr(target, "_shelter_resting", False):
            self._leave_shelter(target)
        return start_entity_combat(self, attacker, target)

    def _combat_attack_interval(self, attacker) -> float:
        interval = float(combat_attack_interval(attacker))
        mult = 1.0
        if self._is_player_species_entity(attacker):
            mult *= float(self._supply_debuff_multiplier())
        if self.weather_system:
            try:
                mult *= float(self.weather_system.get_movement_multiplier())
            except Exception:
                pass
        mult *= float(self._temperature_debuff_multiplier(attacker))
        if self._is_player_species_entity(attacker):
            interval_mult = float((getattr(self, "_tech_effects", {}) or {}).get("global_attack_interval_mult", 1.0) or 1.0)
            mult *= 1.0 / max(0.2, interval_mult)
        interval /= max(0.35, mult)
        return interval

    def _combat_attack_range(self, attacker) -> float:
        return combat_attack_range(attacker)

    def _combat_damage(self, attacker, target) -> float:
        damage = float(combat_damage(self, attacker, target))
        if self._is_player_species_entity(attacker):
            damage *= float(self._supply_debuff_multiplier())
        if self.weather_system:
            try:
                damage *= float(self.weather_system.get_movement_multiplier())
            except Exception:
                pass
        damage *= float(self._temperature_debuff_multiplier(attacker))
        return damage

    def _grant_fauna_combat_rewards(self, attacker, target):
        grant_fauna_combat_rewards(self, attacker, target)

    def _update_entity_combat(self, ent, dt: float):
        update_entity_combat(self, ent, dt)

    def _draw_fauna_health_bar(self, screen, ent):
        draw_fauna_health_bar(self, screen, ent)

    def _draw_species_health_bar(self, screen, ent):
        draw_species_health_bar(self, screen, ent)

    def _load_mutations_data(self):
        """
        Charge et met en cache le JSON des mutations.
        """
        if hasattr(self, "_mutations_cache"):
            return self._mutations_cache

        try:
            with open(resource_path("Game/data/mutations.json"), "r", encoding="utf-8") as f:
                self._mutations_cache = json.load(f)
        except Exception as e:
            print(f"[Phase1] Impossible de charger mutations.json : {e}")
            self._mutations_cache = {}

        return self._mutations_cache

    def _get_selected_base_mutations(self) -> list[str]:
        """
        Récupère la liste des IDs de mutations de base sélectionnées
        dans l'App ou les settings.
        """
        app = self.app
        # priorité : valeur en mémoire (menu espèce)
        if hasattr(app, "selected_base_mutations") and app.selected_base_mutations:
            return list(app.selected_base_mutations)

        # fallback : config (si tu veux garder un défaut global)
        try:
            return list(app.settings.get("species.base_mutations", []) or [])
        except Exception:
            return []

    def _get_species_creation_data(self) -> dict:
        data = getattr(self.app, "species_creation", None)
        return data if isinstance(data, dict) else {}

    def _apply_species_creation_to_espece(self):
        """
        Applique le nom, la couleur et les ajustements de stats
        choisis dans le menu de création d'espèce.
        """
        if not self.espece:
            return

        data = self._get_species_creation_data()
        if not data:
            return

        name = str(data.get("name", "") or "").strip()
        if name:
            self.espece.nom = name

        color_name = data.get("color")
        color_rgb = data.get("color_rgb")
        if color_name:
            self.espece.color_name = color_name
        if isinstance(color_rgb, (list, tuple)) and len(color_rgb) == 3:
            self.espece.color_rgb = tuple(color_rgb)

        stats = data.get("stats", {}) or {}
        mapping_espece = {
            "physique": "base_physique",
            "sens": "base_sens",
            "mental": "base_mental",
            "environnement": "base_environnement",
            "social": "base_social",
            "genetique": "genetique",
        }
        for categorie, d in stats.items():
            attr_espece = mapping_espece.get(categorie)
            if not attr_espece or not isinstance(d, dict):
                continue
            cible = getattr(self.espece, attr_espece, None)
            if not isinstance(cible, dict):
                continue
            for stat, delta in d.items():
                if stat in cible and isinstance(delta, (int, float)):
                    cible[stat] += delta

    def _apply_base_mutations_to_species(self):
        """
        Applique les effets des mutations de base sur les stats de base
        de l'espèce (base_physique, base_sens, etc.).
        À appeler après la création de self.espece, avant create_individu().
        """
        ids = self._get_selected_base_mutations()
        if not ids or not self.espece:
            return

        # Appliquer sur l'espèce uniquement (les individus n'existent pas encore)
        self.espece.mutations.apply_base_mutations(
            ids, apply_to_species=True, apply_to_individus=False
        )

    def _apply_base_mutations_to_individus(self):
        """
        Applique sur les individus déjà créés les effets qui concernent
        par exemple la catégorie 'combat' (attaque à distance, etc.).
        À appeler après la création de self.joueur / self.joueur2.
        """
        ids = getattr(self.espece, "base_mutations", None)
        if not ids:
            return

        # Les individus sont maintenant présents : on applique uniquement les effets
        # non recopiés via les stats de base (ex : catégorie combat).
        for mut_id in ids:
            mutation = self.espece.mutations.get_mutation(mut_id)
            if not mutation:
                continue
            effets_combat = mutation.get("effets", {}).get("combat")
            if not effets_combat:
                continue
            self.espece.mutations.apply_effects(
                {"combat": effets_combat},
                mut_id,
                apply_to_species=False,
                apply_to_individus=True,
            )

    # ---------- Bonheur / Décès ----------
    def _clamp_happiness(self, value: float) -> float:
        return max(self.happiness_min, min(self.happiness_max, float(value)))

    def change_happiness(self, delta: float, reason: str | None = None):
        before = self.happiness
        self.happiness = self._clamp_happiness(self.happiness + float(delta))
        for ent in self.entities:
            if getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "jauges", None) is not None:
                ent.jauges["bonheur"] = self.happiness
        if reason:
            add_notification(f"{reason} ({before:.0f} → {self.happiness:.0f})")

    def _species_has_mutation(self, mutation_id: str | None) -> bool:
        wanted = str(mutation_id or "").strip()
        if not wanted or not self.espece:
            return False
        manager = getattr(self.espece, "mutations", None)
        if manager is None:
            return False
        if hasattr(manager, "_resolve_mutation_id"):
            try:
                wanted = str(manager._resolve_mutation_id(wanted) or wanted)
            except Exception:
                pass
        wanted_norm = wanted.casefold()
        known: set[str] = set()
        for raw in list(getattr(manager, "actives", []) or []) + list(getattr(self.espece, "base_mutations", []) or []):
            name = str(raw or "").strip()
            if not name:
                continue
            known.add(name)
            known.add(name.casefold())
        return wanted in known or wanted_norm in known

    def set_death_policy(self, mode: str | None):
        self.death_response_mode = mode
        if mode:
            add_notification(f"Gestion des corps choisie : {mode}.")
            if str(mode).strip().casefold() == "enterrer":
                converted = self._convert_species_corpses_to_graves()
                if converted > 0:
                    add_notification(f"{converted} cadavre(s) transforme(s) en tombes.")

    def _is_species_grave_overlay(self, cell) -> bool:
        if isinstance(cell, dict):
            if str(cell.get("state", "")).strip().lower() == "grave":
                return True
            pid = cell.get("pid")
            try:
                return int(pid) == int(_SPECIES_GRAVESTONE_PROP_ID)
            except Exception:
                return False
        if isinstance(cell, int):
            return int(cell) == int(_SPECIES_GRAVESTONE_PROP_ID)
        return False

    def _is_species_corpse_overlay(self, cell) -> bool:
        if isinstance(cell, dict):
            state = str(cell.get("state", "")).strip().lower()
            if state in {"corpse", "grave"}:
                return True
            pid = cell.get("pid")
            try:
                pid_int = int(pid)
                return pid_int in {int(_SPECIES_CORPSE_PROP_ID), int(_SPECIES_GRAVESTONE_PROP_ID)}
            except Exception:
                return False
        if isinstance(cell, int):
            return int(cell) in {int(_SPECIES_CORPSE_PROP_ID), int(_SPECIES_GRAVESTONE_PROP_ID)}
        return False

    def _can_harvest_species_corpse(self, ent=None, tile: tuple[int, int] | None = None) -> bool:
        if str(self.death_response_mode or "").strip().casefold() == "enterrer":
            return False
        if not self._species_has_mutation("Cannibale"):
            return False
        if ent is not None:
            if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
                return False
            if getattr(ent, "espece", None) != self.espece:
                return False
        if tile is None:
            return True
        i, j = int(tile[0]), int(tile[1])
        cell = self._get_construction_cell(i, j, generate=False)
        if self._is_species_grave_overlay(cell):
            return False
        return self._is_species_corpse_overlay(cell)

    def can_entity_harvest_species_corpse(self, ent, tile: tuple[int, int] | None = None) -> bool:
        return self._can_harvest_species_corpse(ent=ent, tile=tile)

    def _drop_species_corpse(self, i: int, j: int) -> bool:
        if not self.world:
            return False
        if i < 0 or j < 0 or i >= self.world.width or j >= self.world.height:
            return False
        current = self._get_construction_cell(i, j, generate=True)
        if current and not self._is_species_corpse_overlay(current):
            return False
        is_burial_mode = str(self.death_response_mode or "").strip().casefold() == "enterrer"
        corpse = {
            "pid": int(_SPECIES_GRAVESTONE_PROP_ID if is_burial_mode else _SPECIES_CORPSE_PROP_ID),
            "state": "grave" if is_burial_mode else "corpse",
            "name": "Tombe" if is_burial_mode else "Cadavre",
        }
        self.world.overlay[j][i] = corpse
        return True

    def _convert_species_corpses_to_graves(self) -> int:
        if not self.world or not getattr(self.world, "overlay", None):
            return 0
        converted = 0
        for j, row in enumerate(self.world.overlay):
            for i, cell in enumerate(row):
                if not self._is_species_corpse_overlay(cell):
                    continue
                if self._is_species_grave_overlay(cell):
                    continue
                row[i] = {
                    "pid": int(_SPECIES_GRAVESTONE_PROP_ID),
                    "state": "grave",
                    "name": "Tombe",
                }
                converted += 1
        return converted

    def _clear_species_corpse(self, i: int, j: int) -> bool:
        if not self.world:
            return False
        if i < 0 or j < 0 or i >= self.world.width or j >= self.world.height:
            return False
        current = self._get_construction_cell(i, j, generate=False)
        if not self._is_species_corpse_overlay(current):
            return False
        self.world.overlay[j][i] = 0
        return True

    def _sum_warehouse_stock(self, resource_keys: tuple[str, ...]) -> float:
        total = 0.0
        for key in resource_keys:
            try:
                total += max(0.0, float(self.warehouse.get(key, 0) or 0))
            except Exception:
                continue
        return total

    def _food_stock_units(self) -> float:
        return self._sum_warehouse_stock(_FOOD_STOCK_KEYS)

    def _water_stock_units(self) -> float:
        return self._sum_warehouse_stock(_WATER_STOCK_KEYS)

    def _food_units_per_individual(self) -> float:
        return float(getattr(self, "_supply_cached_food_units_per_ind", 0.0))

    def _water_units_per_individual(self) -> float:
        return float(getattr(self, "_supply_cached_water_units_per_ind", 0.0))

    def _food_stock_ratio(self) -> float:
        return float(getattr(self, "_supply_cached_food_ratio", 0.0))

    def _water_stock_ratio(self) -> float:
        return float(getattr(self, "_supply_cached_water_ratio", 0.0))

    def _supply_debuff_multiplier(self) -> float:
        return float(getattr(self, "_supply_cached_debuff_mult", 1.0))

    def get_individual_supply_work_multiplier(self, ent) -> float:
        mult = 1.0
        if ent is None or getattr(ent, "is_egg", False):
            return mult
        if self._is_player_species_entity(ent):
            mult *= float(self._supply_debuff_multiplier())
        if self.weather_system:
            try:
                mult *= float(self.weather_system.get_movement_multiplier())
            except Exception:
                pass
        mult *= float(self._temperature_debuff_multiplier(ent))
        return max(0.35, min(1.0, mult))

    def _take_from_warehouse_pool(self, resource_keys: tuple[str, ...], quantity: int) -> int:
        remaining = max(0, int(quantity))
        if remaining <= 0:
            return 0
        taken = 0
        for key in resource_keys:
            stock = int(self.warehouse.get(key, 0) or 0)
            if stock <= 0:
                continue
            used = min(stock, remaining)
            self.warehouse[key] = stock - used
            remaining -= used
            taken += used
            if remaining <= 0:
                break
        return taken

    def _update_group_supply(self, dt: float) -> None:
        # Le système de ravitaillement ne démarre qu'après la construction d'un entrepôt.
        if not self.has_built_warehouse(force_scan=False):
            self._group_supply_food_buffer = 0.0
            self._group_supply_water_buffer = 0.0
            self._group_supply_damage_timer = 0.0
            self._supply_cached_population = max(1, int(self._count_living_species_members()))
            self._supply_cached_food_units_per_ind = float(self.food_target_per_individual)
            self._supply_cached_water_units_per_ind = float(self.water_target_per_individual)
            self._supply_cached_food_ratio = 1.0
            self._supply_cached_water_ratio = 1.0
            self._supply_cached_debuff_mult = 1.0
            return

        pop = int(self._count_living_species_members())
        if pop <= 0:
            self._group_supply_food_buffer = 0.0
            self._group_supply_water_buffer = 0.0
            self._group_supply_damage_timer = 0.0
            self._supply_cached_population = 1
            self._supply_cached_food_units_per_ind = 0.0
            self._supply_cached_water_units_per_ind = 0.0
            self._supply_cached_food_ratio = 0.0
            self._supply_cached_water_ratio = 0.0
            self._supply_cached_debuff_mult = 1.0
            return

        self._group_supply_food_buffer += max(0.0, float(self.food_consumption_per_individual_per_sec)) * pop * float(dt)
        self._group_supply_water_buffer += max(0.0, float(self.water_consumption_per_individual_per_sec)) * pop * float(dt)

        food_need = int(self._group_supply_food_buffer)
        if food_need > 0:
            self._group_supply_food_buffer -= float(food_need)
            self._take_from_warehouse_pool(_FOOD_STOCK_KEYS, food_need)

        water_need = int(self._group_supply_water_buffer)
        if water_need > 0:
            self._group_supply_water_buffer -= float(water_need)
            self._take_from_warehouse_pool(_WATER_STOCK_KEYS, water_need)

        self._supply_cached_population = max(1, pop)
        self._supply_cached_food_units_per_ind = self._food_stock_units() / float(self._supply_cached_population)
        self._supply_cached_water_units_per_ind = self._water_stock_units() / float(self._supply_cached_population)

        food_target = max(0.1, float(self.food_target_per_individual))
        water_target = max(0.1, float(self.water_target_per_individual))
        self._supply_cached_food_ratio = self._supply_cached_food_units_per_ind / food_target
        self._supply_cached_water_ratio = self._supply_cached_water_units_per_ind / water_target
        ratio = min(self._supply_cached_food_ratio, self._supply_cached_water_ratio)

        if ratio >= 1.0:
            self._supply_cached_debuff_mult = 1.0
        elif ratio >= 0.66:
            self._supply_cached_debuff_mult = 0.90
        elif ratio >= 0.33:
            self._supply_cached_debuff_mult = 0.75
        else:
            self._supply_cached_debuff_mult = 0.60

        critical_ratio = ratio
        if critical_ratio >= 0.20:
            self._group_supply_damage_timer = 0.0
            return

        self._group_supply_damage_timer += float(dt)
        while self._group_supply_damage_timer >= 5.0:
            self._group_supply_damage_timer -= 5.0
            for ent in self.entities:
                if getattr(ent, "is_egg", False):
                    continue
                if getattr(ent, "espece", None) != self.espece:
                    continue
                if getattr(ent, "_dead_processed", False):
                    continue
                hp = float(getattr(ent, "jauges", {}).get("sante", 0) or 0)
                if hp <= 0:
                    continue
                ent.jauges["sante"] = max(0.0, hp - 1.0)

    def _apply_death_morale_effects(self):
        mode = self.death_response_mode
        if not mode:
            return
        if mode == "abandonner":
            self.change_happiness(-3, "Une mort non prise en charge pèse sur le groupe.")
            return
        if mode == "manger":
            ratio = self._food_stock_ratio()
            if ratio < 0.25:
                delta = 2
            elif ratio < 0.5:
                delta = 1
            elif abs(ratio - 0.5) < 0.01:
                delta = 0
            elif ratio < 0.75:
                delta = -1
            else:
                delta = -2
            self.change_happiness(delta, "Réaction cannibale face au manque ou à l'abondance.")
            return
        if mode == "enterrer":
            self.change_happiness(-2, "Le deuil pèse sur le clan.")

    def _count_living_species_members(self) -> int:
        count = 0
        for ent in self.entities:
            if getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "espece", None) != self.espece:
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if ent.jauges.get("sante", 0) <= 0:
                continue
            count += 1
        return count

    def count_living_members_by_class(self, class_id: str | None = None) -> int:
        wanted = str(class_id or "").strip().lower()
        count = 0
        for ent in self.entities:
            if getattr(ent, "is_egg", False) or getattr(ent, "is_fauna", False):
                continue
            if getattr(ent, "espece", None) != self.espece:
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "jauges", {}).get("sante", 0) <= 0:
                continue
            if wanted and str(getattr(ent, "role_class", "") or "").strip().lower() != wanted:
                continue
            count += 1
        return count

    def get_dominant_role_class(self, min_count: int = 0) -> tuple[str | None, int]:
        counts: dict[str, int] = {}
        for ent in self.entities:
            if getattr(ent, "is_egg", False) or getattr(ent, "is_fauna", False):
                continue
            if getattr(ent, "espece", None) != self.espece:
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "jauges", {}).get("sante", 0) <= 0:
                continue
            role = str(getattr(ent, "role_class", "") or "").strip().lower()
            if not role:
                continue
            counts[role] = counts.get(role, 0) + 1

        if not counts:
            return None, 0
        best_role, best_count = max(counts.items(), key=lambda kv: kv[1])
        if int(best_count) < int(min_count):
            return None, int(best_count)
        return best_role, int(best_count)

    def set_main_class(self, class_id: str | None):
        if not self.espece:
            return
        normalized = str(class_id or "").strip().lower()
        if normalized not in ROLE_CLASS_LABELS:
            return
        if getattr(self.espece, "main_class", None) == normalized:
            return
        self.espece.set_main_class(normalized)
        day = int(getattr(self.day_night, "jour", 0) or 0)
        self.class_state["main_class"] = normalized
        self.class_state["chosen_day"] = day
        if self.tech_tree and hasattr(self.tech_tree, "set_main_class"):
            self.tech_tree.set_main_class(normalized)
        self._tech_effects_dirty = True
        self.event_manager.runtime_flags["class_choice_ready"] = False
        self.event_manager.runtime_flags["class_choice_candidate"] = None
        label = ROLE_CLASS_LABELS.get(normalized, normalized.title())
        add_notification(f"Classe principale fixee: {label}.")
        self.log_world_event("class", f"L'espece adopte la classe principale '{label}'.")

    def _current_day_hour_minute(self) -> tuple[int, int, int]:
        dn = getattr(self, "day_night", None)
        if dn is None:
            return 0, 0, 0
        ratio = float(dn.get_time_ratio() if hasattr(dn, "get_time_ratio") else 0.0)
        ratio = max(0.0, min(1.0, ratio))
        hours_float = ratio * 24.0
        hour = int(hours_float) % 24
        minute = int((hours_float - int(hours_float)) * 60.0) % 60
        day = int(getattr(dn, "jour", 0) or 0)
        return day, hour, minute

    def _game_minutes_absolute(self) -> float:
        day, hour, minute = self._current_day_hour_minute()
        return float(day * 24 * 60 + hour * 60 + minute)

    def log_world_event(self, category: str, message: str):
        day, hour, minute = self._current_day_hour_minute()
        entry = {
            "day": int(day),
            "hour": int(hour),
            "minute": int(minute),
            "category": str(category or "event"),
            "message": str(message or ""),
        }
        self.world_history.append(entry)
        if len(self.world_history) > 1200:
            self.world_history = self.world_history[-1200:]

    def is_horde_active(self) -> bool:
        return bool((self.horde_state or {}).get("active", False))

    def get_horde_aggressive_spawn_multiplier(self) -> float:
        if not self.is_horde_active():
            return 1.0
        return float((self.horde_state or {}).get("aggressive_spawn_multiplier", 3.0) or 3.0)

    def get_horde_spawn_cycle_multiplier(self) -> float:
        return self.get_horde_aggressive_spawn_multiplier()

    def start_horde(self, duration_minutes: float = 120.0):
        now = self._game_minutes_absolute()
        day, _hour, _minute = self._current_day_hour_minute()
        duration = max(1.0, float(duration_minutes or 120.0))
        ends = now + duration
        already_active = self.is_horde_active()
        self.horde_state["active"] = True
        self.horde_state["ends_at_minute"] = max(float(self.horde_state.get("ends_at_minute", 0.0) or 0.0), ends)
        self.horde_state["last_horde_day"] = float(day)
        self.horde_state["aggressive_spawn_multiplier"] = float(
            self.horde_state.get("aggressive_spawn_multiplier", 3.0) or 3.0
        )
        self.event_manager.runtime_flags["horde_active"] = True
        if not already_active:
            add_notification("Alerte: horde hostile active pour 2 heures.")
            self.log_world_event("horde", "Debut d'une horde hostile (2h).")

    def _update_horde_state(self):
        if not self.is_horde_active():
            self.event_manager.runtime_flags["horde_active"] = False
            return
        now = self._game_minutes_absolute()
        ends = float(self.horde_state.get("ends_at_minute", 0.0) or 0.0)
        if now < ends:
            return
        self.horde_state["active"] = False
        self.horde_state["ends_at_minute"] = 0.0
        self.event_manager.runtime_flags["horde_active"] = False
        add_notification("Fin de la horde hostile.")
        self.log_world_event("horde", "Fin de la horde hostile.")

    def _structure_is_attackable(self, cell) -> bool:
        if self.is_structure_indestructible_mode_active():
            return False
        if not isinstance(cell, dict):
            return False
        if not cell.get("craft_id") and cell.get("state") != "building":
            return False
        if cell.get("state") == "destroyed":
            return False
        return True

    def _find_nearest_attackable_structure(self, attacker, max_radius: int = 8):
        if not self.world or attacker is None:
            return None
        if self.is_pacifist_mode_active():
            return None
        ex, ey = int(getattr(attacker, "x", 0)), int(getattr(attacker, "y", 0))
        width, height = self.world.width, self.world.height
        for r in range(1, max_radius + 1):
            best = None
            best_dist = 10**9
            x0 = max(0, ex - r)
            x1 = min(width - 1, ex + r)
            y0 = max(0, ey - r)
            y1 = min(height - 1, ey + r)
            for j in range(y0, y1 + 1):
                for i in range(x0, x1 + 1):
                    if max(abs(i - ex), abs(j - ey)) != r:
                        continue
                    cell = self._get_construction_cell(i, j)
                    if not self._structure_is_attackable(cell):
                        continue
                    dist = abs(i - ex) + abs(j - ey)
                    if dist < best_dist:
                        best = (i, j)
                        best_dist = dist
            if best is not None:
                return best
        return None

    def _damage_structure_at(self, i: int, j: int, damage: float, attacker=None) -> bool:
        if not self.world:
            return False
        if self.is_pacifist_mode_active() and getattr(attacker, "is_fauna", False):
            return False
        if self.is_structure_indestructible_mode_active():
            return False
        cell = self._get_construction_cell(i, j)
        if not self._structure_is_attackable(cell):
            return False

        craft_id = cell.get("craft_id")
        craft_def = self.craft_system.crafts.get(craft_id, {}) if craft_id else {}
        max_hp = float(cell.get("max_hp", 0.0) or 0.0)
        if max_hp <= 0:
            max_hp = max(20.0, float(self.craft_system._compute_structure_hp(craft_def or {"cost": cell.get("cost", {})})))
        hp = float(cell.get("hp", max_hp) or max_hp)
        hp = max(0.0, hp - max(0.0, float(damage)))
        cell["max_hp"] = max_hp
        cell["hp"] = hp

        if hp > 0.0:
            self.world.overlay[j][i] = cell
            return True

        # Destruction
        self.world.overlay[j][i] = 0
        self.construction_sites.pop((int(i), int(j)), None)

        refund_total = 0
        if self.has_built_warehouse():
            costs = dict(cell.get("cost") or craft_def.get("cost") or {})
            for res_id, amount in costs.items():
                try:
                    qty = int(math.ceil(float(amount) * 0.3))
                except Exception:
                    qty = 0
                if qty <= 0:
                    continue
                self.warehouse[res_id] = self.warehouse.get(res_id, 0) + qty
                refund_total += qty

        name = str(cell.get("name") or craft_id or "Structure")
        if refund_total > 0:
            add_notification(f"{name} detruit ({refund_total} ressources recuperees).")
        else:
            add_notification(f"{name} detruit.")
        self.log_world_event("build", f"{name} a ete detruit.")
        if craft_id == "Entrepot_primitif" and int(self._warehouse_built_count or 0) > 0:
            self._warehouse_built_count = max(0, int(self._warehouse_built_count) - 1)
        self._refresh_craft_gate_state(force=True)
        return True

    def _focus_camera_on_nearest_species_member(self) -> bool:
        if not self.espece or not self.view:
            return False

        cam_x = float(getattr(self.view, "cam_x", 0.0) or 0.0)
        cam_y = float(getattr(self.view, "cam_y", 0.0) or 0.0)
        nearest = None
        best_dist2 = None

        for ent in self.entities:
            if getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "espece", None) != self.espece:
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "jauges", {}).get("sante", 0) <= 0:
                continue

            try:
                sx, sy = self.view.world_to_screen(
                    float(getattr(ent, "x", 0.0)),
                    float(getattr(ent, "y", 0.0)),
                    float(getattr(ent, "z", 0.0) or 0.0),
                )
            except Exception:
                continue

            dx = float(sx) - cam_x
            dy = float(sy) - cam_y
            dist2 = dx * dx + dy * dy
            if best_dist2 is None or dist2 < best_dist2:
                best_dist2 = dist2
                nearest = (sx, sy)

        if nearest is None:
            return False

        self.view.cam_x = float(nearest[0])
        self.view.cam_y = float(nearest[1])
        self.view.mouse_pan_active = False
        return True

    def _has_player_species_entities(self) -> bool:
        if not self.espece:
            return False
        for ent in self.entities:
            if getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if getattr(ent, "espece", None) == self.espece:
                return True
        return False

    def _build_endgame_summary(self, reason: str) -> dict:
        self._normalize_statistics_state()
        self._flush_daily_stats(int(getattr(self.day_night, "jour", 0) or 0), include_partial=True)
        espece_name = getattr(self.espece, "nom", "") if self.espece else ""
        species_level = int(getattr(self.espece, "species_level", 1) or 1) if self.espece else 1
        days = int(getattr(self.day_night, "jour", 0) or 0)
        deaths = int(getattr(self, "species_death_count", 0) or 0)
        play_time = int(self.session_time_seconds or 0)
        tech_tree = getattr(self, "tech_tree", None)
        species = getattr(self, "espece", None)
        mutations = getattr(species, "mutations", None) if species else None
        mutation_ids = set()
        if species:
            mutation_ids.update(getattr(species, "base_mutations", []) or [])
        if mutations:
            mutation_ids.update(getattr(mutations, "actives", []) or [])

        max_pop = max(
            int(self._run_stats.get("max_population", 0) or 0),
            int(getattr(species, "population", 0) or 0),
        )
        total_pop = max(
            int(self._run_stats.get("total_population", 0) or 0),
            int(getattr(species, "population", 0) or 0),
        )
        self._run_stats["max_population"] = max_pop
        self._run_stats["total_population"] = total_pop
        self._run_stats["max_innovation"] = max(
            int(self._run_stats.get("max_innovation", 0) or 0),
            int(getattr(tech_tree, "innovations", 0) or 0),
        )

        return {
            "species_name": espece_name,
            "species_level": species_level,
            "days_survived": days,
            "deaths": deaths,
            "play_time_sec": play_time,
            "reason": reason,
            "animals_killed": int(self._run_stats.get("animals_killed", 0) or 0),
            "tech_unlocked": int(len(getattr(tech_tree, "unlocked", []) or [])),
            "resources_by_type": dict(self._run_stats.get("resources_by_type", {}) or {}),
            "max_population": max_pop,
            "total_population": total_pop,
            "max_innovation": int(self._run_stats.get("max_innovation", 0) or 0),
            "mutations_unlocked": int(len(mutation_ids)),
            "species_stats": self._collect_species_stats(species),
            "daily_stats": list(self._daily_stats),
        }

    def _compute_endgame_xp(self, summary: dict) -> int:
        species_level = int(summary.get("species_level", 1) or 1)
        days = int(summary.get("days_survived", 0) or 0)
        deaths = int(summary.get("deaths", 0) or 0)
        minutes = int(summary.get("play_time_sec", 0) or 0) // 60
        xp = species_level * 10 + days * 15 + minutes * 2 + deaths * 3
        return max(10, int(xp))

    def _trigger_end_game(self, reason: str):
        if self._game_end_pending:
            # Si on est encore dans PHASE1 malgré le flag, forcer l'écran de fin.
            if getattr(self.app, "state_key", None) == "PHASE1" and self._game_end_summary:
                self._endgame_debug(
                    f"trigger(reuse) reason={reason} pending={self._game_end_pending} "
                    f"entities={len(self.entities)} living={self._count_living_species_members()}"
                )
                self.app.change_state(
                    "END_SCREEN",
                    summary=self._game_end_summary,
                    reason=self._game_end_reason or reason,
                    xp_gain=int(self._game_end_xp or 0),
                    save_path=self._save_path,
                )
            return
        self._game_end_pending = True
        self._game_end_reason = reason
        summary = self._build_endgame_summary(reason)
        xp_gain = self._compute_endgame_xp(summary)
        self._game_end_summary = summary
        self._game_end_xp = int(xp_gain)
        self._endgame_debug(
            f"trigger(new) reason={reason} entities={len(self.entities)} "
            f"living={self._count_living_species_members()} xp={xp_gain}"
        )
        self.app.change_state(
            "END_SCREEN",
            summary=summary,
            reason=reason,
            xp_gain=xp_gain,
            save_path=self._save_path,
        )

    def _handle_entity_death(self, ent):
        if getattr(ent, "_dead_processed", False):
            return
        death_i = int(getattr(ent, "x", 0) or 0)
        death_j = int(getattr(ent, "y", 0) or 0)
        ent._dead_processed = True
        if getattr(ent, "_shelter_resting", False):
            self._leave_shelter(ent)
        self._stop_entity_combat(ent, stop_motion=False)

        for other in list(self.entities):
            if other is ent:
                continue
            if getattr(other, "_combat_target", None) is ent:
                self._stop_entity_combat(other)

        if hasattr(ent, "comportement"):
            try:
                ent.comportement.cancel_work("death")
            except Exception:
                pass

        if hasattr(ent, "espece"):
            try:
                ent.espece.remove_individu(ent)
            except Exception:
                pass

        if ent in self.entities:
            self.entities.remove(ent)

        if self.joueur is ent:
            self.joueur = self.entities[0] if self.entities else None

        add_notification(f"{getattr(ent, 'nom', 'Un individu')} est mort.")

        if getattr(ent, "espece", None) == self.espece:
            self._drop_species_corpse(death_i, death_j)
            self._reset_belligerant_kill_streak("La ferveur belligerante retombe apres une perte.")
            self.species_death_count += 1
            self._stats_current_day["deaths"] = int(self._stats_current_day.get("deaths", 0) or 0) + 1
            survivors = self._count_living_species_members()
            self._run_stats["max_population"] = max(int(self._run_stats.get("max_population", 0) or 0), survivors)
            self.death_event_ready = self.species_death_count == 1 and survivors > 0
            self.event_manager.runtime_flags["species_survivors"] = survivors
            self.event_manager.runtime_flags["species_death_count"] = self.species_death_count

            if self.death_response_mode and self.species_death_count >= 2:
                self._apply_death_morale_effects()
            if survivors <= 0:
                if self._gameplay_ready:
                    self._endgame_debug(
                        f"death(last) ent={getattr(ent,'nom',None)} deaths={self.species_death_count} "
                        f"entities={len(self.entities)}"
                    )
                    self._trigger_end_game("Votre espece a disparu.")

    def is_craft_unlocked(self, craft_id: str | None) -> bool:
        if not craft_id:
            return False
        if craft_id == "Entrepot_primitif":
            return True
        if not self.has_built_warehouse():
            return False
        return craft_id in self.unlocked_crafts

    def unlock_craft(self, craft_id: str | None):
        if not craft_id:
            return
        if craft_id not in self.unlocked_crafts:
            self.unlocked_crafts.add(craft_id)
            craft_def = self.craft_system.crafts.get(craft_id, {})
            label = craft_def.get("name", craft_id)
            add_notification(f"Craft débloqué : {label}")
        if self.bottom_hud:
            self.bottom_hud.refresh_craft_buttons()

    # ---------- FAUNE ----------
    def _rabbit_definition(self) -> PassiveFaunaDefinition:
        return rabbit_definition()

    def _fauna_definition_catalog(self) -> dict[str, PassiveFaunaDefinition]:
        return fauna_definition_catalog()

    def get_fauna_definition(self, species_id: str | None) -> Optional[PassiveFaunaDefinition]:
        return resolve_fauna_definition(species_id)

    def _init_fauna_species(self, definition: PassiveFaunaDefinition | None = None):
        if definition is None:
            definition = self._rabbit_definition()
        key = definition.species_name
        if key not in self.fauna_species_by_name:
            factory = PassiveFaunaFactory(self, self.assets, definition)
            self.fauna_species_by_name[key] = factory.create_species()
        species = self.fauna_species_by_name[key]
        if self.fauna_species is None:
            self.fauna_species = species
        return species

    # ---------- WORLD LIFECYCLE ----------
    def enter(self, **kwargs):
        self._perf_update_settings()
        self._perf_trace_frames = 120 if self._perf_logs_enabled else 0
        requested_save_path = kwargs.get("save_path")
        load_save = bool(kwargs.get("load_save", False))
        source = "new_world"
        if load_save:
            source = "load_save"
        elif kwargs.get("world", None) is not None:
            source = "loading_state_world"
        perf = self._perf_enter_start(source)

        # Toujours repartir sur un etat propre avant d'appliquer une sauvegarde
        # ou de generer un nouveau monde.
        self._reset_session_state()
        self._perf_enter_mark(perf, "Etat de session reset")
        if requested_save_path:
            self._save_path = str(requested_save_path)
        elif load_save:
            self._save_path = SaveManager.latest_save_path()
        else:
            self._save_path = SaveManager.create_new_save_path()
        self._perf_enter_mark(perf, f"Save slot actif = {self._save_path}")

        # 1) Si on demande explicitement de charger une sauvegarde et qu'elle existe
        if load_save and self.save_exists():
            self._perf_enter_mark(perf, "Sauvegarde detectee, tentative de chargement")
            if self.load():
                self._perf_enter_mark(perf, "Sauvegarde chargee")
                if self.espece and not self.bottom_hud:
                    self.bottom_hud = BottomHUD(self, self.espece, self.day_night)
                    self._perf_enter_mark(perf, "BottomHUD cree depuis sauvegarde")
                if not self.fauna_species:
                    self._init_fauna_species()
                    self._perf_enter_mark(perf, "Espece faune initialisee depuis sauvegarde")
                self._attach_phase_to_entities()
                if self.espece and getattr(self.espece, "main_class", None):
                    self.class_state["main_class"] = getattr(self.espece, "main_class", None)
                self._bootstrap_run_statistics()
                self._normalize_statistics_state()
                self._ensure_weather_system()
                self._refresh_craft_gate_state(force=True)
                self._gameplay_ready = True
                self._endgame_debug(
                    f"enter(load) entities={len(self.entities)} species={getattr(self.espece,'nom',None)} "
                    f"living={self._count_living_species_members()} pending={self._game_end_pending}"
                )
                self._perf_enter_mark(perf, "Entites rattachees a la phase")
                self._set_cursor(self.default_cursor_path)
                self._perf_enter_mark(perf, "Curseur initialise, entree terminee (save)")
                return
            self._perf_enter_mark(perf, "Echec chargement sauvegarde, fallback creation")

        # 2) Si le loader nous a deja donne un monde et des params -> on les utilise
        pre_world = kwargs.get("world", None)
        pre_params = kwargs.get("params", None)

        if pre_world is not None:
            self.world = pre_world
            self._perf_enter_mark(perf, "Monde pre-genere recu")
            # si params non fournis, tente d'heriter depuis le world, sinon on garde self.params tel quel
            self.params = pre_params or getattr(pre_world, "params", None) or self.params
            self._perf_enter_mark(perf, "Params associes au monde")
            self.view.set_world(self.world)
            self._perf_enter_mark(perf, "World injecte dans la vue")

            # s'assurer qu'on a un joueur (si on n'a pas charge une save)
            if not self.joueur:
                try:
                    sx, sy = self.world.spawn
                except Exception:
                    sx, sy = 0, 0
                if not self._is_walkable(int(sx), int(sy), generate=False):
                    fallback_spawn = self._find_nearest_walkable((int(sx), int(sy)), max_radius=16)
                    if fallback_spawn:
                        sx, sy = fallback_spawn
                self._perf_enter_mark(perf, f"Point de spawn resolu ({sx}, {sy})")
                from Game.species.species import Espece
                self.espece = Espece("Hominidé")
                self._perf_enter_mark(perf, "Espece joueur creee")
                self._apply_species_creation_to_espece()
                self._perf_enter_mark(perf, "Parametres de creation espece appliques")
                self._apply_base_mutations_to_species()
                self._perf_enter_mark(perf, "Mutations de base appliquees a l'espece")
                self.joueur = self.espece.create_individu(
                    x=float(sx),
                    y=float(sy),
                    assets=self.assets,
                )
                self._perf_enter_mark(perf, "Joueur principal cree")

                self.joueur2 = self.espece.create_individu(
                    x=float(sx + 1),
                    y=float(sy + 1),
                    assets=self.assets,
                )
                self._perf_enter_mark(perf, "Joueur secondaire cree")
                self._apply_base_mutations_to_individus()
                self._perf_enter_mark(perf, "Mutations appliquees aux individus")
                self.entities = [self.joueur, self.joueur2]
                self._init_fauna_species()
                self._perf_enter_mark(perf, "Espece faune initialisee")
                self._attach_phase_to_entities()
                self._bootstrap_run_statistics()
                self._perf_enter_mark(perf, "Entites rattachees a la phase")
            if self.bottom_hud is None:
                self.bottom_hud = BottomHUD(self, self.espece, self.day_night)
                self._perf_enter_mark(perf, "BottomHUD cree")
            else:
                self.bottom_hud.species = self.espece
                self._perf_enter_mark(perf, "BottomHUD espece mise a jour")
            self._perf_enter_mark(perf, "Entree terminee (monde pre-genere)")            
            self._ensure_weather_system()
            self._seed_corruption_for_new_world()
            self._gameplay_ready = True
            self._endgame_debug(
                f"enter(pre_world) entities={len(self.entities)} species={getattr(self.espece,'nom',None)} "
                f"living={self._count_living_species_members()} pending={self._game_end_pending}"
            )
            return  # IMPORTANT: on ne tente pas de regenerer ni de charger un preset

        # 3) Sinon, generation classique depuis un preset (avec fallback)
        # Par defaut on part sur "Custom".
        preset = kwargs.get("preset") or "Custom"
        seed_override = kwargs.get("seed", None)
        progress_cb = kwargs.get("progress", None)
        self._perf_enter_mark(perf, f"Generation locale via preset={preset}, seed={seed_override}")
        try:
            self.params = load_world_params_from_preset(preset)
            self._perf_enter_mark(perf, "Preset charge")
        except KeyError as ke:
            print(f"[Phase1] {ke} -> tentative de fallback de preset...")
            self._perf_enter_mark(perf, "Preset introuvable, fallback en cours")
            for candidate in ("Custom", "custom", "Default", "default", "Tempere", "Neutre", "Temperate"):
                try:
                    self.params = load_world_params_from_preset(candidate)
                    print(f"[Phase1] Fallback preset = {candidate}")
                    self._perf_enter_mark(perf, f"Fallback preset charge ({candidate})")
                    break
                except Exception:
                    pass
            if self.params is None:
                raise

        import traceback

        try:
            world = self.gen.generate_planet(self.params, rng_seed=seed_override, progress=progress_cb)
            self._perf_enter_mark(perf, "Monde genere en local")
        except Exception:
            traceback.print_exc()
            raise
        self.world = world
        self.view.set_world(self.world)
        self._perf_enter_mark(perf, "Monde affecte a la vue")
        if self.fog is None:
            self.fog = FogOfWar(self.world.width, self.world.height, chunk_size=64)
            self._perf_enter_mark(perf, "FogOfWar initialise")
        self.view.fog = self.fog

        self.view.set_world(self.world)
        self._perf_enter_mark(perf, "Vue rafraichie avec fog")

        try:
            sx, sy = self.world.spawn
        except Exception:
            sx, sy = 0, 0
        if not self._is_walkable(int(sx), int(sy), generate=False):
            fallback_spawn = self._find_nearest_walkable((int(sx), int(sy)), max_radius=16)
            if fallback_spawn:
                sx, sy = fallback_spawn
        self._perf_enter_mark(perf, f"Point de spawn resolu ({sx}, {sy})")
        if not self.joueur:
            from Game.species.species import Espece
            self.espece = Espece("Hominidé")
            self._perf_enter_mark(perf, "Espece joueur creee")
            self._apply_species_creation_to_espece()
            self._perf_enter_mark(perf, "Parametres de creation espece appliques")
            self._apply_base_mutations_to_species()
            self._perf_enter_mark(perf, "Mutations de base appliquees a l'espece")
            self.joueur = self.espece.create_individu(
                x=float(sx),
                y=float(sy),
                assets=self.assets,
            )
            self._perf_enter_mark(perf, "Joueur principal cree")
            self.joueur2 = self.espece.create_individu(
                x=float(sx + 1),
                y=float(sy + 1),
                assets=self.assets,
            )
            self._perf_enter_mark(perf, "Joueur secondaire cree")
            self._apply_base_mutations_to_individus()
            self._perf_enter_mark(perf, "Mutations appliquees aux individus")
            self.entities = [self.joueur, self.joueur2]
            self._init_fauna_species()
            self._perf_enter_mark(perf, "Espece faune initialisee")
            self._attach_phase_to_entities()
            self._bootstrap_run_statistics()
            self._perf_enter_mark(perf, "Entites rattachees a la phase")
            self._ensure_move_runtime(self.joueur)
            self._ensure_move_runtime(self.joueur2)
            for e in self.entities:
                self._ensure_move_runtime(e)
            self._perf_enter_mark(perf, "Runtime de mouvement initialise")
        if self.bottom_hud is None:
            self.bottom_hud = BottomHUD(self, self.espece, self.day_night)
            self._perf_enter_mark(perf, "BottomHUD cree")
        else:
            self.bottom_hud.species = self.espece
            self._perf_enter_mark(perf, "BottomHUD espece mise a jour")
        self._set_cursor(self.default_cursor_path)
        self._perf_enter_mark(perf, "Curseur initialise")
        self._ensure_weather_system()
        self._seed_corruption_for_new_world()
        self._refresh_craft_gate_state(force=False)
        self._gameplay_ready = True
        self._endgame_debug(
            f"enter(new) entities={len(self.entities)} species={getattr(self.espece,'nom',None)} "
            f"living={self._count_living_species_members()} pending={self._game_end_pending}"
        )

    def _control_key(self, path: str, fallback: int) -> int:
        settings = getattr(self.app, "settings", None)
        if settings is None:
            return int(fallback)
        raw = settings.get(path, fallback)
        try:
            return int(raw)
        except Exception:
            return int(fallback)

    def _control_keys(self) -> dict[str, int]:
        return {
            "props_transparency": self._control_key("controls.props_transparency", pygame.K_h),
            "inspect_mode": self._control_key("controls.inspect_mode", pygame.K_i),
            "focus_nearest": self._control_key("controls.focus_nearest", pygame.K_SPACE),
            "map_toggle": self._control_key("controls.map_toggle", pygame.K_m),
        }

    # ---------- INPUT ----------
    def handle_input(self, events):
        controls = self._control_keys()
        key_props = controls["props_transparency"]
        key_inspect = controls["inspect_mode"]
        key_focus = controls["focus_nearest"]
        key_map = controls["map_toggle"]

        if self.espece and self.espece.lvl_up.active:
            for e in events:
                self.espece.lvl_up.handle_event(e, self.screen)
            return

        # Le menu latéral a priorité : s'il est ouvert il consomme tout l'input.
        if self.right_hud and self.right_hud.handle(events):
            return

        # Le HUD du bas ne doit pas rester interactif pendant une pause
        # ou quand un menu en jeu est ouvert.
        if self.bottom_hud is not None and not self.paused and not self.ui_menu_open:
            self.bottom_hud.handle(events)

        for e in events:
            # Fenêtres d'information : priorité de gestion
            consumed = False
            for win in list(self.info_windows):
                if win.closed:
                    self.info_windows.remove(win)
                    continue
                if win.handle_event(e):
                    consumed = True
                    break
            if consumed:
                continue

            if self.rename_active:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        self._commit_rename()
                    elif e.key == pygame.K_ESCAPE:
                        self._cancel_rename()
                    elif e.key == pygame.K_BACKSPACE:
                        self.rename_value = self.rename_value[:-1]
                    else:
                        if e.unicode and len(self.rename_value) < self.rename_max_length:
                            if e.unicode.isprintable():
                                self.rename_value += e.unicode
                continue

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.paused and self._pause_achievements_open:
                        self._pause_achievements_open = False
                    else:
                        self.paused = not self.paused
                        if not self.paused:
                            self._pause_achievements_open = False
                elif e.key == key_focus:
                    self._focus_camera_on_nearest_species_member()
                elif e.key == key_map:
                    self.minimap_visible = not self.minimap_visible
                    if self.minimap_visible:
                        self._minimap_refresh_cd = 0.0
                        self._update_minimap_cache(0.0, force=True)
                elif e.key == pygame.K_F6:
                    self._ensure_weather_system()
                    if self.weather_system:
                        self.weather_system.force_weather("rain", duration_minutes=30.0)
                        add_notification("Meteo forcee : pluie")
                elif e.key == key_props:
                    self.props_transparency_active = True
                    self.view.set_props_transparency(True)
                elif e.key == key_inspect:
                    self.inspect_mode_active = True
                    self._set_cursor(self.inspect_cursor_path)
                elif e.key == pygame.K_n:
                    ent = None
                    if self.selected_entities:
                        ent = self.selected_entities[0]
                    elif self.selected and self.selected[0] == "entity":
                        ent = self.selected[1]
                    if ent is not None:
                        self.start_rename_target(ent)

            elif e.type == pygame.KEYUP and e.key == key_props:
                self.props_transparency_active = False
                self.view.set_props_transparency(False)
            elif e.type == pygame.KEYUP and e.key == key_inspect:
                self.inspect_mode_active = False
                self._set_cursor(self.default_cursor_path)

            if not self.paused:
                if e.type == pygame.MOUSEWHEEL:
                    mouse_pos = pygame.mouse.get_pos()
                    if self._is_point_over_minimap(mouse_pos):
                        self._zoom_minimap(int(getattr(e, "y", 0) or 0))
                        continue
                    if self._ui_captures_click(mouse_pos):
                        continue
                self.view.handle_event(e)

                # --- CLIC GAUCHE ---
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    keys_state = pygame.key.get_pressed()

                    # 1) Mode "placement de craft"
                    if self.selected_craft is not None:
                        tile = None
                        if not self.is_craft_unlocked(self.selected_craft):
                            add_notification("Ce plan n'est pas débloqué.")
                            self.selected_craft = None
                            self._reset_drag_selection()
                            return
                        if self.selected_craft == "Entrepot_primitif" and self.warehouse_exists_or_planned(force_scan=True):
                            add_notification("Tu ne peux avoir qu'un seul entrepôt.")
                            self.selected_craft = None
                            self._reset_drag_selection()
                            return
                        hit = self.view.pick_at(mx, my)
                        if hit:
                            kind, payload = hit
                            if kind == "tile":
                                tile = payload              # (i, j)
                            elif kind == "prop":
                                i, j, _pid = payload
                                tile = (i, j)

                        if tile is None:
                            tile = self._fallback_pick_tile(mx, my)

                        if tile is not None and self.joueur and self.world:
                            if not self._tile_is_visible(tile):
                                add_notification("Tuile hors du champ de vision.")
                                return
                            self._clear_species_corpse(int(tile[0]), int(tile[1]))
                            result = self.craft_system.craft_item(
                                craft_id=self.selected_craft,
                                builder=self.joueur,
                                world=self.world,
                                tile=tile,
                                notify=add_notification,
                                storage=self.warehouse,
                            )
                            if result:
                                self._register_construction_site(result)
                                self.selected_craft = None  # on sort du mode placement
                        self._reset_drag_selection()
                        return  # on ne fait pas la logique de sélection classique

                    if handle_inspection_panel_click(self, (mx, my), self.screen):
                        self._ui_click_blocked = True
                        self._reset_drag_selection()
                        continue

                    if self._ui_captures_click((mx, my)):
                        self._ui_click_blocked = True
                        self._reset_drag_selection()
                        continue

                    if keys_state[key_inspect]:
                        hit = self.view.pick_at(mx, my)
                        if hit and hit[0] == "prop":
                            self._describe_craft_prop(hit[1])
                            self._reset_drag_selection()
                            continue

                    self._ui_click_blocked = False
                    self._dragging_selection = True
                    self._drag_select_start = (mx, my)
                    self._drag_select_rect = pygame.Rect(mx, my, 0, 0)

                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    mx, my = e.pos
                    if self._ui_click_blocked:
                        self._ui_click_blocked = False
                        self._reset_drag_selection()
                        continue
                    if self.selected_craft is not None:
                        self._reset_drag_selection()
                        continue
                    if self._dragging_selection and self._drag_select_start:
                        rect = self._drag_select_rect
                        if rect and (rect.width > self._drag_threshold or rect.height > self._drag_threshold):
                            self._select_entities_in_rect(rect)
                        else:
                            self._handle_single_left_click(mx, my)
                    else:
                        self._handle_single_left_click(mx, my)
                    self._reset_drag_selection()

                elif e.type == pygame.MOUSEMOTION and self._dragging_selection:
                    self._update_drag_rect(e.pos)

                # --- CLIC DROIT = ORDRE DE DÉPLACEMENT (si une créature est sélectionnée) ---
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    self.selected_craft = None
                    entities = self._get_order_entities()
                    if not entities:
                        continue
                    mx, my = pygame.mouse.get_pos()
                    hit = self.view.pick_at(mx, my)
                    harvest_mode = pygame.key.get_pressed()[pygame.K_d]
                    self._issue_order_to_entities(entities, hit, harvest_mode, (mx, my))



            if self.paused:
                if self._pause_achievements_open:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                        self._pause_ach_scroll += 40
                    elif e.type == pygame.KEYDOWN and e.key in (pygame.K_UP, pygame.K_PAGEUP):
                        self._pause_ach_scroll -= 40
                    elif e.type == pygame.MOUSEWHEEL:
                        self._pause_ach_scroll -= int(e.y * 40)
                    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        if self._pause_ach_back_rect and self._pause_ach_back_rect.collidepoint(e.pos):
                            self._pause_achievements_open = False
                    self._pause_ach_scroll = max(0, min(self._pause_ach_scroll, self._pause_ach_max_scroll))
                    continue

                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.end_run_button_rect and self.end_run_button_rect.collidepoint(e.pos):
                        self.paused = False
                        self._trigger_end_game("Partie terminee par le joueur.")
                        return
                    if self.achievements_button_rect and self.achievements_button_rect.collidepoint(e.pos):
                        self._update_achievements()
                        self._pause_achievements_open = True
                        self._pause_ach_scroll = 0
                        continue
                    if self.menu_button_rect and self.menu_button_rect.collidepoint(e.pos):
                        self.paused = False  # pour eviter que le rendu de pause bloque tout

                        # --- Sauvegarde avant retour au menu ---
                        try:
                            ok = self.save()
                            if ok:
                                self.save_message = "Sauvegarde effectuee !"
                            else:
                                print("[Phase1] Sauvegarde echouee.")
                                self.save_message = "Erreur de sauvegarde."
                        except Exception as ex:
                            print(f"[Phase1] Erreur lors de la sauvegarde: {ex}")
                            self.save_message = "Erreur de sauvegarde."

                        self.save_message_timer = 2.5
                        pygame.display.flip()  # force un dernier rendu avant de changer d'etat
                        pygame.time.wait(300)

                        # --- Quitte proprement vers le menu principal ---
                        self.app.change_state("MENU")
                        return


    # ---------- UPDATE ----------
    def update(self, dt: float):
        t0 = time.perf_counter()
        t_last = t0
        should_trace = self._perf_logs_enabled and self._perf_trace_frames > 0

        def mark(label: str):
            nonlocal t_last
            if not should_trace:
                return
            now_t = time.perf_counter()
            print(f"[Perf][Phase1][Update] {label} | +{now_t - t_last:.3f}s | total {now_t - t0:.3f}s")
            t_last = now_t

        mark("Debut frame update")
        if self.espece and self.espece.lvl_up.active:
            mark("Sortie rapide lvl_up actif")
            if self._perf_trace_frames > 0:
                self._perf_trace_frames -= 1
            return
        self._sync_tech_tree_main_class()
        if bool(getattr(self, "_tech_effects_dirty", False)):
            self._recompute_tech_effects()
        if self.paused or self.ui_menu_open:
            # Meme en pause on continue les timers d'evenements
            if self.quest_manager:
                self.quest_manager.update(dt)
            self.event_manager.update(dt, self)
            mark("Sortie rapide pause/menu")
            if self._perf_trace_frames > 0:
                self._perf_trace_frames -= 1
            return

        self.session_time_seconds += dt

        self._update_frame_id += 1
        if self.quest_manager:
            self.quest_manager.update(dt)
        mark("Quest manager update")
        self.event_manager.update(dt, self)
        mark("Event manager update")

        # Mettre a jour le cycle jour/nuit
        self.day_night.update(dt)
        self._run_stats["max_innovation"] = max(
            int(self._run_stats.get("max_innovation", 0) or 0),
            int(getattr(getattr(self, "tech_tree", None), "innovations", 0) or 0),
        )
        if self.weather_system and self.joueur:
            self.weather_system.update(
                dt,
                int(self.joueur.x),
                int(self.joueur.y),
            )
        self._update_horde_state()
        self._update_weather_vfx(dt)
        self._update_corruption(dt)
        mark("Day/night update")

        if self.tech_tree:
            current_day = int(self.day_night.jour)
            if current_day > self._last_innovation_day:
                for _ in range(current_day - self._last_innovation_day):
                    self.tech_tree.add_innovation(1)
                self._last_innovation_day = current_day
            self._flush_daily_stats(current_day)
        mark("Tech tree update")

        if self.espece and getattr(self.espece, "reproduction_system", None):
            try:
                self.espece.reproduction_system.update(dt)
            except Exception as e:
                print(f"[Reproduction] update error: {e}")
        mark("Reproduction update")

        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)
        self._update_minimap_cache(dt)
        mark("Vue update")

        def get_radius(ent):
            if getattr(ent, "is_egg", False):
                return 1
            vision = ent.sens.get("vision", 5)
            return max(2, int(1 + vision * 0.7))

        if self.fog:
            light_level = self.day_night.get_light_level(min_light=0.08)
            nv01 = float(self._player_night_vision01())
            if nv01 > 0:
                light_level = min(1.0, float(light_level) + (1.0 - float(light_level)) * 0.35 * nv01)

            # Reduction de visibilite par la meteo
            if self.weather_system:
                visibility_mult = self.weather_system.get_visibility_multiplier()
                light_level *= visibility_mult

            observers = [
                e
                for e in self.entities
                if not getattr(e, "is_egg", False)
                and not getattr(e, "is_fauna", False)
            ]
            self.fog.recompute(observers, get_radius, light_level)
            mark(f"Fog recompute (observers={len(observers)})")
        else:
            self.fog = FogOfWar(self.world.width, self.world.height, chunk_size=64)
            mark("Fog recreate")
        self.view.fog = self.fog

        if self.fauna_spawner:
            self.fauna_spawner.update(dt, self)
        mark("Fauna spawner update")

        self._update_campfires(dt)
        self._update_water_collectors(dt)
        self._update_gardens(dt)
        self._update_group_supply(dt)
        mark("Group supply update")

        dead_entities: list = []
        for e in list(self.entities):
            if getattr(e, "is_egg", False):
                continue
            self._ensure_move_runtime(e)
            e._combat_recent_timer = max(0.0, float(getattr(e, "_combat_recent_timer", 0.0) or 0.0) - float(dt))
            self._update_entity_movement(e, dt)
            if hasattr(e, "comportement"):
                e.comportement.update(dt, self.world)
            self._update_entity_combat(e, dt)
            self._update_entity_passive_regen(e, dt)
            self._update_entity_auto_mode(e, dt)
            if e.jauges.get("sante", 0) <= 0:
                dead_entities.append(e)
        mark(f"Entities update loop (count={len(self.entities)})")

        for ent in dead_entities:
            self._handle_entity_death(ent)
        mark(f"Entity deaths handled (count={len(dead_entities)})")

        if self.espece and self._count_living_species_members() <= 0:
            self._trigger_end_game("Votre espece a disparu.")
            return

        self._update_construction_sites()
        self._warehouse_gate_probe_cd = max(0.0, float(self._warehouse_gate_probe_cd) - dt)
        if self._warehouse_gate_probe_cd <= 0.0:
            self._refresh_craft_gate_state()
            self._warehouse_gate_probe_cd = 0.75
        mark("Construction sites update")

        if self.save_message_timer > 0:
            self.save_message_timer -= dt
            if self.save_message_timer <= 0:
                self.save_message = ""

        self._update_achievements()

        total = time.perf_counter() - t0
        if self._perf_logs_enabled and (should_trace or total >= self._perf_slow_frame_sec):
            print(f"[Perf][Phase1][Update] Fin frame | total {total:.3f}s | entities={len(self.entities)}")
        if self._perf_trace_frames > 0:
            self._perf_trace_frames -= 1

    def draw_pause_screen(self, screen):
            """Affiche l'écran de pause avec le bouton de retour au menu"""
            # Overlay semi-transparent
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            # Titre "PAUSE"
            font_title = pygame.font.SysFont(None, 60)
            text = font_title.render("PAUSE", True, (255, 255, 255))
            text_rect = text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 200))
            screen.blit(text, text_rect)
            
            # Boutons
            button_width = 320
            button_height = 60
            button_x = screen.get_width() / 2 - button_width / 2
            gap = 14
            total_h = button_height * 3 + gap * 2
            top_y = screen.get_height() / 2 - total_h / 2
            end_button_y = top_y
            achievements_button_y = top_y + button_height + gap
            menu_button_y = achievements_button_y + button_height + gap

            self.end_run_button_rect = pygame.Rect(button_x, end_button_y, button_width, button_height)
            self.achievements_button_rect = pygame.Rect(button_x, achievements_button_y, button_width, button_height)
            self.menu_button_rect = pygame.Rect(button_x, menu_button_y, button_width, button_height)

            mouse_pos = pygame.mouse.get_pos()
            font_button = pygame.font.SysFont(None, 36)

            for rect, label in (
                (self.end_run_button_rect, "Terminer la partie"),
                (self.achievements_button_rect, "Succes"),
                (self.menu_button_rect, "Retour au menu principal"),
            ):
                is_hover = rect.collidepoint(mouse_pos)
                button_color = (80, 80, 120) if is_hover else (60, 60, 90)
                border_color = (150, 150, 200) if is_hover else (100, 100, 150)

                pygame.draw.rect(screen, button_color, rect, border_radius=10)
                pygame.draw.rect(screen, border_color, rect, 3, border_radius=10)

                button_text = font_button.render(label, True, (255, 255, 255))
                button_text_rect = button_text.get_rect(center=rect.center)
                screen.blit(button_text, button_text_rect)

    def _build_achievement_session_context(self) -> dict:
        run_stats = getattr(self, "_run_stats", {}) or {}
        resources_by_type = run_stats.get("resources_by_type", {})
        total_resources = 0
        if isinstance(resources_by_type, dict):
            for v in resources_by_type.values():
                try:
                    total_resources += int(v or 0)
                except Exception:
                    pass
        return {
            "days_survived": int(getattr(self.day_night, "jour", 0) or 0),
            "animals_killed": int(run_stats.get("animals_killed", 0) or 0),
            "resources_collected": int(total_resources),
            "species_level": int(getattr(getattr(self, "espece", None), "species_level", 1) or 1),
            "session_time_seconds": int(self.session_time_seconds or 0),
        }

    def _update_achievements(self):
        prog = getattr(getattr(self, "app", None), "progression", None)
        if prog is None:
            return
        prog.update_achievements(self._build_achievement_session_context())

    def _draw_pause_achievements_menu(self, screen):
        prog = getattr(getattr(self, "app", None), "progression", None)
        if prog is None:
            return

        achievements = prog.get_achievements(sorted_list=True)
        W, H = screen.get_size()

        # assombrit la scene
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        title_size = clamp(int(H * 0.085), 34, 84)
        item_title_size = clamp(int(H * 0.030), 16, 32)
        item_size = clamp(int(H * 0.024), 12, 26)
        btn_size = clamp(int(H * 0.036), 16, 36)

        title_font = self.assets.get_font("MightySouly", title_size)
        item_title_font = self.assets.get_font("MightySouly", item_title_size)
        item_font = self.assets.get_font("KiwiSoda", item_size)
        btn_font = self.assets.get_font("MightySouly", btn_size)

        title_surf = title_font.render("Succes", True, (230, 230, 230))
        screen.blit(title_surf, (W // 2 - title_surf.get_width() // 2, max(24, int(H * 0.06))))

        margin = clamp(int(W * 0.10), 40, 140)
        top = clamp(int(H * 0.18), 90, 180)
        bottom = clamp(int(H * 0.18), 90, 180)
        panel_rect = pygame.Rect(
            margin,
            top,
            max(200, W - 2 * margin),
            max(160, H - top - bottom),
        )

        pygame.draw.rect(screen, (30, 38, 50), panel_rect, border_radius=14)
        pygame.draw.rect(screen, (90, 110, 140), panel_rect, width=2, border_radius=14)

        if not achievements:
            empty = item_font.render("Aucun succes pour le moment.", True, (130, 140, 150))
            screen.blit(empty, (panel_rect.centerx - empty.get_width() // 2, panel_rect.centery - empty.get_height() // 2))
        else:
            pad = 16
            line_gap = 4
            card_gap = 10
            title_h = item_title_font.get_height()
            line_h = item_font.get_height()
            card_h = pad * 2 + title_h + (line_h * 2) + (line_gap * 2)

            content_h = len(achievements) * (card_h + card_gap) - card_gap
            self._pause_ach_max_scroll = max(0, content_h - (panel_rect.height - pad * 2))
            self._pause_ach_scroll = max(0, min(self._pause_ach_scroll, self._pause_ach_max_scroll))

            prev_clip = screen.get_clip()
            screen.set_clip(panel_rect)

            y = panel_rect.y + pad - self._pause_ach_scroll
            for ach in achievements:
                if y > panel_rect.bottom:
                    break

                unlocked = bool(ach.get("unlocked", False))
                card_bg = (58, 78, 104) if unlocked else (36, 44, 56)
                txt_title = (235, 235, 235) if unlocked else (170, 170, 170)
                txt_body = (210, 215, 220) if unlocked else (150, 155, 165)

                rect = pygame.Rect(panel_rect.x + pad, y, panel_rect.width - pad * 2, card_h)
                if rect.bottom >= panel_rect.y and rect.top <= panel_rect.bottom:
                    pygame.draw.rect(screen, card_bg, rect, border_radius=10)
                    pygame.draw.rect(screen, (90, 110, 140), rect, width=1, border_radius=10)

                    title_txt = str(ach.get("title") or "Succes")
                    desc_txt = str(ach.get("description") or "")
                    progress = int(ach.get("progress", 0) or 0)
                    unlocked_txt = "Oui" if unlocked else "Non"
                    date_txt = str(ach.get("unlocked_at") or "")
                    status_line = f"Progression: {progress}%  |  Debloque: {unlocked_txt}"
                    if unlocked and date_txt:
                        status_line += f"  |  Date: {date_txt}"

                    ts = item_title_font.render(title_txt, True, txt_title)
                    ds = item_font.render(desc_txt, True, txt_body)
                    ss = item_font.render(status_line, True, txt_body)

                    tx = rect.x + pad
                    ty = rect.y + pad
                    screen.blit(ts, (tx, ty))
                    screen.blit(ds, (tx, ty + title_h + line_gap))
                    screen.blit(ss, (tx, ty + title_h + line_gap + line_h + line_gap))

                y += card_h + card_gap

            screen.set_clip(prev_clip)

            if self._pause_ach_scroll < self._pause_ach_max_scroll:
                hint = item_font.render("Faites defiler pour voir plus.", True, (130, 140, 150))
                screen.blit(hint, (panel_rect.centerx - hint.get_width() // 2, panel_rect.bottom - hint.get_height() - 8))

        # bouton retour
        back_text = btn_font.render("Retour", True, (230, 230, 230))
        back_rect = back_text.get_rect(center=(W // 2, H - max(50, int(H * 0.08))))
        self._pause_ach_back_rect = back_rect.inflate(24, 12)

        mouse_pos = pygame.mouse.get_pos()
        is_hover = self._pause_ach_back_rect.collidepoint(mouse_pos)
        if is_hover:
            pygame.draw.rect(screen, (60, 60, 90), self._pause_ach_back_rect, border_radius=10)
            pygame.draw.rect(screen, (150, 150, 200), self._pause_ach_back_rect, 2, border_radius=10)
        screen.blit(back_text, back_rect)

    # ---------- RENDER ----------
    def render(self, screen: pygame.Surface):
        screen.fill((10, 12, 18))
        self.view.begin_hitframe()
        
        # 1) Rendu carte + entités
        self.view.render(screen, world_entities=self.entities)

        self._draw_construction_bars(screen)
        dx, dy, wall_h = self.view._proj_consts()
        for ent in self.entities:
            visible, explored = self._tile_fog_state((int(ent.x), int(ent.y)))
            if not explored:
                continue
            self._draw_fauna_health_bar(screen, ent)
            self._draw_species_health_bar(screen, ent)
            draw_work_bar(self, screen, ent)
            if not visible:
                continue

            renderer = getattr(ent, "renderer", None)
            if renderer is None and hasattr(ent, "espece"):
                renderer = getattr(ent.espece, "renderer", None)

            sprite, rect = None, None
            if renderer and hasattr(renderer, "get_draw_surface_and_rect"):
                try:
                    sprite, rect = renderer.get_draw_surface_and_rect(
                        self.view, self.world, ent.x, ent.y
                    )
                except Exception:
                    sprite, rect = None, None

            if rect is None:
                continue

            mask = self.view._mask_for_surface(sprite) if sprite is not None else None
            self.view.push_hit("entity", ent, rect, mask)

        if self.espece and self.espece.lvl_up.active:
            self.espece.lvl_up.render(screen, self.assets)
            return

        # 2) Appliquer le filtre jour/nuit sur TOUT ce qui est déjà dessiné
        self.apply_day_night_lighting(screen)
        self._draw_weather_effects(screen)
        #2bis)
        if not self.paused and not self.ui_menu_open:
            self._draw_group_supply_hud(screen)
            self._draw_weather_hud(screen)
            self._draw_species_minimap(screen)

        # 2bis) Sélection rectangle (drag)
        self._draw_selection_box(screen)

        # 3) Marqueur de sélection
        self._draw_selection_marker(screen)
        self._draw_hover_entity_name(screen)

        # 4) HUD / pause / notifications
        if self.paused and not self.ui_menu_open:
            if self._pause_achievements_open:
                self._draw_pause_achievements_menu(screen)
            else:
                self.draw_pause_screen(screen)

        if not self.paused and not self.ui_menu_open:
            draw_inspection_panel(self, screen)

        if not self.paused and not self.ui_menu_open and self.bottom_hud is not None:
            self.bottom_hud.draw(screen)

        # HUD droite : toujours visible (et affiche le menu si ouvert)
        if not self.paused and self.right_hud:
            self.right_hud.draw(screen)

        if self.save_message:
            add_notification(self.save_message)
            self.save_message = None

        # Fenêtres d'information
        if self.info_windows:
            for win in list(self.info_windows):
                if win.closed:
                    self.info_windows.remove(win)
                    continue
                win.draw(screen)


    # ---------- SELECTION HELPERS ----------
    def _entity_screen_rect(self, ent) -> Optional[pygame.Rect]:
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return None
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        rect = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return rect

    def _set_selected_entities(self, entities: list) -> None:
        valid = [e for e in entities if e in self.entities and not getattr(e, "is_fauna", False)]
        self.selected_entities = valid
        if valid:
            self.selected = ("entity", valid[0])
            if self.rename_active and self.rename_target is not valid[0]:
                self._cancel_rename()
        elif self.selected and self.selected[0] == "entity":
            self.selected = None
        if not self.selected and not self.selected_entities:
            self.info_windows = []

    def start_rename_target(self, ent) -> None:
        if ent is None or getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
            return
        if getattr(ent, "name_locked", False):
            return
        self.rename_active = True
        self.rename_target = ent
        self.rename_value = getattr(ent, "nom", "") or ""

    def _commit_rename(self) -> None:
        target = self.rename_target
        if target is None:
            self._cancel_rename()
            return
        new_name = (self.rename_value or "").strip()
        if not new_name:
            self._cancel_rename()
            return
        if hasattr(target, "set_name"):
            target.set_name(new_name, locked=False)
        else:
            target.nom = new_name
        add_notification(f"Nom mis à jour : {target.nom}")
        self._cancel_rename()

    def _cancel_rename(self) -> None:
        self.rename_active = False
        self.rename_target = None
        self.rename_value = ""

    def _select_entities_in_rect(self, rect: pygame.Rect) -> None:
        selected = []
        for ent in self.entities:
            er = self._entity_screen_rect(ent)
            if not er:
                continue
            if rect.colliderect(er) and rect.collidepoint(er.center):
                selected.append(ent)
        self._set_selected_entities(selected)
        if not selected:
            self.selected = None

    def _reset_drag_selection(self):
        self._dragging_selection = False
        self._drag_select_start = None
        self._drag_select_rect = None

    def _update_drag_rect(self, pos: tuple[int, int]):
        if not self._dragging_selection or not self._drag_select_start:
            return
        sx, sy = self._drag_select_start
        ex, ey = pos
        x = min(sx, ex)
        y = min(sy, ey)
        w = abs(ex - sx)
        h = abs(ey - sy)
        self._drag_select_rect = pygame.Rect(x, y, w, h)

    def _ui_captures_click(self, pos: tuple[int, int]) -> bool:
        if inspection_panel_contains_point(self, pos, self.screen):
            return True
        if self._is_point_over_minimap(pos):
            return True
        if self.bottom_hud:
            if self.bottom_hud.context_menu and self.bottom_hud.context_menu.get("rect"):
                if self.bottom_hud.context_menu["rect"].collidepoint(pos):
                    return True
            if self.bottom_hud.visible and self.bottom_hud.panel_rect.collidepoint(pos):
                return True
        for win in self.info_windows:
            if not win.closed and win.rect.collidepoint(pos):
                return True
        return False

    def _set_cursor(self, image_path: str, hotspot=(0, 0)):
        app_cursor = getattr(self.app, "set_cursor_image", None)
        if callable(app_cursor):
            if app_cursor(image_path, hotspot=hotspot):
                return
        try:
            surf = pygame.image.load(image_path).convert_alpha()
            cursor = pygame.cursors.Cursor(hotspot, surf)
            pygame.mouse.set_cursor(cursor)
        except Exception as e:
            print("[Cursor] Erreur set_cursor_image:", e, "path=", image_path)

    def _get_order_entities(self) -> list:
        if self.selected_entities:
            return [e for e in self.selected_entities if e in self.entities and not getattr(e, "is_fauna", False)]
        if self.selected and self.selected[0] == "entity" and self.selected[1] in self.entities:
            if getattr(self.selected[1], "is_fauna", False):
                return []
            return [self.selected[1]]
        return []

    def _entity_inventory_weight(self, ent) -> float:
        total = 0.0
        for stack in getattr(ent, "carrying", []) or []:
            qty = float(stack.get("quantity", 0) or 0)
            unit_weight = float(stack.get("weight", 0) or 0)
            total += qty * unit_weight
        return total

    def _entity_inventory_is_full(self, ent) -> bool:
        limit = float(getattr(ent, "physique", {}).get("weight_limit", 10) or 10)
        if limit <= 0:
            return True
        return self._entity_inventory_weight(ent) >= max(0.0, limit - 0.05)

    def _auto_mark_failed_prop(self, ent, prop_target):
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return
        if not prop_target:
            return
        i, j, pid = prop_target
        ent.ia["auto_failed_prop"] = (int(i), int(j), str(pid))

    def _auto_is_failed_prop(self, ent, prop_target) -> bool:
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return False
        blocked = ent.ia.get("auto_failed_prop")
        if not blocked:
            return False
        i, j, pid = prop_target
        return tuple(blocked) == (int(i), int(j), str(pid))

    def _auto_find_nearest_harvestable_prop(self, ent, max_radius: int = 8):
        if not self.world:
            return None
        ex, ey = int(ent.x), int(ent.y)
        width, height = self.world.width, self.world.height

        for r in range(1, max_radius + 1):
            best = None
            best_dist = 1e9
            x0 = max(0, ex - r)
            x1 = min(width - 1, ex + r)
            y0 = max(0, ey - r)
            y1 = min(height - 1, ey + r)
            for j in range(y0, y1 + 1):
                for i in range(x0, x1 + 1):
                    if max(abs(i - ex), abs(j - ey)) != r:
                        continue
                    cell = self._get_construction_cell(i, j)
                    if not isinstance(cell, int) or cell not in _AUTO_HARVESTABLE_PROP_IDS:
                        continue
                    if self._auto_is_failed_prop(ent, (i, j, cell)):
                        continue
                    dist = abs(i - ex) + abs(j - ey)
                    if dist < best_dist:
                        best = (i, j, int(cell))
                        best_dist = dist
            if best is not None:
                return best
        return None

    def _auto_extract_warehouse_target(self, i: int, j: int):
        cell = self._get_construction_cell(i, j)
        if isinstance(cell, int):
            if int(cell) == 102:
                return (i, j, 102, "Entrepot_primitif")
            return None
        if not isinstance(cell, dict):
            return None

        craft_id = cell.get("craft_id")
        interaction = cell.get("interaction")
        interaction_type = interaction.get("type") if isinstance(interaction, dict) else None
        if interaction_type != "warehouse" and craft_id != "Entrepot_primitif":
            return None
        pid = int(cell.get("pid", 102) or 102)
        return (i, j, pid, craft_id or "Entrepot_primitif")

    def _auto_find_nearest_warehouse(self, ent, max_radius: int = 120):
        if not self.world:
            return None
        ex, ey = int(ent.x), int(ent.y)
        width, height = self.world.width, self.world.height

        for r in range(1, max_radius + 1):
            best = None
            best_dist = 1e9
            x0 = max(0, ex - r)
            x1 = min(width - 1, ex + r)
            y0 = max(0, ey - r)
            y1 = min(height - 1, ey + r)
            for j in range(y0, y1 + 1):
                for i in range(x0, x1 + 1):
                    if max(abs(i - ex), abs(j - ey)) != r:
                        continue
                    target = self._auto_extract_warehouse_target(i, j)
                    if not target:
                        continue
                    dist = abs(i - ex) + abs(j - ey)
                    if dist < best_dist:
                        best = target
                        best_dist = dist
            if best is not None:
                return best
        return None

    def _auto_order_harvest(self, ent, prop_target) -> bool:
        i, j, pid = prop_target
        target = self._find_nearest_walkable((i, j), forbidden=self._occupied_tiles(exclude=[ent]), ent=ent)
        if not target:
            return False
        objectif = ("prop", (i, j, pid))
        if self._same_prop_target(ent, ("prop", (i, j, pid))):
            return False
        return self._apply_entity_order(
            ent,
            target=target,
            etat="se_deplace_vers_prop",
            objectif=objectif,
            action_mode=None,
            craft_id=None,
        )

    def _auto_order_deposit(self, ent, warehouse_target) -> bool:
        i, j, pid, craft_id = warehouse_target
        target = self._find_nearest_walkable((i, j), forbidden=self._occupied_tiles(exclude=[ent]), ent=ent)
        if not target:
            return False
        return self._apply_entity_order(
            ent,
            target=target,
            etat="se_deplace_vers_prop",
            objectif=("prop", (i, j, pid)),
            action_mode="interact",
            craft_id=craft_id,
        )

    def _auto_next_step_tile(self, ent):
        ex, ey = int(ent.x), int(ent.y)
        occupied = self._occupied_tiles(exclude=[ent])
        directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        start_dir = int(ent.ia.get("auto_walk_dir", 0) or 0) % len(directions)

        for k in range(len(directions)):
            idx = (start_dir + k) % len(directions)
            dx, dy = directions[idx]
            tile = (ex + dx, ey + dy)
            if tile in occupied:
                continue
            if self._is_walkable(*tile, ent=ent):
                ent.ia["auto_walk_dir"] = idx
                return tile

        fallback = self._find_nearest_walkable((ex, ey), max_radius=2, forbidden=occupied, ent=ent)
        if fallback and fallback != (ex, ey):
            return fallback
        return None

    def _entity_low_health(self, ent) -> bool:
        hp = float(getattr(ent, "jauges", {}).get("sante", 0) or 0)
        max_hp = float(getattr(ent, "max_sante", 100) or 100)
        if max_hp <= 0:
            return True
        return hp / max_hp <= 0.35

    def _auto_find_nearest_hunt_target(self, ent, max_radius: int = 20):
        best = None
        best_d2 = None
        ex, ey = float(ent.x), float(ent.y)
        max_d2 = float(max_radius * max_radius)
        for other in self.entities:
            if other is ent:
                continue
            if not getattr(other, "is_fauna", False):
                continue
            if getattr(other, "_dead_processed", False):
                continue
            if getattr(other, "jauges", {}).get("sante", 0) <= 0:
                continue
            dx = float(other.x) - ex
            dy = float(other.y) - ey
            d2 = dx * dx + dy * dy
            if d2 > max_d2:
                continue
            if best is None or d2 < best_d2:
                best = other
                best_d2 = d2
        return best

    def _auto_order_hunt(self, ent, target_ent) -> bool:
        if target_ent is None or target_ent not in self.entities:
            return False
        return self._start_entity_combat(ent, target_ent)

    def _update_entity_auto_mode(self, ent, dt: float):
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return
        auto_mode = str(ent.ia.get("auto_mode") or "").strip().lower()
        if auto_mode not in {"harvest", "hunt"}:
            return
        if getattr(ent, "is_fauna", False):
            return

        cooldown = max(0.0, float(ent.ia.get("auto_next_decision_in", 0.0) or 0.0) - dt)
        ent.ia["auto_next_decision_in"] = cooldown
        if cooldown > 0.0:
            return
        ent.ia["auto_next_decision_in"] = 0.2

        force_deposit = bool(ent.ia.get("auto_need_deposit")) or self._entity_inventory_is_full(ent)
        if auto_mode == "hunt" and self._entity_low_health(ent):
            force_deposit = True
        if force_deposit:
            ent.ia["auto_need_deposit"] = True

            objectif = ent.ia.get("objectif")
            heading_warehouse = False
            if objectif and objectif[0] == "prop":
                oi, oj, opid = objectif[1]
                wh_target = self._auto_extract_warehouse_target(int(oi), int(oj))
                heading_warehouse = ent.ia.get("order_action") == "interact" and wh_target is not None
                if not heading_warehouse:
                    self._auto_mark_failed_prop(ent, (oi, oj, opid))

            work = getattr(ent, "work", None)
            if work and work.get("type") == "harvest":
                self._auto_mark_failed_prop(
                    ent,
                    (work.get("i", int(ent.x)), work.get("j", int(ent.y)), work.get("pid", 0)),
                )

            if not heading_warehouse:
                if hasattr(ent, "comportement"):
                    ent.comportement.cancel_work("auto_need_deposit")
                else:
                    ent.work = None
                    ent.ia["etat"] = "idle"
                    ent.ia["objectif"] = None
                    ent.ia["order_action"] = None
                    ent.ia["target_craft_id"] = None
                ent.move_path = []
                ent._move_from = (float(ent.x), float(ent.y))
                ent._move_to = None
                ent._move_t = 0.0

            warehouse = self._auto_find_nearest_warehouse(ent)
            if warehouse and self._auto_order_deposit(ent, warehouse):
                ent.ia["auto_next_decision_in"] = 0.5
            return

        if getattr(ent, "work", None):
            return
        if getattr(ent, "move_path", None):
            if ent.move_path:
                return
        if getattr(ent, "_move_to", None) is not None:
            return

        etat = ent.ia.get("etat")
        if etat not in ("idle", "se_deplace"):
            return

        if auto_mode == "harvest":
            harvest_target = self._auto_find_nearest_harvestable_prop(ent)
            if harvest_target and self._auto_order_harvest(ent, harvest_target):
                ent.ia["auto_next_decision_in"] = 0.45
                return
        else:
            hunt_target = self._auto_find_nearest_hunt_target(ent)
            if hunt_target and self._auto_order_hunt(ent, hunt_target):
                ent.ia["auto_next_decision_in"] = 0.35
                return

        step_tile = self._auto_next_step_tile(ent)
        if step_tile:
            ok = self._apply_entity_order(
                ent,
                target=step_tile,
                etat="se_deplace",
                objectif=None,
                action_mode=None,
                craft_id=None,
            )
            if ok:
                ent.ia["auto_next_decision_in"] = 0.5

    def deposit_to_warehouse(self, inventory: list[dict]) -> int:
        """
        Transfère tout l'inventaire fourni dans l'entrepôt partagé.
        Retourne le nombre d'items transférés.
        """
        if not inventory:
            return 0
        moved = 0
        for stack in list(inventory):
            res_id = stack.get("id") or stack.get("name")
            qty = int(stack.get("quantity", 0))
            if not res_id or qty <= 0:
                continue
            self.warehouse[res_id] = self.warehouse.get(res_id, 0) + qty
            moved += qty
            by_type = self._run_stats.setdefault("resources_by_type", {})
            by_type[res_id] = int(by_type.get(res_id, 0) or 0) + qty
            self._stats_current_day["resources_collected"] = int(self._stats_current_day.get("resources_collected", 0) or 0) + qty
        inventory.clear()
        return moved

    def _craft_def_from_cell(self, cell):
        craft_def = None
        if isinstance(cell, dict):
            cid = cell.get("craft_id")
            if cid and self.craft_system:
                craft_def = self.craft_system.crafts.get(cid, {})
            fallback = {
                "name": cell.get("name") or cell.get("craft_id"),
                "craft_id": cell.get("craft_id"),
                "cost": cell.get("cost", {}),
                "interaction": cell.get("interaction"),
            }
            if craft_def:
                merged = dict(fallback)
                merged.update(craft_def)
                return merged
            return fallback if fallback.get("name") or fallback.get("craft_id") else None
        return None

    def _describe_craft_prop(self, payload):
        if not self.world:
            return
        i, j, pid = payload
        try:
            cell = self.world.overlay[j][i]
        except Exception:
            cell = None

        craft_def = self._craft_def_from_cell(cell)
        prop_entry = self._get_prop_description_entry(pid) or {}

        sprite_name = None
        try:
            sprite_name = get_prop_sprite_name(int(pid))
        except Exception:
            sprite_name = None

        name = craft_def.get("name") if craft_def else None
        if not name:
            name = prop_entry.get("name")
        if not name and sprite_name:
            name = str(sprite_name).replace("_", " ").strip().title()
        if not name:
            name = f"Prop {pid}"

        desc = craft_def.get("description") if craft_def else None
        if not desc:
            desc = prop_entry.get("description")
        interaction = craft_def.get("interaction") if craft_def else None

        content_lines: list[str] = []
        if desc:
            content_lines.extend(desc.split("\n"))
        else:
            content_lines.append("Aucune description.")
        if sprite_name:
            content_lines.append(f"Sprite: {sprite_name}")

        if isinstance(interaction, dict) and interaction.get("type") == "warehouse":
            if not self.warehouse:
                content_lines.append("Entrepot : aucun stock.")
            else:
                content_lines.append("Contenu de l'entrepot :")
                for res, qty in self.warehouse.items():
                    content_lines.append(f"- {res} : {qty}")

        title_surf = self.font.render(name, True, (245, 245, 245))
        body_surfs = [self.small_font.render(line, True, (225, 225, 225)) for line in content_lines]

        mx, my = pygame.mouse.get_pos()
        win = DraggableWindow(title_surf, body_surfs, (mx, my))
        self.info_windows.append(win)

    def _handle_single_left_click(self, mx: int, my: int):
        hit = self.view.pick_at(mx, my)
        if hit:
            kind, payload = hit
            if kind == "entity":
                if getattr(payload, "is_fauna", False):
                    self.selected = None
                    self._set_selected_entities([])
                else:
                    self._set_selected_entities([payload])
            elif kind == "prop":
                self.selected = ("prop", payload)
                self._set_selected_entities([])
            else:
                self.selected = ("tile", payload)
                self._set_selected_entities([])
        else:
            i_j = self._fallback_pick_tile(mx, my)
            self.selected = ("tile", i_j) if i_j else None
            self._set_selected_entities([])
        if not self.selected and not self.selected_entities:
            self.info_windows = []

    def _draw_selection_box(self, screen: pygame.Surface):
        if not self._drag_select_rect or self._drag_select_rect.width <= 0 or self._drag_select_rect.height <= 0:
            return
        rect = self._drag_select_rect
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((80, 180, 120, 60))
        screen.blit(overlay, rect.topleft)
        pygame.draw.rect(screen, (80, 200, 120), rect, 1)

    # ---------- SELECTION MARKER ----------
    def _draw_selection_marker(self, screen: pygame.Surface):
        """
        Affiche un effet visuel autour de l'entité sélectionnée uniquement.
        - Utilise le sprite 'vfx_aura_alpha' centré sur la tuile de l'entité.
        - Ne montre rien pour les tiles / props.
        """
        entities = []
        if self.selected_entities:
            entities = [e for e in self.selected_entities if e in self.entities]
        elif self.selected and self.selected[0] == "entity":
            entities = [self.selected[1]]
        if not entities:
            return

        aura = self.assets.get_image("vfx_aura_alpha")
        if aura is None:
            return

        for ent in entities:
            poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
            if not poly:
                continue

            min_x = min(p[0] for p in poly)
            max_x = max(p[0] for p in poly)
            min_y = min(p[1] for p in poly)
            max_y = max(p[1] for p in poly)

            center_x = (min_x + max_x) // 2
            center_y = (min_y + max_y) // 2

            aura_rect = aura.get_rect(center=(center_x, center_y))
            screen.blit(aura, aura_rect)

    def _draw_hover_entity_name(self, screen: pygame.Surface):
        if self.ui_menu_open:
            return
        mx, my = pygame.mouse.get_pos()
        hit = self.view.pick_at(mx, my)
        if not hit or hit[0] != "entity":
            return
        ent = hit[1]
        if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
            return
        name = getattr(ent, "nom", "")
        if not name:
            return
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return
        center_x = int(sum(p[0] for p in poly) / len(poly))
        top_y = int(min(p[1] for p in poly)) - 18
        text = self.small_font.render(name, True, (245, 245, 245))
        padding = 4
        bg_rect = text.get_rect(center=(center_x, top_y))
        bg_rect.inflate_ip(padding * 2, padding)
        bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg.fill((10, 10, 20, 160))
        screen.blit(bg, bg_rect.topleft)
        screen.blit(text, text.get_rect(center=bg_rect.center))


    # ---------- FALLBACK PICK (ancien beam) ----------
    def _fallback_pick_tile(self, mx: int, my: int) -> Optional[tuple[int,int]]:
        dx, dy, _ = self.view._proj_consts()
        base = int(self.view.click_lift_factor * dy) if hasattr(self.view, "click_lift_factor") else int(0.7 * dy)
        for off in (base, int(base*0.66), int(base*0.33), 0):
            t = self.view.pick_tile_at(mx, my - off)
            if t:
                return t
        return None

    def _tile_is_visible(self, tile: tuple[int, int]) -> bool:
        if not self.fog:
            return True
        i, j = tile
        try:
            return bool(self.fog.visible[j][i])
        except Exception:
            return True

    def _tile_fog_state(self, tile: tuple[int, int]) -> tuple[bool, bool]:
        if not self.fog:
            return True, True
        i, j = tile
        try:
            return self.fog.is_visible(i, j), self.fog.is_explored(i, j)
        except Exception:
            return True, True

    # ---------- PATHFINDING & COLLISIONS ----------
    def _is_walkable(self, i: int, j: int, generate: bool = True, ent=None) -> bool:
        w = self.world
        if not w: return False
        if i < 0 or j < 0 or i >= w.width or j >= w.height:
            return False

        if hasattr(w, "get_tile_snapshot"):
            snap = w.get_tile_snapshot(i, j, generate=generate)
            if snap is None:
                return False
            _lvl, gid, overlay, bid = snap
            if overlay and not self._is_species_corpse_overlay(overlay):
                return False
            if int(bid) in _WATER_BIOME_IDS:
                return self._entity_can_walk_on_water(ent)
            # Fallback ultra conservateur pour anciens IDs/tiles.
            name = get_ground_sprite_name(gid) if gid is not None else None
            if name and any(token in name.lower() for token in ("water", "ocean", "sea", "lake", "river")):
                return self._entity_can_walk_on_water(ent)
            return True

        # Fallback pour mondes qui n'exposent pas get_tile_snapshot.
        try:
            pid = w.overlay[j][i]
            if pid and not self._is_species_corpse_overlay(pid):
                return False
        except Exception:
            pass
        try:
            gid = w.ground_id[j][i]
        except Exception:
            gid = None
        name = get_ground_sprite_name(gid) if gid is not None else None
        if name and any(token in name.lower() for token in ("water", "ocean", "sea", "lake", "river")):
            return self._entity_can_walk_on_water(ent)
        return True

    def _occupied_tiles(self, exclude: list | None = None) -> set[tuple[int, int]]:
        exclude = set(exclude or [])
        occupied = set()
        for ent in self.entities:
            if ent in exclude:
                continue
            occupied.add((int(ent.x), int(ent.y)))
        return occupied

    def _get_construction_cell(self, i: int, j: int, generate: bool = False):
        w = self.world
        if not w:
            return None
        if hasattr(w, "get_tile_snapshot"):
            snap = w.get_tile_snapshot(i, j, generate=generate)
            if snap is None:
                return None
            _lvl, _gid, overlay, _bid = snap
            return overlay
        try:
            return w.overlay[j][i]
        except Exception:
            return None

    def _is_construction_site(self, i: int, j: int) -> bool:
        cell = self._get_construction_cell(i, j)
        return isinstance(cell, dict) and cell.get("state") == "building"

    def _astar_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        *,
        ent=None,
        allow_partial: bool = False,
        generate: bool = False,
        max_nodes: int = 20000,
        time_budget_sec: float | None = 0.02,
    ) -> list[tuple[int, int]]:
        if not self._is_walkable(*goal, generate=generate, ent=ent):
            return []
        sx, sy = start
        gx, gy = goal
        if (sx, sy) == (gx, gy):
            return []

        # Heuristique octile (8-connexe, coût diag = sqrt(2))
        import math

        sqrt2 = 1.41421356237
        octile_k = sqrt2 - 2.0

        def h(a, b):
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            return (dx + dy) + octile_k * min(dx, dy)

        t0 = time.perf_counter()
        openh: list[tuple[float, float, tuple[int, int]]] = []
        heapq.heappush(openh, (h(start, goal), 0.0, start))
        came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        gscore: dict[tuple[int, int], float] = {start: 0.0}

        best = start
        best_h = h(start, goal)
        expanded = 0

        neigh = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ]

        while openh:
            if time_budget_sec is not None and (time.perf_counter() - t0) >= time_budget_sec:
                break
            if expanded >= max_nodes:
                break

            _f, gc, cur = heapq.heappop(openh)
            if gc != gscore.get(cur):
                continue

            if cur == goal:
                path = []
                while cur in came and cur is not None:
                    path.append(cur)
                    cur = came[cur]
                path.reverse()
                return path

            expanded += 1
            cur_h = h(cur, goal)
            if cur_h < best_h:
                best_h = cur_h
                best = cur

            for dx, dy in neigh:
                nx, ny = cur[0] + dx, cur[1] + dy
                if not self._is_walkable(nx, ny, generate=generate, ent=ent):
                    continue
                step_cost = sqrt2 if (dx != 0 and dy != 0) else 1.0
                ng = gc + step_cost
                if ng < gscore.get((nx, ny), 1e18):
                    gscore[(nx, ny)] = ng
                    came[(nx, ny)] = cur
                    heapq.heappush(openh, (ng + h((nx, ny), goal), ng, (nx, ny)))

        if not allow_partial:
            return []

        if best == start or best not in came:
            return []

        cur = best
        path: list[tuple[int, int]] = []
        while cur in came and cur is not None:
            path.append(cur)
            cur = came[cur]
        path.reverse()
        return path

    def _los_clear(self, a: tuple[float,float], b: tuple[float,float], ent=None) -> bool:
        """
        Line-of-sight grossière : on échantillonne la droite AB et on vérifie
        que chaque sample tombe sur une case walkable. Suffisant pour lisser.
        """
        import math
        ax, ay = a; bx, by = b
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return True
        steps = int(dist * 4) + 1  # sur-échantillonnage léger
        for s in range(steps + 1):
            t = s / max(1, steps)
            x = ax + dx * t
            y = ay + dy * t
            if not self._is_walkable(int(x), int(y), generate=False, ent=ent):
                return False
        return True

    def _smooth_path(self, nodes: list[tuple[int,int]], ent=None) -> list[tuple[float,float]]:
        """
        String-pulling simple : on garde le point courant, on pousse aussi loin
        que possible en conservant la visibilité, puis on place un waypoint au
        centre de la case retenue.
        """
        if not nodes:
            return []
        # Les chemins longs rendent le lissage (LOS) très coûteux -> on garde le tracé brut.
        if len(nodes) > 90:
            return [(i + 0.5, j + 0.5) for (i, j) in nodes]
        # Convertit nodes -> centres flottants
        pts = [(i + 0.5, j + 0.5) for (i, j) in nodes]
        smoothed = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            # recule tant que la LOS échoue
            while j > i + 1 and not self._los_clear(pts[i], pts[j], ent=ent):
                j -= 1
            smoothed.append(pts[j])
            i = j
        return smoothed

    def _update_entity_movement(self, ent, dt: float):
        # Rien à faire ?
        if getattr(ent, "move_path", None) and ent.move_path and ent.ia.get("etat") in ("recolte", "construction", "interaction", "demonte"):
            if hasattr(ent, "comportement"):
                ent.comportement.cancel_work("movement_started")
            else:
                if getattr(ent, "work", None):
                    ent.work = None
                ent.ia["etat"] = "se_deplace"
                ent.ia["objectif"] = None
        if not getattr(ent, "move_path", None) or not ent.move_path:
            if ent.ia["etat"] == "se_deplace_vers_prop":
                action = ent.ia.get("order_action")
                craft_def = self._craft_def_from_order(ent) if action in ("interact", "dismantle") else None
                if hasattr(ent, "comportement"):
                    if action == "interact":
                        ent.comportement.interact_with_craft(ent.ia.get("objectif"), self.world, craft_def)
                    elif action == "dismantle":
                        ent.comportement.dismantle_craft(ent.ia.get("objectif"), self.world, craft_def)
                    else:
                        ent.comportement.recolter_ressource(ent.ia.get("objectif"), self.world)
            elif ent.ia["etat"] == "se_deplace_vers_construction":
                if hasattr(ent, "comportement"):
                    ent.comportement.build_construction(ent.ia.get("objectif"), self.world)
            elif ent.ia["etat"] == "se_deplace":
                ent.ia["etat"] = "idle"
                ent.ia["objectif"] = None
                ent.ia["order_action"] = None
                ent.ia["target_craft_id"] = None

        # Init du segment courant
        if ent._move_to is None:
            if not ent.move_path:
                return
            # _move_from est la position actuelle (flottante)
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = ent.move_path[0]  # (x, y) flottant désormais
            ent._move_t = 0.0

        tx, ty = ent._move_to
        fx, fy = ent._move_from

        # Longueur du segment en coordonnées monde (pas "1 tuile" supposée)
        seg_len = max(1e-6, ((tx - fx)**2 + (ty - fy)**2) ** 0.5)

        # Vitesse monde = "tuiles par seconde" mais on l'applique en distance euclidienne
        speed = max(0.2, float(self._compute_entity_move_speed(ent)))
        ent.move_speed = speed
        # t progresse à la bonne vitesse quelle que soit l'orientation
        ent._move_t += (dt * speed) / seg_len

        if ent._move_t >= 1.0:
            # On arrive exactement au point visé
            ent.x, ent.y = float(tx), float(ty)
            # Passe au waypoint suivant
            if ent.move_path:
                ent.move_path.pop(0)
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_t = 0.0
            ent._move_to = ent.move_path[0] if ent.move_path else None
        else:
            # Interpolation linéaire
            ent.x = fx + (tx - fx) * ent._move_t
            ent.y = fy + (ty - fy) * ent._move_t

    def _find_nearest_walkable(self, target: tuple[int, int], max_radius: int = 8, forbidden: set[tuple[int, int]] | None = None, ent=None) -> Optional[tuple[int, int]]:
        """Retourne la case libre la plus proche du point cible (si eau/obstacle), en évitant les cases interdites."""
        tx, ty = target
        forbidden = forbidden or set()
        if self._is_walkable(tx, ty, ent=ent) and (tx, ty) not in forbidden:
            return target

        best = None
        best_dist = 9999
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = tx + dx, ty + dy
                    if not self._is_walkable(nx, ny, ent=ent):
                        continue
                    if (nx, ny) in forbidden:
                        continue
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best = (nx, ny)
                        best_dist = d
            if best:
                break
        return best

    def _apply_entity_order(self, ent, target: tuple[int, int], etat: str, objectif, action_mode: str | None, craft_id: str | None):
        start_pos = (int(ent.x), int(ent.y))
        allow_partial = bool(etat == "se_deplace" and not objectif and not action_mode)
        if getattr(ent, "_shelter_resting", False):
            self._leave_shelter(ent)
        raw_path = self._astar_path(
            start_pos,
            target,
            ent=ent,
            allow_partial=allow_partial,
            generate=False,
        )
        if not raw_path and start_pos != target:
            return False

        if etat != "combat":
            self._clear_entity_combat_refs(ent)

        if hasattr(ent, "comportement"):
            ent.comportement.cancel_work("player_new_order")
        else:
            if getattr(ent, "work", None):
                ent.work = None
            ent.ia["etat"] = "idle"
            ent.ia["objectif"] = None

        ent.ia["etat"] = etat
        ent.ia["objectif"] = objectif
        ent.ia["order_action"] = action_mode
        ent.ia["target_craft_id"] = craft_id if action_mode in ("interact", "dismantle") else None
        if etat == "se_deplace_vers_construction":
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None

        if raw_path and raw_path[0] == start_pos:
            raw_path = raw_path[1:]
        waypoints = self._smooth_path(raw_path, ent=ent) if raw_path else []
        if waypoints is None:
            waypoints = []
        ent.move_path = waypoints
        ent._move_from = (float(ent.x), float(ent.y))
        ent._move_to = waypoints[0] if waypoints else None
        ent._move_t = 0.0
        return True

    def _issue_order_to_entities(self, entities: list, hit, harvest_mode: bool = False, click_pos: tuple[int, int] | None = None):
        entities = [e for e in entities if e in self.entities and not getattr(e, "is_fauna", False)]
        if not entities:
            return

        base_target = None
        objectif = None
        etat = "se_deplace"
        action_mode = None
        craft_id = None

        if hit:
            kind, payload = hit
            if kind == "tile":
                base_target = payload
                objectif = None
                etat = "se_deplace"
            elif kind == "entity":
                if getattr(payload, "is_fauna", False):
                    for ent in entities:
                        self._start_entity_combat(ent, payload)
                    return
                base_target = (int(payload.x), int(payload.y))
                objectif = None
                etat = "se_deplace"
            elif kind == "prop":
                i, j, pid = payload
                cell = self._get_construction_cell(i, j)
                if self._is_species_corpse_overlay(cell):
                    leader = entities[0] if entities else None
                    if not self._can_harvest_species_corpse(ent=leader, tile=(i, j)):
                        if self._is_species_grave_overlay(cell):
                            add_notification("Cette tombe ne peut pas etre recoltee.")
                        elif not self._species_has_mutation("Cannibale"):
                            add_notification("Il faut la mutation Cannibale pour recolter un cadavre.")
                        else:
                            add_notification("Ce cadavre ne peut pas etre recolte.")
                        return
                    etat = "se_deplace_vers_prop"
                    objectif = ("prop", (i, j, pid))
                    base_target = (i, j)
                    action_mode = None
                    craft_id = None
                else:
                    craft_id = cell.get("craft_id") if isinstance(cell, dict) else None
                    if self._is_construction_site(i, j):
                        etat = "se_deplace_vers_construction"
                        objectif = ("construction", (i, j))
                        base_target = (i, j)
                        action_mode = None
                    else:
                        etat = "se_deplace_vers_prop"
                        objectif = ("prop", (i, j, pid))
                        base_target = (i, j)
                        if isinstance(cell, dict) and craft_id:
                            action_mode = "dismantle" if harvest_mode else "interact"
                        else:
                            action_mode = None
        if base_target is None:
            cx, cy = click_pos if click_pos else pygame.mouse.get_pos()
            base_target = self._fallback_pick_tile(cx, cy)
            if base_target:
                etat = "se_deplace"
                objectif = None

        if base_target is None:
            return

        reserved = self._occupied_tiles(exclude=entities)
        dismantle_assigned = False
        for ent in entities:
            if action_mode == "dismantle" and dismantle_assigned:
                break
            if objectif and objectif[0] == "prop" and self._same_prop_target(ent, ("prop", objectif[1])):
                continue
            desired = base_target
            forbidden = set(reserved)
            if not self._is_walkable(*desired, ent=ent) or desired in forbidden:
                desired = self._find_nearest_walkable(desired, forbidden=forbidden, ent=ent)
            if not desired:
                continue
            reserved.add(desired)
            ok = self._apply_entity_order(ent, desired, etat, objectif, action_mode, craft_id)
            if ok and action_mode == "dismantle":
                dismantle_assigned = True
    
    def _same_prop_target(self, ent, hit):
        if not hit or hit[0] != "prop":
            return False
        i, j, pid = hit[1]
        tgt = (int(i), int(j), str(pid))

        # compare à l'objectif courant (si on est en chemin vers le prop)
        cur = ent.ia.get("objectif")
        if cur and cur[0] == "prop":
            ci, cj, cpid = cur[1]
            if (int(ci), int(cj), str(cpid)) == tgt:
                return True

        # compare au job en cours (si déjà en train de récolter)
        w = getattr(ent, "work", None)
        if w and w.get("type") == "harvest":
            if (w["i"], w["j"], str(w["pid"])) == tgt:
                return True
        return False

    def _craft_def_from_order(self, ent):
        craft_id = ent.ia.get("target_craft_id")
        objectif = ent.ia.get("objectif")
        cell = None
        if objectif and objectif[0] == "prop":
            i, j, _pid = objectif[1]
            cell = self._get_construction_cell(i, j)
        craft_def = None
        if craft_id and self.craft_system:
            craft_def = self.craft_system.crafts.get(craft_id)
        if isinstance(cell, dict):
            fallback = {
                "cost": cell.get("cost", {}),
                "name": cell.get("name") or cell.get("craft_id") or "Construction",
                "pid": cell.get("pid"),
                "craft_id": cell.get("craft_id"),
                "interaction": cell.get("interaction"),
            }
            if craft_def:
                merged = dict(fallback)
                merged.update(craft_def)
                return merged
            return fallback
        return craft_def

    def _register_construction_site(self, craft_result):
        tile = craft_result.get("tile")
        site = craft_result.get("site")
        if not tile or not site:
            return
        key = (int(tile[0]), int(tile[1]))
        self.construction_sites[key] = {
            "name": site.get("name", site.get("craft_id", "Construction")),
            "work_required": site.get("work_required", 1.0),
            "work_done": site.get("work_done", 0.0),
        }
        self._assign_idle_workers_to_construction(key)

    def _assign_idle_workers_to_construction(self, tile: tuple[int, int], max_workers: int = 3):
        assigned = 0
        reserved = self._occupied_tiles()
        for ent in self.entities:
            if assigned >= max_workers:
                break
            if getattr(ent, "is_fauna", False):
                continue
            if ent.ia.get("etat") != "idle" or getattr(ent, "work", None):
                continue
            if not self._is_construction_site(*tile):
                break
            # Filtre de distance pour éviter d'envoyer les entités trop loin
            dx = int(ent.x) - tile[0]
            dy = int(ent.y) - tile[1]
            dist2 = dx * dx + dy * dy
            if dist2 > (self.construction_assign_radius ** 2):
                continue
            self._ensure_move_runtime(ent)
            target = self._find_nearest_walkable(tile, forbidden=reserved, ent=ent)
            if not target:
                continue
            reserved.add(target)
            raw_path = self._astar_path((int(ent.x), int(ent.y)), target, ent=ent)
            if not raw_path:
                if (int(ent.x), int(ent.y)) == target:
                    ent.move_path = []
                    ent._move_from = (float(ent.x), float(ent.y))
                    ent._move_to = None
                    ent._move_t = 0.0
                    ent.ia["etat"] = "se_deplace_vers_construction"
                    ent.ia["objectif"] = ("construction", tile)
                    ent.ia["order_action"] = None
                    ent.ia["target_craft_id"] = None
                    assigned += 1
                continue
            if raw_path and raw_path[0] == (int(ent.x), int(ent.y)):
                raw_path = raw_path[1:]
            waypoints = self._smooth_path(raw_path, ent=ent)
            ent.move_path = waypoints
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = waypoints[0] if waypoints else None
            ent._move_t = 0.0
            ent.ia["etat"] = "se_deplace_vers_construction"
            ent.ia["objectif"] = ("construction", tile)
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None
            assigned += 1

    def _update_construction_sites(self):
        if not self.construction_sites:
            return
        finished: list[tuple[int, int]] = []
        for key, meta in list(self.construction_sites.items()):
            i, j = key
            cell = self._get_construction_cell(i, j)
            if isinstance(cell, dict) and cell.get("state") == "building":
                meta["work_done"] = cell.get("work_done", meta.get("work_done", 0.0))
                meta["work_required"] = cell.get("work_required", meta.get("work_required", 1.0))
                continue
            # Construction absente ou terminée
            finished.append(key)
        for key in finished:
            meta = self.construction_sites.pop(key, {})
            cell = self._get_construction_cell(*key)
            if meta and cell not in (None, 0, False):
                add_notification(f"{meta.get('name', 'Construction')} terminée.")
                if isinstance(cell, dict) and str(cell.get("state") or "") == "built":
                    craft_id = str(cell.get("craft_id") or "")
                    if craft_id == "Entrepot_primitif":
                        prev = int(self._warehouse_built_count or 0)
                        self._warehouse_built_count = prev + 1
                        if prev <= 0:
                            self._grant_warehouse_starter_stock()
                    if craft_id == "Recuperateur_eau":
                        self._water_collector_tiles.add((int(key[0]), int(key[1])))
                    if craft_id == "Feu_de_camp":
                        self._campfire_tiles.add((int(key[0]), int(key[1])))
                    if craft_id == "Jardin":
                        self._garden_tiles.add((int(key[0]), int(key[1])))
        if finished:
            self._refresh_craft_gate_state(force=True)

    def _draw_construction_bars(self, screen):
        if not self.construction_sites:
            return
        for (i, j), meta in self.construction_sites.items():
            cell = self._get_construction_cell(i, j)
            if not (isinstance(cell, dict) and cell.get("state") == "building"):
                continue
            required = max(1e-3, float(cell.get("work_required", meta.get("work_required", 1.0))))
            progress = max(0.0, min(1.0, float(cell.get("work_done", meta.get("work_done", 0.0))) / required))
            poly = self.view.tile_surface_poly(int(i), int(j))
            if not poly:
                continue
            cx = sum(p[0] for p in poly) / len(poly)
            top = min(p[1] for p in poly) - 14
            bar_w, bar_h = 54, 7
            bg = pygame.Rect(int(cx - bar_w/2), int(top - bar_h), bar_w, bar_h)
            fg = bg.inflate(-2, -2)
            fg.width = int(fg.width * progress)
            s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 170))
            screen.blit(s, (bg.x, bg.y))
            pygame.draw.rect(screen, (200, 210, 120), fg, border_radius=2)

    # ---------- MINI-MAP ----------
    def _get_minimap_map_size(self) -> int:
        if self._minimap_scaled_surface is not None:
            try:
                return int(self._minimap_scaled_surface.get_width())
            except Exception:
                pass
        return max(120, int(self._minimap_display_size))

    def _get_minimap_panel_rect(self) -> pygame.Rect | None:
        if not self.minimap_visible:
            return None
        sw, _sh = self.screen.get_size()
        map_size = self._get_minimap_map_size()
        panel_w = map_size + 20
        panel_h = map_size + 44
        panel_x = sw - panel_w - 20
        panel_y = 125
        return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    def _get_minimap_map_rect(self) -> pygame.Rect | None:
        panel_rect = self._get_minimap_panel_rect()
        if panel_rect is None:
            return None
        map_size = self._get_minimap_map_size()
        return pygame.Rect(panel_rect.x + 10, panel_rect.y + 24, map_size, map_size)

    def _is_point_over_minimap(self, pos: tuple[int, int]) -> bool:
        panel_rect = self._get_minimap_panel_rect()
        if panel_rect is None:
            return False
        return bool(panel_rect.collidepoint(pos))

    def _zoom_minimap(self, wheel_delta: int) -> None:
        if not self.minimap_visible or self.world is None:
            return
        d = int(wheel_delta)
        if d == 0:
            return
        # Molette haut => zoom in (span plus petit), bas => zoom out.
        factor = 0.86 if d > 0 else 1.16
        current = float(max(1, int(self._minimap_world_span)))
        new_span = int(round(current * factor))
        min_span = int(max(32, int(self._minimap_world_span_min)))
        max_span = int(max(min_span + 1, int(self._minimap_world_span_max)))
        new_span = max(min_span, min(max_span, new_span))
        if new_span == int(self._minimap_world_span):
            return
        self._minimap_world_span = int(new_span)
        self._minimap_refresh_cd = 0.0
        self._update_minimap_cache(0.0, force=True)

    def _minimap_focus_tile(self) -> tuple[int, int]:
        world = self.world
        if world is None:
            return (0, 0)
        width = max(1, int(world.width))
        height = max(1, int(world.height))
        if self.joueur is not None:
            return (int(self.joueur.x) % width, max(0, min(height - 1, int(self.joueur.y))))
        if self.entities:
            for ent in self.entities:
                if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
                    continue
                if getattr(ent, "espece", None) is not self.espece:
                    continue
                return (int(ent.x) % width, max(0, min(height - 1, int(ent.y))))
        try:
            sx, sy = world.spawn
            return (int(sx) % width, max(0, min(height - 1, int(sy))))
        except Exception:
            return (width // 2, height // 2)

    def _wrap_dx(self, x: int, cx: int, width: int) -> int:
        if width <= 0:
            return int(x) - int(cx)
        return int((int(x) - int(cx) + width // 2) % width) - width // 2

    def _sample_minimap_color(self, snap) -> tuple[int, int, int]:
        if snap is None:
            return (12, 16, 22)
        _lvl, _gid, overlay, bid = snap
        try:
            biome_id = int(bid)
        except Exception:
            biome_id = -1
        base = _MINIMAP_BIOME_COLORS.get(biome_id, (72, 86, 72))
        if overlay:
            # Case occupée par une structure/prop: petit boost de luminosité
            return (
                min(255, base[0] + 14),
                min(255, base[1] + 14),
                min(255, base[2] + 14),
            )
        return base

    def _rebuild_minimap_cache(self, center: tuple[int, int]) -> None:
        world = self.world
        if world is None:
            return
        sample = max(32, int(self._minimap_sample_size))
        span = max(64, int(self._minimap_world_span))
        half = span * 0.5
        width = max(1, int(world.width))
        height = max(1, int(world.height))
        cx, cy = center

        base = pygame.Surface((sample, sample))
        step = span / float(sample)
        for py in range(sample):
            wy = int(cy - half + (py + 0.5) * step)
            wy = max(0, min(height - 1, wy))
            for px in range(sample):
                wx = int(cx - half + (px + 0.5) * step) % width
                snap = world.get_tile_snapshot(wx, wy, generate=False) if hasattr(world, "get_tile_snapshot") else None
                base.set_at((px, py), self._sample_minimap_color(snap))

        display_size = max(120, int(self._minimap_display_size))
        self._minimap_base_surface = base
        self._minimap_scaled_surface = pygame.transform.scale(base, (display_size, display_size))
        self._minimap_cache_center = (int(cx), int(cy))

    def _update_minimap_cache(self, dt: float, force: bool = False) -> None:
        if not self.minimap_visible or self.world is None:
            return

        center = self._minimap_focus_tile()
        need_rebuild = force or self._minimap_scaled_surface is None or self._minimap_cache_center is None
        if not need_rebuild:
            last_x, last_y = self._minimap_cache_center
            dx = abs(self._wrap_dx(center[0], last_x, int(self.world.width)))
            dy = abs(int(center[1]) - int(last_y))
            if dx + dy >= 8:
                need_rebuild = True

        self._minimap_refresh_cd -= float(dt)
        if self._minimap_refresh_cd <= 0.0:
            need_rebuild = True

        if need_rebuild:
            self._rebuild_minimap_cache(center)
            self._minimap_last_center = center
            self._minimap_refresh_cd = float(self._minimap_refresh_interval)

    def _draw_species_minimap(self, screen: pygame.Surface) -> None:
        if not self.minimap_visible or self.world is None:
            return
        self._update_minimap_cache(0.0)
        if self._minimap_scaled_surface is None or self._minimap_cache_center is None:
            return

        panel_rect = self._get_minimap_panel_rect()
        map_rect = self._get_minimap_map_rect()
        if panel_rect is None or map_rect is None:
            return
        panel_x, panel_y = panel_rect.x, panel_rect.y
        panel_w, panel_h = panel_rect.w, panel_rect.h

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((15, 22, 30, 210))
        pygame.draw.rect(bg, (88, 112, 146), bg.get_rect(), 2, border_radius=10)
        screen.blit(bg, panel_rect.topleft)

        title = self.small_font.render("Mini-map", True, (210, 220, 240))
        screen.blit(title, (panel_x + 12, panel_y + 6))
        screen.blit(self._minimap_scaled_surface, map_rect.topleft)

        center_x, center_y = self._minimap_cache_center
        span = float(max(64, int(self._minimap_world_span)))
        half = span * 0.5
        world_w = max(1, int(self.world.width))
        world_h = max(1, int(self.world.height))

        # Indicateur du joueur principal (ou centre caméra de minimap)
        cpx = map_rect.x + map_rect.width // 2
        cpy = map_rect.y + map_rect.height // 2
        pygame.draw.rect(screen, (245, 245, 255), pygame.Rect(cpx - 1, cpy - 1, 3, 3))

        for ent in self.entities:
            if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "espece", None) is not self.espece:
                continue
            ex = int(ent.x) % world_w
            ey = max(0, min(world_h - 1, int(ent.y)))
            dx = float(self._wrap_dx(ex, center_x, world_w))
            dy = float(ey - center_y)
            if abs(dx) > half or abs(dy) > half:
                continue
            rx = (dx + half) / span
            ry = (dy + half) / span
            px = map_rect.x + int(rx * (map_rect.width - 1))
            py = map_rect.y + int(ry * (map_rect.height - 1))
            color = (250, 238, 120)
            if ent is self.joueur:
                color = (255, 255, 255)
            pygame.draw.rect(screen, color, pygame.Rect(px - 1, py - 1, 3, 3))

        pygame.draw.rect(screen, (130, 150, 180), map_rect, 1)

    def _draw_group_supply_hud(self, screen: pygame.Surface) -> None:
        if self.paused or self.ui_menu_open:
            return
        if self.espece is None:
            return
        if not self.has_built_warehouse(force_scan=False):
            return

        pop = max(1, int(getattr(self, "_supply_cached_population", 1)))
        food_units = self._food_units_per_individual()
        water_units = self._water_units_per_individual()
        food_ratio = self._food_stock_ratio()
        water_ratio = self._water_stock_ratio()
        debuff_mult = self._supply_debuff_multiplier()

        panel_w = 260
        panel_h = 88
        panel_x = 20
        panel_y = 24
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((14, 20, 28, 210))
        pygame.draw.rect(panel, (96, 114, 142), panel.get_rect(), 2, border_radius=10)
        screen.blit(panel, panel_rect.topleft)

        title = self.small_font.render(f"Ravitaillement ({pop} ind.)", True, (220, 230, 245))
        screen.blit(title, (panel_x + 10, panel_y + 6))

        def draw_bar(y: int, label: str, ratio: float, units_per_ind: float, color: tuple[int, int, int]) -> None:
            bar_x = panel_x + 92
            bar_y = y
            bar_w = 152
            bar_h = 12
            clamped = max(0.0, min(1.0, float(ratio)))
            fill_w = int(bar_w * clamped)

            label_surf = self.small_font.render(label, True, (196, 206, 226))
            screen.blit(label_surf, (panel_x + 10, bar_y - 2))
            pygame.draw.rect(screen, (38, 46, 62), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            if fill_w > 0:
                pygame.draw.rect(screen, color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
            pygame.draw.rect(screen, (110, 126, 154), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)
            value = self.small_font.render(f"{units_per_ind:.1f}/ind", True, (224, 230, 240))
            screen.blit(value, (bar_x + bar_w - value.get_width(), bar_y - 14))

        draw_bar(panel_y + 30, "Nourriture", food_ratio, food_units, (224, 174, 76))
        draw_bar(panel_y + 56, "Eau", water_ratio, water_units, (98, 176, 235))

        if debuff_mult < 0.999:
            debuff_pct = int(round((1.0 - debuff_mult) * 100.0))
            alert = self.small_font.render(f"Debuff actif: -{debuff_pct}%", True, (255, 128, 128))
            screen.blit(alert, (panel_x + 10, panel_y + panel_h - 16))

    def apply_day_night_lighting(self, surface: pygame.Surface):
        # Nuit plus marquée par défaut, mais la vision nocturne réduit le filtre sombre.
        nv01 = float(self._player_night_vision01())
        min_light = 0.08 + 0.30 * nv01  # 0.08 (très sombre) -> 0.38 (vision nocturne forte)
        light = self.day_night.get_light_level(min_light=min_light)

        # 1) Brightness (gris) : 255 = normal, <255 = sombre
        m = int(255 * light)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((m, m, m, 255))
        surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # 1.5) Filtre noir additionnel (la vision nocturne l'atténue via 'light')
        night_alpha = int(max(0.0, min(180.0, (1.0 - float(light)) * 180.0)))
        if night_alpha > 0:
            dark = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, night_alpha))
            surface.blit(dark, (0, 0))

        # 1.75) Lumières locales (feux de camp)
        self._apply_campfire_lights(surface, light_level=light)

        # 2) Tint (couleur) léger par-dessus (optionnel mais joli)
        r, g, b = self.day_night.get_ambient_color()
        tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # alpha faible sinon ça “salit” l’image
        tint.fill((r, g, b, 35))
        surface.blit(tint, (0, 0))

    def _apply_campfire_lights(self, surface: pygame.Surface, *, light_level: float) -> None:
        """
        Ajoute un éclairage local autour des feux de camp (pid=101).
        Utilise un blend additif pour "casser" l'obscurité.
        """
        if not self._campfire_tiles:
            return
        try:
            light_level = float(light_level)
        except Exception:
            light_level = 1.0
        darkness = max(0.0, min(1.0, 1.0 - light_level))
        if darkness <= 0.02:
            return

        dx, dy, _wall_h = self.view._proj_consts()
        base_radius = max(48, int(8.5 * float(dy)))
        intensity = 0.35 + 0.85 * darkness
        r0, g0, b0 = 255, 200, 120

        layer = pygame.Surface(surface.get_size())
        layer.fill((0, 0, 0))

        for i, j in list(self._campfire_tiles):
            poly = self.view.tile_surface_poly(int(i), int(j))
            if not poly:
                continue
            cx = int(sum(p[0] for p in poly) / len(poly))
            cy = int(sum(p[1] for p in poly) / len(poly) - float(dy) * 0.6)

            # Si hors-écran, on évite de dessiner
            if cx < -base_radius or cy < -base_radius:
                continue
            sw, sh = surface.get_size()
            if cx > sw + base_radius or cy > sh + base_radius:
                continue

            for k, falloff in enumerate((1.0, 0.70, 0.45, 0.25)):
                radius = int(base_radius * falloff)
                strength = intensity * (0.65 ** k)
                color = (int(r0 * strength), int(g0 * strength), int(b0 * strength))
                pygame.draw.circle(layer, color, (cx, cy), radius)

        surface.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    def _draw_weather_hud(self, screen: pygame.Surface):
        if not self.weather_system or not self.joueur:
            return
        
        try:
            weather_info = self.weather_system.get_weather_info()
            temperature = self.weather_system.get_current_temperature(
                int(self.joueur.x), 
                int(self.joueur.y)
            )
            
            # Dimensions du panel
            w, h = screen.get_size()
            panel_w, panel_h = 220, 95
            x, y = w - panel_w - 20, 20
            
            # Fond
            bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            bg.fill((20, 28, 36, 200))
            pygame.draw.rect(bg, (80, 120, 150), bg.get_rect(), 2, border_radius=10)
            
            # --- MODIFICATION ICI : AFFICHAGE DU SPRITE ---
            weather_id = weather_info.get("id")
            weather_icon_key = weather_info.get("icon")
            weather_name = weather_info.get("name", "Inconnu")
            sprite = self.weather_icons.get(weather_id)
            if sprite is None and weather_icon_key is not None:
                sprite = (
                    self.weather_icons.get(weather_icon_key)
                    or self.weather_icons.get(str(weather_icon_key))
                )
            if sprite is None:
                sprite = self.weather_icons.get(weather_name)
            if sprite is not None:
                # On place le sprite à gauche (x=10, y=15)
                bg.blit(sprite, (10, 15))
            else:
                # Fallback : dessiner un carré gris si l'image manque
                pygame.draw.rect(bg, (100, 100, 100), (10, 15, 40, 40))
            
            # Nom condition (décalé pour laisser la place au sprite)
            font_name = pygame.font.SysFont("consolas", 16, bold=True)
            name_surf = font_name.render(weather_name, True, (220, 230, 255))
            bg.blit(name_surf, (60, 15))
            
            # Température
            font_temp = pygame.font.SysFont("consolas", 20, bold=True)
            temp_color = (100, 150, 255) if temperature < 10 else (255, 150, 100) if temperature > 25 else (200, 220, 200)
            temp_surf = font_temp.render(f"{temperature}°C", True, temp_color)
            bg.blit(temp_surf, (60, 40))
            
            # Temps restant
            font_small = pygame.font.SysFont("consolas", 12)
            time_left = int(weather_info.get("time_remaining", 0))
            time_surf = font_small.render(f"Durée: {time_left}min", True, (180, 180, 180))
            bg.blit(time_surf, (15, 70))
            
            screen.blit(bg, (x, y))
            
        except Exception as e:
            print(f"[Weather] Erreur affichage HUD: {e}")
