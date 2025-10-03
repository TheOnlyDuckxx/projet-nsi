class State:
    def __init__(self, app): self.app = app
    def enter(self, **kwargs): pass
    def handle_input(self, events): pass
    def update(self, dt): pass
    def render(self, screen): pass
    def exit(self): pass
