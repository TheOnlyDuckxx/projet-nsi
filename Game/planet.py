import pygame
import random
import math

WIDTH, HEIGHT = 800, 800
RADIUS = 300
center = (WIDTH // 2, HEIGHT // 2)

N_POINTS = 40000
N_HOTSPOTS = 50           # plus de petites zones
SPREAD_MIN = 0.03         # petites zones
SPREAD_MAX = 0.12
ROT = 0.01                # rotation rad/frame

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()


# ----------------------------------------------------
# GÉNÉRATION HOTSPOTS (coord sphériques)
# ----------------------------------------------------

hotspots = []
for _ in range(N_HOTSPOTS):
    lat = random.uniform(-math.pi/2, math.pi/2)
    lon = random.uniform(-math.pi, math.pi)
    spread = random.uniform(SPREAD_MIN, SPREAD_MAX)
    hotspots.append((lat, lon, spread))


# ----------------------------------------------------
# GÉNÉRATION DES POINTS UNIQUEMENT AUTOUR DES HOTSPOTS
# ----------------------------------------------------

points = []

for _ in range(N_POINTS):
    # choisir un hotspot source
    h_lat, h_lon, spread = random.choice(hotspots)

    # bruit gaussien sphérique
    lat = h_lat + random.gauss(0, spread)
    lon = h_lon + random.gauss(0, spread)

    # normalisation longitude
    if lon > math.pi:
        lon -= 2 * math.pi
    if lon < -math.pi:
        lon += 2 * math.pi

    # stocker point
    points.append([lat, lon])


# ----------------------------------------------------
# BOUCLE PRINCIPALE
# ----------------------------------------------------

running = True
while running:
    clock.tick(60)
    screen.fill((0, 0, 0))

    for p in points:
        lat, lon = p

        # rotation longitude
        lon += ROT
        if lon > math.pi:
            lon -= 2 * math.pi
        p[1] = lon

        # projection 2D
        x = center[0] + RADIUS * math.cos(lat) * math.cos(lon)
        y = center[1] + RADIUS * math.sin(lat)

        # dessiner point
        pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), 1)


    pygame.display.flip()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

pygame.quit()

