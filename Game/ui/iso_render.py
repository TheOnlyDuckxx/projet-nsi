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
        return {10:"prop_tree_2", 11:"prop_rock", 12:"prop_bush"}.get(pid)

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

        self.cam_x = 0
        self.cam_y = 0
        self.zoom = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 3.0

        # métriques écran (fallback si display pas encore créé)
        try:
            sw, sh = pygame.display.get_surface().get_size()
        except Exception:
            sw, sh = (1280, 720)

        self.screen_w = sw
        self.screen_h = sh
        self.cx = sw // 2
        self.cy = sh // 2

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
    def _proj_consts(self):
        # à appeler à chaque frame AVANT le rendu (zoom peut changer)
        base = self.assets.get_image("tile_grass")
        tw, th = base.get_width(), base.get_height()
        dx = (tw * 0.5) * self.zoom
        dy = dx * 0.5
        wall_h = max(0, th * self.zoom - dy*2)  # si tu as des “murs” verticaux
        return dx, dy, wall_h

    def _world_to_screen(self, i, j, z, dx, dy, wall_h):
        sx = self.cx + (i - j) * dx - self.cam_x
        sy = self.cy + (i + j) * dy - self.cam_y - z * wall_h
        return int(sx), int(sy)

    def _screen_to_world_floor(self, sx, sy, dx, dy):
        # inversion approx (z=0)
        x = sx - self.cx + self.cam_x
        y = sy - self.cy + self.cam_y
        if dx <= 0 or dy <= 0:
            return 0, 0
        i = int((x/(2*dx)) + (y/(2*dy)))
        j = int((y/(2*dy)) - (x/(2*dx)))
        return i, j

    def _visible_bounds(self, W, H):
        dx, dy, wall_h = self._proj_consts()
        corners = [(0,0),(self.screen_w,0),(0,self.screen_h),(self.screen_w,self.screen_h)]
        ii, jj = [], []
        for sx, sy in corners:
            i, j = self._screen_to_world_floor(sx, sy, dx, dy)
            ii.append(i); jj.append(j)
        i_min = max(0, min(ii) - 2)
        j_min = max(0, min(jj) - 2)
        i_max = min(W-1, max(ii) + 2)
        j_max = min(H-1, max(jj) + 2)
        return i_min, i_max, j_min, j_max, dx, dy, wall_h

    def render(self, screen):
        if not self.world: return
        W, H = self.world.width, self.world.height
        i_min, i_max, j_min, j_max, dx, dy, wall_h = self._visible_bounds(W, H)
        sw, sh = screen.get_size()
        if (sw != self.screen_w) or (sh != self.screen_h):
            self.screen_w, self.screen_h = sw, sh
            self.cx = sw // 2
            self.cy = sh // 2

        if not self.world:
            return
        # ORDRE ISO: (i+j) croissant pour empilements corrects
        for s in range(i_min + j_min, i_max + j_max + 1):
            i0 = max(i_min, s - j_max)
            i1 = min(i_max, s - j_min)
            for i in range(i0, i1 + 1):
                j = s - i
                # on vérifie qu’on reste dans la carte
                if not (0 <= i < W and 0 <= j < H):
                    continue

                z = self.world.levels[j][i] if self.world.levels else 0
                sx, sy = self._world_to_screen(i, j, z, dx, dy, wall_h)

                if sx < -200 or sx > self.screen_w + 200 or sy < -300 or sy > self.screen_h + 300:
                    continue

                # sol
                gid = self.world.ground_id[j][i]
                gimg = self._get_scaled_ground(gid)
                if gimg:
                    screen.blit(gimg, (sx - gimg.get_width() // 2, sy - gimg.get_height() + dy * 2))

                # props
                pid = self.world.overlay[j][i]
                if pid:
                    pimg = self._get_scaled_prop(pid)
                    if pimg:
                        # 1) y de la "surface" (haut du mur vertical de la tuile de sol)
                        surface_y = sy - (gimg.get_height() - dy * 2)

                        # 2) on pose le prop sur cette surface
                        psx = sx - pimg.get_width() // 2
                        psy = surface_y - (pimg.get_height() - dy * 2)  # même logique d’ancrage que les tuiles

                        if not (psx < -200 or psx > self.screen_w + 200 or psy < -300 or psy > self.screen_h + 300):
                            screen.blit(pimg, (psx, psy))

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
    def _apply_zoom(self, wheel_dir: int) -> None:
        """
        wheel_dir > 0  : zoom avant
        wheel_dir < 0  : zoom arrière
        """
        # 1) point monde sous la souris AVANT zoom
        dx, dy, _ = self._proj_consts()
        mx, my = pygame.mouse.get_pos()
        i0, j0 = self._screen_to_world_floor(mx, my, dx, dy)

        # 2) calcule le nouveau zoom avec un facteur
        #    ex: step=0.1 -> facteur = 1.1 ; dézoom = 1/1.1
        factor = 1.0 + float(self.zoom_step)
        if wheel_dir > 0:
            new_zoom = min(self.zoom * factor, self.max_zoom)
        else:
            new_zoom = max(self.zoom / factor, self.min_zoom)

        # si rien ne change (déjà à la borne), on quitte
        if abs(new_zoom - self.zoom) < 1e-6:
            return

        old_zoom = self.zoom
        self.zoom = new_zoom

        # 3) recalcule les constantes proj APRÈS zoom
        dx2, dy2, _ = self._proj_consts()

        # 4) ajuste la caméra pour que (i0,j0) reste sous le curseur
        sx0, sy0 = self._world_to_screen(i0, j0, 0, dx2, dy2, 0)
        self.cam_x += (sx0 - mx)
        self.cam_y += (sy0 - my)


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
        surf = pygame.transform.scale(base, scale).convert_alpha()
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
        surf = pygame.transform.scale(base, scale).convert_alpha()
        self._prop_cache[key] = surf
        return surf

