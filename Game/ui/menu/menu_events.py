import pygame
from Game.core.utils import Button, ButtonStyle

class EventsMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Menu Événements"
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
            self.back_btn.handle(events)

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

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
