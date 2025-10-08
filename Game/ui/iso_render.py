# ui/iso_render.py
from __future__ import annotations
import pygame, math
from typing import Optional, Tuple

# Fallbacks si helpers indisponibles
try:
    from world.tiles import get_ground_sprite_name
except Exception:
    def get_ground_sprite_name(gid: int) -> str:
        return {
            0:"tile_ocean",1:"tile_beach",2:"tile_grass",3:"tile_forest",
            4:"tile_rock",5:"tile_taiga",6:"tile_desert",7:"tile_rainforest",8:"tile_steppe"
        }.get(gid, "tile_grass")

try:
    from world.ressource import get_prop_sprite_name
except Exception:
    def get_prop_sprite_name(pid: int) -> Optional[str]:
        return {10:"prop_tree", 11:"prop_rock", 12:"prop_bush"}.get(pid)

class IsoMapView:
    def __init__(self, assets, screen_size: Tuple[int,int],
                 min_zoom=0.7, max_zoom=2.0, zoom_step=0.1):
        self.assets = assets
        self.screen_w, self.screen_h = screen_size

        # valeurs par défaut (seront recalibrées)
        self.base_dx = 32.0
        self.base_dy = 16.0
        self.base_dz = 24.0

        self.zoom = 1.0
        self.min_zoom, self.max_zoom, self.zoom_step = min_zoom, max_zoom, zoom_step

        self.cam_x = 0.0
        self.cam_y = 0.0

        self.world = None
        self.max_levels = 6

        self._ground_cache = {}
        self._prop_cache   = {}

        self.pan_keys_speed = 600
        self.mouse_pan_active = False
        self.mouse_pan_start = (0, 0)
        self.cam_start_at_drag = (0.0, 0.0)

        # Auto-calibrage depuis un sprite "sol" de référence
        self._autocalibrate_from_sprite_key("tile_grass")

    # ---------- Calibration ----------
    def _autocalibrate_from_sprite_key(self, key: str):
        try:
            img = self.assets.get_image(key)
            w, h = img.get_width(), img.get_height()
            # 2:1 ISO → dy = dx/2 ; dx = w/2 (distance entre centres adjacents)
            dx = w * 0.5
            dy = dx * 0.5
            # “mur” vertical = hauteur totale - hauteur losange (≈ 2*dy)
            dz = max(1.0, h - 2.0*dy)
            self.base_dx, self.base_dy, self.base_dz = dx, dy, dz
            # print(f"[ISO CAL] dx={dx:.1f}, dy={dy:.1f}, dz={dz:.1f} from '{key}' ({w}x{h})")
        except Exception:
            # garde les defaults si l'image n'existe pas
            pass

    # ---------- State ----------
    def set_world(self, world) -> None:
        self.world = world
        self.max_levels = max(max(row) for row in world.levels) if world.levels else 6

        # centre la caméra SUR le spawn, puis on recentre au blit (screen_w/2, screen_h/2)
        sx, sy = self.world_to_screen(world.spawn[0], world.spawn[1], 0)
        self.cam_x, self.cam_y = sx, sy

    # ---------- Input ----------
    def handle_event(self, e: pygame.event.EventType) -> None:
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

    def update(self, dt: float, keys=None) -> None:
        if keys is None: keys = pygame.key.get_pressed()
        speed = (self.pan_keys_speed / max(self.zoom, 0.1)) * dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.cam_x -= speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.cam_x += speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:    self.cam_y -= speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  self.cam_y += speed

    # ---------- Render ----------
    def render(self, screen: pygame.Surface) -> None:
        if not self.world: return

        dx = self.base_dx * self.zoom
        dy = self.base_dy * self.zoom
        dz = self.base_dz * self.zoom

        W, H = self.world.width, self.world.height

        # ordre iso: diagonales s = x+y
        s_min, s_max = 0, (W - 1) + (H - 1)
        for s in range(s_min, s_max + 1):
            x_start = max(0, s - (H - 1))
            x_end   = min(W - 1, s)
            for x in range(x_start, x_end + 1):
                y = s - x
                levels = self.world.levels[y][x]
                gid    = self.world.ground_id[y][x]

                # piles de sols
                for z in range(levels):
                    sx, sy = self.world_to_screen(x, y, z, dx, dy, dz)
                    sx = sx - self.cam_x + self.screen_w * 0.5
                    sy = sy - self.cam_y + self.screen_h * 0.5
                    img = self._get_scaled_ground(gid)
                    screen.blit(img, (sx - img.get_width() * 0.5, sy - img.get_height()))

                # overlay sur le sommet
                pid = self.world.overlay[y][x]
                if pid:
                    prop = self._get_scaled_prop(pid)
                    if prop:
                        sx, sy = self.world_to_screen(x, y, max(levels, 0), dx, dy, dz)
                        sx = sx - self.cam_x + self.screen_w * 0.5
                        sy = sy - self.cam_y + self.screen_h * 0.5
                        screen.blit(prop, (sx - prop.get_width() * 0.5, sy - prop.get_height()))

    # ---------- Projection ----------
    def world_to_screen(self, x: float, y: float, z: float,
                        dx: Optional[float]=None, dy: Optional[float]=None, dz: Optional[float]=None) -> Tuple[float,float]:
        if dx is None: dx = self.base_dx * self.zoom
        if dy is None: dy = self.base_dy * self.zoom
        if dz is None: dz = self.base_dz * self.zoom
        # projection iso 2:1
        sx = (x - y) * dx
        sy = (x + y) * dy - z * dz
        return sx, sy

    # ---------- Zoom ----------
    def _apply_zoom(self, direction: int) -> None:
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + direction * self.zoom_step))
        if abs(new_zoom - self.zoom) < 1e-6: return
        self.zoom = new_zoom
        self._ground_cache.clear(); self._prop_cache.clear()

    # ---------- Assets ----------
    def _zoom_key(self) -> int:
        return int(round(self.zoom * 100))

    def _get_scaled_ground(self, gid: int) -> pygame.Surface:
        key = (gid, self._zoom_key())
        surf = self._ground_cache.get(key)
        if surf is not None: return surf
        name = get_ground_sprite_name(gid)
        base = self.assets.get_image(name)
        scale = (int(base.get_width()*self.zoom), int(base.get_height()*self.zoom))
        surf = pygame.transform.smoothscale(base, scale).convert_alpha()
        self._ground_cache[key] = surf
        return surf

    def _get_scaled_prop(self, pid: int) -> Optional[pygame.Surface]:
        key = (pid, self._zoom_key())
        surf = self._prop_cache.get(key)
        if surf is not None: return surf
        name = get_prop_sprite_name(pid)
        if not name: return None
        base = self.assets.get_image(name)
        scale = (int(base.get_width()*self.zoom), int(base.get_height()*self.zoom))
        surf = pygame.transform.smoothscale(base, scale).convert_alpha()
        self._prop_cache[key] = surf
        return surf

