import pygame
from core.state import State
from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import Button, ButtonStyle, Slider, Toggle, ValueSelector, OptionSelector

class WorldCreationMenu(State):
    def __init__(self, app):
        super().__init__(app)
        self.font = pygame.font.Font(None, 36)
        
        # Exemple de paramètres du monde
        self.params = {
            "seed": "Aléatoire",
            "age": 2000,
            "Taille": 40000,
            "Climat": "Tempéré",
            "Niveau des océans": 0,
            "Ressources": "Normale"
        }

        # Exemple de boutons
        self.buttons = [
            Button("Lancer la partie",(WIDTH//2,250 ), anchor="center", on_click= lambda b: self.start_game),
            Button( "Retour", (WIDTH//2,300 ), anchor="center",on_click= lambda b:self.back_to_menu)

        ]
        self.selectors = [
            ValueSelector((100, 150, 300, 50), "Age du monde en millions d'années", 1000, 4000, 500, 2000, self.font),
            ValueSelector((100, 220, 300, 50), "Niveau des océans en mètres", -50, 100, 10, 0, self.font),
            ValueSelector((100, 290, 300, 50), "Taille du monde en kilomètres", 20000, 60000, 5000, 40000, self.font)
        ]
        self.option_selectors = [
            OptionSelector((200, 220, 300, 50), "Climat", ["Aride", "Tempéré", "Tropical"], start_index=1, font=self.font),
            OptionSelector((200, 290, 300, 50), "Ressources", ["Eparse", "Normale", "Abondante"], start_index=1, font=self.font)
        ]

    def handle_events(self, events):
        for event in events:
            for b in self.buttons:
                b.handle_event(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.back_to_menu()

    def update(self, dt):
        """
        Met à jour les paramètres du monde en fonction des valeurs sélectionnées.
        Cette fonction est appelée à chaque frame.
        """
        # Met à jour les paramètres numériques
        self.params["age"] = self.selectors[0].value
        self.params["Niveau des océans"] = self.selectors[1].value
        self.params["Taille"] = self.selectors[2].value

        # Met à jour les paramètres textuels
        self.params["Climat"] = self.option_selectors[0].value
        self.params["Ressources"] = self.option_selectors[1].value

    def render(self, screen):
        screen.fill((20, 20, 40))
        y = 100
        for k, v in self.params.items():
            text = self.font.render(f"{k}: {v}", True, (255, 255, 255))
            screen.blit(text, (100, y))
            y += 50
        
        for b in self.buttons:
            b.render(screen)

    def start_game(self):
        # Passer à la phase 1, avec les paramètres choisis
        from gameplay.phase1 import Phase1
        self.app.change_state(Phase1(self.app, world_params=self.params))

    def back_to_menu(self):
        from ui.menu import MainMenu
        self.app.change_state(MainMenu(self.app))