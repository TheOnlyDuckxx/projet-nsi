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
    def __init__(self, app):
        super().__init__(app, title="Paramètres du monde")

        self.font = app.assets.get_font("MightySouly", 22)
        self.btn_font = app.assets.get_font("MightySouly", 28)

        # --- Charger les paramètres custom existants ---
        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
                self.params = presets.get("presets", {}).get("Custom", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.params = {}

        # --- Layout panneau gauche ---
        margin = 40
        panel_width = WIDTH // 2 - 2 * margin
        panel_height = HEIGHT - 220
        panel_x = margin
        panel_y = 170
        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

        # --- Globe à droite ---
        self.globe_radius = min(WIDTH, HEIGHT) // 4
        self.globe_center = (int(WIDTH * 0.66), HEIGHT // 2 + 20)

        self.N_POINTS = 40000
        self.N_HOTSPOTS = 50
        self.SPREAD_MIN = 0.03
        self.SPREAD_MAX = 0.12
        self.ROT = 0.01  # rotation rad/frame

        self._generate_hotspot_globe()

        # --- Nom du monde (champ texte simple) ---
        self.world_name = self.params.get("world_name", "Monde sans nom")
        self.name_active = False
        self.name_rect = pygame.Rect(
            self.panel_rect.x + 30,
            self.panel_rect.y + 40,
            self.panel_rect.width - 60,
            36
        )

        # --- Définition des 12 paramètres ---
        # key = clé dans le JSON, label = texte affiché, options = valeurs possibles
        self.param_defs = [
            ("world_size", "Taille du monde",
             ["Petite planète", "Moyenne", "Grande", "Gigantesque"]),

            ("water_coverage", "Pourcentage d'eau",
             ["Aride", "Tempéré", "Océanique"]),

            ("temperature", "Température moyenne",
             ["Glaciaire", "Froid", "Tempéré", "Chaud", "Ardent"]),

            ("atmosphere_density", "Densité atmosphérique",
             ["Faible", "Normale", "Épaisse"]),

            ("resource_density", "Densité de ressources",
             ["Pauvre", "Moyenne", "Riche", "Instable"]),

            ("biodiversity", "Biodiversité initiale",
             ["Faible", "Moyenne", "Élevée", "Extrême"]),

            ("tectonic_activity", "Activité tectonique",
             ["Stable", "Moyenne", "Instable", "Chaotique"]),

            ("weather", "Conditions météorologiques",
             ["Calme", "Variable", "Extrême"]),

            ("gravity", "Gravité",
             ["Faible", "Moyenne", "Forte"]),

            ("cosmic_radiation", "Radiation cosmique",
             ["Faible", "Moyenne", "Forte"]),

            ("mystic_influence", "Influence mystique",
             ["Nulle", "Faible", "Moyenne", "Forte"]),

            ("dimensional_stability", "Stabilité dimensionnelle",
             ["Stable", "Fissuré", "Instable"]),
        ]

        self.option_widgets: dict[str, OptionSelector] = {}
        self._build_param_widgets()

        # --- Styles de boutons (même look que le menu principal) ---
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
            hover_zoom=1.10,
            zoom_speed=0.22,
        )
        ghost = ButtonStyle(
            draw_background=False,
            font=self.btn_font,
            text_color=(0, 0, 0),
            hover_zoom=1.08,
            zoom_speed=0.22,
        )

        y_buttons = self.panel_rect.bottom - 50

        # BOUTON RETOUR (à gauche)
        self.btn_back = self.add(Button(
            "Retour",
            (self.panel_rect.x + 60, y_buttons),
            anchor="midleft",
            style=ghost,
            on_click=lambda b: self.app.change_state("MENU"),
        ))

        # BOUTON LANCER (à droite)
        self.btn_next = self.add(Button(
            "Suivant",
            (self.panel_rect.right - 60, y_buttons),
            anchor="midright",
            style=primary,
            on_click=lambda b: self._go_to_species_creation(),
        ))

    # ---------- Création des 12 sélecteurs ----------
    def _build_param_widgets(self):
        col_width = self.panel_rect.width // 2 - 40
        start_y = self.name_rect.bottom + 40
        gap_y = 100

        for idx, (key, label, options) in enumerate(self.param_defs):
            if idx < 6:
                col_x = self.panel_rect.x + 30
                row = idx
            else:
                col_x = self.panel_rect.x + 30 + self.panel_rect.width // 2
                row = idx - 6

            y = start_y + row * gap_y
            rect = (col_x, y, col_width, 44)

            # valeur par défaut = milieu de la liste
            if len(options) % 2 == 1:
                default_idx = len(options) // 2
            else:
                default_idx = max(0, len(options) // 2 - 1)
            default_value = options[default_idx]

            current_value = self.params.get(key, default_value)
            if current_value not in options:
                current_value = default_value
            start_index = options.index(current_value)

            widget = self.add(OptionSelector(
                rect=rect,
                label=label,
                options=options,
                start_index=start_index,
                font=self.font
            ))
            self.option_widgets[key] = widget

    def _set(self, key, value):
        self.params[key] = value

    # ---------- Input (widgets + champ texte + ESC) ----------
    def handle_input(self, events):
        super().handle_input(events)

        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.name_active = self.name_rect.collidepoint(e.pos)

            if e.type == pygame.KEYDOWN and self.name_active:
                if e.key == pygame.K_RETURN:
                    self.name_active = False
                elif e.key == pygame.K_BACKSPACE:
                    self.world_name = self.world_name[:-1]
                else:
                    # texte simple, on limite la longueur
                    if e.unicode and e.unicode.isprintable() and len(self.world_name) < 24:
                        self.world_name += e.unicode
    
    def _generate_hotspot_globe(self):
        self.hotspots = []
        for _ in range(self.N_HOTSPOTS):
            lat = random.uniform(-math.pi/2, math.pi/2)
            lon = random.uniform(-math.pi, math.pi)
            spread = random.uniform(self.SPREAD_MIN, self.SPREAD_MAX)
            self.hotspots.append((lat, lon, spread))

        # points = liste [lat, lon]
        self.globe_points = []
        for _ in range(self.N_POINTS):
            h_lat, h_lon, spread = random.choice(self.hotspots)

            lat = h_lat + random.gauss(0, spread)
            lon = h_lon + random.gauss(0, spread)

            # normalisation longitude
            if lon > math.pi:
                lon -= 2 * math.pi
            if lon < -math.pi:
                lon += 2 * math.pi

            self.globe_points.append([lat, lon])

    # ---------- Animation globe ----------
    def update(self, dt):
        # rotation = temps réel * vitesse
        self.ROT = 0.4 * dt  # vitesse stable



    def _draw_globe(self, screen):
        R = self.globe_radius
        cx, cy = self.globe_center

        # Surface transparente pour éviter d'écraser le menu
        surf = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        for p in self.globe_points:
            lat, lon = p

            # rotation longitude
            lon += self.ROT
            if lon > math.pi:
                lon -= 2 * math.pi
            p[1] = lon

            # Projection 2D
            x = R + R * math.cos(lat) * math.cos(lon)
            y = R + R * math.sin(lat)

            # Dessin du pixel
            surf.set_at((int(x), int(y)), (255, 255, 255, 255))


        # Blit final
        screen.blit(surf, (cx - R, cy - R))


    # ---------- Render complet ----------
    def render(self, screen):
        # fond + overlay + titre (copié de BaseMenu.render)
        screen.fill((10, 10, 15))
        title_surf = self.title_font.render(self.title, True, (230, 230, 230))
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 100))

        # panneau de gauche
        panel_color = (235, 235, 238)
        border_color = (180, 180, 190)
        pygame.draw.rect(screen, panel_color, self.panel_rect, border_radius=24)
        pygame.draw.rect(screen, border_color, self.panel_rect, 2, border_radius=24)

        # nom du monde
        label_surf = self.font.render("Nom de votre monde", True, (40, 40, 40))
        screen.blit(label_surf, (self.name_rect.x, self.name_rect.y - 28))

        pygame.draw.rect(screen, (245, 245, 248), self.name_rect, border_radius=10)
        border = (80, 130, 220) if self.name_active else (190, 190, 200)
        pygame.draw.rect(screen, border, self.name_rect, 2, border_radius=10)

        display_name = self.world_name if self.world_name else "Sans nom"
        name_surf = self.font.render(display_name, True, (30, 30, 30))
        screen.blit(name_surf, (self.name_rect.x + 10, self.name_rect.y + 6))

        # widgets (sélecteurs + boutons)
        for w in self.widgets:
            w.draw(screen)
        for w in self.widgets:
            if hasattr(w, "draw_popup"):
                w.draw_popup(screen)

        # globe à droite
        self._draw_globe(screen)

    # ---------- Clic sur "Lancer la partie" ----------
    def _go_to_species_creation(self):
        # Sauvegarder les paramètres du monde avant de changer d'écran
        self._set("world_name", self.world_name.strip() or "Monde sans nom")
        for key, widget in self.option_widgets.items():
            self._set(key, widget.value())

        # Seed par défaut si néant
        if "seed" not in self.params:
            self.params["seed"] = "Aléatoire"

        # Écrire dans le JSON
        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
        except:
            presets = {}

        if "presets" not in presets:
            presets["presets"] = {}

        presets["presets"]["Custom"] = self.params

        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=4, ensure_ascii=False)

        # Aller vers le menu de création d'espèce
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
        center_x = WIDTH // 2
        start_y = 220
        gap_y = 45

        base_list = list(self.base_mutations.items())

        for i, (mutation_id, data) in enumerate(base_list):
            y = start_y + i * gap_y
            label = data.get("nom", mutation_id)

            def make_get(mid):
                return lambda mid=mid: mid in self.selected_ids

            def make_set(mid):
                def setter(value, mid=mid):
                    self._toggle_mutation(mid, value)
                return setter

            self.add(Toggle(
                label,
                (center_x, y),
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

        y_buttons = start_y + len(base_list) * gap_y + 60

        self.btn_reset = self.add(Button(
            "Réinitialiser",
            (center_x - 200, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self._reset_selection(),
        ))

        self.btn_validate = self.add(Button(
            "Valider",
            (center_x, y_buttons),
            anchor="center",
            style=primary,
            on_click=lambda b: self._validate_and_back(),
        ))

        self.btn_back = self.add(Button(
            "Retour",
            (center_x + 200, y_buttons),
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