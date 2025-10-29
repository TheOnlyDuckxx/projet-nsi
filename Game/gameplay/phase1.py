# Game/gameplay/phase1.py
import pygame
import random
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator

# + imports pour l'espèce
from Game.species.species import Espece

class Phase1:
    """
    État de jeu Phase 1 : île isométrique procédurale.
    - Génère le monde depuis un preset (seed + params)
    - Rendu via IsoMapView (caméra + zoom + culling)
    """
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False

        # Vue iso
        self.view = IsoMapView(self.assets, self.screen.get_size())

        # Générateur
        self.gen = WorldGenerator(tiles_levels=6)

        # Données de monde
        self.params = None
        self.world = None

        # Joueur / entités
        self.joueur = None
        self.entities = []

        # Debug HUD
        self.show_info = True
        self.font = pygame.font.SysFont("consolas", 16)

    def enter(self, **kwargs):
        pre_world = kwargs.get("world")
        pre_params = kwargs.get("params")

        if pre_world is not None and pre_params is not None:
            self.world = pre_world
            self.params = pre_params
            self.view.set_world(self.world)
        else:
            preset = kwargs.get("preset", "Tropical")
            seed_override = kwargs.get("seed", None)
            self.params = load_world_params_from_preset(preset)
            self.world = self.gen.generate_island(self.params, rng_seed=seed_override)
            self.view.set_world(self.world)

        # === CRÉATION DE L’ESPÈCE JOUEUR SUR LE SPAWN ===
        try:
            sx, sy = self.world.spawn  # cohérent avec le centrage caméra :contentReference[oaicite:5]{index=5}
        except Exception:
            sx, sy = 0, 0
        self.joueur = Espece("Hominidé", x=sx, y=sy, assets=self.assets)

        # si tu veux d'autres entités :
        self.entities = [self.joueur]

    def leave(self):
        pass

    def handle_input(self, events):
        for e in events:
              # molette/drag/keys déjà gérés
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
            if not self.paused :
                self.view.handle_event(e)
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_i:
                        self.show_info = not self.show_info
                    if e.key == pygame.K_r:
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            self.world = self.gen.generate_island(self.params, rng_seed=random.getrandbits(63))
                        else:
                            self.world = self.gen.generate_island(self.params)
                        self.view.set_world(self.world)
                        # repositionne le joueur sur le nouveau spawn
                        try:
                            sx, sy = self.world.spawn
                        except Exception:
                            sx, sy = 0, 0
                        if self.joueur:
                            self.joueur.x, self.joueur.y = float(sx), float(sy)

    def update(self, dt):
        if self.paused :
            return
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

        # Update entités (non bloquant)
        if self.joueur:
            try:
                self.joueur.update(self.world)
            except Exception as ex:
                print(f"[Phase1] Update joueur: {ex}")

    def render(self, screen):
        screen.fill((10, 12, 18))
        def _draw_entities_on_tile(i, j, sx, sy, dx, dy, wall_h):
            for e in self.entities:
                if int(e.x) == i and int(e.y) == j:
                    e.draw(screen, self.view, self.world)

        self.view.render(screen, after_tile_cb=_draw_entities_on_tile)
        # rendu du monde

        # Rendu des entités, triées par (i+j) pour cohérence iso
        if self.entities:
            try:
                sorted_entities = sorted(
                        self.entities,
                        key=lambda e: self.view._world_to_screen(e.x, e.y, 0, *self.view._proj_consts())[1]
                    )
                for ent in sorted_entities:
                    ent.draw(screen, self.view, self.world)
            except Exception as ex:
                print(f"[Phase1] Render entités: {ex}")
                # placeholder
                pygame.draw.rect(screen, (255, 0, 255), (self.screen.get_width()//2-10,
                                                         self.screen.get_height()//2-24, 20, 24), 1)

        if self.show_info:
            self._draw_info_panel(screen)
        if self.paused:
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))  # fond noir transparent
            screen.blit(overlay, (0, 0))

            font = pygame.font.SysFont(None, 60)
            text = font.render("PAUSE", True, (255, 255, 255))
            resume_text = font.render("Appuyez sur Échap pour reprendre", True, (200, 200, 200))

            text_rect = text.get_rect(center=(screen.get_width()/2, screen.get_height()/2 - 50))
            resume_rect = resume_text.get_rect(center=(screen.get_width()/2, screen.get_height()/2 + 50))
            screen.blit(text, text_rect)
            screen.blit(resume_text, resume_rect)

    def on_resize(self, new_size):
        self.view.screen_w, self.view.screen_h = new_size

    def _draw_info_panel(self, screen):
        lines = [
            f"Phase1 — {self.params.world_name if self.params else '...'}",
            f"Size: {self.world.width}x{self.world.height}" if self.world else "",
            f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
            "Controls: WASD/flèches = pan | Molette = zoom | Clic milieu = drag | R = regen | Shift+R = reroll | I = info",
        ]
        x, y = 10, 10
        for txt in lines:
            if not txt:
                continue
            surf = self.font.render(txt, True, (220, 230, 240))
            screen.blit(surf, (x, y)); y += 18

    