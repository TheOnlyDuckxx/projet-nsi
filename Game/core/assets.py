import pygame, os
class Assets:
    def __init__(self):
        self.images = {}
        self.fonts  = {}
    def load_image(self, key, path):
        self.images[key] = pygame.image.load(path).convert_alpha()
    def get_image(self, key): return self.images[key]
    def load_font(self, key, path, size):
        self.fonts[key] = pygame.font.Font(path, size)
    def get_font(self, key): return self.fonts[key]