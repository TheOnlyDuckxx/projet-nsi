# APP.PY
# Application principale gérant la boucle pygame


# --------------- IMPORTATION DES MODULES ---------------

import pygame
import time
from Game.core.config import WIDTH, HEIGHT, FPS, TITLE, Settings
from Game.ui.menu.menu_main import (
    MainMenu,
    OptionsMenu,
    CreditMenu,
    AchievementsMenu,
    WorldCreationMenu,
    SpeciesCreationMenu,
    SaveSelectionMenu,
)
from Game.core.assets import Assets
from Game.core.audio import AudioManager
from Game.core.utils import Button, resource_path
from Game.gameplay.phase1 import Phase1
from Game.ui.loading import LoadingState
from Game.ui.hud.notification import draw_notifications
from Game.save.progression import ProgressionManager
from Game.ui.menu.menu_end import EndGameScreen

# --------------- CLASSE PRINCIPALE ---------------
class App:
    def __init__(self):
        pygame.init()

        # init mixer (au cas où)
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.default_cursor_path = resource_path("Game/assets/vfx/1.png")
        self.hover_cursor_path = resource_path("Game/assets/vfx/10.png")
        self._cursor_cache = {}
        self.assets = Assets().load_all(resource_path("Game/assets"))
        self.running = True
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.states = {}
        self.state = None
        self.state_key = None
        self._perf_phase1_trace_frames = 0

        self.settings = Settings()
        self.progression = ProgressionManager()

        # --- AUDIO ---
        self.audio = AudioManager(resource_path("Game/assets/audio")).load_all()
        self.audio.set_volumes(
            enabled=bool(self.settings.get("audio.enabled", True)),
            master=float(self.settings.get("audio.master_volume", 0.8)),
            music=float(self.settings.get("audio.music_volume", 0.8)),
            sfx=float(self.settings.get("audio.sfx_volume", 0.9)),
        )

        # si un setting change -> on réapplique volumes
        self.settings.on_change(self._on_setting_changed)

        self.selected_base_mutations: list[str] = []
        self.species_creation = {
            "name": "",
            "color": "bleu",
            "color_rgb": (70, 130, 220),
            "stats": {},
            "mutations": [],
        }
        self._register_states()
        Button.set_hover_cursor_path(self.hover_cursor_path)
        self.set_cursor_image(self.default_cursor_path)
        self.change_state("MENU")

    def _on_setting_changed(self, path, value):
        if path.startswith("audio."):
            self.audio.set_volumes(
                enabled=bool(self.settings.get("audio.enabled", True)),
                master=float(self.settings.get("audio.master_volume", 0.8)),
                music=float(self.settings.get("audio.music_volume", 0.8)),
                sfx=float(self.settings.get("audio.sfx_volume", 0.9)),
            )

    # Définis les "STATES"
    def _register_states(self):
        self.states["MENU"] = MainMenu(self)
        self.states["SAVE_SELECT"] = SaveSelectionMenu(self)
        self.states["OPTIONS"] = OptionsMenu(self)
        self.states["ACHIEVEMENTS"] = AchievementsMenu(self)
        self.states["CREDITS"] = CreditMenu(self)
        self.states["PHASE1"] = Phase1(self)
        self.states["LOADING"] = LoadingState(self)
        self.states["CREATION"] = WorldCreationMenu(self)
        self.states["SPECIES_CREATION"] = SpeciesCreationMenu(self)
        self.states["END_SCREEN"] = EndGameScreen(self)
    
    def quit_game(self):
        if getattr(self, "progression", None):
            self.progression.flush(force=True)
        self.running=False

    def _load_cursor(self, image_path: str, hotspot=(0, 0)):
        key = (image_path, int(hotspot[0]), int(hotspot[1]))
        cached = self._cursor_cache.get(key)
        if cached is not None:
            return cached
        surf = pygame.image.load(image_path).convert_alpha()
        cursor = pygame.cursors.Cursor((int(hotspot[0]), int(hotspot[1])), surf)
        self._cursor_cache[key] = cursor
        return cursor

    def set_cursor_image(self, image_path: str, hotspot=(0, 0)) -> bool:
        try:
            cursor = self._load_cursor(image_path, hotspot)
            pygame.mouse.set_cursor(cursor)
            return True
        except Exception as e:
            print("[Cursor] Erreur set_cursor_image:", e, "path=", image_path)
            return False

    # Permet de changer de "STATES"
    def change_state(self, key, **kwargs):
        prev_key = self.state_key
        perf_enabled = bool(self.settings.get("debug.perf_logs", True))
        if perf_enabled:
            print(f"[Perf][App] change_state {prev_key} -> {key} (debut)")
        t0 = time.perf_counter()
        Button.reset_cursor_state(restore=True)
        if self.state and hasattr(self.state, "leave"):
            self.state.leave()
        self.state = self.states[key]
        self.state_key = key
        if hasattr(self.state, "enter"):
            self.state.enter(**kwargs)
        if key == "PHASE1":
            self._perf_phase1_trace_frames = 120 if perf_enabled else 0
        if key != "PHASE1":
            self.set_cursor_image(self.default_cursor_path)
        if getattr(self, "progression", None):
            if prev_key == "PHASE1" and key != "PHASE1":
                self.progression.flush(force=True)
            if key == "PHASE1" and prev_key != "PHASE1":
                self.progression.on_game_start()
        if perf_enabled:
            print(f"[Perf][App] change_state {prev_key} -> {key} (fin) | total {time.perf_counter() - t0:.3f}s")

    # Boucle principale pygame
    def run(self):
        print(WIDTH,HEIGHT)
        while self.running:
            perf_enabled = bool(self.settings.get("debug.perf_logs", True))
            slow_frame_sec = max(0.01, float(self.settings.get("debug.perf_slow_frame_ms", 120)) / 1000.0)
            trace_frame = perf_enabled and self.state_key == "PHASE1" and self._perf_phase1_trace_frames > 0
            frame_t0 = time.perf_counter()
            fps_cap = int(self.settings.get("video.fps_cap", FPS))
            dt = self.clock.tick(fps_cap) / 1000.0
            after_tick = time.perf_counter()
            events = pygame.event.get()
            after_events = time.perf_counter()
            Button.reset_cursor_state(restore=True)
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
            if hasattr(self.state, "handle_input"):
                self.state.handle_input(events)
            after_input = time.perf_counter()
            if getattr(self, "progression", None):
                self.progression.tick(dt, active=self.state_key == "PHASE1")
            after_progression = time.perf_counter()
            if hasattr(self.state, "update"):
                if trace_frame:
                    print(f"[Perf][App][Frame] update start state={self.state_key}")
                self.state.update(dt)
                if trace_frame:
                    print(f"[Perf][App][Frame] update end state={self.state_key}")
            after_update = time.perf_counter()
            if hasattr(self.state, "render"):
                if trace_frame:
                    print(f"[Perf][App][Frame] render start state={self.state_key}")
                self.state.render(self.screen)
                if trace_frame:
                    print(f"[Perf][App][Frame] render end state={self.state_key}")
            after_render = time.perf_counter()
            draw_notifications(self.screen)
            pygame.display.flip()
            after_flip = time.perf_counter()
            frame_total = after_flip - frame_t0
            if perf_enabled and (trace_frame or frame_total >= slow_frame_sec):
                print(
                    f"[Perf][App][Frame] state={self.state_key} dt={dt:.3f}s total={frame_total:.3f}s | "
                    f"tick={after_tick - frame_t0:.3f}s events={after_events - after_tick:.3f}s "
                    f"input={after_input - after_events:.3f}s progression={after_progression - after_input:.3f}s "
                    f"update={after_update - after_progression:.3f}s render={after_render - after_update:.3f}s "
                    f"flip+notif={after_flip - after_render:.3f}s"
                )
            if self._perf_phase1_trace_frames > 0 and self.state_key == "PHASE1":
                self._perf_phase1_trace_frames -= 1
        if getattr(self, "progression", None):
            self.progression.flush(force=True)
        pygame.quit()
