import pygame

from Game.core.utils import Button, ButtonStyle
from Game.ui.menu.menu_event import EventMenu
from Game.ui.menu.menu_history import HistoryMenu
from Game.ui.menu.menu_quest import QuestMenu
from Game.ui.menu.menu_species import SpeciesMenu
from Game.ui.menu.menu_tech import TechMenu
from .notification import draw_notifications


class LeftHUD:
    """
    Barre verticale a gauche :
    - ~40% de la hauteur ecran
    - ~5% de la largeur ecran
    - centree verticalement
    """

    def __init__(self, phase):
        self.phase = phase
        self.screen = phase.screen

        self.menus = {
            "species": SpeciesMenu(phase, on_close=self._close_menu),
            "events": EventMenu(phase, on_close=self._close_menu),
            "tech": TechMenu(phase, on_close=self._close_menu),
            "history": HistoryMenu(phase, on_close=self._close_menu),
            "quest": QuestMenu(phase, on_close=self._close_menu),
        }
        self.active_menu_key = None

        if not pygame.font.get_init():
            pygame.font.init()

        self.btn_style = ButtonStyle(
            draw_background=True,
            radius=10,
            padding_x=6,
            padding_y=6,
            hover_zoom=1.03,
        )

        self.button_specs = [
            ("ESP", "species", ("espece", "species")),
            ("EVT", "events", ("event", "events", "evenement")),
            ("TEC", "tech", ("techno", "technologie", "tech")),
            ("HIS", "history", ("histoire", "history")),
            ("QTE", "quest", ("quete", "quest")),
        ]
        self.button_icon_sources = {}
        self.button_icon_cache = {}
        self._load_button_icons()

        self.buttons = []
        self._build_buttons()
        self.bar_rect = pygame.Rect(0, 0, 10, 10)

    def _build_buttons(self):
        self.buttons = []
        for fallback_label, key, _icon_names in self.button_specs:
            btn = Button(
                text=fallback_label,
                pos=(0, 0),
                size=(10, 10),
                anchor="center",
                style=self.btn_style,
                on_click=lambda _b, k=key: self.open_menu(k),
                name=f"right_hud_{key}",
            )
            self.buttons.append(btn)

    def _load_button_icons(self):
        assets = getattr(self.phase, "assets", None)
        if assets is None:
            return

        for _fallback_label, key, icon_names in self.button_specs:
            icon = None
            for icon_key in icon_names:
                try:
                    icon = assets.get_image(icon_key)
                    break
                except Exception:
                    continue
            if icon is not None:
                self.button_icon_sources[key] = icon

    def _apply_button_icons(self, icon_size: int):
        icon_size = max(12, int(icon_size))
        if self.button_icon_cache.get("size") != icon_size:
            cache = {}
            for key, source in self.button_icon_sources.items():
                cache[key] = pygame.transform.smoothscale(source, (icon_size, icon_size))
            self.button_icon_cache = {"size": icon_size, "icons": cache}

        icons = self.button_icon_cache.get("icons", {})
        for (fallback_label, key, _icon_names), btn in zip(self.button_specs, self.buttons):
            icon = icons.get(key)
            if icon is not None:
                btn.icon = icon
                btn.icon_gap = 0
                btn.set_text("")
            else:
                btn.icon = None
                btn.set_text(fallback_label)

    def _update_layout(self):
        sw, sh = self.screen.get_size()
        bar_w = max(48, int(sw * 0.05))
        bar_h = max(220, int(sh * 0.40))
        margin = max(10, int(min(sw, sh) * 0.02))
        x = margin
        y = (sh - bar_h) // 2
        self.bar_rect = pygame.Rect(x, y, bar_w, bar_h)

        font_size = max(14, int(sh * 0.022))
        self.btn_style.font = pygame.font.SysFont("consolas", font_size, bold=True)

        n = len(self.buttons)
        inner_pad = max(8, int(bar_h * 0.04))
        available = bar_h - 2 * inner_pad
        gap = max(8, int(available * 0.04))
        btn_h = max(34, int((available - gap * (n - 1)) / n))
        btn_w = max(34, int(bar_w * 0.84))
        self._apply_button_icons(btn_h * 0.72)

        cx = self.bar_rect.centerx
        top = self.bar_rect.top + inner_pad
        for i, btn in enumerate(self.buttons):
            cy = top + i * (btn_h + gap) + btn_h // 2
            btn.size = (btn_w, btn_h)
            btn.rect = btn._compute_rect()
            btn.move_to((cx, cy))

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
        self.phase.ui_menu_open = True

    def _close_menu(self):
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

    def handle(self, events) -> bool:
        self._update_layout()
        if self.is_menu_open():
            self.menus[self.active_menu_key].handle(events)
            return True

        clicked_any = False
        for btn in self.buttons:
            if btn.handle(events):
                clicked_any = True
        return clicked_any

    def draw(self, screen):
        self._update_layout()
        if self.is_menu_open():
            self.menus[self.active_menu_key].draw(screen)
            draw_notifications(screen)
            return

        bg = pygame.Surface((self.bar_rect.width, self.bar_rect.height))
        bg.fill((45, 45, 50))
        screen.blit(bg, self.bar_rect.topleft)

        pygame.draw.rect(screen, (120, 120, 130), self.bar_rect, 2, border_radius=14)
        for btn in self.buttons:
            btn.draw(screen)
