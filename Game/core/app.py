import pygame
from Game.core.config import WIDTH, HEIGHT, FPS, TITLE, Settings
from Game.core.state import State
from Game.ui.menu import MainMenu,OptionsMenu, CreditMenu
from Game.core.assets import Assets
from Game.core.utils import resource_path
#from Game.gameplay.phase1 import Phase1

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

    def _register_states(self):
        self.states["MENU"] = MainMenu(self)
        self.states["OPTIONS"] = OptionsMenu(self)
        self.states["CREDITS"] = CreditMenu(self)
        #self.states["PHASE1"] = Phase1(self)
        # plus tard: self.states["PHASE2"] = Phase2(self)
    
    def quit_game(self):
        self.running=False

    def change_state(self, key, **kwargs):
        self.state = self.states[key]
        if hasattr(self.state, "enter"):
            self.state.enter(**kwargs)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
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
