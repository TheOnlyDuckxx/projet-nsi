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
    """
    Rendu isométrique avec:
      - caméra (pan)
      - zoom (nombre de cases dans la fenêtre change, pas la résolution)
      - culling
      - ordre de peinture iso (x+y, puis z)
    """
    def __init__(self, assets, screen_size: Tuple[int, int],
                 min_zoom: float = 0.6, max_zoom: float = 2.5, zoom_step: float = 0.1):
        """
        assets: ton gestionnaire d'assets avec get_asset(name) -> Surface
        screen_size: (W,H)
        zoom = facteur d’échelle des tuiles (1.0 = taille "de base")
        """
        self.assets = assets
        self.screen_w, self.screen_h = screen_size

        # Paramètres iso de base (avant zoom) — ajuste ces dimensions à tes sprites
        # dx/dy = demi-largeur/hauteur en pixel du losange au sol (face top)
        self.base_dx = 32   # demi-largeur horizontale du losange
        self.base_dy = 16   # demi-hauteur verticale du losange
        self.base_dz = 24   # élévation par étage (distance verticale entre niveaux)

        # Caméra au centre sur le spawn par défaut (définie à set_world si possible)
        self.cam_x = 0.0
        self.cam_y = 0.0

        # Zoom
        self.zoom = 1.0
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_step = zoom_step

        # Cache surfaces scalées par zoom
        self._ground_cache = {}   # (gid, zoom_round) -> Surface
        self._prop_cache = {}     # (pid, zoom_round) -> Surface

        # Monde
        self.world = None  # WorldData
        self.max_levels = 6

        # Contrôles caméra
        self.pan_keys_speed = 600  # px/s à zoom=1.0 (sera ajusté par zoom)
        self.mouse_pan_active = False
        self.mouse_pan_start = (0, 0)
        self.cam_start_at_drag = (0.0, 0.0)

    # ---------- API publique ----------
    def set_world(self, world) -> None:
        self.world = world
        self.max_levels = max(max(row) for row in world.levels) if world.levels else 6
        sx, sy = self.world_to_screen(world.spawn[0], world.spawn[1], 0)
        # Centrer caméra pile sur le spawn
        self.cam_x = sx - self.screen_w / 2
        self.cam_y = sy - self.screen_h / 2
        print(f"[DEBUG set_world] Spawn {world.spawn} => cam=({self.cam_x:.1f},{self.cam_y:.1f})")

    def handle_event(self, e: pygame.event.EventType) -> None:
        """Zoom molette / drag souris."""
        if e.type == pygame.MOUSEWHEEL:
            if e.y > 0:
                self._apply_zoom(1)
            elif e.y < 0:
                self._apply_zoom(-1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 2:  # clic milieu pour drag
            self.mouse_pan_active = True
            self.mouse_pan_start = pygame.mouse.get_pos()
            self.cam_start_at_drag = (self.cam_x, self.cam_y)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 2:
            self.mouse_pan_active = False
        elif e.type == pygame.MOUSEMOTION and self.mouse_pan_active:
            mx, my = e.pos
            dx = mx - self.mouse_pan_start[0]
            dy = my - self.mouse_pan_start[1]
            # drag = déplace la caméra inversement
            self.cam_x = self.cam_start_at_drag[0] - dx
            self.cam_y = self.cam_start_at_drag[1] - dy

    def update(self, dt: float, keys=None) -> None:
        """Pan clavier (WASD / flèches). dt en secondes."""
        if keys is None:
            keys = pygame.key.get_pressed()
        speed = (self.pan_keys_speed / max(self.zoom, 0.1)) * dt  # vitesse ajuste avec zoom
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.cam_x -= speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.cam_x += speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.cam_y -= speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.cam_y += speed

        # Zoom clavier (+/-)
        if keys[pygame.K_EQUALS] or keys[pygame.K_KP_PLUS]:
            self._apply_zoom(1)
        if keys[pygame.K_MINUS] or keys[pygame.K_KP_MINUS]:
            self._apply_zoom(-1)

    def render(self, screen: pygame.Surface) -> None:
        if self.world is None:
            return
        print(f"[DEBUG CAM] cam=({self.cam_x:.1f}, {self.cam_y:.1f}), zoom={self.zoom:.2f}")
        W, H = self.world.width, self.world.height
        dx, dy, dz = self.base_dx * self.zoom, self.base_dy * self.zoom, self.base_dz * self.zoom

        # Détermine les bornes visibles en se basant sur l’approx inverse iso
        xmin, ymin, xmax, ymax = self._visible_tile_bounds(dx, dy)
        xmin = max(0, xmin); ymin = max(0, ymin)
        xmax = min(W - 1, xmax); ymax = min(H - 1, ymax)

        # Rendu: balayage par diagonales s = x+y
        s_min = xmin + ymin
        s_max = xmax + ymax
        for s in range(s_min, s_max + 1):
            # pour chaque diag, on dessine les tuiles (x,y) où x+y = s
            x_start = max(xmin, s - ymax)
            x_end   = min(xmax, s - ymin)
            for x in range(x_start, x_end + 1):
                y = s - x
                # Sol: empiler les niveaux 0..levels-1
                levels = self.world.levels[y][x]
                ground_id = self.world.ground_id[y][x]
                gx, gy = self.world_to_screen(x, y, 0, dx, dy, dz)
                # dessiner chaque étage (z)
                for z in range(levels):
                    sx, sy = self.world_to_screen(x, y, z, dx, dy, dz)
                    ground_img = self._get_scaled_ground(ground_id)
                    # ancrage: supposons que l'image d'un étage repose "pile" sur sy
                    screen.blit(ground_img, (sx - ground_img.get_width()//2 - self.cam_x,
                         sy - ground_img.get_height() - self.cam_y))
                # Overlay au sommet de pile
                pid = self.world.overlay[y][x]
                if pid:
                    prop_img = self._get_scaled_prop(pid)
                    if prop_img:
                        # ancrage bas-centre sur le sommet du stack
                        sx, sy_top = self.world_to_screen(x, y, max(levels, 0), dx, dy, dz)
                        screen.blit(prop_img, (sx - prop_img.get_width()//2 - self.cam_x,
                                               sy_top - prop_img.get_height() + dy - self.cam_y))
        # ======== TEST AFFICHAGE TILE CENTRALE ========
        test_gid = 2  # herbe
        test_img = self._get_scaled_ground(test_gid)
        center_x, center_y = self.screen_w // 2, self.screen_h // 2
        screen.blit(test_img, (center_x - test_img.get_width() // 2, center_y - test_img.get_height() // 2))
        pygame.draw.circle(screen, (255, 0, 0), (center_x, center_y), 5)
        print("[DEBUG] Tuile test affichée au centre.")
        # ==============================================
                
    # ---------- Zoom ----------
    def _apply_zoom(self, direction: int) -> None:
        """direction: +1 zoom in, -1 zoom out. Conserve le point écran au centre."""
        old_zoom = self.zoom
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + direction * self.zoom_step))
        if abs(new_zoom - old_zoom) < 1e-6:
            return
        # Option: conserver le point au centre (ici on ne recalcule pas cam pour rester simple)
        self.zoom = new_zoom
        self._ground_cache.clear()
        self._prop_cache.clear()

    # ---------- Coordonnées ----------
    def world_to_screen(self, x: float, y: float, z: float,
                        dx: Optional[float]=None, dy: Optional[float]=None, dz: Optional[float]=None) -> Tuple[float, float]:
        """Convertit (x,y,z) grille -> coordonnées écran (avant soustraction caméra)."""
        if dx is None: dx = self.base_dx * self.zoom
        if dy is None: dy = self.base_dy * self.zoom
        if dz is None: dz = self.base_dz * self.zoom
        sx = (x - y) * dx + self.screen_w * 0.5
        sy = (x + y) * dy - z * dz + self.screen_h * 0.25
        return sx, sy

    def screen_to_world_approx(self, sx: float, sy: float) -> Tuple[float, float]:
        """
        Inverse approx (z=0), utile pour estimer le culling.
        On suppose une surface au sol (pas l’élévation).
        """
        dx, dy = self.base_dx * self.zoom, self.base_dy * self.zoom
        X = (sx - self.screen_w * 0.5 + self.cam_x) / dx
        Y = (sy - self.screen_h * 0.25 + self.cam_y) / dy
        # système:
        #  X = x - y
        #  Y = x + y
        x = 0.5 * (X + Y)
        y = 0.5 * (Y - X)
        return x, y

    def _visible_tile_bounds(self, dx: float, dy: float) -> Tuple[int, int, int, int]:
        """
        Renvoie (xmin,ymin,xmax,ymax) des tuiles visibles à l’écran (z=0 approx).
        On élargit un peu pour couvrir les piles et overlays.
        """
        margin = 2
        # coins écran → approx world coords (z=0)
        corners = [
            (0 + self.cam_x, 0 + self.cam_y),
            (self.screen_w + self.cam_x, 0 + self.cam_y),
            (0 + self.cam_x, self.screen_h + self.cam_y),
            (self.screen_w + self.cam_x, self.screen_h + self.cam_y),
        ]
        xs, ys = [], []
        for sx, sy in corners:
            wx, wy = self.screen_to_world_approx(sx, sy)
            xs.append(wx); ys.append(wy)
        xmin = math.floor(min(xs)) - margin
        xmax = math.ceil(max(xs)) + margin
        ymin = math.floor(min(ys)) - margin
        ymax = math.ceil(max(ys)) + margin
        return xmin, ymin, xmax, ymax

    # ---------- Assets scalés/cachés ----------
    def _zoom_key(self) -> int:
        """Clé discrète pour le cache d’images (évite de rescales à chaque frame)."""
        return int(round(self.zoom * 100))  # ex: 160 pour 1.60

    def _get_scaled_ground(self, gid: int) -> pygame.Surface:
        key = (gid, self._zoom_key())
        surf = self._ground_cache.get(key)
        if surf is not None:
            return surf
        name = get_ground_sprite_name(gid)
        base = self.assets.get_image(name)
        # Échelle selon dx/dy/dz: on suppose que l'asset de base colle à base_dx/dy/dz
        sx = self.zoom
        sy = self.zoom
        surf = pygame.transform.smoothscale(base, (int(base.get_width()*sx), int(base.get_height()*sy)))
        self._ground_cache[key] = surf.convert_alpha()
        return self._ground_cache[key]

    def _get_scaled_prop(self, pid: int) -> Optional[pygame.Surface]:
        key = (pid, self._zoom_key())
        surf = self._prop_cache.get(key)
        if surf is not None:
            return surf
        name = get_prop_sprite_name(pid)
        if not name:
            return None
        base = self.assets.get_image(name)
        sx = self.zoom
        sy = self.zoom
        surf = pygame.transform.smoothscale(base, (int(base.get_width()*sx), int(base.get_height()*sy)))
        self._prop_cache[key] = surf.convert_alpha()
        return self._prop_cache[key]
