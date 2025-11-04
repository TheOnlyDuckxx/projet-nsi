# Game/gameplay/phase1.py
import pygame
import random
from typing import List, Tuple
from Game.save.save import SaveManager
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
    - Système de sauvegarde/chargement (.evosave)
    """
    
    
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False
        self.saver = SaveManager()
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

        # Panneau d'inspection
        self.side = SideInfoPanel(self.screen.get_size())

        # Boutons pause
        self.menu_button_rect = None
        self.save_button_rect = None
        
        # Message de sauvegarde
        self.save_message = ""
        self.save_message_timer = 0


    @staticmethod
    def save_exists():
        # délégué au SaveManager par défaut
        return SaveManager().save_exists()

    def save_game(self):
        return self.saver.save_phase1(self)

    def load_game(self):
        return self.saver.load_phase1(self)

    def enter(self, **kwargs):
        # Si on demande explicitement de charger
        if kwargs.get("load_save", False) and self.save_exists():
            if self.load_game():
                return
        
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
        
        # Ne créer le joueur que si on n'a pas chargé une sauvegarde
        if not self.joueur:
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
        # Bouton ✕ du panneau
        self.side.handle(events)

        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif e.key == pygame.K_i:
                    self.show_info = not self.show_info
                elif e.key == pygame.K_TAB:
                    self.side.toggle()
                elif e.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # Ctrl+S pour sauvegarder rapidement
                    self.save_game()
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

            # Gestion des clics sur les boutons de pause
            if self.paused and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Bouton Menu
                if self.menu_button_rect and self.menu_button_rect.collidepoint(e.pos):
                    try:
                        self.app.change_state("MENU")
                    except KeyError:
                        pygame.quit()
                        import sys
                        sys.exit()
                    return
                
                # Bouton Sauvegarder
                if self.save_button_rect and self.save_button_rect.collidepoint(e.pos):
                    self.save_game()
                    return

            if not self.paused:
                self.view.handle_event(e)

                # Clic droit = Inspecter
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
            # Décompte du message de sauvegarde même en pause
            if self.save_message_timer > 0:
                self.save_message_timer -= dt
            return
            
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

        if self.joueur:
            try:
                self.joueur.update(self.world)
            except Exception as ex:
                print(f"[Phase1] Update joueur: {ex}")
        
        # Décompte du message de sauvegarde
        if self.save_message_timer > 0:
            self.save_message_timer -= dt

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

        if self.show_info and not self.paused:
            self._draw_info_panel(screen)

        # Message de sauvegarde (au-dessus de tout)
        if self.save_message_timer > 0:
            self._draw_save_message(screen)

        # Panneau d'inspection (seulement si pas en pause)
        if not self.paused:
            self.side.draw(screen)

        # Écran de pause (doit être dessiné EN DERNIER)
        if self.paused:
            self._draw_pause_screen(screen)

    def _draw_save_message(self, screen):
        """Affiche un message temporaire de sauvegarde"""
        font = pygame.font.SysFont("consolas", 24, bold=True)
        
        # Couleur en fonction du message
        if "✓" in self.save_message:
            color = (100, 255, 100)
        else:
            color = (255, 100, 100)
        
        text = font.render(self.save_message, True, color)
        
        # Position en haut au centre
        x = screen.get_width() // 2 - text.get_width() // 2
        y = 50
        
        # Fond semi-transparent
        padding = 20
        bg_rect = pygame.Rect(x - padding, y - padding // 2, 
                              text.get_width() + padding * 2, 
                              text.get_height() + padding)
        bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 180))
        screen.blit(bg_surf, bg_rect.topleft)
        
        # Texte
        screen.blit(text, (x, y))

    def _draw_pause_screen(self, screen):
        """Affiche l'écran de pause avec les boutons"""
        # Overlay semi-transparent
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Titre "PAUSE"
        font_title = pygame.font.SysFont(None, 60)
        text = font_title.render("PAUSE", True, (255, 255, 255))
        text_rect = text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 130))
        screen.blit(text, text_rect)
        
        # Texte de reprise
        font_subtitle = pygame.font.SysFont(None, 40)
        resume_text = font_subtitle.render("Appuyez sur Échap pour reprendre", True, (200, 200, 200))
        resume_rect = resume_text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 60))
        screen.blit(resume_text, resume_rect)
        
        # Bouton "Sauvegarder"
        button_width = 300
        button_height = 60
        button_x = screen.get_width() / 2 - button_width / 2
        button_y = screen.get_height() / 2 + 10
        
        self.save_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
        
        # Effet hover sur bouton sauvegarder
        mouse_pos = pygame.mouse.get_pos()
        is_hover_save = self.save_button_rect.collidepoint(mouse_pos)
        save_color = (40, 120, 40) if is_hover_save else (30, 90, 30)
        save_border = (80, 200, 80) if is_hover_save else (60, 150, 60)
        
        # Dessiner le bouton sauvegarder
        pygame.draw.rect(screen, save_color, self.save_button_rect, border_radius=10)
        pygame.draw.rect(screen, save_border, self.save_button_rect, 3, border_radius=10)
        
        # Texte du bouton sauvegarder
        font_button = pygame.font.SysFont(None, 36)
        save_text = font_button.render("Sauvegarder (Ctrl+S)", True, (255, 255, 255))
        save_text_rect = save_text.get_rect(center=self.save_button_rect.center)
        screen.blit(save_text, save_text_rect)
        
        # Bouton "Retour au menu"
        button_y2 = button_y + button_height + 20
        self.menu_button_rect = pygame.Rect(button_x, button_y2, button_width, button_height)
        
        # Effet hover sur bouton menu
        is_hover_menu = self.menu_button_rect.collidepoint(mouse_pos)
        menu_color = (80, 80, 120) if is_hover_menu else (60, 60, 90)
        menu_border = (150, 150, 200) if is_hover_menu else (100, 100, 150)
        
        # Dessiner le bouton menu
        pygame.draw.rect(screen, menu_color, self.menu_button_rect, border_radius=10)
        pygame.draw.rect(screen, menu_border, self.menu_button_rect, 3, border_radius=10)
        
        # Texte du bouton menu
        menu_text = font_button.render("Retour au menu principal", True, (255, 255, 255))
        menu_text_rect = menu_text.get_rect(center=self.menu_button_rect.center)
        screen.blit(menu_text, menu_text_rect)

    def on_resize(self, new_size):
        self.view.screen_w, self.view.screen_h = new_size
        self.side.on_resize(new_size)

    def _draw_info_panel(self, screen):
        lines = [
            f"Phase1 — {self.params.world_name if self.params else '...'}",
            f"Size: {self.world.width}x{self.world.height}" if self.world else "",
            f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
            "Controls: Clic droit = Inspecter | TAB = toggle panneau | WASD/flèches = pan | Molette = zoom",
            "Clic milieu = drag | R = regen | Shift+R = reroll | I = info | Ctrl+S = sauvegarder",
        ]
        x, y = 10, 10
        for txt in lines:
            if not txt:
                continue
            surf = self.font.render(txt, True, (220, 230, 240))
            screen.blit(surf, (x, y)); y += 18