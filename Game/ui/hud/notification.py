import time
from typing import List

import pygame

# Configuration de base
NOTIF_FONT = pygame.font.SysFont("consolas", 18)
NOTIF_MAX_WIDTH = 300  # largeur max pixels
NOTIF_BG_COLOR = (25, 25, 25)
NOTIF_TEXT_COLOR = (255, 255, 255)
NOTIF_BORDER_COLOR = (200, 200, 200)
NOTIF_PADDING = 10
NOTIF_SPACING = 10
NOTIF_DURATION = 3.0  # secondes d'affichage
NOTIF_FADE_TIME = 0.5  # secondes avant disparition

notifications: List[dict] = []  # liste globale de notifs actives


def add_notification(message: str):
    """
    Crée et ajoute une notification à afficher.
    """
    if not message:
        return

    # Évite d'empiler plusieurs fois la même notification visible
    for notif in notifications:
        if notif.get("raw") == message:
            return

    wrapped = _wrap_text(message, NOTIF_FONT, NOTIF_MAX_WIDTH - 2 * NOTIF_PADDING)
    width = min(
        NOTIF_MAX_WIDTH,
        max(NOTIF_FONT.size(line)[0] for line in wrapped) + 2 * NOTIF_PADDING,
    )
    height = len(wrapped) * NOTIF_FONT.get_height() + 2 * NOTIF_PADDING

    notif = {
        "raw": message,
        "text": wrapped,
        "start": time.time(),
        "width": width,
        "height": height,
    }
    notifications.append(notif)


def _wrap_text(text, font, max_width):
    """
    Coupe le texte pour qu'il tienne dans la largeur max, avec des retours à la ligne automatiques.
    """
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test_line = current + " " + word if current else word
        if font.size(test_line)[0] <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    return lines


def draw_notifications(screen):
    """
    Affiche toutes les notifications actives en bas à droite de l'écran.
    """
    now = time.time()
    screen_width, screen_height = screen.get_size()

    # On part du bas de l'écran vers le haut
    y = screen_height - NOTIF_SPACING

    # On itère à l'envers (pour supprimer sans bug)
    for notif in notifications[:]:
        elapsed = now - notif["start"]

        # Effet de fade-out
        if elapsed > NOTIF_DURATION + NOTIF_FADE_TIME:
            notifications.remove(notif)
            continue
        elif elapsed > NOTIF_DURATION:
            alpha = 255 * (1 - (elapsed - NOTIF_DURATION) / NOTIF_FADE_TIME)
        else:
            alpha = 255

        # Création du fond avec alpha
        surface = pygame.Surface((notif["width"], notif["height"]), pygame.SRCALPHA)
        surface.fill((*NOTIF_BG_COLOR, int(alpha * 0.9)))

        # Bordure
        pygame.draw.rect(surface, NOTIF_BORDER_COLOR, surface.get_rect(), 2)

        # Texte
        text_y = NOTIF_PADDING
        for line in notif["text"]:
            text_surf = NOTIF_FONT.render(line, True, NOTIF_TEXT_COLOR)
            surface.blit(text_surf, (NOTIF_PADDING, text_y))
            text_y += NOTIF_FONT.get_height()

        # Position (bas-droite)
        x = screen_width - notif["width"] - NOTIF_SPACING
        y -= notif["height"]
        screen.blit(surface, (x, y))
        y -= NOTIF_SPACING
