import pygame
from Game.core.config import WIDTH, HEIGHT, FPS, TITLE
from Game.core.state import State
from Game.ui.menu import MainMenu
#from Game.gameplay.phase1 import Phase1

class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.states = {}
        self.state = None
        self._register_states()
        self.change_state("MENU")

    def _register_states(self):
        self.states["MENU"] = MainMenu(self)
        #self.states["PHASE1"] = Phase1(self)
        # plus tard: self.states["PHASE2"] = Phase2(self)

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
