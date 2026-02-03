# APP.PY
# Application principale gérant la boucle pygame


# --------------- IMPORTATION DES MODULES ---------------

import pygame
from Game.core.config import WIDTH, HEIGHT, FPS, TITLE, Settings
from Game.ui.menu.menu_main import MainMenu, OptionsMenu, CreditMenu, WorldCreationMenu, SpeciesCreationMenu
from Game.core.assets import Assets
from Game.core.audio import AudioManager
from Game.core.utils import Button, resource_path
from Game.gameplay.phase1 import Phase1
from Game.ui.loading import LoadingState
from Game.ui.hud.notification import draw_notifications
from Game.save.progression import ProgressionManager

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
        self.states["OPTIONS"] = OptionsMenu(self)
        self.states["CREDITS"] = CreditMenu(self)
        self.states["PHASE1"] = Phase1(self)
        self.states["LOADING"] = LoadingState(self)
        self.states["CREATION"] = WorldCreationMenu(self)
        self.states["SPECIES_CREATION"] = SpeciesCreationMenu(self)
    
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
        Button.reset_cursor_state(restore=True)
        if self.state and hasattr(self.state, "leave"):
            self.state.leave()
        self.state = self.states[key]
        self.state_key = key
        if hasattr(self.state, "enter"):
            self.state.enter(**kwargs)
        if key != "PHASE1":
            self.set_cursor_image(self.default_cursor_path)
        if getattr(self, "progression", None):
            if prev_key == "PHASE1" and key != "PHASE1":
                self.progression.flush(force=True)
            if key == "PHASE1" and prev_key != "PHASE1":
                self.progression.on_game_start()

    # Boucle principale pygame
    def run(self):
        print(WIDTH,HEIGHT)
        while self.running:
            fps_cap = int(self.settings.get("video.fps_cap", FPS))
            dt = self.clock.tick(fps_cap) / 1000.0
            events = pygame.event.get()
            Button.reset_cursor_state(restore=True)
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
            if hasattr(self.state, "handle_input"):
                self.state.handle_input(events)
            if getattr(self, "progression", None):
                self.progression.tick(dt, active=self.state_key == "PHASE1")
            if hasattr(self.state, "update"):
                self.state.update(dt)
            if hasattr(self.state, "render"):
                self.state.render(self.screen)
            draw_notifications(self.screen)
            pygame.display.flip()
        if getattr(self, "progression", None):
            self.progression.flush(force=True)
        pygame.quit()
