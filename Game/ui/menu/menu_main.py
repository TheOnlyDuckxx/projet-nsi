# MENU.PY
# Gère le menu principal


# --------------- IMPORTATION DES MODULES ---------------

import pygame
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import Button, ButtonStyle, Slider, Toggle, ValueSelector, OptionSelector
import json 
import os 
import math
import random
# --------------- CLASSE PRINCIPALE ---------------


# Classe de base pour l'hérédité des autres menus
class BaseMenu:
    def __init__(self, app, title:str):
        self.app = app
        self.title = title
        self.bg = pygame.transform.scale(app.assets.get_image("test_menu_background"),(WIDTH, HEIGHT))
        self.title_font = app.assets.get_font("MightySouly", 64)
        self.btn_font = app.assets.get_font("MightySouly", 28)
        self.widgets = []

        # overlay sombre pour lisibilité
        self._overlay = pygame.Surface((WIDTH, HEIGHT))
        self._overlay.set_alpha(90)
        self._overlay.fill((0, 0, 0))

    # Permet d'ajouter un widget
    def add(self, widget):
        self.widgets.append(widget)
        return widget

    # Permet de prendre en charge les events (clics etc.)
    def handle_input(self, events):
        for w in self.widgets:
            w.handle(events)

    def update(self, dt):
        pass
    
    # Affiche le menu niveau moteur
    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))
        title_surf = self.title_font.render(self.title, True, (230,230,230))
        screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 120))

        # 1) corps des widgets
        for w in self.widgets:
            w.draw(screen)

        # 2) popups par-dessus
        for w in self.widgets:
            if hasattr(w, "draw_popup"):
                w.draw_popup(screen)


