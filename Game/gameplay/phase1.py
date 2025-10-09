import pygame
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator


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

        # Vue iso (bornes de zoom ajustables)
        self.view = IsoMapView(self.assets, self.screen.get_size(),
                               min_zoom=0.7, max_zoom=2.0, zoom_step=0.1)

        # Générateur
        self.gen = WorldGenerator(tiles_levels=6)

        # Données de monde (définies dans enter)
        self.params = None
        self.world = None

        # Petits flags debug (si tu veux afficher texte/seed)
        self.show_info = True
        self.font = pygame.font.SysFont("consolas", 16)

    # -------------------------------------------------------------
    # Cycle de vie de l'état
    # -------------------------------------------------------------
    def enter(self, **kwargs):
        # Si un monde est déjà prêt (loader), on l’utilise
        pre_world = kwargs.get("world")
        pre_params = kwargs.get("params")

        if pre_world is not None and pre_params is not None:
            self.world = pre_world
            self.params = pre_params
            self.view.set_world(self.world)
            return

        # Sinon, ancien comportement
        preset = kwargs.get("preset", "Tropical")
        seed_override = kwargs.get("seed", None)
        self.params = load_world_params_from_preset(preset)
        self.world = self.gen.generate_island(self.params, rng_seed=seed_override)
        self.view.set_world(self.world)

    def leave(self):
        """Optionnel : nettoyer si besoin."""
        pass

    # -------------------------------------------------------------
    # Événements
    # -------------------------------------------------------------
    def handle_input(self, events):
        for e in events:
            # Laisse la vue gérer molette et drag (clic milieu)
            self.view.handle_event(e)

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_i:
                    self.show_info = not self.show_info
                # R = régénère avec même seed; Shift+R = nouvelle seed
                if e.key == pygame.K_r:
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        # reroll: seed aléatoire → force rng_seed=None pour recalcul depuis params+random
                        self.params.seed = None
                        self.world = self.gen.generate_island(self.params, rng_seed=None)
                    else:
                        # régénère strictement la même carte
                        self.world = self.gen.generate_island(self.params)
                    self.view.set_world(self.world)

    # -------------------------------------------------------------
    # Update / Render
    # -------------------------------------------------------------
    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

    def render(self, screen):
        screen.fill((10, 12, 18))
        self.view.render(screen)

        if self.show_info:
            self._draw_info_panel(screen)

    # -------------------------------------------------------------
    # Utilitaires
    # -------------------------------------------------------------
    def on_resize(self, new_size):
        """À appeler si ton App gère VIDEORESIZE : on met à jour la vue."""
        self.view.screen_w, self.view.screen_h = new_size
        # Tu peux recentrer la caméra si tu veux, sinon on garde la position.

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
            screen.blit(surf, (x, y))
            y += 18
