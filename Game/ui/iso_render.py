# ui/iso_render.py
from __future__ import annotations
import pygame
import math
from typing import Optional, Tuple

# Fallbacks si helpers indisponibles
from Game.world.tiles import get_ground_sprite_name


def get_prop_sprite_name(pid: int) -> Optional[str]:
    mapping = {
        8: "prop_tree_3",
        9: "prop_tree_1",
        10: "prop_tree_2",
        12: "prop_tree_dead",
        13: "prop_rock",
        14: "prop_palm",
        15: "prop_cactus",
        16: "prop_bush",
        17: "prop_berry_bush",
        18: "prop_reeds",
        19: "prop_driftwood",
        20: "prop_flower",
        21: "prop_stump",
        22: "prop_log",
        23: "prop_boulder",
        25:"prop_flower2",
        26:"prop_flower3",
        102: "craft_entrepot",
        28: "prop_blueberry_bush",
        29: "prop_rock",
        30: "prop_rock",
        31: "prop_rock",
        32: "prop_clay",
        33: "prop_vine",
        34: "prop_mushroom1",
        35: "prop_mushroom2",
        36: "prop_mushroom3", 
        37: "prop_stump",
        38: "prop_bush",
        39: "prop_tree_2",
        40: "prop_reeds",
    }
    
    return mapping.get(pid, "prop_tree_2")

