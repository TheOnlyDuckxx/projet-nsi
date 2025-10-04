import pygame
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import resource_path, Button, ButtonStyle

class MainMenu:
    def __init__(self, app):
        self.app = app
        self.title_font = pygame.font.Font(resource_path("Game/assets/sfx/MightySouly.ttf"), 64)
        self.btn_font   = pygame.font.Font(resource_path("Game/assets/sfx/MightySouly.ttf"), 28)
        self.start_rect = pygame.Rect(WIDTH//2-120, HEIGHT//2, 240, 60)
        self.background = pygame.transform.scale(pygame.image.load(resource_path("Game/assets/sfx/test_menu_background.jpg")).convert(),(WIDTH, HEIGHT))
        ghost_style = ButtonStyle(draw_background=False, font=self.btn_font, text_color=(230,230,230), hover_zoom=1.10)
        self.btn_start = Button("Continuer", (WIDTH//2, HEIGHT//2 -40), anchor="center", style=ghost_style)
        self.btn_ng = Button("Nouvelle Partie", (WIDTH//2, HEIGHT//2), anchor="center", style=ghost_style)
        self.btn_options = Button("Options", (WIDTH//2, HEIGHT//2 +40), anchor="center", style=ghost_style)
        self.btn_credits = Button("Crédits", (WIDTH//2, HEIGHT//2 + 80), anchor="center", style=ghost_style)
        self.btn_quit = Button("Quitter", (WIDTH//2, HEIGHT//2 +120), anchor="center", style=ghost_style)
        
    def handle_input(self, events):
        clicked_start  = self.btn_start.handle(events)
        clicked_credit = self.btn_credits.handle(events)
        clicked_ng = self.btn_ng.handle(events)
        clicked_options = self.btn_options.handle(events)
        clicked_quit = self.btn_quit.handle(events)

        if clicked_start:
            self.app.change_state("PHASE1")
        if clicked_ng:
            self.app.change_state("WORLDGEN")
        if clicked_options:
            self.app.change_state("OPTIONS")
        if clicked_quit:
            self.app.quit_game()
        if clicked_credit:
            self.app.change_state("CREDITS")

        
    def render(self, screen):
        
        screen.blit(self.background, (0, 0))
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(100)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        title = self.title_font.render("EvoNSI", True, (230,230,230))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 180))
        
        
        self.btn_start.draw(screen)
        self.btn_ng.draw(screen)
        self.btn_options.draw(screen)
        self.btn_credits.draw(screen)
        self.btn_quit.draw(screen)



