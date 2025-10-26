import pygame
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from Game.core.assets import Assets
from Game.species.species import Espece
pygame.init()
screen = pygame.display.set_mode((50, 50))

mon_espece = Espece("Hominidé", 400, 300)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((0, 125, 125))
    mon_espece.draw(screen)
    pygame.display.flip()
