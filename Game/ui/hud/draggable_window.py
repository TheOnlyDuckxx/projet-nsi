import pygame


class DraggableWindow:
    """
    Petite fenêtre déplaçable et réutilisable :
    - Affiche un titre et une liste de surfaces de contenu.
    - Peut être déplacée en attrapant la barre de titre.
    - Bouton de fermeture intégré (croix).
    """

    def __init__(self, title_surf: pygame.Surface, content_surfs: list[pygame.Surface], pos: tuple[int, int]):
        self.title_surf = title_surf
        self.content_surfs = content_surfs

        self.pad = 12
        self.gap = 6
        self.section_gap = 10

        # Dimensions
        max_w = title_surf.get_width()
        if content_surfs:
            max_w = max(max_w, max(s.get_width() for s in content_surfs))
        width = max_w + self.pad * 2 + 28  # un peu plus pour la croix

        height = self.pad + title_surf.get_height() + self.section_gap
        if content_surfs:
            height += sum(s.get_height() for s in content_surfs) + self.gap * (len(content_surfs) - 1)
        height += self.pad

        self.rect = pygame.Rect(pos[0], pos[1], width, height)
        self.header_height = self.title_surf.get_height() + self.pad

        self._dragging = False
        self._drag_offset = (0, 0)
        self.closed = False
        self._close_rect = pygame.Rect(self.rect.right - self.pad - 16, self.rect.y + self.pad // 2, 16, 16)

    # ---------- Interaction ----------
    def handle_event(self, e: pygame.event.EventType) -> bool:
        """
        Retourne True si l'événement est consommé.
        """
        if self.closed:
            return False

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                if self._close_rect.collidepoint(e.pos):
                    self.closed = True
                    return True
                if e.pos[1] <= self.rect.y + self.header_height:
                    self._dragging = True
                    self._drag_offset = (e.pos[0] - self.rect.x, e.pos[1] - self.rect.y)
                    return True
                return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._dragging = False
        elif e.type == pygame.MOUSEMOTION and self._dragging:
            dx, dy = self._drag_offset
            self.rect.topleft = (e.pos[0] - dx, e.pos[1] - dy)
            self._update_close_rect()
            return True
        return False

    # ---------- Rendu ----------
    def _update_close_rect(self):
        self._close_rect = pygame.Rect(self.rect.right - self.pad - 16, self.rect.y + self.pad // 2, 16, 16)

    def draw(self, screen: pygame.Surface):
        if self.closed:
            return

        pygame.draw.rect(screen, (20, 20, 28), self.rect, border_radius=10)
        pygame.draw.rect(screen, (90, 140, 190), self.rect, 2, border_radius=10)

        x = self.rect.x + self.pad
        y = self.rect.y + self.pad

        # Titre
        screen.blit(self.title_surf, (x, y))

        # Bouton fermer
        self._update_close_rect()
        pygame.draw.rect(screen, (140, 80, 80), self._close_rect, border_radius=4)
        cross_font = pygame.font.SysFont("consolas", 14, bold=True)
        cross_surf = cross_font.render("×", True, (255, 255, 255))
        cross_rect = cross_surf.get_rect(center=self._close_rect.center)
        screen.blit(cross_surf, cross_rect)

        y += self.title_surf.get_height() + self.section_gap

        # Contenu
        for surf in self.content_surfs:
            screen.blit(surf, (x, y))
            y += surf.get_height() + self.gap
