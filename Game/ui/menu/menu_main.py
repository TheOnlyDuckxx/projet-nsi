# MENU.PY
# Gère le menu principal


# --------------- IMPORTATION DES MODULES ---------------

import pygame
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import Button, ButtonStyle, Slider, Toggle
from Game.species.species import Espece
from Game.species.sprite_render import EspeceRenderer
import json 
import os 
import math
import random

def _trim_sprite(surface: pygame.Surface) -> pygame.Surface:
    try:
        rect = surface.get_bounding_rect()
        if rect.width <= 0 or rect.height <= 0:
            return surface
        return surface.subsurface(rect).copy()
    except Exception:
        return surface
# --------------- CLASSE PRINCIPALE ---------------


# Classe de base pour l'hérédité des autres menus
class BaseMenu:
    def __init__(self, app, title:str):
        self.app = app
        self.app.audio.play_music("main_chill", loops=-1)
        self.title = title
        self.bg = pygame.transform.scale(app.assets.get_image("menu_background"),(WIDTH, HEIGHT))
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

        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        # Fonts dépendants de HEIGHT
        title_size = clamp(int(HEIGHT * 0.085), 34, 84)
        item_size  = clamp(int(HEIGHT * 0.040), 18, 44)
        self.title_font = app.assets.get_font("MightySouly", title_size)
        self.btn_font = app.assets.get_font("MightySouly", item_size)

        # Largeur sliders
        slider_w = clamp(int(WIDTH * 0.36), 280, 620)

        x = WIDTH // 2

        # --- Widgets (positions provisoires, on re-layout après) ---
        self.toggle_fullscreen = self.add(Toggle(
            "Plein écran",
            (x, 0),
            get_value=lambda: app.settings.get("video.fullscreen", False),
            set_value=lambda v: app.settings.set("video.fullscreen", v),
            font=self.btn_font
        ))

        self.toggle_vsync = self.add(Toggle(
            "VSync",
            (x, 0),
            get_value=lambda: app.settings.get("video.vsync", False),
            set_value=lambda v: app.settings.set("video.vsync", v),
            font=self.btn_font
        ))

        self.slider_master = self.add(Slider(
            "Volume général",
            (x, 0),
            width=slider_w,
            get_value=lambda: app.settings.get("audio.master_volume", 0.8),
            set_value=lambda v: app.settings.set("audio.master_volume", float(v)),
            font=self.btn_font,
            min_v=0.0, max_v=1.0, step=0.01
        ))

        self.slider_music = self.add(Slider(
            "Volume musique",
            (x, 0),
            width=slider_w,
            get_value=lambda: app.settings.get("audio.music_volume", 0.8),
            set_value=lambda v: app.settings.set("audio.music_volume", float(v)),
            font=self.btn_font,
            min_v=0.0, max_v=1.0, step=0.01
        ))

        self.slider_sfx = self.add(Slider(
            "Volume sfx",
            (x, 0),
            width=slider_w,
            get_value=lambda: app.settings.get("audio.sfx_volume", 0.8),
            set_value=lambda v: app.settings.set("audio.sfx_volume", float(v)),
            font=self.btn_font,
            min_v=0.0, max_v=1.0, step=0.01
        ))

        self.slider_fps = self.add(Slider(
            "Limite FPS",
            (x, 0),
            width=slider_w,
            get_value=lambda: float(app.settings.get("video.fps_cap", 60)),
            set_value=lambda v: app.settings.set("video.fps_cap", int(v)),
            font=self.btn_font,
            min_v=30, max_v=240, step=5
        ))

        self.toggle_perf_logs = self.add(Toggle(
            "Logs performance",
            (x, 0),
            get_value=lambda: bool(app.settings.get("debug.perf_logs", True)),
            set_value=lambda v: app.settings.set("debug.perf_logs", bool(v)),
            font=self.btn_font
        ))

        ghost = ButtonStyle(draw_background=False, font=self.btn_font, text_color=(230,230,230), hover_zoom=1.08)
        self.btn_back = Button(
            "← Retour",
            (x, 0),
            anchor="center",
            style=ghost,
            on_click=lambda b: app.change_state("MENU")
        )
        self.add(self.btn_back)

        # --- Layout vertical centré (anti-chevauchement) ---
        self._layout_centered()

    def _layout_centered(self):
        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        x = WIDTH // 2

        # Pré-rendu titre pour mesurer
        title_surf = self.title_font.render(self.title, True, (230, 230, 230))
        title_h = title_surf.get_height()

        title_gap = clamp(int(HEIGHT * 0.050), 18, 60)
        item_gap  = clamp(int(HEIGHT * 0.030), 10, 30)
        back_gap  = clamp(int(HEIGHT * 0.040), 16, 46)

        items = [
            self.toggle_fullscreen,
            self.toggle_vsync,
            self.slider_master,
            self.slider_music,
            self.slider_sfx,
            self.slider_fps,
            self.toggle_perf_logs,
        ]

        def item_block_h(w):
            # Toggle = hauteur du bouton
            if hasattr(w, "btn"):
                return w.btn.rect.height

            # Slider : label est à bar_top - 36, knob dépasse => il faut une “hauteur de bloc” plus grande
            # (on s'aligne sur votre implémentation Slider._rebuild_rects) :contentReference[oaicite:3]{index=3}
            label_h = w.label_surf.get_height()
            return 5 + label_h + (2 * w.knob_r) + 5  # marge sécurité

        blocks = [item_block_h(w) for w in items]
        total_h = title_h + title_gap + sum(blocks) + item_gap * (len(items) - 1) + back_gap + self.btn_back.rect.height

        top_y = HEIGHT // 2 - total_h // 2

        # Stocke pour render
        self._title_surf = title_surf
        self._title_pos = (x - title_surf.get_width() // 2, top_y)

        cursor = top_y + title_h + title_gap

        for w, bh in zip(items, blocks):
            if hasattr(w, "btn"):
                # Toggle
                w.btn.move_to((x, cursor + bh // 2))
            else:
                # Slider : on place le centre de la barre en tenant compte du label au-dessus
                label_h = w.label_surf.get_height()
                bar_center_y = cursor + 36 + label_h + 8 + w.knob_r
                w.pos = (x, bar_center_y)
                w._rebuild_rects()
            cursor += bh + item_gap

        # Bouton retour sous le bloc
        cursor += back_gap
        self.btn_back.move_to((x, cursor + self.btn_back.rect.height // 2))

    def handle_input(self, events):
        super().handle_input(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

    def render(self, screen):
        # même fond que partout (menu_background + overlay)
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))

        # titre centré (pas celui de BaseMenu à y=120)
        screen.blit(self._title_surf, self._title_pos)

        for w in self.widgets:
            w.draw(screen)
        for w in self.widgets:
            if hasattr(w, "draw_popup"):
                w.draw_popup(screen)




class MainMenu(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="The Long Evolution")

        # ---------- Helpers ----------
        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        self._clamp = clamp

        # ---------- Zone overlay (40% WIDTH) ----------
        self.overlay_w = int(WIDTH * 0.40)
        self.overlay_surf = pygame.Surface((self.overlay_w, HEIGHT), pygame.SRCALPHA)
        # Noir transparent
        self.overlay_surf.fill((0, 0, 0, 160))  # alpha 0..255 (augmente si tu veux plus sombre)

        # ---------- Fonts (dépendants de HEIGHT) ----------
        title_size = clamp(int(HEIGHT * 0.10), 42, 96)
        btn_size = clamp(int(HEIGHT * 0.04), 18, 30)
        self.title_font = app.assets.get_font("MightySouly", title_size)
        self.btn_font = app.assets.get_font("KiwiSoda", btn_size)
        # ---------- Sprite de bouton ----------
        # On évite de "trim" pour ne pas casser les marges transparentes du sprite.
        try:
            self._btn_sprite_default = _trim_sprite(app.assets.get_image("btn_menu_default").convert_alpha())
            self._btn_sprite_hover = _trim_sprite(app.assets.get_image("btn_menu_hover").convert_alpha())
        except Exception:
            # fallback (anciens noms)
            self._btn_sprite_default = _trim_sprite(app.assets.get_image("menus_bouton").convert_alpha())
            self._btn_sprite_hover = self._btn_sprite_default

        self._sprite_cache: dict[tuple[int, int, bool], pygame.Surface] = {}

        # ---------- Boutons ----------
        from Game.gameplay.phase1 import Phase1
        self.has_save = Phase1.save_exists()

        self._buttons = []
        self._rebuild_layout()

    # ------------ Bouton sprite interne ------------
    class _SpriteButton:
        def __init__(self, text, rect: pygame.Rect, font, on_click):
            self.text = text
            self.rect = rect
            self.font = font
            self.on_click = on_click
            self.hovered = False
            self.pressed = False

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

    def _get_scaled_sprite(self, w: int, h: int, hovered: bool) -> pygame.Surface:
        key = (max(1, w), max(1, h), hovered)
        if key not in self._sprite_cache:
            src = self._btn_sprite_hover if hovered else self._btn_sprite_default
            sw, sh = src.get_size()
            scale = min(w / max(1, sw), h / max(1, sh))
            nw = max(1, int(sw * scale))
            nh = max(1, int(sh * scale))
            self._sprite_cache[key] = pygame.transform.smoothscale(src, (nw, nh))
        return self._sprite_cache[key]

    def _rebuild_layout(self):
        """Recrée la liste des boutons + positions (centrés dans l'overlay gauche)."""
        self._buttons.clear()

        # Dimensions boutons (dépendants de WIDTH/HEIGHT)
        btn_w = self._clamp(int(self.overlay_w * 0.86), 200, self.overlay_w - 20)
        btn_h = self._clamp(int(HEIGHT * 0.12), 56, 140)
        gap = self._clamp(int(HEIGHT * 0.03), 10, 44)
        title_gap = self._clamp(int(HEIGHT * 0.05), 12, 60)

        # Liste des actions (avec ou sans sauvegarde)
        actions = []
        if self.has_save:
            actions.append(("Reprendre", lambda: self.app.change_state("PHASE1", load_save=True)))
        actions += [
            ("Commencer", lambda: self.app.change_state("CREATION")),
            ("Options", lambda: self.app.change_state("OPTIONS")),
            ("Credits", lambda: self.app.change_state("CREDITS")),
            ("Quitter", lambda: self.app.quit_game()),
        ]

        # Mesure titre pour centrer le bloc (titre + boutons) verticalement
        title_surf = self.title_font.render(self.title, True, (235, 235, 235))
        title_h = title_surf.get_height()

        n = len(actions)
        total_h = title_h + title_gap + (n * btn_h) + ((n - 1) * gap)

        start_y = (HEIGHT // 2) - (total_h // 2)
        center_x = self.overlay_w // 2

        # Stocke pour render
        self._title_surf = title_surf
        self._title_pos = (center_x - title_surf.get_width() // 2, start_y)

        # Place boutons
        y = start_y + title_h + title_gap
        for label, cb in actions:
            rect = pygame.Rect(
                center_x - btn_w // 2,
                y,
                btn_w,
                btn_h
            )
            self._buttons.append(self._SpriteButton(label, rect, self.btn_font, cb))
            y += btn_h + gap

    def enter(self):
        """Rafraîchit la détection de sauvegarde quand on revient au menu."""
        from Game.gameplay.phase1 import Phase1
        new_has_save = Phase1.save_exists()
        if new_has_save != self.has_save:
            self.has_save = new_has_save
            self._rebuild_layout()

    def handle_input(self, events):
        for b in self._buttons:
            b.handle(events)

    def render(self, screen):
        # 1) fond
        screen.blit(self.bg, (0, 0))

        # 2) overlay gauche 40%
        screen.blit(self.overlay_surf, (0, 0))

        # 3) titre centré dans l'overlay
        screen.blit(self._title_surf, self._title_pos)

        # 4) boutons sprite (centrés dans l'overlay)
        for b in self._buttons:
            sprite = self._get_scaled_sprite(b.rect.width, b.rect.height, b.hovered)
            screen.blit(
                sprite,
                (b.rect.centerx - sprite.get_width() // 2, b.rect.centery - sprite.get_height() // 2),
            )

            # plus d'overlay au survol : sprite only
            if b.pressed:
                ov = pygame.Surface(b.rect.size, pygame.SRCALPHA)
                ov.fill((0, 0, 0, 35))
                screen.blit(ov, b.rect.topleft)

            # texte centré
            txt = b.font.render(b.text, True, (245, 245, 245))
            screen.blit(txt, (b.rect.centerx - txt.get_width() // 2, b.rect.centery - txt.get_height() // 2))

    


class CreditMenu(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="Crédits")

        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        title_size  = clamp(int(HEIGHT * 0.085), 34, 84)
        credit_size = clamp(int(HEIGHT * 0.032), 16, 34)
        btn_size    = clamp(int(HEIGHT * 0.040), 18, 44)

        self.title_font  = app.assets.get_font("MightySouly", title_size)
        self.credit_font = app.assets.get_font("MightySouly", credit_size)
        self.btn_font    = app.assets.get_font("MightySouly", btn_size)

        self.lines = [
            "Jeu créé par :",
            "• Romain Trohel",
            "• Paul Juillet",
            "• Timéo Barré--Golvet",
            "",
            "Commencé le 02/10/2025 et terminé le ...",
        ]

        ghost = ButtonStyle(draw_background=False, font=self.btn_font, text_color=(230,230,230), hover_zoom=1.08)
        self.btn_back = Button("← Retour", (WIDTH//2, HEIGHT//2), anchor="center", style=ghost,
                               on_click=lambda b: self.app.change_state("MENU"))
        self.add(self.btn_back)

        self._compute_layout()

    def _compute_layout(self):
        def clamp(v, a, b):
            return a if v < a else b if v > b else v

        x = WIDTH // 2
        color = (230, 230, 230)

        self._title_surf = self.title_font.render(self.title, True, color)

        self._text_surfs = [self.credit_font.render(line, True, color) for line in self.lines]
        line_gap = clamp(int(HEIGHT * 0.012), 4, 16)
        title_gap = clamp(int(HEIGHT * 0.035), 10, 40)
        back_gap = clamp(int(HEIGHT * 0.050), 14, 60)

        text_h = sum(s.get_height() for s in self._text_surfs) + (len(self._text_surfs) - 1) * line_gap
        total_h = self._title_surf.get_height() + title_gap + text_h + back_gap + self.btn_back.rect.height

        top_y = HEIGHT // 2 - total_h // 2

        self._title_pos = (x - self._title_surf.get_width() // 2, top_y)

        # positions des lignes centrées
        y = top_y + self._title_surf.get_height() + title_gap
        self._lines_pos = []
        for s in self._text_surfs:
            self._lines_pos.append((x - s.get_width() // 2, y))
            y += s.get_height() + line_gap

        # bouton retour bien sous le texte
        y += back_gap
        self.btn_back.move_to((x, y + self.btn_back.rect.height // 2))

    def handle_input(self, events):
        super().handle_input(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))

        screen.blit(self._title_surf, self._title_pos)
        for s, pos in zip(self._text_surfs, self._lines_pos):
            screen.blit(s, pos)

        for w in self.widgets:
            w.draw(screen)



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

        # Sprite de bouton (default + hover) sans trim pour préserver les marges transparentes
        self._btn_sprite_default = _trim_sprite(app.assets.get_image("btn_menu_default").convert_alpha())
        try:
            self._btn_sprite_hover = _trim_sprite(app.assets.get_image("btn_menu_hover").convert_alpha())
        except Exception:
            self._btn_sprite_hover = self._btn_sprite_default
        self._sprite_cache: dict[tuple[int, int, bool], pygame.Surface] = {}

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

    def _get_scaled_sprite(self, w: int, h: int, hovered: bool) -> pygame.Surface:
        key = (max(1, w), max(1, h), hovered)
        if key not in self._sprite_cache:
            src = self._btn_sprite_hover if hovered else self._btn_sprite_default
            sw, sh = src.get_size()
            scale = min(w / max(1, sw), h / max(1, sh))
            nw = max(1, int(sw * scale))
            nh = max(1, int(sh * scale))
            self._sprite_cache[key] = pygame.transform.smoothscale(src, (nw, nh))
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

        self.title_font = self.app.assets.get_font("KiwiSoda", title_size)
        self.small_font = self.app.assets.get_font("KiwiSoda", label_size)
        self.value_font = self.app.assets.get_font("KiwiSoda", value_size)

        # Dimensions cibles (on rescale si ça dépasse)
        top_pad = int(H * 0.04)
        gap1 = int(H * 0.025)
        gap2 = int(H * 0.04)
        gap3 = int(H * 0.03)
        bottom_pad = int(H * 0.05)

        input_h = int(H * 0.10)
        input_w = int(left_w * 0.50)

        btn_h = int(H * 0.12)
        row_gap = max(2, int(H * 0.012))

        nav_h = int(H * 0.12)

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
        sprite = self._get_scaled_sprite(rect.width, rect.height, hovered)
        screen.blit(
            sprite,
            (rect.centerx - sprite.get_width() // 2, rect.centery - sprite.get_height() // 2),
        )

        # Plus d'overlay au survol : sprite only
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
    LEFT_BG = (32, 44, 48)
    RIGHT_BG = (8, 8, 12)
    PANEL_LINE = (75, 84, 96)
    CARD_BG = (46, 58, 68)
    CARD_BG_HOVER = (56, 70, 82)
    CARD_BG_DISABLED = (32, 38, 46)
    ACCENT = (80, 160, 200)
    TEXT = (232, 232, 232)
    MUT_GAIN = (80, 200, 140)
    MUT_COST = (220, 110, 110)
    INPUT_BG = (235, 235, 235)
    INPUT_FG = (25, 25, 25)
    INPUT_PLACEHOLDER = (120, 120, 120)

    def __init__(self, app):
        super().__init__(app, title="Creation d'espece")

        self.base_points = 10
        self.active_tab = 0
        self.error_msg = ""

        # --- inputs (nom + couleur) ---
        prev = getattr(app, "species_creation", {}) if isinstance(getattr(app, "species_creation", None), dict) else {}
        self.species_name = str(prev.get("name", "") or "")
        self.name_active = False
        self._cursor_t = 0.0
        self._cursor_on = True

        self.color_options = [
            {"id": "bleu", "label": "Bleu royal", "swatch": (70, 130, 220)},
            {"id": "cyan", "label": "Cyan", "swatch": (60, 200, 220)},
            {"id": "saphir", "label": "Saphir", "swatch": (60, 110, 200)},
            {"id": "marine", "label": "Marine", "swatch": (50, 90, 160)},
        ]
        self.selected_color = prev.get("color", "bleu") or "bleu"
        if self.selected_color not in {c["id"] for c in self.color_options}:
            self.selected_color = self.color_options[0]["id"]

        # --- mutations (base) ---
        mutations_path = os.path.join("Game", "data", "mutations.json")
        try:
            with open(mutations_path, "r", encoding="utf-8") as f:
                all_mutations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[SpeciesCreationMenu] Impossible de charger mutations.json : {e}")
            all_mutations = {}

        self.base_mutations = {
            mid: data for mid, data in all_mutations.items()
            if data.get("base", False)
        }
        self._mutation_list = sorted(
            list(self.base_mutations.items()),
            key=lambda kv: str(kv[1].get("nom", kv[0]))
        )

        default_sel = []
        if isinstance(prev.get("mutations"), list):
            default_sel = list(prev.get("mutations"))
        elif hasattr(app, "selected_base_mutations"):
            default_sel = list(app.selected_base_mutations or [])
        else:
            default_sel = app.settings.get("species.base_mutations", []) or []

        self.selected_ids: set[str] = {
            mid for mid in default_sel if mid in self.base_mutations
        }

        # --- stats (sliders) ---
        base_ref = Espece("Base")
        self._base_stats = {
            "physique": dict(base_ref.base_physique),
            "sens": dict(base_ref.base_sens),
            "mental": dict(base_ref.base_mental),
            "environnement": dict(base_ref.base_environnement),
            "social": dict(base_ref.base_social),
            "genetique": dict(base_ref.genetique),
        }

        self.stat_defs = [
            ("physique", "force", "Force"),
            ("physique", "endurance", "Endurance"),
            ("physique", "vitesse", "Vitesse"),
            ("physique", "taille", "Taille"),
            ("physique", "stockage_energetique", "Stockage energie"),
            ("sens", "vision", "Vision"),
            ("sens", "ouie", "Ouie"),
            ("sens", "odorat", "Odorat"),
            ("mental", "intelligence", "Intelligence"),
            ("mental", "dexterite", "Dexterite"),
            ("mental", "agressivite", "Agressivite"),
            ("mental", "sociabilite", "Sociabilite"),
            ("social", "cohesion", "Cohesion"),
            ("environnement", "adaptabilite", "Adaptabilite"),
        ]

        prev_stats = prev.get("stats", {}) if isinstance(prev.get("stats"), dict) else {}
        self.stat_deltas = {}
        self.stat_limits = {}
        for cat, key, _label in self.stat_defs:
            base_val = int(self._base_stats.get(cat, {}).get(key, 0) or 0)
            min_delta = -min(5, base_val)
            max_delta = 5
            self.stat_limits[(cat, key)] = (min_delta, max_delta)
            delta = int(prev_stats.get(cat, {}).get(key, 0) or 0)
            self.stat_deltas[(cat, key)] = max(min_delta, min(max_delta, delta))

        # --- UI runtime ---
        self._layout = {}
        self._last_size = None
        self._stat_items = []
        self._stat_layout_key = None
        self._tab_rects = []
        self._name_rect = None
        self._color_rects = []
        self._mutation_cards = []
        self._tab_labels = ["Identite", "Stats", "Mutations"]

        # preview (animation)
        self._preview_espece = None
        self._preview_renderer = None
        self._refresh_preview()

        # buttons (created on layout)
        self.btn_back = None
        self.btn_start = None
        self._btn_layout_key = None

    # ----------------- helpers -----------------
    def _clamp(self, v, a, b):
        return a if v < a else b if v > b else v

    def _mutation_points_value(self, mutation_id: str) -> int:
        data = self.base_mutations.get(mutation_id, {})
        try:
            return int(data.get("points", 0) or 0)
        except Exception:
            return 0

    def _mutation_points_total(self) -> int:
        return sum(self._mutation_points_value(mid) for mid in self.selected_ids)

    def _stat_spent_points(self) -> int:
        return int(sum(self.stat_deltas.values()))

    def _points_remaining(self) -> int:
        return int(self.base_points - self._stat_spent_points() + self._mutation_points_total())

    def _set_stat_delta(self, key, new_val):
        old = int(self.stat_deltas.get(key, 0))
        if new_val == old:
            return
        min_delta, max_delta = self.stat_limits.get(key, (-5, 5))
        new_val = max(min_delta, min(max_delta, int(new_val)))

        diff = new_val - old
        if diff > 0:
            remaining = self._points_remaining()
            if remaining - diff < 0:
                new_val = old + max(0, remaining)
                diff = new_val - old
        self.stat_deltas[key] = new_val
        if self._points_remaining() >= 0 and self.error_msg.startswith("Points"):
            self.error_msg = ""

    def _get_incompatibles(self, data: dict) -> set:
        inc1 = set(data.get("incompatibles", []) or [])
        inc2 = set(data.get("imcompatibles", []) or [])
        return inc1 | inc2

    def _toggle_mutation(self, mutation_id: str):
        if mutation_id in self.selected_ids:
            self.selected_ids.discard(mutation_id)
            self.error_msg = ""
            self._refresh_preview()
            return

        data = self.base_mutations.get(mutation_id, {})
        incompat_ids = self._get_incompatibles(data)
        conflict = incompat_ids & self.selected_ids
        if conflict:
            noms = [
                self.base_mutations[c]["nom"] if c in self.base_mutations else c
                for c in conflict
            ]
            self.error_msg = "Incompatible avec : " + ", ".join(noms)
            return

        pts = self._mutation_points_value(mutation_id)
        if self._points_remaining() + pts < 0:
            self.error_msg = "Points insuffisants pour cette mutation."
            return

        self.selected_ids.add(mutation_id)
        self.error_msg = ""
        self._refresh_preview()

    def _refresh_preview(self):
        self._preview_espece = Espece(self.species_name.strip() or "Espece")
        try:
            self._preview_espece.mutations.apply_base_mutations(
                list(self.selected_ids),
                apply_to_species=True,
                apply_to_individus=False,
            )
        except Exception:
            pass
        self._preview_renderer = EspeceRenderer(self._preview_espece, self.app.assets)

    # ----------------- layout -----------------
    def _build_stat_sliders(self, content_rect, slider_w, font):
        self._stat_items = []
        for cat, key, label in self.stat_defs:
            min_delta, max_delta = self.stat_limits.get((cat, key), (-5, 5))

            def make_get(k):
                return lambda k=k: float(self.stat_deltas.get(k, 0))

            def make_set(k):
                def setter(v, k=k):
                    self._set_stat_delta(k, int(round(v)))
                return setter

            slider = Slider(
                label,
                (0, 0),
                width=slider_w,
                get_value=make_get((cat, key)),
                set_value=make_set((cat, key)),
                font=font,
                min_v=min_delta,
                max_v=max_delta,
                step=1,
            )
            self._stat_items.append({
                "cat": cat,
                "key": key,
                "label": label,
                "slider": slider,
            })

    def _compute_layout(self, screen):
        W, H = screen.get_size()
        if self._last_size == (W, H):
            return
        self._last_size = (W, H)

        left_w = int(W * 0.60)
        right_w = W - left_w

        margin = self._clamp(int(W * 0.04), 12, max(12, int(left_w * 0.14)))
        top_pad = self._clamp(int(H * 0.04), 10, 40)
        tabs_h = self._clamp(int(H * 0.065), 34, 72)
        tabs_gap = self._clamp(int(W * 0.012), 6, 18)
        content_gap = self._clamp(int(H * 0.02), 8, 30)
        bottom_pad = self._clamp(int(H * 0.05), 14, 60)
        buttons_h = self._clamp(int(H * 0.085), 42, 90)
        buttons_gap = self._clamp(int(W * 0.02), 12, 36)

        content_top = top_pad + tabs_h + content_gap
        buttons_y = H - bottom_pad - buttons_h
        content_rect = pygame.Rect(
            margin,
            content_top,
            left_w - 2 * margin,
            max(20, buttons_y - content_top - content_gap),
        )

        # fonts
        tab_size = self._clamp(int(H * 0.028), 14, 28)
        label_size = self._clamp(int(H * 0.024), 12, 24)
        small_size = self._clamp(int(H * 0.021), 11, 22)
        points_size = self._clamp(int(H * 0.040), 18, 40)
        btn_size = self._clamp(int(H * 0.032), 16, 32)

        self.tab_font = self.app.assets.get_font("MightySouly", tab_size)
        self.label_font = self.app.assets.get_font("MightySouly", label_size)
        self.small_font = self.app.assets.get_font("MightySouly", small_size)
        self.points_font = self.app.assets.get_font("MightySouly", points_size)
        self.btn_font = self.app.assets.get_font("MightySouly", btn_size)

        # tabs
        tab_w = int((content_rect.width - 2 * tabs_gap) / 3)
        self._tab_rects = []
        for i in range(3):
            rx = margin + i * (tab_w + tabs_gap)
            self._tab_rects.append(pygame.Rect(rx, top_pad, tab_w, tabs_h))

        # name input + colors (tab 1)
        input_h = self._clamp(int(content_rect.height * 0.14), 36, 64)
        input_w = int(content_rect.width * 0.70)
        self._name_rect = pygame.Rect(
            content_rect.x,
            content_rect.y + self._clamp(int(content_rect.height * 0.06), 6, 20),
            input_w,
            input_h,
        )

        swatch = self._clamp(int(H * 0.05), 28, 48)
        sw_gap = self._clamp(int(W * 0.01), 8, 16)
        colors_y = self._name_rect.bottom + self._clamp(int(content_rect.height * 0.08), 12, 30)
        self._color_rects = []
        cur_x = content_rect.x
        for opt in self.color_options:
            rect = pygame.Rect(cur_x, colors_y, swatch, swatch)
            self._color_rects.append((rect, opt))
            cur_x += swatch + sw_gap

        # stats (tab 2)
        stats_cols = 2 if len(self.stat_defs) > 8 else 1
        col_gap = self._clamp(int(content_rect.width * 0.06), 12, 32)
        col_w = int((content_rect.width - col_gap * (stats_cols - 1)) / stats_cols)
        slider_w = int(col_w * 0.86)

        stat_layout_key = (stats_cols, slider_w, label_size)
        if self._stat_layout_key != stat_layout_key:
            self._build_stat_sliders(content_rect, slider_w, self.label_font)
            self._stat_layout_key = stat_layout_key

        rows = int(math.ceil(len(self._stat_items) / max(1, stats_cols)))
        label_h = self.label_font.render("X", True, (0, 0, 0)).get_height()
        knob_r = 10
        block_h = 36 + label_h + 2 * knob_r + 14
        row_gap = self._clamp(int(content_rect.height * 0.02), 6, 20)
        row_h = max(block_h, int((content_rect.height - row_gap * max(0, rows - 1)) / max(1, rows)))

        for idx, item in enumerate(self._stat_items):
            col = idx // rows
            row = idx % rows
            cx = content_rect.x + col * (col_w + col_gap) + col_w / 2
            row_y = content_rect.y + row * (row_h + row_gap)
            bar_center_y = row_y + 36 + label_h + 8 + knob_r
            slider = item["slider"]
            slider.width = slider_w
            slider.pos = (int(cx), int(bar_center_y))
            slider._rebuild_rects()

        # mutations (tab 3)
        mut_cols = 2 if content_rect.width > 420 else 1
        mut_gap = self._clamp(int(H * 0.015), 8, 20)
        mut_rows = int(math.ceil(len(self._mutation_list) / max(1, mut_cols)))
        mut_w = int((content_rect.width - mut_gap * (mut_cols - 1)) / mut_cols) if mut_cols > 0 else content_rect.width
        mut_h = int((content_rect.height - mut_gap * max(0, mut_rows - 1)) / max(1, mut_rows)) if mut_rows > 0 else 40
        mut_h = max(46, min(mut_h, 96))

        self._mutation_cards = []
        for i, (mid, _data) in enumerate(self._mutation_list):
            col = i % mut_cols
            row = i // mut_cols
            x = content_rect.x + col * (mut_w + mut_gap)
            y = content_rect.y + row * (mut_h + mut_gap)
            self._mutation_cards.append({"id": mid, "rect": pygame.Rect(x, y, mut_w, mut_h)})

        # buttons (right panel, under preview)
        right_margin = self._clamp(int(W * 0.03), 10, max(10, int(right_w * 0.18)))
        raw_btn_w = int((right_w - 2 * right_margin - buttons_gap) / 2)
        stacked = raw_btn_w < 90
        btn_w = max(100, right_w - 2 * right_margin) if stacked else max(90, raw_btn_w)
        btn_layout_key = (btn_w, buttons_h, btn_size, stacked)
        if self._btn_layout_key != btn_layout_key:
            primary = ButtonStyle(
                draw_background=True,
                bg_color=(60, 90, 120),
                hover_bg_color=(80, 120, 160),
                active_bg_color=(60, 140, 210),
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
                hover_zoom=1.06,
                zoom_speed=0.22,
            )
            ghost = ButtonStyle(
                draw_background=False,
                font=self.btn_font,
                text_color=(230, 230, 230),
                hover_zoom=1.06,
                zoom_speed=0.22,
            )
            if stacked:
                back_pos = (left_w + right_margin + btn_w // 2, buttons_y - buttons_h - buttons_gap + buttons_h // 2)
                start_pos = (left_w + right_margin + btn_w // 2, buttons_y + buttons_h // 2)
            else:
                back_pos = (left_w + right_margin + btn_w // 2, buttons_y + buttons_h // 2)
                start_pos = (left_w + right_margin + btn_w + buttons_gap + btn_w // 2, buttons_y + buttons_h // 2)

            self.btn_back = Button(
                "Retour",
                back_pos,
                size=(btn_w, buttons_h),
                anchor="center",
                style=ghost,
                on_click=lambda b: self.app.change_state("CREATION"),
            )
            self.btn_start = Button(
                "Lancer",
                start_pos,
                size=(btn_w, buttons_h),
                anchor="center",
                style=primary,
                on_click=lambda b: self._validate_and_start(),
            )
            self._btn_layout_key = btn_layout_key
        else:
            if stacked:
                back_pos = (left_w + right_margin + btn_w // 2, buttons_y - buttons_h - buttons_gap + buttons_h // 2)
                start_pos = (left_w + right_margin + btn_w // 2, buttons_y + buttons_h // 2)
            else:
                back_pos = (left_w + right_margin + btn_w // 2, buttons_y + buttons_h // 2)
                start_pos = (left_w + right_margin + btn_w + buttons_gap + btn_w // 2, buttons_y + buttons_h // 2)
            if self.btn_back:
                self.btn_back.move_to(back_pos)
            if self.btn_start:
                self.btn_start.move_to(start_pos)

        self._layout = {
            "W": W,
            "H": H,
            "left_w": left_w,
            "right_w": right_w,
            "content_rect": content_rect,
            "buttons_y": buttons_y,
        }

    # ----------------- input/update -----------------
    def update(self, dt):
        self._cursor_t += dt
        if self._cursor_t >= 0.45:
            self._cursor_t = 0.0
            self._cursor_on = not self._cursor_on

    def handle_input(self, events):
        screen = self.app.screen if hasattr(self.app, "screen") else None
        if screen:
            self._compute_layout(screen)

        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

        # tabs and clicks
        for e in events:
            if e.type != pygame.MOUSEBUTTONDOWN or e.button != 1:
                continue
            mx, my = e.pos

            # tabs
            for i, rect in enumerate(self._tab_rects):
                if rect.collidepoint(mx, my):
                    self.active_tab = i
                    self.name_active = False
                    return

            # tab 1: name + colors
            if self.active_tab == 0:
                if self._name_rect and self._name_rect.collidepoint(mx, my):
                    self.name_active = True
                else:
                    self.name_active = False
                for rect, opt in self._color_rects:
                    if rect.collidepoint(mx, my):
                        self.selected_color = opt["id"]

            # tab 3: mutations
            if self.active_tab == 2:
                for card in self._mutation_cards:
                    if card["rect"].collidepoint(mx, my):
                        self._toggle_mutation(card["id"])
                        break

        # keyboard input (name)
        for e in events:
            if e.type == pygame.KEYDOWN and self.name_active:
                if e.key == pygame.K_RETURN:
                    self.name_active = False
                elif e.key == pygame.K_BACKSPACE:
                    self.species_name = self.species_name[:-1]
                else:
                    if e.unicode and e.unicode.isprintable() and len(self.species_name) < 24:
                        self.species_name += e.unicode

        # sliders
        if self.active_tab == 1:
            for item in self._stat_items:
                item["slider"].handle(events)

        # buttons
        if self.btn_back:
            self.btn_back.handle(events)
        if self.btn_start:
            self.btn_start.handle(events)

    # ----------------- validation -----------------
    def _validate_and_start(self):
        if self._points_remaining() < 0:
            self.error_msg = "Points insuffisants."
            return

        # store in app
        stats_out = {}
        for (cat, key), delta in self.stat_deltas.items():
            if int(delta) == 0:
                continue
            stats_out.setdefault(cat, {})[key] = int(delta)

        color_rgb = None
        for opt in self.color_options:
            if opt["id"] == self.selected_color:
                color_rgb = opt["swatch"]
                break

        self.app.selected_base_mutations = list(self.selected_ids)
        self.app.species_creation = {
            "name": self.species_name.strip() or "Espece sans nom",
            "color": self.selected_color,
            "color_rgb": color_rgb or (70, 130, 220),
            "stats": stats_out,
            "mutations": list(self.selected_ids),
        }

        try:
            self.app.settings.set("species.base_mutations", list(self.selected_ids))
        except Exception:
            pass

        preset_name = "Custom"
        seed = None
        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
            seed = presets.get("presets", {}).get(preset_name, {}).get("seed")
        except Exception:
            seed = None

        self.app.change_state("LOADING", preset=preset_name, seed=seed)

    # ----------------- rendering -----------------
    def _draw_tabs(self, screen):
        for i, rect in enumerate(self._tab_rects):
            active = i == self.active_tab
            bg = self.ACCENT if active else (38, 48, 58)
            border = (20, 24, 30)
            pygame.draw.rect(screen, bg, rect, border_radius=12)
            pygame.draw.rect(screen, border, rect, width=2, border_radius=12)
            label = self._tab_labels[i]
            txt = self.tab_font.render(label, True, (250, 250, 250))
            screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

    def _draw_identity_tab(self, screen):
        # label
        label = self.label_font.render("Nom de l'espece", True, self.TEXT)
        screen.blit(label, (self._name_rect.x, self._name_rect.y - label.get_height() - 6))

        # input
        pygame.draw.rect(screen, self.INPUT_BG, self._name_rect, border_radius=10)
        border = (255, 255, 255) if self.name_active else (210, 210, 210)
        pygame.draw.rect(screen, border, self._name_rect, 2, border_radius=10)

        if self.species_name:
            txt = self.label_font.render(self.species_name, True, self.INPUT_FG)
            screen.blit(txt, (self._name_rect.x + 12, self._name_rect.centery - txt.get_height() // 2))
        else:
            ph = self.label_font.render("Entrez un nom...", True, self.INPUT_PLACEHOLDER)
            screen.blit(ph, (self._name_rect.x + 12, self._name_rect.centery - ph.get_height() // 2))

        if self.name_active and self._cursor_on:
            base_x = self._name_rect.x + 12
            if self.species_name:
                tmp = self.label_font.render(self.species_name, True, self.INPUT_FG)
                base_x += tmp.get_width() + 2
            cy = self._name_rect.centery
            pygame.draw.line(screen, (30, 30, 30), (base_x, cy - self._name_rect.height // 4), (base_x, cy + self._name_rect.height // 4), 2)

        # colors
        color_label_y = self._name_rect.bottom + 12
        cl = self.label_font.render("Couleur (sprite bleu pour toutes)", True, self.TEXT)
        screen.blit(cl, (self._name_rect.x, color_label_y))

        for rect, opt in self._color_rects:
            pygame.draw.rect(screen, opt["swatch"], rect, border_radius=8)
            is_selected = opt["id"] == self.selected_color
            border_col = self.ACCENT if is_selected else (20, 24, 30)
            pygame.draw.rect(screen, border_col, rect, width=3 if is_selected else 2, border_radius=8)
            if is_selected:
                pygame.draw.rect(screen, (255, 255, 255), rect.inflate(-6, -6), width=1, border_radius=6)

            label = self.small_font.render(opt["label"], True, self.TEXT)
            screen.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 6))

    def _draw_stats_tab(self, screen):
        for item in self._stat_items:
            slider = item["slider"]
            slider.draw(screen)
            cat = item["cat"]
            key = item["key"]
            base_val = int(self._base_stats.get(cat, {}).get(key, 0) or 0)
            delta = int(self.stat_deltas.get((cat, key), 0))
            total = base_val + delta
            sign = f"{delta:+d}"
            val_txt = self.small_font.render(f"{total} ({sign})", True, self.TEXT)
            screen.blit(val_txt, (slider.bar_rect.right + 8, slider.bar_rect.centery - val_txt.get_height() // 2))

    def _draw_mutations_tab(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        for card in self._mutation_cards:
            mid = card["id"]
            rect = card["rect"]
            data = self.base_mutations.get(mid, {})
            name = data.get("nom", mid)
            pts = self._mutation_points_value(mid)
            selected = mid in self.selected_ids

            incompat = self._get_incompatibles(data)
            blocked = bool(incompat & self.selected_ids) and not selected

            bg = self.CARD_BG_DISABLED if blocked else (self.CARD_BG_HOVER if rect.collidepoint(mouse_pos) else self.CARD_BG)
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            border_col = self.ACCENT if selected else (20, 24, 30)
            pygame.draw.rect(screen, border_col, rect, width=2, border_radius=10)

            name_surf = self.small_font.render(str(name), True, self.TEXT)
            screen.blit(name_surf, (rect.x + 12, rect.y + 10))

            pts_color = self.MUT_GAIN if pts > 0 else self.MUT_COST if pts < 0 else (200, 200, 200)
            pts_surf = self.small_font.render(f"{pts:+d} pts", True, pts_color)
            screen.blit(pts_surf, (rect.right - pts_surf.get_width() - 12, rect.y + 10))

            if blocked:
                lock = self.small_font.render("Incompatible", True, (200, 120, 120))
                screen.blit(lock, (rect.x + 12, rect.bottom - lock.get_height() - 8))

    def _draw_preview(self, screen, rect):
        pygame.draw.rect(screen, self.RIGHT_BG, rect)

        # subtle vignette
        vignette = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 100), vignette.get_rect(), border_radius=24)
        screen.blit(vignette, rect.topleft)

        # points
        remaining = self._points_remaining()
        pts_color = self.ACCENT if remaining >= 0 else (220, 120, 120)
        pts_txt = self.points_font.render(f"Points restants : {remaining}", True, pts_color)
        screen.blit(pts_txt, (rect.centerx - pts_txt.get_width() // 2, rect.y + 24))

        # sprite preview
        if self._preview_renderer:
            try:
                sprite, _ax, _ay = self._preview_renderer._compose()
                sw, sh = sprite.get_size()
                target_h = rect.height * 0.45
                scale = target_h / max(1, sh)
                scale = max(0.2, min(scale, 4.0))
                new_w, new_h = int(sw * scale), int(sh * scale)
                sprite = pygame.transform.smoothscale(sprite, (new_w, new_h))
                px = rect.centerx - new_w // 2
                py = rect.centery - new_h // 2 + int(rect.height * 0.08)
                screen.blit(sprite, (px, py))
            except Exception:
                pass

    def render(self, screen):
        self._compute_layout(screen)
        W, H = self._layout["W"], self._layout["H"]
        left_w = self._layout["left_w"]

        # background split
        pygame.draw.rect(screen, self.LEFT_BG, pygame.Rect(0, 0, left_w, H))
        pygame.draw.rect(screen, self.RIGHT_BG, pygame.Rect(left_w, 0, W - left_w, H))
        pygame.draw.line(screen, self.PANEL_LINE, (left_w, 0), (left_w, H), 2)

        # tabs
        self._draw_tabs(screen)

        # content
        if self.active_tab == 0:
            self._draw_identity_tab(screen)
        elif self.active_tab == 1:
            self._draw_stats_tab(screen)
        else:
            self._draw_mutations_tab(screen)

        # preview right
        right_rect = pygame.Rect(left_w, 0, W - left_w, H)
        self._draw_preview(screen, right_rect)

        # buttons (on top of preview, under animation)
        if self.btn_back:
            self.btn_back.draw(screen)
        if self.btn_start:
            self.btn_start.draw(screen)

        # error/info
        if self.error_msg:
            err = self.small_font.render(self.error_msg, True, (230, 120, 120))
            screen.blit(err, (self._layout["content_rect"].x, self._layout["buttons_y"] - err.get_height() - 6))
