# ui/iso_view.py
from __future__ import annotations
import pygame
import math
from typing import Optional, Tuple

# Fallbacks si tes modules n’exposent pas de helpers noms → sprites
try:
    from world.tiles import get_ground_sprite_name  # get_ground_sprite_name(id:int) -> str
except Exception:
    def get_ground_sprite_name(gid: int) -> str:
        # Adapte à tes noms d'assets ! (ex: "block_grass_iso")
        MAP = {
            0: "tile_ocean",
            1: "tile_beach",
            2: "tile_grass",
            3: "tile_forest",
            4: "tile_rock",
            5: "tile_taiga",
            6: "tile_desert",
            7: "tile_rainforest",
            8: "tile_steppe",
        }
        return MAP.get(gid, "tile_grass")

try:
    from world.ressource import get_prop_sprite_name  # get_prop_sprite_name(id:int) -> str
except Exception:
    def get_prop_sprite_name(pid: int) -> Optional[str]:
        MAP = {
            10: "prop_tree",
            11: "prop_rock",
            12: "prop_bush",
        }
        return MAP.get(pid, None)


class IsoMapView:
    def __init__(self, assets, screen_size, min_zoom=0.6, max_zoom=2.5, zoom_step=0.1):
        self.assets = assets
        self.screen_w, self.screen_h = screen_size
        self.base_dx = 32
        self.base_dy = 16
        self.base_dz = 24
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_step = zoom_step
        self._ground_cache = {}
        self._prop_cache = {}
        self.world = None
        self.max_levels = 6
        self.pan_keys_speed = 600
        self.mouse_pan_active = False
        self.mouse_pan_start = (0, 0)
        self.cam_start_at_drag = (0.0, 0.0)

    # --- CONFIGURATION ---
    def set_world(self, world):
        """Reçoit un WorldData et centre la caméra sur le spawn."""
        self.world = world
        self.max_levels = max(max(row) for row in world.levels) if world.levels else 6
        sx, sy = self.world_to_screen(world.spawn[0], world.spawn[1], 0)
        # 🧭 centrage caméra au milieu de l’écran
        self.cam_x = sx
        self.cam_y = sy
        print(f"[DEBUG set_world] Spawn {world.spawn} -> screen=({sx:.1f},{sy:.1f})")

    # --- CONTROLES ---
    def handle_event(self, e):
        if e.type == pygame.MOUSEWHEEL:
            self._apply_zoom(1 if e.y > 0 else -1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 2:
            self.mouse_pan_active = True
            self.mouse_pan_start = pygame.mouse.get_pos()
            self.cam_start_at_drag = (self.cam_x, self.cam_y)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 2:
            self.mouse_pan_active = False
        elif e.type == pygame.MOUSEMOTION and self.mouse_pan_active:
            mx, my = e.pos
            dx = mx - self.mouse_pan_start[0]
            dy = my - self.mouse_pan_start[1]
            self.cam_x = self.cam_start_at_drag[0] - dx
            self.cam_y = self.cam_start_at_drag[1] - dy

    def update(self, dt, keys=None):
        if keys is None:
            keys = pygame.key.get_pressed()
        speed = (self.pan_keys_speed / max(self.zoom, 0.1)) * dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.cam_x -= speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.cam_x += speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.cam_y -= speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.cam_y += speed

    # --- RENDU ---
    def render(self, screen):
        if not self.world:
            return

        dx, dy, dz = self.base_dx * self.zoom, self.base_dy * self.zoom, self.base_dz * self.zoom
        W, H = self.world.width, self.world.height

        for y in range(H):
            for x in range(W):
                levels = self.world.levels[y][x]
                gid = self.world.ground_id[y][x]
                for z in range(levels):
                    sx, sy = self.world_to_screen(x, y, z, dx, dy, dz)
                    sx = sx - self.cam_x + self.screen_w / 2
                    sy = sy - self.cam_y + self.screen_h / 2
                    img = self._get_scaled_ground(gid)
                    screen.blit(img, (sx - img.get_width() // 2, sy - img.get_height()))
                pid = self.world.overlay[y][x]
                if pid:
                    prop = self._get_scaled_prop(pid)
                    if prop:
                        sx, sy = self.world_to_screen(x, y, levels, dx, dy, dz)
                        sx = sx - self.cam_x + self.screen_w / 2
                        sy = sy - self.cam_y + self.screen_h / 2
                        screen.blit(prop, (sx - prop.get_width() // 2, sy - prop.get_height()))

    # --- COORDONNÉES ---
    def world_to_screen(self, x, y, z, dx=None, dy=None, dz=None):
        if dx is None: dx = self.base_dx * self.zoom
        if dy is None: dy = self.base_dy * self.zoom
        if dz is None: dz = self.base_dz * self.zoom
        sx = (x - y) * dx
        sy = (x + y) * dy - z * dz
        return sx, sy

    # --- ZOOM ---
    def _apply_zoom(self, direction):
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + direction * self.zoom_step))
        if abs(new_zoom - self.zoom) > 1e-6:
            self.zoom = new_zoom
            self._ground_cache.clear()
            self._prop_cache.clear()

    # --- ASSETS ---
    def _zoom_key(self): return int(round(self.zoom * 100))
    def _get_scaled_ground(self, gid):
        key = (gid, self._zoom_key())
        surf = self._ground_cache.get(key)
        if surf: return surf
        name = get_ground_sprite_name(gid)
        base = self.assets.get_image(name)
        scale = (int(base.get_width() * self.zoom), int(base.get_height() * self.zoom))
        surf = pygame.transform.smoothscale(base, scale).convert_alpha()
        self._ground_cache[key] = surf
        return surf
    def _get_scaled_prop(self, pid):
        key = (pid, self._zoom_key())
        surf = self._prop_cache.get(key)
        if surf: return surf
        name = get_prop_sprite_name(pid)
        if not name: return None
        base = self.assets.get_image(name)
        scale = (int(base.get_width() * self.zoom), int(base.get_height() * self.zoom))
        surf = pygame.transform.smoothscale(base, scale).convert_alpha()
        self._prop_cache[key] = surf
        return surf
