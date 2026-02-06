# --- imports en haut du fichier ---
import pygame
import random
import heapq
import json
import hashlib
import math
import time
from typing import Optional
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator
from Game.world.tiles import get_ground_sprite_name
from Game.species.fauna import AggressiveFaunaDefinition, PassiveFaunaFactory, PassiveFaunaDefinition
from Game.species.species import Espece
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
from Game.ui.hud.draggable_window import DraggableWindow
from Game.world.weather import WEATHER_CONDITIONS, WeatherSystem
from Game.gameplay.tech_tree import TechTreeManager
from Game.gameplay.fauna_spawner import FaunaSpawner

_WATER_BIOME_IDS = {1, 3, 4}
_AUTO_HARVESTABLE_PROP_IDS = {
    10, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 23, 29, 30, 31, 32, 33, 34,
    35, 36, 37, 38, 39, 40,
}

class Phase1:
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False

        self.view = IsoMapView(self.assets, self.screen.get_size())
        self.gen = WorldGenerator(tiles_levels=6, chunk_size=64, cache_chunks=256)
        self.params = None
        self.world = None
        self.fog=None
        
        # Système jour/nuit
        # Cycle de 10 minutes réelles (600 secondes)
        self.day_night = DayNightCycle(cycle_duration=600)
        self.day_night.set_time(6, 0)  # Commence à 6h du matin
        self.day_night.set_speed(3.0)   # Vitesse normale
        self.event_manager = EventManager()
        #Météo
        self.weather_system = None 
        self.weather_icons: dict[str, pygame.Surface] = {}
        self._load_weather_icons()
        self._weather_vfx_particles: dict[str, list[dict]] = {
            "rain": [],
            "snow": [],
            "sand": [],
        }
        self._weather_vfx_time = 0.0
        self._weather_flash_timer = 0.0
        self._weather_flash_alpha = 0
        self._weather_last_condition_id = None
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
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False

        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None
        self._game_end_summary = None
        self._game_end_xp = 0
        self._gameplay_ready = False
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
        self.ui_menu_open = False
        self.right_hud = LeftHUD(self)


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
        self.session_time_seconds = 0.0
        self._game_end_pending = False
        self._game_end_reason = None

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
        self.right_hud = LeftHUD(self)
        self.bottom_hud = None
        self._set_cursor(self.default_cursor_path)
        self._init_craft_unlocks()
        self.happiness = 10.0
        self.happiness_min = -100.0
        self.happiness_max = 100.0
        self.species_death_count = 0
        self.death_event_ready = False
        self.death_response_mode = None
        self.food_reserve_capacity = 100
        self.weather_system = None
        self._weather_vfx_particles = {"rain": [], "snow": [], "sand": []}
        self._weather_vfx_time = 0.0
        self._weather_flash_timer = 0.0
        self._weather_flash_alpha = 0
        self._weather_last_condition_id = None
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
    def _attach_phase_to_entities(self):
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
        # Nettoie les fenêtres d'info éventuelles (pour éviter les références périmées)
        self.info_windows = []
        # Réinitialise le curseur
        self._set_cursor(self.default_cursor_path)

    def _load_weather_icons(self):
        """Charge les icônes météo disponibles dans le pack d'assets."""
        self.weather_icons = {}
        if not self.assets:
            return

        default_sprite = None
        try:
            default_sprite = self.assets.get_image("placeholder")
        except Exception:
            default_sprite = None

        for condition_id, condition in WEATHER_CONDITIONS.items():
            sprite_key = condition.sprites or condition_id
            try:
                sprite = self.assets.get_image(sprite_key)
            except Exception:
                sprite = default_sprite
            if sprite is None:
                continue

            scaled_sprite = pygame.transform.smoothscale(sprite, (40, 40))
            self.weather_icons[condition_id] = scaled_sprite
            self.weather_icons[str(sprite_key)] = scaled_sprite
            self.weather_icons[condition.name] = scaled_sprite

    def _ensure_weather_system(self):
        """Initialise la météo si un monde est présent."""
        if self.weather_system is not None or self.world is None:
            return
        try:
            raw_seed = getattr(self.params, "seed", 0) if self.params is not None else 0
            world_seed = getattr(self.world, "seed", None)
            if isinstance(raw_seed, str):
                # Ex: "Aléatoire" dans le menu de création.
                # Si le monde a déjà un seed final, on l'utilise.
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
        except Exception as e:
            print(f"[Weather] Erreur initialisation: {e}")

    def _reset_weather_vfx_if_needed(self, condition_id: str | None):
        if condition_id == self._weather_last_condition_id:
            return
        self._weather_last_condition_id = condition_id
        self._weather_vfx_particles["rain"].clear()
        self._weather_vfx_particles["snow"].clear()
        self._weather_vfx_particles["sand"].clear()
        self._weather_flash_timer = 0.0
        self._weather_flash_alpha = 0

    def _update_weather_vfx(self, dt: float):
        if not self.weather_system:
            return

        weather_info = self.weather_system.get_weather_info()
        condition_id = weather_info.get("id")
        self._reset_weather_vfx_if_needed(condition_id)
        self._weather_vfx_time += max(0.0, dt)

        w, h = self.screen.get_size()
        area_scale = max(0.55, min(2.0, (w * h) / (1280 * 720)))

        rain_target = 0
        snow_target = 0
        sand_target = 0

        if condition_id == "rain":
            rain_target = int(150 * area_scale)
        elif condition_id == "heavy_rain":
            rain_target = int(250 * area_scale)
        elif condition_id == "storm":
            rain_target = int(320 * area_scale)
        elif condition_id == "snow":
            snow_target = int(120 * area_scale)
        elif condition_id == "blizzard":
            snow_target = int(230 * area_scale)
        elif condition_id == "sandstorm":
            sand_target = int(220 * area_scale)

        rain_particles = self._weather_vfx_particles["rain"]
        while len(rain_particles) < rain_target:
            rain_particles.append({
                "x": random.uniform(-w * 0.2, w * 1.2),
                "y": random.uniform(-h, 0),
                "vx": random.uniform(-140.0, -40.0),
                "vy": random.uniform(620.0, 980.0),
                "length": random.uniform(8.0, 20.0),
                "width": random.choice((1, 1, 1, 2)),
            })
        del rain_particles[rain_target:]

        for p in rain_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["y"] > h + 24 or p["x"] < -w * 0.3:
                p["x"] = random.uniform(-w * 0.2, w * 1.2)
                p["y"] = random.uniform(-h * 0.35, -8.0)

        snow_particles = self._weather_vfx_particles["snow"]
        while len(snow_particles) < snow_target:
            snow_particles.append({
                "x": random.uniform(0, w),
                "y": random.uniform(-h, 0),
                "vx": random.uniform(-30.0, 30.0),
                "vy": random.uniform(30.0, 80.0),
                "radius": random.uniform(1.5, 3.8),
                "phase": random.uniform(0.0, math.tau),
            })
        del snow_particles[snow_target:]

        for p in snow_particles:
            p["x"] += (p["vx"] + math.sin(self._weather_vfx_time * 1.6 + p["phase"]) * 18.0) * dt
            p["y"] += p["vy"] * dt
            if p["y"] > h + 8:
                p["y"] = random.uniform(-h * 0.3, -6.0)
                p["x"] = random.uniform(0, w)
            elif p["x"] < -12:
                p["x"] = w + 12
            elif p["x"] > w + 12:
                p["x"] = -12

        sand_particles = self._weather_vfx_particles["sand"]
        while len(sand_particles) < sand_target:
            sand_particles.append({
                "x": random.uniform(-w, 0),
                "y": random.uniform(0, h),
                "vx": random.uniform(260.0, 440.0),
                "vy": random.uniform(-20.0, 20.0),
                "length": random.uniform(10.0, 18.0),
            })
        del sand_particles[sand_target:]

        for p in sand_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["x"] > w + 20:
                p["x"] = random.uniform(-w * 0.35, -8.0)
                p["y"] = random.uniform(0, h)
            elif p["y"] < -8 or p["y"] > h + 8:
                p["y"] = random.uniform(0, h)

        if condition_id == "storm":
            if self._weather_flash_timer > 0.0:
                self._weather_flash_timer -= dt
                self._weather_flash_alpha = max(0, int(self._weather_flash_alpha * 0.88))
            elif random.random() < min(0.35 * max(dt, 0.0), 0.2):
                self._weather_flash_timer = random.uniform(0.05, 0.18)
                self._weather_flash_alpha = random.randint(120, 185)
        else:
            self._weather_flash_timer = 0.0
            self._weather_flash_alpha = 0

    def _draw_weather_effects(self, screen: pygame.Surface):
        if not self.weather_system:
            return

        condition_id = self.weather_system.get_weather_info().get("id")
        if not condition_id:
            return

        w, h = screen.get_size()
        fx = pygame.Surface((w, h), pygame.SRCALPHA)

        if condition_id in ("rain", "heavy_rain", "storm"):
            rain_color = (160, 185, 220, 150 if condition_id == "rain" else 180)
            for p in self._weather_vfx_particles["rain"]:
                x0 = int(p["x"])
                y0 = int(p["y"])
                x1 = int(p["x"] + (p["vx"] / max(p["vy"], 1.0)) * p["length"])
                y1 = int(p["y"] + p["length"])
                pygame.draw.line(fx, rain_color, (x0, y0), (x1, y1), int(p["width"]))
            if condition_id in ("heavy_rain", "storm"):
                fx.fill((16, 24, 36, 28), special_flags=pygame.BLEND_RGBA_ADD)

        if condition_id in ("snow", "blizzard"):
            for p in self._weather_vfx_particles["snow"]:
                pygame.draw.circle(
                    fx,
                    (245, 248, 255, 190 if condition_id == "blizzard" else 160),
                    (int(p["x"]), int(p["y"])),
                    max(1, int(p["radius"])),
                )
            if condition_id == "blizzard":
                fx.fill((210, 220, 235, 40))

        if condition_id == "sandstorm":
            fx.fill((165, 120, 65, 58))
            for p in self._weather_vfx_particles["sand"]:
                x0 = int(p["x"])
                y0 = int(p["y"])
                x1 = int(p["x"] + p["length"])
                y1 = int(p["y"] + p["length"] * 0.06)
                pygame.draw.line(fx, (225, 185, 120, 140), (x0, y0), (x1, y1), 2)

        if condition_id == "fog":
            fx.fill((208, 220, 228, 74))
            for i in range(4):
                y = int((i + 0.2) * (h / 4) + math.sin(self._weather_vfx_time * 0.35 + i * 0.9) * 24)
                band_h = int(h * 0.22)
                pygame.draw.ellipse(
                    fx,
                    (228, 236, 242, 36),
                    (-int(w * 0.12), y, int(w * 1.25), band_h),
                )

        if condition_id == "heatwave":
            fx.fill((255, 188, 118, 22))
            for y in range(0, h, 7):
                shift = int(math.sin(self._weather_vfx_time * 4.0 + y * 0.028) * 4)
                pygame.draw.line(fx, (255, 218, 165, 18), (0 + shift, y), (w + shift, y), 1)

        if condition_id == "cloudy":
            fx.fill((86, 96, 112, 18))

        if condition_id == "storm":
            fx.fill((10, 14, 24, 44))

        screen.blit(fx, (0, 0))

        if self._weather_flash_alpha > 0:
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((236, 244, 255, self._weather_flash_alpha))
            screen.blit(flash, (0, 0))

    def _init_craft_unlocks(self):
        """Initialise l'ensemble des crafts accessibles par défaut."""
        tech_locked_crafts: set[str] = set()
        if self.tech_tree and getattr(self.tech_tree, "techs", None):
            for tech_data in (self.tech_tree.techs or {}).values():
                if not isinstance(tech_data, dict):
                    continue
                for craft_id in tech_data.get("craft", []) or []:
                    if craft_id:
                        tech_locked_crafts.add(str(craft_id))

        self.unlocked_crafts = set()
        for cid, craft_def in self.craft_system.crafts.items():
            locked = craft_def.get("locked") or craft_def.get("requires_unlock")
            if cid in tech_locked_crafts:
                locked = True
            if not locked:
                self.unlocked_crafts.add(cid)

    def _on_tech_unlocked(self, tech_id: str, tech_data: dict) -> None:
        for craft_id in tech_data.get("craft", []) or []:
            self.unlock_craft(craft_id)
        name = tech_data.get("nom", tech_id)
        add_notification(f"Technologie débloquée : {name}")

    def start_tech_research(self, tech_id: str) -> bool:
        if not self.tech_tree:
            return False
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
        if not hasattr(ent, "move_speed"):  ent.move_speed = 3.5        # tuiles/s
        if not hasattr(ent, "_move_from"):  ent._move_from = None       # (x,y) float
        if not hasattr(ent, "_move_to"):    ent._move_to = None         # (i,j) int
        if not hasattr(ent, "_move_t"):     ent._move_t = 0.0           # 0..1
        if not hasattr(ent, "_combat_target"): ent._combat_target = None
        if not hasattr(ent, "_combat_attack_cd"): ent._combat_attack_cd = 0.0
        if not hasattr(ent, "_combat_repath_cd"): ent._combat_repath_cd = 0.0
        # ---------- Mutations de base de l'espèce ----------

    def _clear_entity_combat_refs(self, ent):
        self._ensure_move_runtime(ent)
        ent._combat_target = None
        ent._combat_attack_cd = 0.0
        ent._combat_repath_cd = 0.0

    def _stop_entity_combat(self, ent, stop_motion: bool = True):
        self._clear_entity_combat_refs(ent)
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return
        if ent.ia.get("etat") == "combat":
            ent.ia["etat"] = "idle"
            ent.ia["objectif"] = None
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None
        if stop_motion:
            ent.move_path = []
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = None
            ent._move_t = 0.0

    def _start_entity_combat(self, attacker, target) -> bool:
        if not attacker or not target:
            return False
        if attacker is target:
            return False
        if attacker not in self.entities or target not in self.entities:
            return False
        if getattr(attacker, "is_egg", False):
            return False
        if getattr(target, "is_egg", False):
            return False
        if not hasattr(attacker, "ia") or not isinstance(attacker.ia, dict):
            return False
        if getattr(target, "_dead_processed", False) or target.jauges.get("sante", 0) <= 0:
            return False

        attacker_is_fauna = bool(getattr(attacker, "is_fauna", False))
        attacker_is_aggressive = bool(getattr(attacker, "is_aggressive", False))
        target_is_fauna = bool(getattr(target, "is_fauna", False))

        if attacker_is_fauna and not attacker_is_aggressive:
            return False
        if attacker_is_aggressive:
            if target_is_fauna:
                return False
        else:
            if not target_is_fauna:
                return False

        self._ensure_move_runtime(attacker)
        if hasattr(attacker, "comportement"):
            attacker.comportement.cancel_work("combat_start")
        attacker.ia["etat"] = "combat"
        attacker.ia["objectif"] = ("combat", (int(target.x), int(target.y)))
        attacker.ia["order_action"] = None
        attacker.ia["target_craft_id"] = None
        attacker._combat_target = target
        attacker._combat_attack_cd = 0.0
        attacker._combat_repath_cd = 0.0
        return True

    def _combat_attack_interval(self, attacker) -> float:
        speed = float(getattr(attacker, "physique", {}).get("vitesse", 3) or 3)
        agilite = float(getattr(attacker, "combat", {}).get("agilite", 0) or 0)
        base = max(0.35, 1.2 - speed * 0.05 - agilite * 0.01)
        combat = getattr(attacker, "combat", {}) or {}
        atk_speed = combat.get("attaque_speed", combat.get("attack_speed", None))
        try:
            atk_speed = float(atk_speed) if atk_speed is not None else None
        except Exception:
            atk_speed = None
        if atk_speed is not None and atk_speed > 0:
            return max(0.2, base / atk_speed)
        return base

    def _combat_attack_range(self, attacker) -> float:
        taille = float(getattr(attacker, "physique", {}).get("taille", 3) or 3)
        return max(0.85, 0.75 + taille * 0.06)

    def _combat_damage(self, attacker, target) -> float:
        physique = getattr(attacker, "physique", {}) or {}
        force = float(physique.get("force", 1) or 1)
        speed = float(physique.get("vitesse", 1) or 1)
        taille = float(physique.get("taille", 1) or 1)
        combat = getattr(attacker, "combat", {}) or {}
        melee = float(combat.get("attaque_melee", 0) or 0)
        attack_bonus = float(combat.get("attaque", combat.get("attack", 0)) or 0)
        defense = float(getattr(target, "combat", {}).get("defense", 0) or 0)

        raw = 1.0 + force * 1.4 + speed * 0.55 + taille * 0.2 + melee * 0.05 + attack_bonus
        reduced = raw - defense * 0.2
        dmg = max(1.0, reduced)
        return dmg * random.uniform(0.9, 1.1)

    def _grant_fauna_combat_rewards(self, attacker, target):
        if not attacker or not target:
            return
        if getattr(target, "_combat_loot_granted", False):
            return
        target._combat_loot_granted = True

        physique = getattr(target, "physique", {}) or {}
        taille = float(physique.get("taille", 2) or 2)
        endurance = float(physique.get("endurance", 3) or 3)
        xp_gain = max(8, int(round(endurance * 5 + taille * 2)))
        attacker.add_xp(xp_gain)

        meat_qty = max(1, int(round(taille * 0.7 + endurance * 0.35 + random.uniform(0.2, 1.2))))
        leather_qty = int(taille // 3)
        if random.random() < 0.55:
            leather_qty += 1

        drops = [("meat", meat_qty)]
        if leather_qty > 0:
            drops.append(("leather", leather_qty))

        gained: list[str] = []
        for item_id, qty in drops:
            taken = 0
            if hasattr(attacker, "comportement") and hasattr(attacker.comportement, "_add_to_inventory"):
                try:
                    taken = int(attacker.comportement._add_to_inventory(item_id, int(qty)))
                except Exception:
                    taken = 0
            if taken > 0:
                gained.append(f"{item_id} x{taken}")

        add_notification(f"{attacker.nom} a vaincu {target.nom} (+{xp_gain} XP espèce).")
        if gained:
            add_notification("Butin récupéré : " + ", ".join(gained))

    def _update_entity_combat(self, ent, dt: float):
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return
        self._ensure_move_runtime(ent)

        if ent.ia.get("etat") != "combat":
            if ent._combat_target is not None:
                self._clear_entity_combat_refs(ent)
            return

        if getattr(ent, "is_fauna", False) and not getattr(ent, "is_aggressive", False):
            self._stop_entity_combat(ent)
            return

        target = ent._combat_target
        if (
            target is None
            or target is ent
            or target not in self.entities
        ):
            self._stop_entity_combat(ent)
            return
        if getattr(ent, "is_aggressive", False):
            if getattr(target, "is_fauna", False) or getattr(target, "is_egg", False):
                self._stop_entity_combat(ent)
                return
        else:
            if not getattr(target, "is_fauna", False):
                self._stop_entity_combat(ent)
                return
        if getattr(target, "_dead_processed", False) or target.jauges.get("sante", 0) <= 0:
            self._stop_entity_combat(ent)
            return

        dist = math.hypot(float(target.x) - float(ent.x), float(target.y) - float(ent.y))
        attack_range = self._combat_attack_range(ent)

        ent._combat_attack_cd = max(0.0, float(ent._combat_attack_cd) - dt)

        if dist <= attack_range:
            ent.move_path = []
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = None
            ent._move_t = 0.0

            if ent._combat_attack_cd > 0.0:
                return

            damage = self._combat_damage(ent, target)
            target.jauges["sante"] = max(0.0, float(target.jauges.get("sante", 0)) - damage)
            target._last_attacker = ent
            ent._combat_attack_cd = self._combat_attack_interval(ent)
            if hasattr(ent, "attack_anim_ms"):
                ent._attack_anim_until_ms = pygame.time.get_ticks() + int(ent.attack_anim_ms)

            if target.jauges.get("sante", 0) <= 0:
                if not getattr(ent, "is_fauna", False) and getattr(target, "is_fauna", False):
                    self._grant_fauna_combat_rewards(ent, target)
                self._stop_entity_combat(ent)
            return

        ent._combat_repath_cd = max(0.0, float(ent._combat_repath_cd) - dt)
        if ent._combat_repath_cd > 0.0:
            return

        chase_tile = self._find_nearest_walkable(
            (int(target.x), int(target.y)),
            max_radius=2,
            forbidden=self._occupied_tiles(exclude=[ent, target]),
        )
        if chase_tile is None:
            chase_tile = (int(target.x), int(target.y))

        self._apply_entity_order(
            ent,
            target=chase_tile,
            etat="combat",
            objectif=("combat", (int(target.x), int(target.y))),
            action_mode=None,
            craft_id=None,
        )
        ent._combat_repath_cd = 0.25

    def _draw_fauna_health_bar(self, screen, ent):
        if not getattr(ent, "is_fauna", False):
            return
        if ent.jauges.get("sante", 0) <= 0:
            return
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return

        max_hp = float(getattr(ent, "max_sante", 100) or 100)
        hp = float(ent.jauges.get("sante", 0) or 0)
        ratio = max(0.0, min(1.0, hp / max(1.0, max_hp)))

        cx = sum(p[0] for p in poly) / len(poly)
        top = min(p[1] for p in poly) - 18
        bar_w, bar_h = 46, 7
        bg = pygame.Rect(int(cx - bar_w / 2), int(top - bar_h), bar_w, bar_h)
        fg = bg.inflate(-2, -2)
        fg.width = int(max(1, fg.width) * ratio)

        surface = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 175))
        screen.blit(surface, (bg.x, bg.y))

        if fg.width > 0:
            color = (220, 60, 60) if ratio < 0.35 else (235, 170, 60) if ratio < 0.7 else (90, 205, 105)
            pygame.draw.rect(screen, color, fg, border_radius=2)

    def _draw_species_health_bar(self, screen, ent):
        if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
            return
        if getattr(ent, "espece", None) != self.espece:
            return
        max_hp = float(getattr(ent, "max_sante", 100) or 100)
        hp = float(ent.jauges.get("sante", 0) or 0)
        if hp <= 0 or hp >= max_hp:
            return
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return

        ratio = max(0.0, min(1.0, hp / max(1.0, max_hp)))
        cx = sum(p[0] for p in poly) / len(poly)
        top = min(p[1] for p in poly) - 22
        bar_w, bar_h = 48, 6
        bg = pygame.Rect(int(cx - bar_w / 2), int(top - bar_h), bar_w, bar_h)
        fg = bg.inflate(-2, -2)
        fg.width = int(max(1, fg.width) * ratio)

        surface = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 165))
        screen.blit(surface, (bg.x, bg.y))

        if fg.width > 0:
            color = (220, 80, 80) if ratio < 0.35 else (235, 170, 60) if ratio < 0.7 else (90, 205, 105)
            pygame.draw.rect(screen, color, fg, border_radius=2)

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

    def set_death_policy(self, mode: str | None):
        self.death_response_mode = mode
        if mode:
            add_notification(f"Gestion des corps choisie : {mode}.")

    def _food_stock_ratio(self) -> float:
        capacity = max(1.0, float(self.food_reserve_capacity))
        stock = float(self.warehouse.get("food", 0)) + float(self.warehouse.get("meat", 0))
        return stock / capacity

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
        espece_name = getattr(self.espece, "nom", "") if self.espece else ""
        species_level = int(getattr(self.espece, "species_level", 1) or 1) if self.espece else 1
        days = int(getattr(self.day_night, "jour", 0) or 0)
        deaths = int(getattr(self, "species_death_count", 0) or 0)
        play_time = int(self.session_time_seconds or 0)
        return {
            "species_name": espece_name,
            "species_level": species_level,
            "days_survived": days,
            "deaths": deaths,
            "play_time_sec": play_time,
            "reason": reason,
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
        ent._dead_processed = True
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
            self.species_death_count += 1
            survivors = self._count_living_species_members()
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

    # ---------- FAUNE PASSIVE ----------
    def _rabbit_definition(self):
        return PassiveFaunaDefinition(
            species_name="Lapin",
            entity_name="Lapin",
            move_speed=2.1,
            hp=100,
            vision_range=10.0,
            flee_distance=6.0,
            sprite_sheet_idle="rabbit_idle",
            sprite_sheet_run="rabbit_run",
            sprite_sheet_frame_size=(32, 32),
            sprite_base_scale=0.75,
        )
    
    def capybara_definition(self):
        return PassiveFaunaDefinition(
            species_name="Capybara",
            entity_name="Capybara",
            move_speed=1.1,
            hp=100,
            vision_range=4.0,
            flee_distance=1.0,
            sprite_sheet_idle="capybara_idle",
            sprite_sheet_frame_size=(32, 32),
            sprite_base_scale=0.75,
        )

    def _scorpion_definition(self):
        return AggressiveFaunaDefinition(
            species_name="Scorpion",
            entity_name="Scorpion",
            move_speed=3.6,
            hp=70,
            vision_range=15.0,
            flee_distance=0.0,
            attack=3.0,
            attack_speed=1.7,
            sprite_sheet_idle="scorpion_idle",
            sprite_sheet_frame_size=(32, 32),
            sprite_base_scale=0.8,
        )
    
    def _champi_definition(self):
        return AggressiveFaunaDefinition(
            species_name="Scorpion",
            entity_name="Scorpion",
            move_speed=1.6,
            hp=200,
            vision_range=6.0,
            flee_distance=0.0,
            attack=10.0,
            attack_speed=0.6,
            sprite_sheet_idle="champi_idle",
            sprite_sheet_frame_size=(32, 32),
            sprite_base_scale=0.8,
        )

    def _fauna_definition_catalog(self) -> dict[str, PassiveFaunaDefinition]:
        return {
            "lapin": self._rabbit_definition(),
            "rabbit": self._rabbit_definition(),
            "capybara": self.capybara_definition(),
            "scorpion": self._scorpion_definition(),
            "champi": self._champi_definition(),
        }

    def get_fauna_definition(self, species_id: str | None) -> Optional[PassiveFaunaDefinition]:
        if not species_id:
            return None
        key = str(species_id).strip().lower()
        return self._fauna_definition_catalog().get(key)

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
                self._ensure_weather_system()
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
                self._perf_enter_mark(perf, "Entites rattachees a la phase")
            if self.bottom_hud is None:
                self.bottom_hud = BottomHUD(self, self.espece, self.day_night)
                self._perf_enter_mark(perf, "BottomHUD cree")
            else:
                self.bottom_hud.species = self.espece
                self._perf_enter_mark(perf, "BottomHUD espece mise a jour")
            self._perf_enter_mark(perf, "Entree terminee (monde pre-genere)")            
            self._ensure_weather_system()
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
        self._gameplay_ready = True
        self._endgame_debug(
            f"enter(new) entities={len(self.entities)} species={getattr(self.espece,'nom',None)} "
            f"living={self._count_living_species_members()} pending={self._game_end_pending}"
        )

    # ---------- INPUT ----------
    def handle_input(self, events):
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
                    self.paused = not self.paused
                elif e.key == pygame.K_F6:
                    self._ensure_weather_system()
                    if self.weather_system:
                        self.weather_system.force_weather("rain", duration_minutes=30.0)
                        add_notification("Meteo forcee : pluie")
                elif e.key == pygame.K_h:
                    self.props_transparency_active = True
                    self.view.set_props_transparency(True)
                elif e.key == pygame.K_i:
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

            elif e.type == pygame.KEYUP and e.key == pygame.K_h:
                self.props_transparency_active = False
                self.view.set_props_transparency(False)
            elif e.type == pygame.KEYUP and e.key == pygame.K_i:
                self.inspect_mode_active = False
                self._set_cursor(self.default_cursor_path)

            if not self.paused:
                if e.type == pygame.MOUSEWHEEL and self._ui_captures_click(pygame.mouse.get_pos()):
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

                    if keys_state[pygame.K_i]:
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



            if self.paused and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.end_run_button_rect and self.end_run_button_rect.collidepoint(e.pos):
                    self.paused = False
                    self._trigger_end_game("Partie terminee par le joueur.")
                    return
                if self.menu_button_rect and self.menu_button_rect.collidepoint(e.pos):
                    self.paused = False  # pour éviter que le rendu de pause bloque tout

                    # --- Sauvegarde avant retour au menu ---
                    try:
                        ok = self.save()
                        if ok:
                            self.save_message = "Sauvegarde effectuée !"
                        else:
                            print("[Phase1] Sauvegarde échouée.")
                            self.save_message = "Erreur de sauvegarde."
                    except Exception as ex:
                        print(f"[Phase1] Erreur lors de la sauvegarde: {ex}")
                        self.save_message = "Erreur de sauvegarde."

                    self.save_message_timer = 2.5
                    pygame.display.flip()  # force un dernier rendu avant de changer d'état
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
        if self.paused or self.ui_menu_open:
            # Meme en pause on continue les timers d'evenements
            self.event_manager.update(dt, self)
            mark("Sortie rapide pause/menu")
            if self._perf_trace_frames > 0:
                self._perf_trace_frames -= 1
            return

        self.session_time_seconds += dt

        self._update_frame_id += 1
        self.event_manager.update(dt, self)
        mark("Event manager update")

        # Mettre a jour le cycle jour/nuit
        self.day_night.update(dt)
        if self.weather_system and self.joueur:
            self.weather_system.update(
                dt,
                int(self.joueur.x),
                int(self.joueur.y),
            )
        self._update_weather_vfx(dt)
        mark("Day/night update")

        if self.tech_tree:
            current_day = self.day_night.jour
            if current_day > self._last_innovation_day:
                for _ in range(current_day - self._last_innovation_day):
                    self.tech_tree.add_innovation(1)
                self._last_innovation_day = current_day
        mark("Tech tree update")

        if self.espece and getattr(self.espece, "reproduction_system", None):
            try:
                self.espece.reproduction_system.update(dt)
            except Exception as e:
                print(f"[Reproduction] update error: {e}")
        mark("Reproduction update")

        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)
        mark("Vue update")

        def get_radius(ent):
            if getattr(ent, "is_egg", False):
                return 1
            vision = ent.sens.get("vision", 5)
            return max(2, int(1 + vision * 0.7))

        if self.fog:
            light_level = self.day_night.get_light_level()

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

        dead_entities: list = []
        for e in list(self.entities):
            if getattr(e, "is_egg", False):
                continue
            self._ensure_move_runtime(e)
            self._update_entity_movement(e, dt)
            e.faim_timer += dt
            if e.faim_timer >= 5.0:
                e.faim_timer = 0
                e.jauges["faim"] -= 1
                if e.jauges["faim"] < 20:
                    e.comportement.try_eating()
            if hasattr(e, "comportement"):
                e.comportement.update(dt, self.world)
            self._update_entity_combat(e, dt)
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
        mark("Construction sites update")

        if self.save_message_timer > 0:
            self.save_message_timer -= dt
            if self.save_message_timer <= 0:
                self.save_message = ""

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
            text_rect = text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 100))
            screen.blit(text, text_rect)
            
            # Boutons
            button_width = 320
            button_height = 60
            button_x = screen.get_width() / 2 - button_width / 2
            end_button_y = screen.get_height() / 2 - 30
            menu_button_y = screen.get_height() / 2 + 50

            self.end_run_button_rect = pygame.Rect(button_x, end_button_y, button_width, button_height)
            self.menu_button_rect = pygame.Rect(button_x, menu_button_y, button_width, button_height)

            mouse_pos = pygame.mouse.get_pos()
            font_button = pygame.font.SysFont(None, 36)

            for rect, label in (
                (self.end_run_button_rect, "Terminer la partie"),
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

    # ---------- RENDER ----------
    def render(self, screen: pygame.Surface):
        screen.fill((10, 12, 18))
        self.view.begin_hitframe()
        
        # 1) Rendu carte + entités
        self.view.render(screen, world_entities=self.entities)

        self._draw_construction_bars(screen)
        dx, dy, wall_h = self.view._proj_consts()
        for ent in self.entities:
            self._draw_fauna_health_bar(screen, ent)
            self._draw_species_health_bar(screen, ent)
            draw_work_bar(self, screen, ent)

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
            self._draw_weather_hud(screen)
        
        # 2bis) Sélection rectangle (drag)
        self._draw_selection_box(screen)

        # 3) Marqueur de sélection
        self._draw_selection_marker(screen)
        self._draw_hover_entity_name(screen)

        # 4) HUD / pause / notifications
        if self.paused and not self.ui_menu_open:
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
        target = self._find_nearest_walkable((i, j), forbidden=self._occupied_tiles(exclude=[ent]))
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
        target = self._find_nearest_walkable((i, j), forbidden=self._occupied_tiles(exclude=[ent]))
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
            if self._is_walkable(*tile):
                ent.ia["auto_walk_dir"] = idx
                return tile

        fallback = self._find_nearest_walkable((ex, ey), max_radius=2, forbidden=occupied)
        if fallback and fallback != (ex, ey):
            return fallback
        return None

    def _update_entity_auto_mode(self, ent, dt: float):
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return
        if ent.ia.get("auto_mode") != "harvest":
            return
        if getattr(ent, "is_fauna", False):
            return

        cooldown = max(0.0, float(ent.ia.get("auto_next_decision_in", 0.0) or 0.0) - dt)
        ent.ia["auto_next_decision_in"] = cooldown
        if cooldown > 0.0:
            return
        ent.ia["auto_next_decision_in"] = 0.2

        force_deposit = bool(ent.ia.get("auto_need_deposit")) or self._entity_inventory_is_full(ent)
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

        harvest_target = self._auto_find_nearest_harvestable_prop(ent)
        if harvest_target and self._auto_order_harvest(ent, harvest_target):
            ent.ia["auto_next_decision_in"] = 0.45
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
        name = craft_def.get("name") if craft_def else None
        if not name:
            name = f"Prop {pid}"
        desc = craft_def.get("description") if craft_def else None
        interaction = craft_def.get("interaction") if craft_def else None

        content_lines: list[str] = []
        if desc:
            content_lines.extend(desc.split("\n"))
        else:
            content_lines.append("Aucune description.")

        # Infos spéciales entrepôt
        if isinstance(interaction, dict) and interaction.get("type") == "warehouse":
            if not self.warehouse:
                content_lines.append("Entrepôt : aucun stock.")
            else:
                content_lines.append("Contenu de l'entrepôt :")
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

    # ---------- PATHFINDING & COLLISIONS ----------
    def _is_walkable(self, i: int, j: int, generate: bool = True) -> bool:
        w = self.world
        if not w: return False
        if i < 0 or j < 0 or i >= w.width or j >= w.height:
            return False

        if hasattr(w, "get_tile_snapshot"):
            snap = w.get_tile_snapshot(i, j, generate=generate)
            if snap is None:
                return False
            _lvl, gid, overlay, bid = snap
            if overlay:
                return False
            if int(bid) in _WATER_BIOME_IDS:
                return False
            # Fallback ultra conservateur pour anciens IDs/tiles.
            name = get_ground_sprite_name(gid) if gid is not None else None
            if name and any(token in name.lower() for token in ("water", "ocean", "sea", "lake")):
                return False
            return True

        # Fallback pour mondes qui n'exposent pas get_tile_snapshot.
        try:
            pid = w.overlay[j][i]
            if pid:
                return False
        except Exception:
            pass
        try:
            gid = w.ground_id[j][i]
        except Exception:
            gid = None
        name = get_ground_sprite_name(gid) if gid is not None else None
        if name and any(token in name.lower() for token in ("water", "ocean", "sea", "lake")):
            return False
        return True

    def _occupied_tiles(self, exclude: list | None = None) -> set[tuple[int, int]]:
        exclude = set(exclude or [])
        occupied = set()
        for ent in self.entities:
            if ent in exclude:
                continue
            occupied.add((int(ent.x), int(ent.y)))
        return occupied

    def _get_construction_cell(self, i: int, j: int):
        try:
            return self.world.overlay[j][i] if self.world else None
        except Exception:
            return None

    def _is_construction_site(self, i: int, j: int) -> bool:
        cell = self._get_construction_cell(i, j)
        return isinstance(cell, dict) and cell.get("state") == "building"

    def _astar_path(self, start: tuple[int,int], goal: tuple[int,int]) -> list[tuple[int,int]]:
        if not self._is_walkable(*goal):
            return []
        sx, sy = start; gx, gy = goal
        if (sx, sy) == (gx, gy):
            return []

        # Heuristique octile (8-connexe, coût diag = sqrt(2))
        import math
        def h(a, b):
            dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
            return (dx + dy) + (math.sqrt(2) - 2.0) * min(dx, dy)

        openh = []
        heapq.heappush(openh, (h(start, goal), 0.0, start))
        came = {start: None}
        gscore = {start: 0.0}

        neigh = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        while openh:
            _, gc, cur = heapq.heappop(openh)
            if cur == goal:
                path = []
                while cur in came and cur is not None:
                    path.append(cur); cur = came[cur]
                path.reverse()
                return path

            for dx, dy in neigh:
                nx, ny = cur[0] + dx, cur[1] + dy
                if not self._is_walkable(nx, ny):
                    continue
                step_cost = math.sqrt(2.0) if dx != 0 and dy != 0 else 1.0
                ng = gc + step_cost
                if ng < gscore.get((nx, ny), 1e18):
                    gscore[(nx, ny)] = ng
                    came[(nx, ny)] = cur
                    f = ng + h((nx, ny), goal)
                    heapq.heappush(openh, (f, ng, (nx, ny)))
        return []

    def _los_clear(self, a: tuple[float,float], b: tuple[float,float]) -> bool:
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
            if not self._is_walkable(int(x), int(y)):
                return False
        return True

    def _smooth_path(self, nodes: list[tuple[int,int]]) -> list[tuple[float,float]]:
        """
        String-pulling simple : on garde le point courant, on pousse aussi loin
        que possible en conservant la visibilité, puis on place un waypoint au
        centre de la case retenue.
        """
        if not nodes:
            return []
        # Convertit nodes -> centres flottants
        pts = [(i + 0.5, j + 0.5) for (i, j) in nodes]
        smoothed = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            # recule tant que la LOS échoue
            while j > i + 1 and not self._los_clear(pts[i], pts[j]):
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
        speed = max(0.2, float(getattr(ent, "move_speed", 3.5)))
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

    def _find_nearest_walkable(self, target: tuple[int, int], max_radius: int = 8, forbidden: set[tuple[int, int]] | None = None) -> Optional[tuple[int, int]]:
        """Retourne la case libre la plus proche du point cible (si eau/obstacle), en évitant les cases interdites."""
        tx, ty = target
        forbidden = forbidden or set()
        if self._is_walkable(tx, ty) and (tx, ty) not in forbidden:
            return target

        best = None
        best_dist = 9999
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = tx + dx, ty + dy
                    if not self._is_walkable(nx, ny):
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

        start_pos = (int(ent.x), int(ent.y))
        raw_path = self._astar_path(start_pos, target)
        if not raw_path:
            if start_pos == target:
                ent.move_path = []
                ent._move_from = (float(ent.x), float(ent.y))
                ent._move_to = None
                ent._move_t = 0.0
                return True
            return False
        if raw_path and raw_path[0] == start_pos:
            raw_path = raw_path[1:]
        waypoints = self._smooth_path(raw_path)
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
            if not self._is_walkable(*desired) or desired in forbidden:
                desired = self._find_nearest_walkable(desired, forbidden=forbidden)
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
            target = self._find_nearest_walkable(tile, forbidden=reserved)
            if not target:
                continue
            reserved.add(target)
            raw_path = self._astar_path((int(ent.x), int(ent.y)), target)
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
            waypoints = self._smooth_path(raw_path)
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

    def apply_day_night_lighting(self, surface: pygame.Surface):
        light = self.day_night.get_light_level(min_light=0.45)

        # 1) Brightness (gris) : 255 = normal, <255 = sombre
        m = int(255 * light)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((m, m, m, 255))
        surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # 2) Tint (couleur) léger par-dessus (optionnel mais joli)
        r, g, b = self.day_night.get_ambient_color()
        tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # alpha faible sinon ça “salit” l’image
        tint.fill((r, g, b, 35))
        surface.blit(tint, (0, 0))
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
