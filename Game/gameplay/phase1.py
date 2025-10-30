# Game/gameplay/phase1.py
import pygame
import random
from typing import List, Tuple
from Game.ui.iso_render import IsoMapView, get_prop_sprite_name
from Game.world.tiles import get_ground_sprite_name
from world.world_gen import load_world_params_from_preset, WorldGenerator

# + imports pour l'espèce
from Game.species.species import Espece
from Game.ui.panels import SideInfoPanel

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

        # Panneau d’inspection
        self.side = SideInfoPanel(self.screen.get_size())

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

        # spawn espèce
        try:
            sx, sy = self.world.spawn
        except Exception:
            sx, sy = 0, 0
        self.joueur = Espece("Hominidé", x=sx, y=sy, assets=self.assets)
        self.entities = [self.joueur]

    def leave(self):
        pass

    def _gather_tile_info(self, i: int, j: int) -> Tuple[str, List[Tuple[str, str]]]:
        w = self.world
        try:
            gid = w.ground_id[j][i]
        except Exception:
            gid = None
        try:
            biome = w.biome[j][i]
        except Exception:
            biome = "?"
        try:
            level = w.levels[j][i] if w.levels else 0
        except Exception:
            level = 0
        try:
            pid = w.overlay[j][i]
        except Exception:
            pid = None

        gname = get_ground_sprite_name(gid) if gid is not None else "?"
        pname = get_prop_sprite_name(pid) if pid else None

        ents_here = [e for e in self.entities if int(getattr(e, "x", -9999)) == i and int(getattr(e, "y", -9999)) == j]

        fields: List[Tuple[str, str]] = [
            ("Coordonnées (i,j)", f"{i}, {j}"),
            ("Altitude", f"{level}"),
            ("Biome", f"{biome}"),
            ("Sol", f"{gname} (id {gid})" if gid is not None else "Inconnu"),
            ("Prop", f"{pname} (id {pid})" if pid else "Aucun"),
        ]
        for idx, e in enumerate(ents_here, 1):
            name = getattr(e, "nom", None) or getattr(e, "name", None) or e.__class__.__name__
            extra = []
            stats = getattr(e, "stats", None)
            if isinstance(stats, dict):
                for k, v in list(stats.items())[:6]:
                    extra.append(f"{k}:{v}")
            fields.append((f"Entité {idx}", f"{name} @({int(e.x)},{int(e.y)})" + (f" | {', '.join(extra)}" if extra else "")))
        return "Inspection", fields

    def handle_input(self, events):
        # NEW: bouton ✕ du panneau
        self.side.handle(events)

        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif e.key == pygame.K_i:
                    self.show_info = not self.show_info
                elif e.key == pygame.K_TAB:  # toggle panneau
                    self.side.toggle()
                elif e.key == pygame.K_r:
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        self.world = self.gen.generate_island(self.params, rng_seed=random.getrandbits(63))
                    else:
                        self.world = self.gen.generate_island(self.params)
                    self.view.set_world(self.world)
                    try:
                        sx, sy = self.world.spawn
                    except Exception:
                        sx, sy = 0, 0
                    if self.joueur:
                        self.joueur.x, self.joueur.y = float(sx), float(sy)

            if not self.paused:
                self.view.handle_event(e)

                # CHANGE: clic droit (button == 3) = Inspecter
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    mx, my = pygame.mouse.get_pos()

                    # Ignore si on clique DANS le panneau
                    if self.side.open and mx >= (self.screen.get_width() - self.side.width):
                        continue

                    dx, dy, _ = self.view._proj_consts()
                    base_lift = int(self.view.click_lift_factor * dy)
                    candidates = (base_lift, int(base_lift * 0.66), int(base_lift * 0.33), 0)

                    hit = None
                    for off in candidates:
                        hit = self.view.pick_tile_at(mx, my - off)
                        if hit is not None:
                            break

                    if hit is not None:
                        i, j = hit
                        title, fields = self._gather_tile_info(i, j)
                        self.side.set_content(title, fields)

    def update(self, dt):
        if self.paused:
            return
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

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
                pygame.draw.rect(screen, (255, 0, 255),
                                 (self.screen.get_width() // 2 - 10, self.screen.get_height() // 2 - 24, 20, 24), 1)

        if self.show_info:
            self._draw_info_panel(screen)

        # Panneau d’inspection
        self.side.draw(screen)

        if self.paused:
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            font = pygame.font.SysFont(None, 60)
            text = font.render("PAUSE", True, (255, 255, 255))
            resume_text = font.render("Appuyez sur Échap pour reprendre", True, (200, 200, 200))
            text_rect = text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 50))
            resume_rect = resume_text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 + 50))
            screen.blit(text, text_rect)
            screen.blit(resume_text, resume_rect)

    def on_resize(self, new_size):
        self.view.screen_w, self.view.screen_h = new_size
        self.side.on_resize(new_size)

    def _draw_info_panel(self, screen):
        lines = [
            f"Phase1 — {self.params.world_name if self.params else '...'}",
            f"Size: {self.world.width}x{self.world.height}" if self.world else "",
            f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
            # CHANGE: texte d'aide -> clic droit
            "Controls: Clic droit = Inspecter | TAB = toggle panneau | WASD/flèches = pan | Molette = zoom | Clic milieu = drag | R = regen | Shift+R = reroll | I = info",
        ]
        x, y = 10, 10
        for txt in lines:
            if not txt:
                continue
            surf = self.font.render(txt, True, (220, 230, 240))
            screen.blit(surf, (x, y)); y += 18