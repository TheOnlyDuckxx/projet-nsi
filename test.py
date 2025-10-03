import pygame, sys
from pygame.locals import *
pygame.init()
pygame.display.set_caption('isometric view')
screen = pygame.display.set_mode((900, 900), 0, 32)

# Charger l'image du cube
grass_img = pygame.image.load('grass.png').convert()
grass_img.set_colorkey((0, 0, 0))

# Charger la carte
f = open('map3.txt')
map_data = [[int(c) for c in row] for row in f.read().split('\n')]
f.close()

# Taille fixe de la zone d'affichage en pixels
MAP_DISPLAY_SIZE = 500

# Nombre de cases visibles (change avec le zoom)
visible_tiles = 10.0
min_tiles = 5.0
max_tiles = 50.0
zoom_step = 1.0

# Variables pour le déplacement (camera)
camera_x = 0
camera_y = 0
is_dragging = False
last_mouse_pos = (0, 0)

while True:
    screen.fill((0, 0, 0))
   
    # Calculer le centre de l'écran
    screen_center_x = screen.get_width() // 2
    screen_center_y = screen.get_height() // 2
    
    # Calculer la taille d'une case en fonction du nombre de cases visibles
    # Pour une grille isométrique, la largeur totale = visible_tiles * tile_width
    tile_scale = MAP_DISPLAY_SIZE / (visible_tiles * 20)  # 20 est la largeur de base d'une case iso
   
    # Déterminer la plage de cases à afficher
    tiles_to_draw = int(visible_tiles) + 2  # +2 pour les marges
    
    # Dessiner la carte
    for y in range(max(0, int(camera_y)), min(len(map_data), int(camera_y) + tiles_to_draw)):
        for x in range(max(0, int(camera_x)), min(len(map_data[0]), int(camera_x) + tiles_to_draw)):
            height = map_data[y][x]
            
            for h in range(height):  # Dessiner chaque étage
                # Coordonnées isométriques relatives à la caméra
                rel_x = x - camera_x
                rel_y = y - camera_y
                
                # Coordonnées isométriques de base
                iso_x = rel_x * 10 - rel_y * 10
                iso_y = rel_x * 5 + rel_y * 5 - h * 14
               
                # Appliquer l'échelle pour s'adapter au nombre de cases visibles
                scaled_x = iso_x * tile_scale
                scaled_y = iso_y * tile_scale
               
                # Centrer sur l'écran
                final_x = screen_center_x + scaled_x
                final_y = screen_center_y + scaled_y
               
                # Mettre à l'échelle l'image du cube
                scaled_grass = pygame.transform.scale(
                    grass_img,
                    (int(grass_img.get_width() * tile_scale),
                     int(grass_img.get_height() * tile_scale))
                )
               
                screen.blit(scaled_grass, (final_x, final_y))
    
    # Afficher les infos
    font = pygame.font.Font(None, 36)
    info_text = font.render(f'Cases visibles: {visible_tiles:.1f}x{visible_tiles:.1f}', True, (255, 255, 255))
    screen.blit(info_text, (10, 10))
   
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
            if event.button == 4:  # Molette vers le haut (zoom in = moins de cases visibles)
                visible_tiles = max(visible_tiles - zoom_step, min_tiles)
               
            elif event.button == 5:  # Molette vers le bas (zoom out = plus de cases visibles)
                visible_tiles = min(visible_tiles + zoom_step, max_tiles)
               
            elif event.button == 2:  # Clic molette (bouton du milieu)
                is_dragging = True
                last_mouse_pos = pygame.mouse.get_pos()
       
        if event.type == MOUSEBUTTONUP:
            if event.button == 2:
                is_dragging = False
       
        if event.type == MOUSEMOTION:
            if is_dragging:
                current_mouse_pos = pygame.mouse.get_pos()
                # Le déplacement est proportionnel au niveau de zoom
                move_speed = visible_tiles / 100.0
                dx = (last_mouse_pos[0] - current_mouse_pos[0]) * move_speed
                dy = (last_mouse_pos[1] - current_mouse_pos[1]) * move_speed
                
                # Convertir le déplacement écran en déplacement grille isométrique
                camera_x += (dx - dy) * 0.1
                camera_y += (dx + dy) * 0.1
                
                # Limiter la caméra aux bords de la carte
                camera_x = max(0, min(camera_x, len(map_data[0]) - visible_tiles))
                camera_y = max(0, min(camera_y, len(map_data) - visible_tiles))
                
                last_mouse_pos = current_mouse_pos
   
    pygame.display.update()