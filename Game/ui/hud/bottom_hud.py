from typing import List

import pygame

from Game.core.utils import Button, ButtonStyle
from Game.gameplay.craft import load_crafts
from Game.world.day_night import ClockRenderer
from .notification import add_notification


class BottomHUD:
    """
    HUD du bas de l'écran pour la Phase 1.

    - Barre d'XP de l'espèce
    - Niveau d'espèce (cercle)
    - Placeholder horloge jour/nuit
    - Stats de base de l'espèce
    - Zone de quick craft avec boutons
    - Bouton pour plier / déplier le panneau
    """

    def __init__(self, phase, species, day_night_cycle):
        # phase = Phase1 (pour screen, assets...)
        self.phase = phase
        self.assets = phase.assets
        self.screen = phase.screen
        self.species = species
        self.crafts = load_crafts("Game/data/crafts.json")
        # Système jour/nuit
        self.day_night = day_night_cycle
        self.clock_renderer = ClockRenderer(radius=18)

        self.visible = True      # panneau déplié ou non
        self.height = 140        # hauteur du panneau
        self.margin = 12         # marge avec le bord écran

        if not pygame.font.get_init():
            pygame.font.init()
        self.font = pygame.font.SysFont("consolas", 18, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 14)

        # --- Bouton de repli / dépli ---
        toggle_style = ButtonStyle(
            draw_background=True,
            radius=10,
            padding_x=6,
            padding_y=2,
            font=self.small_font,
            hover_zoom=1.1,
        )
        self.toggle_button = Button(
            text="▼",
            pos=(0, 0),
            size=(28, 22),
            anchor="center",
            style=toggle_style,
            on_click=self._on_toggle,
        )

        # --- Boutons de quick craft ---
        craft_style = ButtonStyle(
            hover_zoom=1.0,
        )

        self.craft_buttons: List[tuple[str, Button]] = []

        for craft_id, craft_def in self.crafts.items():
            image_name = craft_def.get("image", "feu_de_camp")
            try:
                surf = self.assets.get_image(image_name)
            except Exception:
                surf = self.assets.get_image("feu_de_camp")

            btn = Button(
                text="",
                pos=(0, 0),
                size=(70, 70),
                anchor="center",
                style=craft_style,
                on_click=self._make_craft_cb(craft_id),
                on_right_click=self._make_craft_info_cb(craft_id),
                icon=surf,
            )
            self.craft_buttons.append((craft_id, btn))

        # Rects de layout (calculés à chaque frame)
        self.panel_rect = pygame.Rect(0, 0, 100, 100)
        self.left_rect = pygame.Rect(0, 0, 50, 50)
        self.right_rect = pygame.Rect(0, 0, 50, 50)
        self.context_menu = None
        self._context_menu_just_opened = False
        self._context_menu_dragging = False
        self._context_menu_drag_offset = (0, 0)

    # ---------- Callbacks ----------

    def _make_craft_cb(self, craft_id: str):
        def _cb(_btn):
            self.phase.selected_craft = craft_id
            craft_def = self.crafts.get(craft_id, {})
            label = craft_def.get("name", craft_id)
            add_notification(f"Placement de : {label} (clique sur une tuile)")
            self.context_menu = None
            self._context_menu_just_opened = False
            self._context_menu_dragging = False
        return _cb

    def _make_craft_info_cb(self, craft_id: str):
        def _cb(btn: Button):
            self._open_craft_menu(craft_id, btn.rect)
        return _cb

    def _on_toggle(self, _btn):
        self.visible = not self.visible
        # change l’icone du bouton pour que ce soit plus clair
        self.toggle_button.text = "▲" if not self.visible else "▼"
        if not self.visible:
            self.context_menu = None
            self._context_menu_just_opened = False
            self._context_menu_dragging = False

    # ---------- Layout ----------

    def _update_layout(self):
        """Calcule les rectangles du panneau en fonction de la taille de l'écran."""
        if not self.screen:
            return

        sw, sh = self.screen.get_size()
        self.panel_rect = pygame.Rect(
            self.margin,
            sh - self.height - self.margin,
            sw - 2 * self.margin,
            self.height,
        )

        pad = 16
        left_w = int(self.panel_rect.width * 0.45)

        self.left_rect = pygame.Rect(
            self.panel_rect.x + pad,
            self.panel_rect.y + pad,
            left_w - pad,
            self.panel_rect.height - 2 * pad,
        )

        self.right_rect = pygame.Rect(
            self.panel_rect.x + left_w,
            self.panel_rect.y + pad,
            self.panel_rect.width - left_w - pad,
            self.panel_rect.height - 2 * pad,
        )

        # Bouton de repli : collé en haut à droite du panneau
        if self.visible:
            toggle_x = self.panel_rect.right - 20
            toggle_y = self.panel_rect.top - 10
            self.toggle_button.move_to((toggle_x, toggle_y))

        # Boutons de craft alignés en ligne dans la partie droite
        if self.craft_buttons:
            bw = self.craft_buttons[0][1].rect.width
            gap = 10
            total = len(self.craft_buttons) * bw + (len(self.craft_buttons) - 1) * gap
            start_x = self.right_rect.x + (self.right_rect.width - total) // 2 + bw // 2
            center_y = self.right_rect.y + 40
            for i, (_cid, btn) in enumerate(self.craft_buttons):
                cx = start_x + i * (bw + gap)
                btn.move_to((cx, center_y))

    # ---------- Interaction ----------

    def handle(self, events):
        """
        À appeler depuis Phase1.handle_input.
        On envoie les événements aux boutons du HUD.
        """
        self._update_layout()
        self.toggle_button.handle(events)
        if not self.visible:
            return
        for craft_id, btn in self.craft_buttons:
            btn.handle(events)
        self._handle_context_menu_events(events)

    # ---------- Dessin des sous-parties ----------

    def _draw_xp_bar(self, screen):
        xp = self.species.xp
        xp_max = self.species.xp_to_next
        ratio = max(0.0, min(1.0, xp / xp_max))

        bar_h = 18
        rect = pygame.Rect(self.left_rect.x-10, self.left_rect.y, self.left_rect.width, bar_h)

        pygame.draw.rect(screen, (40, 70, 40), rect, border_radius=6)
        inner = rect.inflate(-4, -4)
        fill = inner.copy()
        fill.width = int(inner.width * ratio)
        pygame.draw.rect(screen, (90, 200, 90), fill, border_radius=6)
        pygame.draw.rect(screen, (120, 200, 120), rect, 2, border_radius=6)

        txt = self.small_font.render(f"XP {int(xp)}/{int(xp_max)}", True, (240, 240, 240))
        screen.blit(txt, (rect.x + 6, rect.y + 1))

    def _draw_level_and_clock(self, screen):
        # Cercle de niveau
        lvl = getattr(self.species, "species_level", 1)
        cx = self.left_rect.x + 30
        cy = self.left_rect.y + 50
        pygame.draw.circle(screen, (50, 80, 50), (cx, cy), 24)
        pygame.draw.circle(screen, (180, 230, 180), (cx, cy), 24, 2)
        txt = self.font.render(str(lvl), True, (255, 255, 255))
        rect = txt.get_rect(center=(cx, cy))
        screen.blit(txt, rect)

        cy2 = cy + 56
        if hasattr(self, 'clock_renderer'):
            self.clock_renderer.draw(screen, cx, cy2, self.day_night, self.small_font)
        else:
            # Fallback si clock_renderer n'existe pas
            pygame.draw.circle(screen, (40, 40, 40), (cx, cy2), 18)
            pygame.draw.circle(screen, (120, 120, 120), (cx, cy2), 18, 2)
            pygame.draw.line(screen, (220, 220, 220), (cx, cy2), (cx, cy2 - 10), 2)
            pygame.draw.line(screen, (220, 220, 220), (cx, cy2), (cx + 7, cy2), 2)

    def _draw_stats(self, screen):
        stats_rect = pygame.Rect(
            self.left_rect.x + 70,
            self.left_rect.y + 26,
            self.left_rect.width - 80,
            self.left_rect.height - 26,
        )
        pygame.draw.rect(screen, (25, 40, 25), stats_rect, border_radius=8)
        pygame.draw.rect(screen, (80, 120, 80), stats_rect, 2, border_radius=8)

        lines = [
            f"Population : {getattr(self.species, 'population', '?')}",
        ]
        y = stats_rect.y + 8
        for line in lines:
            surf = self.small_font.render(line, True, (230, 240, 230))
            screen.blit(surf, (stats_rect.x + 8, y))
            y += 18

    def _draw_quickcraft(self, screen):
        # Titre "CRAFT"
        title = self.font.render("CRAFT", True, (240, 240, 240))
        t_rect = title.get_rect(midtop=(self.right_rect.centerx, self.right_rect.y))
        screen.blit(title, t_rect)

        # Fond de la zone de craft
        pygame.draw.rect(screen, (20, 55, 20), self.right_rect, border_radius=10)
        pygame.draw.rect(screen, (70, 120, 70), self.right_rect, 2, border_radius=10)

        # Boutons
        for craft_id, btn in self.craft_buttons:
            btn.draw(screen)
            if self.phase.selected_craft == craft_id:
                highlight = btn.rect.inflate(10, 10)
                pygame.draw.rect(screen, (200, 230, 120), highlight, width=3, border_radius=12)

    # ---------- Dessin global ----------

    def draw(self, screen):
        """
        À appeler depuis Phase1.render(screen)
        """
        self._update_layout()
        if not self.visible:
            self.toggle_button.pos = (10, 10)
        # Bouton de repli toujours visible
        self.toggle_button.draw(screen)

        # Si plié : on ne montre pas le panneau
        if not self.visible:
            return

        # Fond général du panneau
        pygame.draw.rect(screen, (20, 60, 20), self.panel_rect, border_radius=16)
        pygame.draw.rect(screen, (80, 140, 80), self.panel_rect, 2, border_radius=16)

        # Partie gauche : XP + niveau + horloge + stats
        self._draw_xp_bar(screen)
        self._draw_level_and_clock(screen)
        self._draw_stats(screen)

        # Partie droite : quick craft
        self._draw_quickcraft(screen)
        self._draw_context_menu(screen)

    # ---------- Menu contextuel ----------

    def _handle_context_menu_events(self, events):
        if not self.context_menu:
            return
        if self._context_menu_just_opened:
            self._context_menu_just_opened = False
            return
        rect = self.context_menu["rect"]
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and rect.collidepoint(e.pos):
                    header_h = self.context_menu.get("header_height", 28)
                    if e.pos[1] <= rect.y + header_h:
                        self._context_menu_dragging = True
                        self._context_menu_drag_offset = (e.pos[0] - rect.x, e.pos[1] - rect.y)
                        continue
                if e.button in (1, 3) and not rect.collidepoint(e.pos):
                    self.context_menu = None
                    self._context_menu_just_opened = False
                    self._context_menu_dragging = False
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self._context_menu_dragging = False
            elif e.type == pygame.MOUSEMOTION and self._context_menu_dragging:
                dx, dy = self._context_menu_drag_offset
                new_x = e.pos[0] - dx
                new_y = e.pos[1] - dy
                if self.screen:
                    sw, sh = self.screen.get_size()
                    new_x = max(self.margin, min(sw - rect.width - self.margin, new_x))
                    new_y = max(self.margin, min(sh - rect.height - self.margin, new_y))
                rect.topleft = (new_x, new_y)
                self.context_menu["rect"] = rect

    def _open_craft_menu(self, craft_id: str, button_rect: pygame.Rect):
        craft_def = self.crafts.get(craft_id)
        if not craft_def:
            self.context_menu = None
            self._context_menu_just_opened = False
            self._context_menu_dragging = False
            return

        title_surf = self.font.render(craft_def.get("name", craft_id), True, (245, 245, 245))
        desc_text = craft_def.get("description", "Aucune description.")
        desc_lines = desc_text.split("\n")
        desc_surfs = [self.small_font.render(line, True, (230, 230, 230)) for line in desc_lines]

        cost = craft_def.get("cost", {})
        if cost:
            cost_label = self.small_font.render("Ressources requises :", True, (215, 230, 215))
            cost_surfs = [
                self.small_font.render(f"- {res} : {amt}", True, (210, 220, 210))
                for res, amt in cost.items()
            ]
        else:
            cost_label = self.small_font.render("Aucune ressource requise", True, (215, 230, 215))
            cost_surfs = []

        sprite_surf = None
        sprite_key = craft_def.get("sprite")
        if sprite_key:
            try:
                sprite_surf = self.assets.get_image(sprite_key)
            except Exception:
                sprite_surf = None

        pad = 12
        gap = 6
        section_gap = 10

        max_width = title_surf.get_width()
        if sprite_surf:
            max_width = max(max_width, sprite_surf.get_width())
        if desc_surfs:
            max_width = max(max_width, max(s.get_width() for s in desc_surfs))
        if cost_label:
            max_width = max(max_width, cost_label.get_width())
        if cost_surfs:
            max_width = max(max_width, max(s.get_width() for s in cost_surfs))

        height = pad + title_surf.get_height()
        height += section_gap
        if sprite_surf:
            height += sprite_surf.get_height()
            height += section_gap
        if desc_surfs:
            height += sum(s.get_height() for s in desc_surfs) + gap * (len(desc_surfs) - 1)
            height += section_gap
        if cost_label:
            height += cost_label.get_height()
        if cost_surfs:
            height += gap + sum(s.get_height() for s in cost_surfs) + gap * (len(cost_surfs) - 1)
        height += pad

        width = max_width + pad * 2

        if self.screen:
            sw, sh = self.screen.get_size()
        else:
            sw = sh = 0

        pos_x = button_rect.centerx - width // 2
        pos_y = self.panel_rect.top - height - 12 if self.visible else button_rect.top - height - 12
        if pos_x < self.margin:
            pos_x = self.margin
        if pos_x + width > sw - self.margin:
            pos_x = sw - width - self.margin
        if pos_y < self.margin:
            pos_y = self.margin
        if pos_y + height > sh - self.margin:
            pos_y = sh - height - self.margin

        rect = pygame.Rect(pos_x, pos_y, width, height)

        self.context_menu = {
            "rect": rect,
            "title": title_surf,
            "description": desc_surfs,
            "cost_label": cost_label,
            "cost_surfs": cost_surfs,
            "sprite": sprite_surf,
            "gap": gap,
            "section_gap": section_gap,
            "pad": pad,
            "header_height": title_surf.get_height() + pad,
        }
        self._context_menu_just_opened = True

    def _draw_context_menu(self, screen):
        if not self.context_menu:
            return
        menu = self.context_menu
        rect: pygame.Rect = menu["rect"]
        pad = menu["pad"]
        gap = menu["gap"]
        section_gap = menu["section_gap"]

        pygame.draw.rect(screen, (16, 60, 22), rect, border_radius=10)
        pygame.draw.rect(screen, (90, 150, 90), rect, 2, border_radius=10)

        x = rect.x + pad
        y = rect.y + pad

        screen.blit(menu["title"], (x, y))
        y += menu["title"].get_height() + section_gap

        sprite_surf = menu["sprite"]
        if sprite_surf:
            sprite_rect = sprite_surf.get_rect()
            sprite_rect.x = rect.centerx - sprite_rect.width // 2
            sprite_rect.y = y
            screen.blit(sprite_surf, sprite_rect)
            y += sprite_rect.height + section_gap

        for surf in menu["description"]:
            screen.blit(surf, (x, y))
            y += surf.get_height() + gap
        if menu["description"]:
            y += section_gap - gap

        if menu["cost_label"]:
            screen.blit(menu["cost_label"], (x, y))
            y += menu["cost_label"].get_height()
        for surf in menu["cost_surfs"]:
            y += gap
            screen.blit(surf, (x, y))
            y += surf.get_height()
