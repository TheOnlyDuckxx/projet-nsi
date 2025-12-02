# MENU.PY
# Gère le menu principal


# --------------- IMPORTATION DES MODULES ---------------

import pygame
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import Button, ButtonStyle, Slider, Toggle, ValueSelector, OptionSelector
import json 
import os 
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
                (WIDTH // 2, y0 - 2*gap),
                anchor="center",
                style=resume_style,
                on_click=lambda b: self.app.change_state("PHASE1", load_save=True),
            ))
        self.btn_species = self.add(Button(
            "CRÉATION D'ESPÈCE",
            (WIDTH // 2, y0 - gap),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("SPECIES_CREATION"),
        ))

        # ---- Boutons normaux ----
        self.btn_monde = self.add(Button(
            "PARAMÈTRES DU MONDE",
            (WIDTH // 2, y0),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("CREATION"),
        ))


        self.btn_start = self.add(Button(
            "NOUVELLE PARTIE",
            (WIDTH // 2, y0 + gap),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("LOADING"),
        ))

        self.btn_options = self.add(Button(
            "OPTIONS",
            (WIDTH // 2, y0 + 2*gap),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("OPTIONS"),
        ))

        self.btn_credits = self.add(Button(
            "Crédits",
            (WIDTH // 2, y0 + 3*gap),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.change_state("CREDITS"),
        ))

        self.btn_quit = self.add(Button(
            "Quitter",
            (WIDTH // 2, y0 + 4*gap),
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

        # --- Polices cohérentes avec le reste des menus ---
        self.font = app.assets.get_font("MightySouly", 22)
        self.btn_font = app.assets.get_font("MightySouly", 28)

        # --- Etat local des paramètres (toujours à jour via les widgets) ---
        preset_path = os.path.join("Game", "data", "world_presets.json")
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
                self.params = presets.get("presets", {}).get("Custom", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.params = {}
            
        # --- Styles de boutons (même look que MainMenu) ---
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

        center_x = WIDTH // 2
        line_y  = 250
        gap_y   = 65
        width   = 540  # largeur visuelle des champs

        # Age (1000..4000 Ma), pas 500
        self.sel_age = self.add(ValueSelector(
            rect=(center_x - width // 2, line_y, width, 50),
            label="Âge du monde (Ma)",
            min_value=1000,
            max_value=4000,
            step=500,
            start_value=2000,
            font=self.font
        ))

        # Niveau des océans (-50..100 m), pas 10
        self.sel_ocean = self.add(ValueSelector(
            rect=(center_x - width // 2, line_y + gap_y, width, 50),
            label="Niveau des océans (m)",
            min_value=-50,
            max_value=100,
            step=10,
            start_value=self.params.get("Niveau des océans", 0),
            font=self.btn_font
        ))

        # Taille du monde (20000..60000 km), pas 5000
        self.sel_size = self.add(ValueSelector(
            rect=(center_x - width // 2, line_y + 2 * gap_y, width, 50),
            label="Taille du monde (km)",
            min_value=20000,
            max_value=60000,
            step=5000,
            start_value=self.params.get("Taille", 40000),
            font=self.btn_font
        ))

        # Climat (Aride / Tempéré / Tropical)
        self.sel_climate = self.add(OptionSelector(
            rect=(center_x - width // 2, line_y + 3 * gap_y, width, 50),
            label="Climat",
            options=["Aride", "Tempéré", "Tropical"],
            start_index=["Aride", "Tempéré", "Tropical"].index(self.params.get("Climat", "Tempéré")),
            font=self.btn_font
        ))

        # Ressources (Éparse / Normale / Abondante)
        self.sel_resources = self.add(OptionSelector(
            rect=(center_x - width // 2, line_y + 4 * gap_y, width, 50),
            label="Ressources",
            options=["Éparse", "Normale", "Abondante"],
            start_index=["Éparse", "Normale", "Abondante"].index(self.params.get("Ressources", "Normale")),
            font=self.btn_font
        ))

        # --- Boutons bas de page ---
        y_buttons = line_y + 4*gap_y + 90

        self.btn_start = self.add(Button(  
            "Lancer la partie",
            (center_x - 150, y_buttons),
            anchor="center",
            style=primary,
            on_click=lambda b: self._on_start_clicked(),
        ))

        self.btn_back = self.add(Button(
            "← Retour",
            (center_x + 150, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.change_state("MENU"),
        ))

    # Petitte utilité pour centraliser la MAJ du dict
    def _set(self, key, value):
        self.params[key] = value

    # Laisse BaseMenu propager aux widgets + ESC pour revenir
    def handle_input(self, events):
        super().handle_input(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.app.change_state("MENU")

    # Pas besoin de surcharger update: les widgets bindent déjà get/set
    def update(self, dt):
        pass

    # BaseMenu gère déjà fond + overlay + titre + draw des widgets
    def render(self, screen):
        super().render(screen)

    # Clique sur "Lancer la partie"
    def _on_start_clicked(self):
        """Met à jour le preset 'custom' dans le fichier JSON et lance la Phase 1."""
        # Chemin du fichier JSON des presets
        preset_path = os.path.join("Game", "data", "world_presets.json")
        self._set("age", self.sel_age.get_value())
        self._set("Niveau des océans", self.sel_ocean.get_value())
        self._set("Taille", self.sel_size.get_value())
        self._set("Ressources", self.sel_resources.value())
        self._set("Climat", self.sel_climate.value())
        
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            presets = {}

        # Ajout / mise à jour du preset personnalisé
        presets["presets"]["Custom"] = self.params

        # Sauvegarde dans le même fichier
        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=4, ensure_ascii=False)
            # Change d'état pour lancer la partie
        self.app.change_state("LOADING")


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
        x_buttons = center_x - 200
        if y_buttons > HEIGHT - 50:
             y_buttons = start_y + len(base_list) + 60 - gap_y
             x_buttons = center_x + 300
        else:
            y_buttons = start_y + len(base_list) * gap_y + 60 - gap_y

        self.btn_reset = self.add(Button(
            "Réinitialiser",
            (x_buttons, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self._reset_selection(),
        ))

        self.btn_validate = self.add(Button(
            "Valider",
            (x_buttons+200, y_buttons),
            anchor="center",
            style=primary,
            on_click=lambda b: self._validate_and_back(),
        ))

        self.btn_back = self.add(Button(
            "Retour",
            (x_buttons+400, y_buttons),
            anchor="center",
            style=ghost,
            on_click=lambda b: self.app.change_state("MENU"),
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

        self.app.change_state("MENU")

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
