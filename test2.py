import pygame, sys, time
from pygame.locals import *

pygame.init()
pygame.display.set_caption('isometric view')
screen = pygame.display.set_mode((900, 900), 0, 32)
display = pygame.Surface((300, 300))

# Charger l'image du cube
grass_img = pygame.image.load('grass.png').convert()
grass_img.set_colorkey((0, 0, 0))

# Charger la carte
f = open('map3.txt')
map_data = [[int(c) for c in row] for row in f.read().split('\n')]
f.close()

# Variables pour le zoom
zoom_level = 1.0
zoom_speed = 0.1
min_zoom = 0.3
max_zoom = 3.0

# Variables pour le déplacement
offset_x = 0
offset_y = 0
is_dragging = False
last_mouse_pos = (0, 0)

while True:
    display.fill((0, 0, 0))
    
    # Dessiner la carte avec des étages
    for y, row in enumerate(map_data):
        for x, height in enumerate(row):
            for h in range(height):  # Dessiner chaque étage
                iso_x = 150 + x * 10 - y * 10
                iso_y = 100 + x * 5 + y * 5 - h * 14  # Décaler chaque étage verticalement
                display.blit(grass_img, (iso_x, iso_y))
    
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                pygame.quit()
                sys.exit()
        
        # Gérer le zoom avec la molette
        if event.type == MOUSEBUTTONDOWN:
            if event.button == 4:  # Molette vers le haut (zoom in)
                zoom_level = min(zoom_level + zoom_speed, max_zoom)
            elif event.button == 5:  # Molette vers le bas (zoom out)
                zoom_level = max(zoom_level - zoom_speed, min_zoom)
            elif event.button == 2:  # Clic molette (bouton du milieu)
                is_dragging = True
                last_mouse_pos = pygame.mouse.get_pos()
        
        if event.type == MOUSEBUTTONUP:
            if event.button == 2:  # Relâcher le clic molette
                is_dragging = False
        
        if event.type == MOUSEMOTION:
            if is_dragging:
                current_mouse_pos = pygame.mouse.get_pos()
                offset_x += current_mouse_pos[0] - last_mouse_pos[0]
                offset_y += current_mouse_pos[1] - last_mouse_pos[1]
                last_mouse_pos = current_mouse_pos
    
    # Calculer la nouvelle taille avec le zoom
    new_width = int(display.get_width() * zoom_level)
    new_height = int(display.get_height() * zoom_level)
    
    # Appliquer le zoom et le déplacement
    scaled_display = pygame.transform.scale(display, (new_width, new_height))
    x_offset = (screen.get_width() - new_width) // 2 + offset_x
    y_offset = (screen.get_height() - new_height) // 2 + offset_y
    
    screen.fill((0, 0, 0))
    screen.blit(scaled_display, (x_offset, y_offset))
    pygame.display.update()