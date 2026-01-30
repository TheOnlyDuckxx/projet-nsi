import pygame
from Game.core.utils import Button, ButtonStyle

class TechMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False
        self.scroll_x = 0
        self._max_scroll_x = 0

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Menu Technologies"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.btn_font = pygame.font.SysFont("consolas", 26, bold=True)

        style = ButtonStyle(draw_background=True, radius=12, padding_x=16, padding_y=10, hover_zoom=1.04, font=self.btn_font)
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

    def open(self): self.active = True
    def close(self): self.active = False

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def handle(self, events):
        if self.active:
            self._handle_scroll_input(events)
            self.back_btn.handle(events)

    def _scroll_tree(self, delta: int):
        if self._max_scroll_x <= 0:
            self.scroll_x = 0
            return
        self.scroll_x = max(0, min(self.scroll_x + delta, self._max_scroll_x))

    def _handle_scroll_input(self, events):
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                # Utiliser la molette pour défiler horizontalement dans l'arbre
                self._scroll_tree(-e.y * 40)

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = int(min(w, h) * 0.04)

        self.title_font = pygame.font.SysFont("consolas", max(28, int(h * 0.06)), bold=True)
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)

        screen.fill((60, 60, 65))  # gris neutre

        title_surf = self.title_font.render(self.title, True, (245, 245, 245))
        title_rect = title_surf.get_rect(midtop=(w // 2, margin))
        screen.blit(title_surf, title_rect)

        bubble_radius = max(28, int(min(w, h) * 0.07))
        bubble_font = pygame.font.SysFont("consolas", max(16, int(bubble_radius * 0.55)), bold=True)
        bubble_color = (90, 90, 95)
        bubble_border = (220, 220, 220)
        line_color = (180, 180, 190)

        root_x = margin + bubble_radius + 10
        root_y = int(h * 0.5)
        child_x = root_x + int(w * 0.5)
        child_offset_y = int(h * 0.18)
        upper_center = (child_x, root_y - child_offset_y)
        lower_center = (child_x, root_y + child_offset_y)
        root_center = (root_x, root_y)

        tree_width = child_x + bubble_radius + margin
        view_width = w - margin
        self._max_scroll_x = max(0, tree_width - view_width)
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x))

        def apply_scroll(center):
            return (center[0] - self.scroll_x, center[1])

        root_center = apply_scroll(root_center)
        upper_center = apply_scroll(upper_center)
        lower_center = apply_scroll(lower_center)

        pygame.draw.line(screen, line_color, root_center, upper_center, 4)
        pygame.draw.line(screen, line_color, root_center, lower_center, 4)

        pygame.draw.line(screen, line_color, upper_center, lower_center, 4)
        mid_x = (upper_center[0] + lower_center[0]) // 2
        mid_y = (upper_center[1] + lower_center[1]) // 2
        warning_radius = max(10, int(bubble_radius * 0.25))
        pygame.draw.circle(screen, (200, 40, 40), (mid_x, mid_y), warning_radius)
        warning_font = pygame.font.SysFont("consolas", max(14, int(warning_radius * 1.2)), bold=True)
        warning_text = warning_font.render("!", True, (245, 245, 245))
        warning_rect = warning_text.get_rect(center=(mid_x, mid_y - 1))
        screen.blit(warning_text, warning_rect)

        def draw_bubble(center, label):
            pygame.draw.circle(screen, bubble_color, center, bubble_radius)
            pygame.draw.circle(screen, bubble_border, center, bubble_radius, 3)
            text = bubble_font.render(label, True, (245, 245, 245))
            text_rect = text.get_rect(center=center)
            screen.blit(text, text_rect)

        draw_bubble(root_center, "Feu")
        draw_bubble(upper_center, "FEU TOTEM")
        draw_bubble(lower_center, "FEUX D’INTIMIDATION")

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
