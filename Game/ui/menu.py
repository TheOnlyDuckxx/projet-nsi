import pygame
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import resource_path, Button, ButtonStyle, Slider, Toggle
from Game.core.assets import Assets


class BaseMenu:
    def __init__(self, app, title:str):
        self.app = app
        self.title = title
        self.bg = pygame.transform.scale(app.assets.get_image("test_menu_background"),(WIDTH, HEIGHT))
        self.title_font = app.assets.get_font("MightySouly", 64)
        self.btn_font = app.assets.get_font("MightySouly", 28)
        self.widgets = []  # chaque widget a: handle(events) -> bool, draw(screen)

        # overlay sombre pour lisibilité
        self._overlay = pygame.Surface((WIDTH, HEIGHT))
        self._overlay.set_alpha(90)
        self._overlay.fill((0, 0, 0))

    def add(self, widget):
        self.widgets.append(widget)
        return widget

    def handle_input(self, events):
        for w in self.widgets:
            w.handle(events)

    def update(self, dt):
        pass

    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))
        title_surf = self.title_font.render(self.title, True, (230,230,230))
        screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 120))
        for w in self.widgets:
            w.draw(screen)



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
            hover_zoom=1.10,   # zoom fluide (activé)
            zoom_speed=0.22,
        )

        ghost = ButtonStyle(
            draw_background=False,
            font=self.btn_font,
            text_color=(230, 230, 230),
            hover_zoom=1.08,
            zoom_speed=0.22,
        )

        y0 = HEIGHT // 2 + 20
        gap = 70

        # ---- Boutons (on_click appelle directement l'app) ----
        self.btn_start = self.add(Button(
            "NOUVELLE PARTIE",
            (WIDTH // 2, y0),
            anchor="center",
            style=primary,
            on_click=lambda b: self.app.change_state("PHASE1"),
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

    # --- Entrées : laisse BaseMenu propager aux widgets; ajoute tes raccourcis si besoin
    def handle_input(self, events):
        super().handle_input(events)

    # --- Rendu : BaseMenu dessine déjà bg + overlay + titre + widgets
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
        
        ghost = ButtonStyle(draw_background=False, font=self.btn_font, text_color=(230,230,230), hover_zoom=1.08)
        self.btn_back = Button("← Retour", (WIDTH//2, 560), anchor="center", style=ghost,
                               on_click=lambda b: self.app.change_state("MENU"))
        self.add(self.btn_back)