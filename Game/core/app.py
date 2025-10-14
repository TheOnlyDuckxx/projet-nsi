# APP.PY
# Application principale gérant la boucle pygame


# --------------- IMPORTATION DES MODULES ---------------

import pygame
from Game.core.config import WIDTH, HEIGHT, FPS, TITLE, Settings
from Game.ui.menu import MainMenu,OptionsMenu, CreditMenu
from Game.core.assets import Assets
from Game.core.utils import resource_path
from Game.gameplay.phase1 import Phase1
from Game.ui.loading import LoadingState
from Game.ui.world_creation import WorldCreationMenu

# --------------- CLASSE PRINCIPALE ---------------
class App:
    def __init__(self):
        pygame.init()
        
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.assets = Assets().load_all(resource_path("Game/assets"))
        self.running = True
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.states = {}
        self.state = None
        self.settings=Settings()
        self._register_states()
        self.change_state("MENU")

    # Définis les "STATES"
    def _register_states(self):
        self.states["MENU"] = MainMenu(self)
        self.states["OPTIONS"] = OptionsMenu(self)
        self.states["CREDITS"] = CreditMenu(self)
        self.states["PHASE1"] = Phase1(self)
        self.states["LOADING"] = LoadingState(self)
        self.states["CREATION"] = WorldCreationMenu(self)
        # plus tard: self.states["PHASE2"] = Phase2(self)
    
    #Fonction pour quitter le jeu
    def quit_game(self):
        self.running=False

    # Permet de changer de "STATES"
    def change_state(self, key, **kwargs):
        if self.state and hasattr(self.state, "leave"):
            self.state.leave()
        self.state = self.states[key]
        if hasattr(self.state, "enter"):
            self.state.enter(**kwargs)

    # Boucle principale pygame
    def run(self):
        while self.running:
            fps_cap = int(self.settings.get("video.fps_cap", FPS))
            dt = self.clock.tick(fps_cap) / 1000.0
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
            if hasattr(self.state, "handle_input"):
                self.state.handle_input(events)
            if hasattr(self.state, "update"):
                self.state.update(dt)
            if hasattr(self.state, "render"):
                self.state.render(self.screen)
            pygame.display.flip()
        pygame.quit()
