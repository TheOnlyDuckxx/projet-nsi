import pygame

class CameraIso:
    def __init__(self, tile_w=20, tile_h=24, zoom=1.0):
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.half_w = tile_w / 2
        self.half_h = tile_h / 2
        self.zoom = zoom
        self.offset = pygame.Vector2(0, 0)
        self._dragging = False
        self._last = pygame.Vector2(0, 0)

    def world_to_screen(self, tx: float, ty: float):
        # isométrique : (x - y, x + y)
        sx = (tx - ty) * self.half_w
        sy = (tx + ty) * self.half_h
        # zoom + offset
        sx = sx * self.zoom + self.offset.x
        sy = sy * self.zoom + self.offset.y
        return int(sx), int(sy)

    def screen_to_world(self, sx: int, sy: int):
        # inverse isométrique
        xz = (sx - self.offset.x) / self.zoom
        yz = (sy - self.offset.y) / self.zoom
        tx = (xz / self.half_w + yz / self.half_h) / 2
        ty = (yz / self.half_h - xz / self.half_w) / 2
        return tx, ty

    def apply_zoom_to_surface(self, surf: pygame.Surface):
        if self.zoom == 1.0:
            return surf
        w, h = surf.get_size()
        return pygame.transform.smoothscale(surf, (int(w * self.zoom), int(h * self.zoom)))

    # --- interactions souris (zoom molette, drag bouton milieu) ---
    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            old = self.zoom
            self.zoom = min(max(self.zoom * (1.1 if event.y > 0 else 1/1.1), 0.4), 4.0)
            # zoom centré sous le curseur
            mx, my = pygame.mouse.get_pos()
            k = self.zoom / old
            self.offset.x = mx - k * (mx - self.offset.x)
            self.offset.y = my - k * (my - self.offset.y)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self._dragging = True
            self._last = pygame.Vector2(event.pos)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION and self._dragging:
            cur = pygame.Vector2(event.pos)
            delta = cur - self._last
            self.offset += delta
            self._last = cur