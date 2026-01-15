# Game/ui/loading.py
import pygame
import threading
from Game.core.config import WIDTH, HEIGHT
from world.world_gen import load_world_params_from_preset, WorldGenerator

class LoadingState:
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.font = app.assets.get_font("MightySouly", 36)
        self.small = pygame.font.SysFont("consolas", 18)

        self.progress = 0.0
        self.phase_txt = "Préparation…"
        self.done = False
        self.failed = None
        self._thread = None

        # visuel simple
        self.bg = pygame.Surface((WIDTH, HEIGHT))
        self.bg.fill((8, 10, 16))
        self.panel = pygame.Surface((520, 160), pygame.SRCALPHA)
        self.panel.fill((0,0,0,0))
        pygame.draw.rect(self.panel, (255,255,255,18), self.panel.get_rect(), border_radius=16)

        # pour passer au state suivant
        self._world = None
        self._params = None

    def enter(self, **kwargs):
        # kwargs possibles: preset, seed
        self.progress = 0.0
        self.phase_txt = "Chargement…"
        self.done = False
        self.failed = None
        self._world = None
        self._params = None

        def worker():
            try:
                preset = kwargs.get("preset", "Custom")
                seed   = kwargs.get("seed", None)
                overrides = {"seed": seed} if seed is not None else None
                self._params = load_world_params_from_preset(preset, overrides=overrides)
                gen = WorldGenerator(tiles_levels=6, chunk_size=64, cache_chunks=256)

                def on_progress(p, label):
                    self.progress = max(0.0, min(1.0, float(p)))
                    self.phase_txt = str(label)

                rng_seed = seed if seed is not None else self._params.seed
                self._world = gen.generate_planet(self._params, rng_seed=rng_seed, progress=on_progress)
                self.done = True
            except Exception as e:
                self.failed = e

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def handle_input(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                # retour au menu si on veut annuler
                self.app.change_state("MENU")

    def update(self, dt):
        if self.failed:
            print(self.failed)
            self.app.change_state("MENU")
            return
        if self.done and self._world:
            # Passe à PHASE1 avec le world déjà prêt
            self.app.change_state("PHASE1", world=self._world, params=self._params)

    def render(self, screen):
        screen.blit(self.bg, (0,0))
        # titre
        title = self.font.render("Génération du monde…", True, (230,230,230))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 140))

        # panneau + barre
        px = WIDTH//2 - self.panel.get_width()//2
        py = HEIGHT//2 - self.panel.get_height()//2
        screen.blit(self.panel, (px, py))

        # contour barre
        bar_w, bar_h = 440, 28
        bx, by = px + 40, py + 64
        pygame.draw.rect(screen, (220,220,230), (bx, by, bar_w, bar_h), width=2, border_radius=10)
        # remplissage
        fill_w = int(bar_w * max(0.0, min(1.0, self.progress)))
        if fill_w > 0:
            pygame.draw.rect(screen, (70,120,210), (bx+2, by+2, fill_w-4, bar_h-4), border_radius=8)

        # label phase
        label = self.small.render(self.phase_txt, True, (200,205,215))
        screen.blit(label, (WIDTH//2 - label.get_width()//2, by - 28))