# Menu des options
class OptionsMenu(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="Options")

        btn_font = app.assets.get_font("MightySouly", 28)

        # --- Widgets ---
        # Fullscreen
        self.toggle_fullscreen = self.add(Toggle(
            "Plein écran",
            (WIDTH//2, 260),
            get_value=lambda: app.settings.get("video.fullscreen", False),
            set_value=lambda v: app.settings.set("video.fullscreen", v),
            font=btn_font
        ))

        # VSync
        self.toggle_vsync = self.add(Toggle(
            "VSync",
            (WIDTH//2, 320),
            get_value=lambda: app.settings.get("video.vsync", False),
            set_value=lambda v: app.settings.set("video.vsync", v),
            font=btn_font
        ))

        # Volume maître (0..1)
        self.slider_volume = self.add(Slider(
            "Volume général",
            (WIDTH//2, 400),
            width=420,
            get_value=lambda: app.settings.get("audio.master_volume", 0.8),
            set_value=lambda v: app.settings.set("audio.master_volume", float(v)),
            font=btn_font,
            min_v=0.0, max_v=1.0, step=0.01
        ))

        # Limite FPS (30..240)
        self.slider_fps = self.add(Slider(
            "Limite FPS",
            (WIDTH//2, 470),
            width=420,
            get_value=lambda: float(app.settings.get("video.fps_cap", 60)),
            set_value=lambda v: app.settings.set("video.fps_cap", int(v)),
            font=btn_font,
            min_v=30, max_v=240, step=5
        ))

        # Boutons du bas
        ghost = ButtonStyle(draw_background=False, font=btn_font, text_color=(230,230,230), hover_zoom=1.08)
        self.btn_back = Button("← Retour", (WIDTH//2, 560), anchor="center", style=ghost,
                               on_click=lambda b: app.change_state("MENU"))
        self.add(self.btn_back)

    def handle_input(self, events):
        super().handle_input(events)
        # Raccourci ECHAP
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

    def render(self, screen):
        super().render(screen)  # fond + titre + widgets (draw est appelé dans BaseMenu)



class MainMenu(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="EvoNSI")
        
        # ---- Styles de boutons ----
        primary = ButtonStyle(
            draw_background=True,
            bg_color=(60, 80, 110),
            hover_bg_color=(80, 110, 155),
            active_bg_color=(40, 140, 240),
            draw_border=True,
            border_color=(20, 30, 45),
            border_width=2,
            radius=14,
            font=self.btn_font,
            text_color=(255, 255, 255),
            hover_text_color=(255, 255, 255),
            active_text_color=(255, 255, 255),
            padding_x=26,
            padding_y=14,
            shadow=True,
            shadow_offset=(3, 3),
            shadow_alpha=90,
            hover_zoom=1.10,
            zoom_speed=0.22,
        )

        # Style spécial pour le bouton "Reprendre" (vert)
        resume_style = ButtonStyle(
            draw_background=True,
            bg_color=(40, 100, 60),
            hover_bg_color=(60, 140, 80),
            active_bg_color=(80, 180, 100),
            draw_border=True,
            border_color=(20, 50, 30),
            border_width=2,
            radius=14,
            font=self.btn_font,
            text_color=(255, 255, 255),
            hover_text_color=(255, 255, 255),
            active_text_color=(255, 255, 255),
            padding_x=26,
            padding_y=14,
            shadow=True,
            shadow_offset=(3, 3),
            shadow_alpha=90,
            hover_zoom=1.10,
            zoom_speed=0.22,
        )

        ghost = ButtonStyle(
            draw_background=False,
            font=self.btn_font,
            text_color=(230, 230, 230),
            hover_zoom=1.08,
            zoom_speed=0.22,
        )

        # Importer Phase1 pour vérifier la sauvegarde
        from Game.gameplay.phase1 import Phase1
        self.has_save = Phase1.save_exists()

        # Calculer les positions en fonction de la présence d'une sauvegarde
        y0 = HEIGHT // 2 + 20
        gap = 70
        
        # Ajuster la position de départ si on a une sauvegarde
        if self.has_save:
            y0 -= gap // 2  # Décaler vers le haut pour faire de la place

        # ---- Bouton "Reprendre" (uniquement si sauvegarde existe) ----
        if self.has_save:
            self.btn_resume = self.add(Button(
                "▶ REPRENDRE LA PARTIE",
                (WIDTH // 2, y0 - gap),
                anchor="center",
                style=resume_style,
                on_click=lambda b: self.app.change_state("PHASE1", load_save=True),
            ))

        # ---- Boutons normaux ----
        self.btn_start = self.add(Button(
            "NOUVELLE PARTIE",
            (WIDTH // 2, y0 ),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("CREATION"),
        ))

        self.btn_options = self.add(Button(
            "OPTIONS",
            (WIDTH // 2, y0 + gap),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("OPTIONS"),
        ))

        self.btn_credits = self.add(Button(
            "Crédits",
            (WIDTH // 2, y0 + 2*gap),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.change_state("CREDITS"),
        ))

        self.btn_quit = self.add(Button(
            "Quitter",
            (WIDTH // 2, y0 + 3*gap),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.quit_game(),
        ))

    def enter(self):
        """Appelé quand on entre dans ce menu - rafraîchit la détection de sauvegarde"""
        from Game.gameplay.phase1 import Phase1
        new_has_save = Phase1.save_exists()
        
        # Si l'état de la sauvegarde a changé, reconstruire le menu
        if new_has_save != self.has_save:
            self.__init__(self.app)

    def handle_input(self, events):
        super().handle_input(events)

    def render(self, screen):
        super().render(screen)
    


class CreditMenu(BaseMenu):
    def __init__(self,app):
        super().__init__(app, title="Credits")
        self.credit_font = app.assets.get_font("MightySouly", 20)
        self.txt ="""
        Jeu créé par : \n
            - Romain Trohel\n
            - Paul Juillet\n
            - Timéo Barré--Golvet\n
        Commencé le 2/10/25 et terminé le ...
        """
        ghost = ButtonStyle(draw_background=False, font=self.btn_font, text_color=(230,230,230), hover_zoom=1.08)
        self.btn_back = Button("← Retour", (WIDTH//2, 560), anchor="center", style=ghost,on_click=lambda b: self.app.change_state("MENU"))
        self.add(self.btn_back)
    def render(self, screen):
        super().render(screen)

        # Couleur du texte
        color = (230, 230, 230)

        # Découpe le texte par ligne
        lines = self.txt.strip().split('\n')

        # Position de départ verticale
        start_y = 250

        for i, line in enumerate(lines):
            # On rend chaque ligne séparément
            credit_line = self.credit_font.render(line.strip(), True, color)
            # Centrage horizontal
            x = WIDTH // 2 - credit_line.get_width() // 2
            y = start_y + i*(credit_line.get_height()-5)
            screen.blit(credit_line, (x, y))


class WorldCreationMenu(BaseMenu):
    GREEN_BG = (0x4b, 0x66, 0x4a)   # #4b664a
    DARK_BG  = (0x1f, 0x21, 0x22)   # #1f2122

    INPUT_BG = (235, 235, 235)
    INPUT_FG = (30, 30, 30)
    INPUT_PLACEHOLDER = (120, 120, 120)

    def __init__(self, app):
        super().__init__(app, title="Paramètres du monde")

        # --- Charger les paramètres custom existants ---
        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
                self.params = presets.get("presets", {}).get("Custom", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.params = {}

        # Champ texte (nom du monde)
        self.world_name = (self.params.get("world_name", "") or "").strip()
        self.name_active = False
        self._cursor_t = 0.0
        self._cursor_on = True

        # Sprite de bouton vert
        self._btn_sprite = app.assets.get_image("boutons_menu").convert_alpha()
        self._sprite_cache: dict[tuple[int, int], pygame.Surface] = {}

        # Définition des 12 paramètres (12 boutons)
        self.param_defs = [
            ("world_size", "Taille", ["Petite", "Moyenne", "Grande", "Gigantesque"]),
            ("water_coverage", "Eau", ["Aride", "Tempéré", "Océanique"]),
            ("temperature", "Température", ["Glaciaire", "Froid", "Tempéré", "Chaud", "Ardent"]),
            ("atmosphere_density", "Atmosphère", ["Faible", "Normale", "Épaisse"]),
            ("resource_density", "Ressources", ["Pauvre", "Moyenne", "Riche", "Instable"]),
            ("biodiversity", "Biodiversité", ["Faible", "Moyenne", "Élevée", "Extrême"]),
            ("tectonic_activity", "Tectonique", ["Stable", "Moyenne", "Instable", "Chaotique"]),
            ("weather", "Météo", ["Calme", "Variable", "Extrême"]),
            ("gravity", "Gravité", ["Faible", "Moyenne", "Forte"]),
            ("cosmic_radiation", "Radiations", ["Faible", "Moyenne", "Forte"]),
            ("mystic_influence", "Mystique", ["Nulle", "Faible", "Moyenne", "Forte"]),
            ("dimensional_stability", "Stabilité", ["Stable", "Fissuré", "Instable"]),
        ]

        # Boutons (paramètres + navigation)
        self._param_buttons = []
        for key, label, options in self.param_defs:
            default_idx = len(options) // 2
            default_val = options[default_idx]
            cur = self.params.get(key, default_val)
            if cur not in options:
                cur = default_val
            self._param_buttons.append(self._CycleButton(key, label, options, options.index(cur)))

        self._btn_back = self._SimpleButton("RETOUR", on_click=lambda: self.app.change_state("MENU"))
        self._btn_next = self._SimpleButton("SUIVANT", on_click=self._go_to_species_creation)

        # Globe (points)
        self.N_POINTS = 30000   # 40k peut être lourd selon les PC
        self.N_HOTSPOTS = 50
        self.SPREAD_MIN = 0.03
        self.SPREAD_MAX = 0.12
        self._rot_step = 0.0

        self.globe_radius = 120
        self.globe_center = (0, 0)
        self._generate_hotspot_globe()

        # Layout cache
        self._last_size = None
        self._layout = {}

    # ----------------- UI helpers -----------------

    class _CycleButton:
        def __init__(self, key, label, options, index):
            self.key = key
            self.label = label
            self.options = options
            self.index = index
            self.rect = pygame.Rect(0, 0, 10, 10)
            self.hovered = False
            self.pressed = False

        def value(self):
            return self.options[self.index]

        def set_rect(self, rect: pygame.Rect):
            self.rect = rect

        def handle(self, events):
            mx, my = pygame.mouse.get_pos()
            self.hovered = self.rect.collidepoint(mx, my)

            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and self.hovered:
                    if e.button in (1, 3):
                        self.pressed = True

                if e.type == pygame.MOUSEBUTTONUP and self.pressed:
                    if self.hovered:
                        if e.button == 1:
                            self.index = (self.index + 1) % len(self.options)
                        elif e.button == 3:
                            self.index = (self.index - 1) % len(self.options)
                    self.pressed = False

    class _SimpleButton:
        def __init__(self, text, on_click):
            self.text = text
            self.on_click = on_click
            self.rect = pygame.Rect(0, 0, 10, 10)
            self.hovered = False
            self.pressed = False

        def set_rect(self, rect: pygame.Rect):
            self.rect = rect

        def handle(self, events):
            mx, my = pygame.mouse.get_pos()
            self.hovered = self.rect.collidepoint(mx, my)

            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.hovered:
                    self.pressed = True
                if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    if self.pressed and self.hovered:
                        self.on_click()
                    self.pressed = False

    def _get_scaled_sprite(self, w: int, h: int) -> pygame.Surface:
        key = (max(1, w), max(1, h))
        if key not in self._sprite_cache:
            self._sprite_cache[key] = pygame.transform.smoothscale(self._btn_sprite, key)
        return self._sprite_cache[key]

    @staticmethod
    def _clamp(v, a, b):
        return a if v < a else b if v > b else v

    def _compute_layout(self, screen: pygame.Surface):
        W, H = screen.get_size()
        if self._last_size == (W, H):
            return
        self._last_size = (W, H)

        left_w = int(W * 0.60)
        right_w = W - left_w

        # Marges/espacements en % de WIDTH total (comme sur ton schéma)
        margin = self._clamp(int(W * 0.05), 10, int(left_w * 0.18))
        col_gap = self._clamp(int(W * 0.05), 10, int(left_w * 0.18))
        inner_w = left_w - 2 * margin
        col_w = max(10, (inner_w - col_gap) // 2)

        # Fonts adaptatives
        title_size = self._clamp(int(H * 0.06), 28, 72)
        label_size = self._clamp(int(H * 0.026), 14, 30)
        value_size = self._clamp(int(H * 0.030), 16, 34)

        self.title_font = self.app.assets.get_font("MightySouly", title_size)
        self.small_font = self.app.assets.get_font("MightySouly", label_size)
        self.value_font = self.app.assets.get_font("MightySouly", value_size)

        # Dimensions cibles (on rescale si ça dépasse)
        top_pad = int(H * 0.04)
        gap1 = int(H * 0.025)
        gap2 = int(H * 0.04)
        gap3 = int(H * 0.03)
        bottom_pad = int(H * 0.05)

        input_h = int(H * 0.10)
        input_w = int(left_w * 0.50)

        btn_h = int(H * 0.10)
        row_gap = max(2, int(H * 0.012))

        nav_h = int(H * 0.10)

        # Mesure du titre
        title_surf = self.title_font.render(self.title, True, (245, 245, 245))
        title_h = title_surf.get_height()

        grid_h = 6 * btn_h + 5 * row_gap

        required = top_pad + title_h + gap1 + input_h + gap2 + grid_h + gap3 + nav_h + bottom_pad
        vscale = min(1.0, (H * 0.96) / max(1, required))

        # Applique vscale (pour les écrans “plats” type 16:9 vs ultra-wide)
        def S(x): return int(x * vscale)

        top_pad, gap1, gap2, gap3, bottom_pad = map(S, (top_pad, gap1, gap2, gap3, bottom_pad))
        input_h, btn_h, row_gap, nav_h = map(S, (input_h, btn_h, row_gap, nav_h))

        # Recalcule grid_h après scale
        grid_h = 6 * btn_h + 5 * row_gap

        # Positions
        title_y = top_pad
        input_y = title_y + title_h + gap1
        grid_y = input_y + input_h + gap2
        nav_y = H - bottom_pad - nav_h

        # Champs
        input_rect = pygame.Rect(
            left_w // 2 - input_w // 2,
            input_y,
            input_w,
            input_h
        )

        # Colonnes boutons
        col1_x = margin
        col2_x = margin + col_w + col_gap

        # Rects 12 boutons (6 + 6)
        param_rects = []
        for r in range(6):
            y = grid_y + r * (btn_h + row_gap)
            param_rects.append(pygame.Rect(col1_x, y, col_w, btn_h))
        for r in range(6):
            y = grid_y + r * (btn_h + row_gap)
            param_rects.append(pygame.Rect(col2_x, y, col_w, btn_h))

        # Rects nav (2 boutons sous les 12)
        nav_gap = self._clamp(int(inner_w * 0.12), 12, int(inner_w * 0.30))
        nav_w = max(10, (inner_w - nav_gap) // 2)
        back_rect = pygame.Rect(margin, nav_y, nav_w, nav_h)
        next_rect = pygame.Rect(margin + nav_w + nav_gap, nav_y, nav_w, nav_h)

        # Globe
        globe_r = int(min(right_w, H) * 0.42)
        globe_r = max(40, globe_r)
        globe_center = (left_w + right_w // 2, H // 2)

        self._layout = {
            "W": W, "H": H,
            "left_w": left_w, "right_w": right_w,
            "input_rect": input_rect,
            "param_rects": param_rects,
            "back_rect": back_rect,
            "next_rect": next_rect,
            "globe_r": globe_r,
            "globe_center": globe_center,
            "title_surf": title_surf,
            "title_pos": (left_w // 2 - title_surf.get_width() // 2, title_y),
        }

        # Applique rects aux boutons
        for i, b in enumerate(self._param_buttons):
            b.set_rect(param_rects[i])

        self._btn_back.set_rect(back_rect)
        self._btn_next.set_rect(next_rect)

        self.globe_radius = globe_r
        self.globe_center = globe_center

        # Si on change beaucoup la taille, le cache sprite doit rester ok (il est indexé par taille)

    # ----------------- Globe -----------------

    def _generate_hotspot_globe(self):
        self.hotspots = []
        for _ in range(self.N_HOTSPOTS):
            lat = random.uniform(-math.pi / 2, math.pi / 2)
            lon = random.uniform(-math.pi, math.pi)
            spread = random.uniform(self.SPREAD_MIN, self.SPREAD_MAX)
            self.hotspots.append((lat, lon, spread))

        self.globe_points = []
        for _ in range(self.N_POINTS):
            h_lat, h_lon, spread = random.choice(self.hotspots)
            lat = h_lat + random.gauss(0, spread)
            lon = h_lon + random.gauss(0, spread)
            if lon > math.pi:
                lon -= 2 * math.pi
            if lon < -math.pi:
                lon += 2 * math.pi
            self.globe_points.append([lat, lon])

    def update(self, dt):
        self._rot_step = 0.40 * dt
        self._cursor_t += dt
        if self._cursor_t >= 0.45:
            self._cursor_t = 0.0
            self._cursor_on = not self._cursor_on

    def _draw_globe(self, screen):
        R = self.globe_radius
        cx, cy = self.globe_center

        # Cercle limite (léger)
        pygame.draw.circle(screen, (70, 70, 70), (cx, cy), R, width=max(1, int(R * 0.01)))

        surf = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        for p in self.globe_points:
            lat, lon = p
            lon += self._rot_step
            if lon > math.pi:
                lon -= 2 * math.pi
            p[1] = lon

            x = R + R * math.cos(lat) * math.cos(lon)
            y = R + R * math.sin(lat)

            ix, iy = int(x), int(y)
            if 0 <= ix < 2 * R and 0 <= iy < 2 * R:
                surf.set_at((ix, iy), (255, 255, 255, 255))

        screen.blit(surf, (cx - R, cy - R))

    # ----------------- Input / events -----------------

    def handle_input(self, events):
        # Layout dépend de la taille d'écran => on update ici aussi
        screen = self.app.screen if hasattr(self.app, "screen") else None
        if screen:
            self._compute_layout(screen)

        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self._layout:
                    self.name_active = self._layout["input_rect"].collidepoint(e.pos)

            if e.type == pygame.KEYDOWN and self.name_active:
                if e.key == pygame.K_RETURN:
                    self.name_active = False
                elif e.key == pygame.K_BACKSPACE:
                    self.world_name = self.world_name[:-1]
                else:
                    if e.unicode and e.unicode.isprintable() and len(self.world_name) < 24:
                        self.world_name += e.unicode

        # Boutons paramètres
        for b in self._param_buttons:
            b.handle(events)

        # Nav
        self._btn_back.handle(events)
        self._btn_next.handle(events)

    # ----------------- Render -----------------

    def _draw_sprite_button(self, screen, rect, hovered, pressed, lines):
        sprite = self._get_scaled_sprite(rect.width, rect.height)
        screen.blit(sprite, rect.topleft)

        # Effet hover/press simple (pas d’éléments “schéma” dessinés)
        if hovered:
            ov = pygame.Surface(rect.size, pygame.SRCALPHA)
            ov.fill((255, 255, 255, 22))
            screen.blit(ov, rect.topleft)
        if pressed:
            ov = pygame.Surface(rect.size, pygame.SRCALPHA)
            ov.fill((0, 0, 0, 25))
            screen.blit(ov, rect.topleft)

        # Texte (centré)
        if len(lines) == 1:
            t = self.value_font.render(lines[0], True, (245, 245, 245))
            screen.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))
        else:
            t1 = self.small_font.render(lines[0], True, (240, 240, 240))
            t2 = self.value_font.render(lines[1], True, (255, 255, 255))
            y = rect.centery - (t1.get_height() + t2.get_height()) // 2
            screen.blit(t1, (rect.centerx - t1.get_width() // 2, y))
            screen.blit(t2, (rect.centerx - t2.get_width() // 2, y + t1.get_height() - 2))

    def render(self, screen):
        self._compute_layout(screen)
        W, H = self._layout["W"], self._layout["H"]
        left_w = self._layout["left_w"]

        # Fonds 60/40
        pygame.draw.rect(screen, self.GREEN_BG, pygame.Rect(0, 0, left_w, H))
        pygame.draw.rect(screen, self.DARK_BG, pygame.Rect(left_w, 0, W - left_w, H))

        # Titre centré sur le bloc gauche
        screen.blit(self._layout["title_surf"], self._layout["title_pos"])

        # Input (placeholder + curseur)
        ir = self._layout["input_rect"]
        pygame.draw.rect(screen, self.INPUT_BG, ir, border_radius=10)
        border = (220, 220, 220) if not self.name_active else (255, 255, 255)
        pygame.draw.rect(screen, border, ir, 2, border_radius=10)

        if self.world_name:
            txt = self.value_font.render(self.world_name, True, self.INPUT_FG)
            screen.blit(txt, (ir.x + 14, ir.centery - txt.get_height() // 2))
        else:
            ph = self.value_font.render("Entrez le nom de votre monde...", True, self.INPUT_PLACEHOLDER)
            screen.blit(ph, (ir.x + 14, ir.centery - ph.get_height() // 2))

        if self.name_active and self._cursor_on:
            # petit curseur
            base_x = ir.x + 14
            if self.world_name:
                tmp = self.value_font.render(self.world_name, True, self.INPUT_FG)
                base_x += tmp.get_width() + 2
            cy = ir.centery
            pygame.draw.line(screen, (40, 40, 40), (base_x, cy - ir.height // 4), (base_x, cy + ir.height // 4), 2)

        # 12 boutons (2 colonnes de 6)
        for b in self._param_buttons:
            self._draw_sprite_button(
                screen,
                b.rect,
                b.hovered,
                b.pressed,
                [b.label, b.value()]
            )

        # Retour / Suivant
        self._draw_sprite_button(screen, self._btn_back.rect, self._btn_back.hovered, self._btn_back.pressed, [self._btn_back.text])
        self._draw_sprite_button(screen, self._btn_next.rect, self._btn_next.hovered, self._btn_next.pressed, [self._btn_next.text])

        # Globe à droite (centré dans le bloc 40%)
        self._draw_globe(screen)

    # ----------------- Save / next -----------------

    def _go_to_species_creation(self):
        self.params["world_name"] = (self.world_name.strip() or "Monde sans nom")

        for b in self._param_buttons:
            self.params[b.key] = b.value()

        if "seed" not in self.params:
            self.params["seed"] = "Aléatoire"

        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
        except Exception:
            presets = {}

        if "presets" not in presets:
            presets["presets"] = {}
        presets["presets"]["Custom"] = self.params

        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=4, ensure_ascii=False)

        self.app.change_state("SPECIES_CREATION")



class SpeciesCreationMenu(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="Création d'espèce")

        self.font = app.assets.get_font("MightySouly", 22)
        self.btn_font = app.assets.get_font("MightySouly", 28)

        # --- Charger le JSON des mutations ---
        mutations_path = os.path.join("Game", "data", "mutations.json")
        try:
            with open(mutations_path, "r", encoding="utf-8") as f:
                all_mutations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[SpeciesCreationMenu] Impossible de charger mutations.json : {e}")
            all_mutations = {}

        # Mutations de base uniquement (base: true)
        self.base_mutations = {
            mid: data for mid, data in all_mutations.items()
            if data.get("base", False)
        }

        # État local : mutations sélectionnées (id → bool)
        # On tente de récupérer ce qui a été déjà choisi (session précédente)
        default_sel = []
        if hasattr(app, "selected_base_mutations"):
            default_sel = list(app.selected_base_mutations or [])
        else:
            # fallback éventuel depuis settings (optionnel)
            default_sel = app.settings.get("species.base_mutations", []) or []

        self.selected_ids: set[str] = {
            mid for mid in default_sel if mid in self.base_mutations
        }

        self.error_msg: str = ""

        # --- Layout des Toggles ---
        base_list = list(self.base_mutations.items())

        # Paramètres du layout multi-colonnes
        max_per_col = 10                            # ← nb max dans la colonne 1 avant de décaler
        col1_x = 150                                # ← colonne de gauche
        col2_x = WIDTH // 2                         # ← colonne du milieu / droite
        start_y = 220
        gap_y = 45

        for i, (mutation_id, data) in enumerate(base_list):

            # Choix colonne
            if i < max_per_col:
                x = col1_x
                y = start_y + i * gap_y
            else:
                # items au-delà du max vont en colonne 2
                x = col2_x
                y = start_y + (i - max_per_col) * gap_y

            label = data.get("nom", mutation_id)

            def make_get(mid):
                return lambda mid=mid: mid in self.selected_ids

            def make_set(mid):
                def setter(value, mid=mid):
                    self._toggle_mutation(mid, value)
                return setter

            self.add(Toggle(
                label,
                (x, y),
                get_value=make_get(mutation_id),
                set_value=make_set(mutation_id),
                font=self.btn_font,
            ))

        # --- Styles de boutons bas ---
        primary = ButtonStyle(
            draw_background=True,
            bg_color=(60, 80, 110),
            hover_bg_color=(80, 110, 155),
            active_bg_color=(40, 140, 240),
            draw_border=True,
            border_color=(20, 30, 45),
            border_width=2,
            radius=14,
            font=self.btn_font,
            text_color=(255, 255, 255),
            hover_text_color=(255, 255, 255),
            active_text_color=(255, 255, 255),
            padding_x=26,
            padding_y=14,
            shadow=True,
            shadow_offset=(3, 3),
            shadow_alpha=90,
            hover_zoom=1.10,
            zoom_speed=0.22,
        )

        ghost = ButtonStyle(
            draw_background=False,
            font=self.btn_font,
            text_color=(230, 230, 230),
            hover_zoom=1.08,
            zoom_speed=0.22,
        )

       # --- Boutons du bas adaptés automatiquement ---
        # On calcule la plus grande hauteur atteinte parmi les colonnes
        total_rows_col1 = min(len(base_list), max_per_col)
        total_rows_col2 = max(0, len(base_list) - max_per_col)

        height_col1 = start_y + total_rows_col1 * gap_y
        height_col2 = start_y + total_rows_col2 * gap_y

        y_buttons = max(height_col1, height_col2) + 80

        # Position en bas : centrée
        button_x = WIDTH // 2

        self.btn_reset = self.add(Button(
            "Réinitialiser",
            (button_x - 200, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self._reset_selection(),
        ))

        self.btn_validate = self.add(Button(
            "Valider",
            (button_x, y_buttons),
            anchor="center",
            style=primary,
            on_click=lambda b: self._validate_and_back(),
        ))

        self.btn_back = self.add(Button(
            "Retour",
            (button_x + 200, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.change_state("CREATION"),
        ))
    # --- Logique de sélection / incompatibilités ---

    def _toggle_mutation(self, mutation_id: str, enabled: bool):
        """
        Active/désactive une mutation, en vérifiant les incompatibilités.
        """
        if enabled:
            data = self.base_mutations.get(mutation_id, {})
            incompat_ids = set(data.get("incompatibles", []))
            conflict = incompat_ids & self.selected_ids
            if conflict:
                # On bloque et on affiche un message d'erreur
                noms = [
                    self.base_mutations[c]["nom"] if c in self.base_mutations else c
                    for c in conflict
                ]
                self.error_msg = "Incompatible avec : " + ", ".join(noms)
                return
            self.selected_ids.add(mutation_id)
            self.error_msg = ""
        else:
            self.selected_ids.discard(mutation_id)
            self.error_msg = ""

    def _reset_selection(self):
        self.selected_ids.clear()
        self.error_msg = ""

    def _validate_and_back(self):
        """
        Sauvegarde la sélection dans l'App (et éventuellement dans les settings)
        puis retourne au menu principal.
        """
        # Stockage en mémoire pour la session
        if hasattr(self.app, "selected_base_mutations"):
            self.app.selected_base_mutations = list(self.selected_ids)

        # Optionnel : persister dans settings
        try:
            self.app.settings.set("species.base_mutations", list(self.selected_ids))
        except Exception:
            pass

        self.app.change_state("LOADING")

    def handle_input(self, events):
        super().handle_input(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

    def render(self, screen):
        super().render(screen)

        # Bandeau d'info / erreurs
        if self.error_msg:
            font = self.app.assets.get_font("MightySouly", 22)
            txt = font.render(self.error_msg, True, (255, 120, 120))
            screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT - 120))
        else:
            font = self.app.assets.get_font("MightySouly", 20)
            msg = "Sélectionne les mutations de base de ton espèce (les incompatibilités sont bloquées)."
            surf = font.render(msg, True, (210, 210, 210))
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 120))