class IsoMapView:
    def __init__(self, assets, screen_size: Tuple[int,int],zoom_step=0.1):
        self.assets = assets
        self.screen_w, self.screen_h = screen_size
        self.click_lift_factor = 0.6  # proportion de dy à soustraire au clic (0.3–0.8)
        # valeurs par défaut (seront recalibrées)
        self.base_dx = 32.0
        self.base_dy = 16.0
        self.base_dz = 24.0

        self.zoom = 1.0
        self.zoom_step = zoom_step

        self.cam_x = 0
        self.cam_y = 0
        self.zoom = 1.5
        self.min_zoom = 1.0
        self.max_zoom = 5.0

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
        self._gray_ground_cache = {}
        self._gray_prop_cache = {}
        self._missing_ground_ids: set[int] = set()
        self._missing_ground_sprites: set[str] = set()

        self.pan_keys_speed = 600
        self.mouse_pan_active = False
        self.mouse_pan_start = (0, 0)
        self.cam_start_at_drag = (0.0, 0.0)

        self.cull_pad_tiles = 6          # marge en cases autour des coins (au lieu de 2)
        self.cull_prop_extra_tiles = 3   # marge pour la hauteur des props
        self.cull_screen_margin_px = None 

        self._hit_stack = []      # pile (kind, payload, rect, mask) pour le picking
        self._mask_cache = {}     # cache de pygame.Mask par Surface (id)
        self._diamond_mask = None # mask losange pour la surface des tuiles

        # Transparence des props
        self.props_transparent = False
        self.transparent_prop_alpha = 90
        self.default_prop_alpha = 255

        # LOD: masquer props/entités si zoom trop faible
        self.lod_props_min_zoom = 1.2
        self.lod_entities_min_zoom = 1.3


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
    
    def _make_gray(self, surf):
        # convertir en array RGB
        arr = pygame.surfarray.pixels3d(surf).copy()

        # gris foncé (40% du niveau de luminosité)
        avg = ((arr[:,:,0] * 0.3 + arr[:,:,1] * 0.59 + arr[:,:,2] * 0.11) * 0.4).astype(arr.dtype)

        arr[:,:,0] = avg
        arr[:,:,1] = avg
        arr[:,:,2] = avg

        # créer surface et réinjecter alpha
        gray = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.surfarray.blit_array(gray, arr)

        # récupérer alpha original
        alpha = pygame.surfarray.pixels_alpha(surf)
        pygame.surfarray.pixels_alpha(gray)[:] = alpha

        return gray



    # ---------- State ----------
    def set_world(self, world) -> None:
        self.world = world
        self.max_levels = int(getattr(world, "tiles_levels", 6) or 6)

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
        if keys[pygame.K_LEFT]:  self.cam_x -= speed
        if keys[pygame.K_RIGHT]: self.cam_x += speed
        if keys[pygame.K_UP]:    self.cam_y -= speed
        if keys[pygame.K_DOWN]:  self.cam_y += speed

    # ---------- Toggle props transparency ----------
    def set_props_transparency(self, transparent: bool, alpha: int | None = None) -> None:
        self.props_transparent = transparent
        if alpha is not None:
            self.transparent_prop_alpha = alpha

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

        # 1) coins écran -> approx (i,j) au niveau z=0
        corners = [(0,0), (self.screen_w,0), (0,self.screen_h), (self.screen_w,self.screen_h)]
        ii, jj = [], []
        for sx, sy in corners:
            i, j = self._screen_to_world_floor(sx, sy, dx, dy)
            ii.append(i); jj.append(j)

        i_min = min(ii); i_max = max(ii)
        j_min = min(jj); j_max = max(jj)

        # 2) marge supplémentaire en cases :
        #    - padding fixe (culling)
        #    - compensation relief (les "murs" font remonter/descendre visuellement)
        #    - props qui peuvent dépasser
        pad = int(self.cull_pad_tiles)

        # combien de cases « verticales » pour couvrir un mur de hauteur wall_h ?
        # 1 pas vertical ≈ 2*dy en pixels (car sy += (i+j)*dy)
        relief_extra = int(math.ceil((wall_h / max(2*dy, 1e-6)) + 1))

        total_pad = pad + relief_extra + int(self.cull_prop_extra_tiles)

        i_min = max(0, i_min - total_pad)
        j_min = max(0, j_min - total_pad)
        i_max = min(W-1, i_max + total_pad)
        j_max = min(H-1, j_max + total_pad)

        return i_min, i_max, j_min, j_max, dx, dy, wall_h
    
        # ---------- Picking: pile de hit ----------
    def begin_hitframe(self):
        """À appeler au début du frame (avant tout dessin) pour vider la pile."""
        self._hit_stack.clear()

    def _mask_for_surface(self, surf: pygame.Surface) -> pygame.mask.Mask:
        key = id(surf)
        m = self._mask_cache.get(key)
        if m is None:
            m = pygame.mask.from_surface(surf)
            self._mask_cache[key] = m
        return m

    def _diamond_mask_for(self, w: int, h: int) -> pygame.mask.Mask:
        """Mask losange de taille (w,h) pour la 'surface' d'une tuile."""
        if (self._diamond_mask is None) or (self._diamond_mask.get_size() != (w, h)):
            tmp = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(tmp, (255,255,255,255), [(w//2,0),(w-1,h//2),(w//2,h-1),(0,h//2)])
            self._diamond_mask = pygame.mask.from_surface(tmp)
        return self._diamond_mask

    def push_hit(self, kind: str, payload, rect: pygame.Rect, mask: pygame.mask.Mask | None):
        """Empile un 'objet cliquable' dessiné à l'écran, dans l'ordre de dessin."""
        self._hit_stack.append((kind, payload, rect, mask))

    def pick_at(self, x: int, y: int):
        """Retourne (kind, payload) du premier objet sous (x,y), en partant du haut."""
        for kind, payload, rect, mask in reversed(self._hit_stack):
            if not rect.collidepoint(x, y):
                continue
            if mask is None:
                return kind, payload
            lx, ly = x - rect.x, y - rect.y
            if 0 <= lx < rect.w and 0 <= ly < rect.h:
                if lx < mask.get_size()[0] and ly < mask.get_size()[1]:
                    if mask.get_at((lx, ly)):
                        return kind, payload
        return None

    def tile_surface_poly(self, i: int, j: int) -> list[tuple[int,int]]:
        """Retourne les 4 points écran (losange) de la surface de la tuile (i,j)."""
        if not self.world: return []
        dx, dy, wall_h = self._proj_consts()
        # altitude si dispo
        z = 0
        try:
            if getattr(self.world, "levels", None):
                z = int(self.world.levels[j][i])
        except Exception:
            z = 0
        cx, cy = self._world_to_screen(i, j, z, dx, dy, wall_h)
        surface_y = cy - int(dy * 2)  # même ‘plateau’ que dans render()
        return [(cx, surface_y - dy), (cx + dx//2, surface_y), (cx, surface_y + dy), (cx - dx//2, surface_y)]

    def prop_draw_rect(self, i: int, j: int, pid: int) -> pygame.Rect | None:
        """Recalcule le rect écran exact du prop (mêmes formules que le render)."""
        if not self.world: return None
        dx, dy, wall_h = self._proj_consts()
        # ground pour positionner la 'surface'
        try:
            gid = self.world.ground_id[j][i]
        except Exception:
            gid = None
        gimg = self._get_scaled_ground(gid) if gid is not None else None
        z = 0
        try:
            if getattr(self.world, "levels", None):
                z = int(self.world.levels[j][i])
        except Exception:
            z = 0
        cx, cy = self._world_to_screen(i, j, z, dx, dy, wall_h)
        surface_y = cy - (gimg.get_height() - int(dy * 2)) if gimg else cy - int(dy * 2)

        pimg = self._get_scaled_prop(pid)
        if not pimg: return None
        psx = int(cx - pimg.get_width() // 2)
        psy = int(surface_y - (pimg.get_height() - 2 * dy))
        return pygame.Rect(psx, psy, pimg.get_width(), pimg.get_height())

    def _build_entity_index(self, world_entities):
        if not world_entities:
            return {}
        entity_map: dict[tuple[int, int], list] = {}
        for e in world_entities:
            key = (int(e.x), int(e.y))
            entity_map.setdefault(key, []).append(e)
        return entity_map

    def _build_fog_cache(self, i_min: int, i_max: int, j_min: int, j_max: int):
        if not (hasattr(self, "fog") and self.fog):
            return None
        fog_cache: dict[tuple[int, int], tuple[bool, bool]] = {}
        for j in range(j_min, j_max + 1):
            for i in range(i_min, i_max + 1):
                fog_cache[(i, j)] = (self.fog.is_visible(i, j), self.fog.is_explored(i, j))
        return fog_cache

    def _build_visible_bands(self, i_min: int, i_max: int, j_min: int, j_max: int):
        bands = []
        for s in range(i_min + j_min, i_max + j_max + 1):
            i0 = max(i_min, s - j_max)
            i1 = min(i_max, s - j_min)
            bands.append((i0, i1, s))
        return bands

    def render(self, screen, after_tile_cb=None,world_entities=None):
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
        entity_map = self._build_entity_index(world_entities)
        fog_cache = self._build_fog_cache(i_min, i_max, j_min, j_max)
        draw_props = self.zoom >= self.lod_props_min_zoom
        draw_entities = self.zoom >= self.lod_entities_min_zoom

        # ORDRE ISO: (i+j) croissant pour empilements corrects
        for i0, i1, s in self._build_visible_bands(i_min, i_max, j_min, j_max):
            for i in range(i0, i1 + 1):
                j = s - i
                # on vérifie qu’on reste dans la carte
                if not (0 <= i < W and 0 <= j < H):
                    continue

                if fog_cache is not None:
                    visible, explored = fog_cache.get((i, j), (True, True))
                else:
                    visible = True
                    explored = True

                if not explored:
                    continue  # jamais vu → noir total

                
                

                if hasattr(self.world, "get_tile_snapshot"):
                    tile_snap = self.world.get_tile_snapshot(i, j, generate=True)
                    if tile_snap is None:
                        continue
                    z, gid, cell, _bid = tile_snap
                else:
                    z = self.world.levels[j][i] if self.world.levels else 0
                    gid = self.world.ground_id[j][i]
                    cell = self.world.overlay[j][i]
                sx, sy = self._world_to_screen(i, j, z, dx, dy, wall_h)

                if sx < -200 or sx > self.screen_w + 200 or sy < -300 or sy > self.screen_h + 300:
                    continue

                # sol
                # sol
                gray = (not visible)
                gimg = self._get_scaled_ground(gid, gray=gray)
                
                if gimg:
                    screen.blit(gimg, (sx - gimg.get_width() // 2, sy - gimg.get_height() + dy * 2))
                
                # --- HIT: tuile (surface losange) ---
                surface_y = sy - (gimg.get_height() - int(dy * 2))     # y du plateau losange
                tile_mask = self._diamond_mask_for(int(dx), int(dy))
                mw, mh = tile_mask.get_size()
                tile_rect = pygame.Rect(int(sx - mw//2), int(surface_y - mh//2), mw, mh)
                self.push_hit("tile", (i, j), tile_rect, tile_mask)


                if callable(after_tile_cb):
                    after_tile_cb(i, j, sx, sy, dx, dy, wall_h)
                # props
                if draw_entities and entity_map:
                    for e in entity_map.get((i, j), []):
                        # dessiner l’entité maintenant => insérée dans le pipeline iso
                        e.draw(screen, self, self.world)

                # --- PROP DE LA TUILE ---
                if draw_props:
                    pid = cell.get("pid") if isinstance(cell, dict) else cell
                    if pid:
                        gray = (not visible)
                        alpha = self.transparent_prop_alpha if self.props_transparent else self.default_prop_alpha
                        if isinstance(cell, dict) and cell.get("state") == "building":
                            alpha = int(alpha * 0.65)
                        pimg = self._get_scaled_prop(pid, gray=gray, alpha=alpha)
                        if pimg:
                            surface_y = sy - (gimg.get_height() - dy * 2)
                            psx = sx - pimg.get_width() // 2
                            psy = surface_y - (pimg.get_height() - dy * 2)
                            screen.blit(pimg, (psx, psy))
                            prop_rect = pygame.Rect(psx, psy, pimg.get_width(), pimg.get_height())
                            prop_mask = self._mask_for_surface(pimg)
                            self.push_hit("prop", (i, j, pid), prop_rect, prop_mask)


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

   
    def _get_scaled_ground(self, gid: int, gray=False):
        key = (gid, self._zoom_key(), gray)
        cache = self._gray_ground_cache if gray else self._ground_cache

        surf = cache.get(key)
        if surf:
            return surf

        try:
            name = get_ground_sprite_name(gid)
        except Exception:
            if gid not in self._missing_ground_ids:
                print(f"[Tiles] ID sol inconnu: {gid} -> fallback tile_grass")
                self._missing_ground_ids.add(gid)
            name = "tile_grass"
        try:
            base = self.assets.get_image(name)
        except Exception:
            if name not in self._missing_ground_sprites:
                print(f"[Tiles] Sprite sol manquant: {name} -> fallback tile_grass")
                self._missing_ground_sprites.add(name)
            base = self.assets.get_image("tile_grass")
        scale = (int(base.get_width()*self.zoom), int(base.get_height()*self.zoom))
        surf = pygame.transform.scale(base, scale).convert_alpha()

        if gray:
            surf = self._make_gray(surf)

        cache[key] = surf
        return surf



    def _get_scaled_prop(self, pid: int, gray=False, alpha: int | None = None) -> Optional[pygame.Surface]:
        if alpha is None:
            alpha = self.default_prop_alpha
        key = (pid, self._zoom_key(), gray, alpha)
        cache = self._gray_prop_cache if gray else self._prop_cache

        surf = cache.get(key)
        if surf is not None:
            return surf

        name = get_prop_sprite_name(pid)
        base = self.assets.get_image(name)

        scale = (int(base.get_width() * self.zoom), int(base.get_height() * self.zoom))
        surf = pygame.transform.scale(base, scale).convert_alpha()

        if gray:
            surf = self._make_gray(surf)

        surf.set_alpha(alpha)
        cache[key] = surf
        return surf


    def pick_tile_at(self, sx: int, sy: int):
        """
        Renvoie (i, j) de la tuile *visible* sous le pixel écran (sx, sy),
        en respectant l'ordre de peinture isométrique + la hauteur (murs).
        Retourne None si rien de valide.
        """
        if not self.world:
            return None

        W, H = self.world.width, self.world.height
        dx, dy, wall_h = self._proj_consts()

        # Estimation (i0, j0) sur plan z≈0 pour restreindre la recherche
        i0, j0 = self._screen_to_world_floor(sx, sy, dx, dy)

        # Petite fenêtre locale autour du point (suffisante même avec relief)
        r = max(6, int(2 + self.max_levels))  # augmente si besoin
        i_min = max(0, i0 - r)
        i_max = min(W - 1, i0 + r)
        j_min = max(0, j0 - r)
        j_max = min(H - 1, j0 + r)

        picked = None  # on garde la DERNIÈRE tuile touchée (celle dessinée au-dessus)

        # Parcours dans le même ordre que le rendu (painter’s algorithm)
        for s in range(i_min + j_min, i_max + j_max + 1):
            i_start = max(i_min, s - j_max)
            i_end   = min(i_max, s - j_min)
            for i in range(i_start, i_end + 1):
                j = s - i
                if not (0 <= j < H):
                    continue

                z = self.world.levels[j][i] if self.world.levels else 0
                cx, cy = self._world_to_screen(i, j, z, dx, dy, wall_h)

                # Sprite du sol tel qu'il est réellement blitté
                gid  = self.world.ground_id[j][i]
                gimg = self._get_scaled_ground(gid)
                if not gimg:
                    continue

                w, h = gimg.get_width(), gimg.get_height()

                # Top-left de l'image au blit (même formule que render)
                tlx = cx - w // 2
                tly = cy - h + int(dy * 2)
                rect = pygame.Rect(tlx, tly, w, h)

                # Si le pixel n'est pas dans le rectangle de l'image → skip rapide
                if not rect.collidepoint(sx, sy):
                    continue

                # Centre du losange (surface), identique à ce que le rendu utilise
                surface_y = cy - (h - int(dy * 2))  # ≈ cy - wall_h

                # Test précis sur la surface losange OU sur le mur vertical :
                # - Losange: |dx|/DX + |dy|/DY <= 1
                in_top = (abs(sx - cx) / max(dx, 1e-6) + abs(sy - surface_y) / max(dy, 1e-6)) <= 1.0
                # - Mur: rectangle entre la surface et la base (zone "noire"/opaque)
                in_wall = (surface_y < sy <= cy and abs(sx - cx) <= dx)

                if in_top or in_wall:
                    picked = (i, j)  # on continue pour garder la *dernière* (au-dessus)

        return picked

    def place_craft(self, i: int, j: int, pid: int):
        """Place directement un prop-id sur la tuile (i,j)."""
        if not self.world:
            return
        if 0 <= i < self.world.width and 0 <= j < self.world.height:
            self.world.overlay[j][i] = pid
