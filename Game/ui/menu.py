import pygame
from Game.core.config import WIDTH, HEIGHT

class MainMenu:
    def __init__(self, app):
        self.app = app
        self.title_font = pygame.font.SysFont("arial", 64)
        self.btn_font   = pygame.font.SysFont("arial", 28)
        self.start_rect = pygame.Rect(WIDTH//2-120, HEIGHT//2, 240, 60)
    def handle_input(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.start_rect.collidepoint(e.pos):
                    self.app.change_state("PHASE1")
    def render(self, screen):
        screen.fill((20, 24, 28))
        title = self.title_font.render("EvoNSI", True, (230,230,230))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 180))
        pygame.draw.rect(screen, (60,120,200), self.start_rect, border_radius=12)
        txt = self.btn_font.render("NOUVELLE PARTIE", True, (255,255,255))
        screen.blit(txt, (self.start_rect.centerx - txt.get_width()//2, self.start_rect.centery - txt.get_height()//2))
