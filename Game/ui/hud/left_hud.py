import pygame

from Game.core.utils import Button, ButtonStyle
from Game.ui.menu.menu_event import EventMenu
from Game.ui.menu.menu_history import HistoryMenu
from Game.ui.menu.menu_options import OptionsMenu
from Game.ui.menu.menu_species import SpeciesMenu
from Game.ui.menu.menu_tech import TechMenu
from .notification import draw_notifications


class LeftHUD:
    """
    Barre verticale à droite :
    - ~40% de la hauteur écran
    - ~5% de la largeur écran
    - centrée verticalement
    - boutons ouvrant des menus (sans logique interne pour l'instant)
    - quand un menu est ouvert : le jeu est en pause (via phase.ui_menu_open)
    """
    def __init__(self, phase):
        self.phase = phase
        self.screen = phase.screen

        # Menus
        self.menus = {
            "species": SpeciesMenu(phase, on_close=self._close_menu),
            "events": EventMenu(phase, on_close=self._close_menu),
            "tech": TechMenu(phase, on_close=self._close_menu),
            "history": HistoryMenu(phase, on_close=self._close_menu),
            "options": OptionsMenu(phase, on_close=self._close_menu),
        }
        self.active_menu_key = None

        # Style boutons HUD
        if not pygame.font.get_init():
            pygame.font.init()

        self.btn_style = ButtonStyle(
            draw_background=True,
            radius=10,
            padding_x=6,
            padding_y=6,
            hover_zoom=1.03,
        )

        # Boutons (créés une fois, repositionnés à chaque frame)
        self.buttons = []
        self._build_buttons()

        # Rect barre
        self.bar_rect = pygame.Rect(0, 0, 10, 10)

    def _build_buttons(self):
        # texte court sinon ça ne rentre pas en 5% de largeur
        entries = [
            ("ESP", "species"),
            ("EVT", "events"),
            ("TEC", "tech"),
            ("HIS", "history"),
            ("OPT", "options"),
        ]

        self.buttons = []
        for label, key in entries:
            btn = Button(
                text=label,
                pos=(0, 0),
                size=(10, 10),          # sera recalculé
                anchor="center",
                style=self.btn_style,
                on_click=lambda _b, k=key: self.open_menu(k),
                name=f"right_hud_{key}",
            )
            self.buttons.append(btn)

    # ---------- Layout ----------
    def _update_layout(self):
        sw, sh = self.screen.get_size()

        bar_w = max(48, int(sw * 0.05))
        bar_h = max(220, int(sh * 0.40))
        margin = max(10, int(min(sw, sh) * 0.02))

        x = margin
        y = (sh - bar_h) // 2

        self.bar_rect = pygame.Rect(x, y, bar_w, bar_h)

        # Police dépendante de l'écran (recréée dynamiquement)
        font_size = max(14, int(sh * 0.022))
        self.btn_style.font = pygame.font.SysFont("consolas", font_size, bold=True)

        # Boutons répartis verticalement dans la barre
        n = len(self.buttons)
        inner_pad = max(8, int(bar_h * 0.04))
        available = bar_h - 2 * inner_pad
        gap = max(8, int(available * 0.04))
        btn_h = max(34, int((available - gap * (n - 1)) / n))
        btn_w = max(34, int(bar_w * 0.84))

        cx = self.bar_rect.centerx
        top = self.bar_rect.top + inner_pad

        for i, btn in enumerate(self.buttons):
            cy = top + i * (btn_h + gap) + btn_h // 2
            btn.size = (btn_w, btn_h)
            btn.rect = btn._compute_rect()
            btn.move_to((cx, cy))

    # ---------- Menu controls ----------
    def is_menu_open(self) -> bool:
        return self.active_menu_key is not None

    def open_menu(self, key: str):
        if key not in self.menus:
            return
        Button.reset_cursor_state(restore=True)
        self.active_menu_key = key
        self.menus[key].open()
        reset_drag = getattr(self.phase, "_reset_drag_selection", None)
        if callable(reset_drag):
            reset_drag()
        if hasattr(self.phase, "_ui_click_blocked"):
            self.phase._ui_click_blocked = False

        # Pause du jeu (sans déclencher l'écran "PAUSE" classique)
        self.phase.ui_menu_open = True

    def _close_menu(self):
        # fermé depuis un menu (bouton retour)
        if self.active_menu_key and self.active_menu_key in self.menus:
            self.menus[self.active_menu_key].close()

        Button.reset_cursor_state(restore=True)
        self.active_menu_key = None
        self.phase.ui_menu_open = False
        reset_drag = getattr(self.phase, "_reset_drag_selection", None)
        if callable(reset_drag):
            reset_drag()
        if hasattr(self.phase, "_ui_click_blocked"):
            self.phase._ui_click_blocked = False

    # ---------- Interaction ----------
    def handle(self, events) -> bool:
        """
        Retourne True si l'UI consomme l'input (menu ouvert ou clic sur HUD),
        pour que Phase1 n'applique pas ces events au monde.
        """
        self._update_layout()

        # Si un menu est ouvert : il capte tout
        if self.is_menu_open():
            self.menus[self.active_menu_key].handle(events)
            return True

        # Sinon : clic sur boutons HUD
        clicked_any = False
        for btn in self.buttons:
            if btn.handle(events):
                clicked_any = True

        return clicked_any

    # ---------- Draw ----------
    def draw(self, screen):
        self._update_layout()

        # Si un menu est ouvert → afficher UNIQUEMENT le menu
        if self.is_menu_open():
            self.menus[self.active_menu_key].draw(screen)
            # Affiche les notifications par-dessus les écrans de menu
            draw_notifications(screen)
            return  # <-- IMPORTANT

        # Sinon : afficher la barre HUD
        bg = pygame.Surface((self.bar_rect.width, self.bar_rect.height))
        bg.fill((45, 45, 50))
        screen.blit(bg, self.bar_rect.topleft)

        pygame.draw.rect(
            screen,
            (120, 120, 130),
            self.bar_rect,
            2,
            border_radius=14
        )

        for btn in self.buttons:
            btn.draw(screen)
