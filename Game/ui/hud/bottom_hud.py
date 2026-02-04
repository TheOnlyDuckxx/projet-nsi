from typing import List

import pygame

from Game.core.utils import Button, ButtonStyle
from Game.world.day_night import ClockRenderer
from .notification import add_notification
from Game.ui.hud.draggable_window import DraggableWindow


class BottomHUD:
    """
    HUD du bas de l'écran pour la Phase 1.

    - Barre d'XP de l'espèce
    - Niveau d'espèce (cercle)
    - Horloge jour/nuit
    - Zone de quick craft avec boutons
    - Bouton pour plier / déplier le panneau
    """

    def __init__(self, phase, species, day_night_cycle):
        # phase = Phase1 (pour screen, assets...)
        self.phase = phase
        self.assets = phase.assets
        self.screen = phase.screen
        self.species = species
        self.crafts = phase.craft_system.crafts
        # Système jour/nuit
        self.day_night = day_night_cycle
        self.clock_renderer = ClockRenderer(radius=22)
        self.level_frame_sprite = self.assets.images.get("CircleFrame")
        self._scaled_level_frame: dict[int, pygame.Surface] = {}

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
        self.craft_style = craft_style

        self.craft_buttons: List[tuple[str, Button]] = []
        self.craft_scroll = 0
        self._craft_view_height = 0
        self._craft_max_scroll = 0

        # Rects de layout (calculés à chaque frame)
        self.panel_rect = pygame.Rect(0, 0, 100, 100)
        self.left_rect = pygame.Rect(0, 0, 50, 50)
        self.right_rect = pygame.Rect(0, 0, 50, 50)
        self.context_menu = None
        self._context_menu_just_opened = False
        self._context_menu_dragging = False
        self._context_menu_drag_offset = (0, 0)

        self.refresh_craft_buttons()

    # ---------- Callbacks ----------
    def refresh_craft_buttons(self):
        """Reconstruit la liste des crafts visibles en fonction des déblocages."""
        craft_buttons: List[tuple[str, Button]] = []
        for craft_id, craft_def in self.crafts.items():
            if hasattr(self.phase, "is_craft_unlocked") and not self.phase.is_craft_unlocked(craft_id):
                continue
            image_name = craft_def.get("image", "feu_de_camp")
            try:
                surf = self.assets.get_image(image_name)
            except Exception:
                try:
                    surf = self.assets.get_image("feu_de_camp")
                except Exception:
                    surf = None

            btn = Button(
                text="",
                pos=(0, 0),
                size=(70, 70),
                anchor="center",
                style=self.craft_style,
                on_click=self._make_craft_cb(craft_id),
                on_right_click=self._make_craft_info_cb(craft_id),
                icon=surf,
            )
            craft_buttons.append((craft_id, btn))

        self.craft_buttons = craft_buttons
        self._layout_craft_buttons()

    def _make_craft_cb(self, craft_id: str):
        def _cb(_btn):
            if hasattr(self.phase, "is_craft_unlocked") and not self.phase.is_craft_unlocked(craft_id):
                add_notification("Ce craft n'est pas encore débloqué.")
                return
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

        self._layout_craft_buttons()

    def _layout_craft_buttons(self):
        """
        Positionne les boutons de craft en grille avec retour à la ligne et
        scroll vertical.
        """
        if not self.craft_buttons:
            self._craft_view_height = 0
            self._craft_max_scroll = 0
            return

        padding_x = 20
        padding_y = 34  # pour laisser la place au titre
        gap_x = 16
        gap_y = 12

        start_x = self.right_rect.x + padding_x
        start_y = self.right_rect.y + padding_y
        available_w = max(0, self.right_rect.width - 2 * padding_x)

        row_h = self.craft_buttons[0][1].rect.height
        positions = []
        x = start_x
        y = start_y

        for _cid, btn in self.craft_buttons:
            bw = btn.rect.width
            if x + bw > start_x + available_w and positions:
                x = start_x
                y += row_h + gap_y
            cx = x + bw // 2
            cy = y + row_h // 2
            positions.append((btn, cx, cy))
            x += bw + gap_x

        if positions:
            total_height = (positions[-1][2] - start_y) + row_h
        else:
            total_height = row_h

        self._craft_view_height = max(row_h, self.right_rect.bottom - start_y - 8)
        self._craft_max_scroll = max(0, total_height - self._craft_view_height)
        self.craft_scroll = max(0, min(self.craft_scroll, self._craft_max_scroll))

        for btn, cx, cy in positions:
            btn.move_to((cx, cy - self.craft_scroll))

    # ---------- Interaction ----------

    def _scroll_crafts(self, delta: int):
        if self._craft_max_scroll <= 0:
            self.craft_scroll = 0
            return
        self.craft_scroll = max(0, min(self.craft_scroll + delta, self._craft_max_scroll))

    def _handle_scroll_input(self, events):
        if not self.visible:
            return
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.right_rect.collidepoint((mx, my)):
                    # e.y positif = scroll vers le haut
                    self._scroll_crafts(-e.y * 30)

    def handle(self, events):
        """
        À appeler depuis Phase1.handle_input.
        On envoie les événements aux boutons du HUD.
        """
        self._handle_scroll_input(events)
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
        # Niveau (gauche) avec cadre sprite
        lvl = getattr(self.species, "species_level", 1)
        cx = self.left_rect.x + 32
        cy = self.left_rect.y + 62
        frame_size = 66

        pygame.draw.circle(screen, (35, 55, 35), (cx, cy), frame_size // 2 - 5)
        if self.level_frame_sprite:
            if frame_size not in self._scaled_level_frame:
                self._scaled_level_frame[frame_size] = pygame.transform.smoothscale(
                    self.level_frame_sprite, (frame_size, frame_size)
                )
            frame = self._scaled_level_frame[frame_size]
            frame_rect = frame.get_rect(center=(cx, cy))
            screen.blit(frame, frame_rect)
        else:
            pygame.draw.circle(screen, (180, 230, 180), (cx, cy), frame_size // 2, 2)

        txt = self.font.render(str(lvl), True, (255, 255, 255))
        rect = txt.get_rect(center=(cx, cy))
        screen.blit(txt, rect)

        # Horloge + heure (droite), à la place de l'ancienne zone de stats
        clock_rect = pygame.Rect(
            self.left_rect.x + 70,
            self.left_rect.y + 26,
            self.left_rect.width - 80,
            self.left_rect.height - 26,
        )
        pygame.draw.rect(screen, (25, 40, 25), clock_rect, border_radius=8)
        pygame.draw.rect(screen, (80, 120, 80), clock_rect, 2, border_radius=8)

        clock_cx = clock_rect.x + 38
        clock_cy = clock_rect.centery - 2
        prev_radius = self.clock_renderer.radius
        self.clock_renderer.radius = 22
        self.clock_renderer.draw(screen, clock_cx, clock_cy, self.day_night, None)
        self.clock_renderer.radius = prev_radius

        time_str = self.day_night.get_time_string() if self.day_night else "--:--"
        label = self.small_font.render("Heure", True, (185, 210, 185))
        screen.blit(label, (clock_cx + 32, clock_rect.y + 10))
        time_txt = self.font.render(time_str, True, (240, 240, 240))
        screen.blit(time_txt, (clock_cx + 32, clock_rect.y + 26))

    def _draw_quickcraft(self, screen):
        # Titre "CRAFT"
        title = self.font.render("CRAFT", True, (240, 240, 240))
        t_rect = title.get_rect(midtop=(self.right_rect.centerx, self.right_rect.y))
        screen.blit(title, t_rect)

        # Fond de la zone de craft
        pygame.draw.rect(screen, (20, 55, 20), self.right_rect, border_radius=10)
        pygame.draw.rect(screen, (70, 120, 70), self.right_rect, 2, border_radius=10)

        prev_clip = screen.get_clip()
        screen.set_clip(self.right_rect)

        for craft_id, btn in self.craft_buttons:
            btn.draw(screen)
            if self.phase.selected_craft == craft_id:
                highlight = btn.rect.inflate(10, 10)
                pygame.draw.rect(screen, (200, 230, 120), highlight, width=3, border_radius=12)

        screen.set_clip(prev_clip)

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

        # Partie gauche : XP + niveau + horloge
        self._draw_xp_bar(screen)
        self._draw_level_and_clock(screen)

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
        cost_surfs = []
        if cost:
            cost_surfs.append(self.small_font.render("Ressources requises :", True, (215, 230, 215)))
            for res, amt in cost.items():
                cost_surfs.append(self.small_font.render(f"- {res} : {amt}", True, (210, 220, 210)))

        sprite_surf = None
        sprite_key = craft_def.get("sprite")
        if sprite_key:
            try:
                sprite_surf = self.assets.get_image(sprite_key)
            except Exception:
                sprite_surf = None

        content_surfs: list[pygame.Surface] = []
        if sprite_surf:
            content_surfs.append(sprite_surf)
        content_surfs.extend(desc_surfs)
        content_surfs.extend(cost_surfs)

        mx, my = button_rect.center
        win = DraggableWindow(title_surf, content_surfs, (mx, my - 120))
        if hasattr(self.phase, "info_windows"):
            self.phase.info_windows.append(win)
        self.context_menu = None
        self._context_menu_just_opened = False
        self._context_menu_dragging = False

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
