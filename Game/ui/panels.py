import pygame
from typing import List, Tuple
from Game.core.utils import Button, ButtonStyle

def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> List[str]:
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w) if cur else w
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or ["—"]


class SideInfoPanel:
    """Panneau d’info vertical à droite de l’écran, avec bouton ✕."""
    def __init__(self, screen_size: Tuple[int, int], width: int = 340):
        self.width = width
        self.open = False
        self.title = "Inspection"
        self.fields: List[Tuple[str, str]] = []
        self.padding = 14
        self.screen_w, self.screen_h = screen_size

        self.bg = (18, 22, 30, 230)
        self.header_bg = (30, 36, 48)
        self.border = (70, 80, 100)
        self.header_h = 44

        # Typo
        self.title_font = pygame.font.SysFont("consolas", 20)
        self.text_font = pygame.font.SysFont("consolas", 14)

        # --- NEW: bouton ✕ ---
        x = self.screen_w - self.width
        header_mid_y = 22
        close_style = ButtonStyle(
            draw_background=False,
            font=pygame.font.SysFont("consolas", 20),
            text_color=(230, 240, 255),
            hover_text_color=(255, 140, 140),
            active_text_color=(255, 220, 220),
            hover_zoom=1.0,  # pas de zoom
            mouse_cursor_hand=True,
        )
        self.close_btn = Button(
            "X",
            pos=(x + self.width - self.padding, header_mid_y),
            anchor="midright",
            style=close_style,
            on_click=lambda _b: self.close(),
            name="panel_close",
        )

    def _layout_close_btn(self):
        """Replace le bouton ✕ selon la taille écran/panneau."""
        x = self.screen_w - self.width
        self.close_btn.move_to((x + self.width - self.padding, self.header_h // 2 + 0))

    def set_content(self, title: str, fields: List[Tuple[str, str]]) -> None:
        self.title = title
        self.fields = fields
        self.open = True
        self._layout_close_btn()

    def close(self) -> None:
        self.open = False

    def toggle(self) -> None:
        self.open = not self.open
        self._layout_close_btn()

    def on_resize(self, size: Tuple[int, int]) -> None:
        self.screen_w, self.screen_h = size
        self._layout_close_btn()

    def handle(self, events) -> None:
        """Gère les interactions internes (bouton ✕)."""
        if not self.open:
            return
        self.close_btn.handle(events)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.open:
            return
        x = self.screen_w - self.width
        y = 0

        # Fond semi-opaque
        panel_surf = pygame.Surface((self.width, self.screen_h), pygame.SRCALPHA)
        panel_surf.fill(self.bg)
        screen.blit(panel_surf, (x, y))

        # En-tête
        header_rect = pygame.Rect(x, y, self.width, self.header_h)
        pygame.draw.rect(screen, self.header_bg, header_rect)
        title_s = self.title_font.render(self.title, True, (230, 240, 255))
        screen.blit(title_s, (x + self.padding, y + 12))

        # --- NEW: bouton ✕ visuel ---
        self.close_btn.draw(screen)

        # Contenu
        ty = header_rect.bottom + 8
        max_w = self.width - 2 * self.padding
        for key, value in self.fields:
            k_s = self.text_font.render(str(key), True, (150, 165, 190))
            screen.blit(k_s, (x + self.padding, ty))
            ty += k_s.get_height() + 2

            for line in _wrap_text(value, self.text_font, max_w):
                v_s = self.text_font.render(line, True, (235, 240, 250))
                screen.blit(v_s, (x + self.padding, ty))
                ty += v_s.get_height()
            ty += 8

        # Bordure gauche
        pygame.draw.line(screen, self.border, (x - 1, 0), (x - 1, self.screen_h), 1)