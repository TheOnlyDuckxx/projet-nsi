# Game/espece/renderer.py
import colorsys
import pygame

DEFAULT_BLOB_COLOR = (70, 130, 220)

class SpriteSheet:
    """Spritesheet en grille (ici surtout 1 ligne)."""
    def __init__(self, sheet: pygame.Surface, frame_w: int, frame_h: int):
        self.sheet = sheet
        self.fw = frame_w
        self.fh = frame_h
        sw, sh = sheet.get_size()
        self.cols = max(1, sw // frame_w)
        self.rows = max(1, sh // frame_h)

    def get_frame(self, idx: int) -> pygame.Surface:
        col = idx % self.cols
        row = (idx // self.cols) % self.rows
        rect = pygame.Rect(col * self.fw, row * self.fh, self.fw, self.fh)
        return self.sheet.subsurface(rect).copy()

class EspeceRenderer:
    """
    Remplace l'ancien système par spritesheet + overlays.
    Interface conservée:
      - update_from_mutations()
      - get_draw_surface_and_rect(view, world, tx, ty)
      - render(screen, view, world, tx, ty)
    """
    BASE_SIZE = (20, 24)  # gardé pour placeholder + échelle "par défaut"
    # Certaines variantes n'utilisent pas la même hauteur de frame.
    VARIANT_FRAME_SIZES = {
        "bipede_blob_idle": (32, 40),
    }
    # Sheets utilisant la même palette que le blob de base (donc recolorisables).
    RECOLORABLE_SHEETS = {
        "base_blob_idle",
        "bipede_blob_idle",
    }

    def __init__(self, espece, assets):
        self.espece = espece
        self.assets = assets

        # --- config base spritesheet ---
        # Pour ne rien casser : si tu ne renseignes rien dans espece, ça marche quand même.
        self.sheet_key = getattr(espece, "sprite_sheet_key", "base_blob_idle")
        self.frame_w, self.frame_h = getattr(espece, "sprite_frame_size", (32, 32))

        # Animations (tu peux étendre plus tard)
        self.animations = getattr(espece, "sprite_anims", None) or {
            "idle": {"frames": [0, 1, 2, 3], "fps": 6.0, "loop": True},
        }
        self.current_anim = "idle"
        self._anim_start_ms = pygame.time.get_ticks()

        # Variants + overlays (mutations)
        self.base_variant_key = self.sheet_key  # peut changer si tu fais des spritesheets par variante
        self.overlay_keys = []

        # Caches
        self._sheet_cache = {}           # key -> SpriteSheet
        self._compose_cache = {}         # (variant, anim, frame_idx, overlays) -> (surface, anchor_x, anchor_y)
        self._scaled_cache = {}          # (compose_id, zoom_eff) -> surface

        # Pour compat éventuelle avec le reste (si quelque part tu touches renderer.layers)
        self.layers = {}
        # Appliquer tout de suite les variants/overlays liés aux mutations.
        self.update_from_mutations()

    # --------- helpers sûrs ----------
    def _placeholder_surface(self, size, label: str) -> pygame.Surface:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((255, 0, 255, 120))
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            f = pygame.font.SysFont("arial", 10)
            txt = f.render(label[:12], True, (0, 0, 0))
            surf.blit(txt, (2, 2))
        except Exception:
            pass
        return surf

    def _get_img(self, key: str, fallback_size=None) -> pygame.Surface:
        try:
            img = self.assets.get_image(key)
            if img is None:
                raise KeyError(key)
            return img
        except Exception:
            print(f"[Renderer] Asset manquant: {key}")
            if fallback_size is None:
                fallback_size = (self.frame_w, self.frame_h)
            return self._placeholder_surface(fallback_size, key)

    def _frame_size_for_variant(self, key: str) -> tuple[int, int]:
        # Par défaut: taille configurée sur l'espèce (souvent 32x32).
        # Certaines sheets ont une hauteur différente (ex: bipède 32x40).
        if key in self.VARIANT_FRAME_SIZES:
            return self.VARIANT_FRAME_SIZES[key]
        return (int(self.frame_w), int(self.frame_h))

    def _resolve_species_color_rgb(self) -> tuple[int, int, int]:
        # Cas preview: renderer branché directement sur une Espece.
        color = getattr(self.espece, "color_rgb", None)
        # Cas runtime: renderer branché sur un Individu -> self.espece.espece
        if color is None and hasattr(self.espece, "espece"):
            color = getattr(getattr(self.espece, "espece", None), "color_rgb", None)

        if isinstance(color, (list, tuple)) and len(color) == 3:
            try:
                r = max(0, min(255, int(color[0])))
                g = max(0, min(255, int(color[1])))
                b = max(0, min(255, int(color[2])))
                return (r, g, b)
            except Exception:
                pass
        return DEFAULT_BLOB_COLOR

    def _resolve_size_scale(self) -> float:
        phys = getattr(self.espece, "physique", None)
        if phys is None and hasattr(self.espece, "espece"):
            phys = getattr(getattr(self.espece, "espece", None), "base_physique", None)
        if phys is None and hasattr(self.espece, "base_physique"):
            phys = getattr(self.espece, "base_physique", None)
        try:
            taille = float((phys or {}).get("taille", 5) or 5)
        except Exception:
            taille = 5.0
        # 5 -> 1.0 ; 1 -> ~0.68 ; 10 -> ~1.4
        return max(0.55, min(1.6, 0.6 + 0.08 * taille))

    def _is_player_species(self) -> bool:
        if hasattr(self.espece, "espece"):
            return bool(getattr(getattr(self.espece, "espece", None), "is_player_species", False))
        return bool(getattr(self.espece, "is_player_species", False))

    def _recolor_base_blob_sheet(self, sheet: pygame.Surface, target_rgb: tuple[int, int, int]) -> pygame.Surface:
        # On garde le sprite original si on reste sur la couleur de base.
        if tuple(target_rgb) == tuple(DEFAULT_BLOB_COLOR):
            return sheet

        out = sheet.copy()
        w, h = out.get_size()
        tr, tg, tb = target_rgb

        for y in range(h):
            for x in range(w):
                r, g, b, a = out.get_at((x, y))
                if a <= 0:
                    continue
                # Ne pas toucher les contours noirs.
                if r <= 20 and g <= 20 and b <= 20:
                    continue
                # Masque HSV : inclut bleu + cyan (haut de tete), mais exclut contours/details.
                h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                hue = h * 360.0
                if not (150.0 <= hue <= 255.0 and s >= 0.20 and v >= 0.12):
                    continue

                shade = max(r, g, b) / 255.0
                # Les zones de highlight restent legerement plus claires que la base.
                highlight = max(0.0, (shade - 0.75) / 0.25)
                nr = max(0, min(255, int(tr * shade + (255 - tr) * highlight)))
                ng = max(0, min(255, int(tg * shade + (255 - tg) * highlight)))
                nb = max(0, min(255, int(tb * shade + (255 - tb) * highlight)))
                out.set_at((x, y), (nr, ng, nb, a))
        return out

    def _get_sheet(self, key: str) -> SpriteSheet:
        fw, fh = self._frame_size_for_variant(key)
        sheet_img = self._get_img(key, fallback_size=(fw, fh))

        if key in self.RECOLORABLE_SHEETS:
            color_rgb = self._resolve_species_color_rgb()
            cache_key = (key, color_rgb, fw, fh)
            if cache_key in self._sheet_cache:
                return self._sheet_cache[cache_key]
            sheet_img = self._recolor_base_blob_sheet(sheet_img, color_rgb)
        else:
            cache_key = (key, fw, fh)
            if cache_key in self._sheet_cache:
                return self._sheet_cache[cache_key]

        if cache_key in self._sheet_cache:
            return self._sheet_cache[cache_key]

        ss = SpriteSheet(sheet_img, fw, fh)
        self._sheet_cache[cache_key] = ss
        return ss

    # --------- animation ----------
    def set_animation(self, name: str, reset: bool = False):
        if name not in self.animations:
            return
        if self.current_anim != name or reset:
            self.current_anim = name
            self._anim_start_ms = pygame.time.get_ticks()
            # le rendu change => on invalide les caches de scale/compo
            self._compose_cache.clear()
            self._scaled_cache.clear()

    def _current_frame_index(self, now_ms: int) -> int:
        anim = self.animations.get(self.current_anim, self.animations["idle"])
        frames = anim["frames"]
        fps = max(0.1, float(anim.get("fps", 6.0)))
        loop = bool(anim.get("loop", True))

        if not frames:
            return 0

        elapsed = max(0, now_ms - self._anim_start_ms)
        frame_time = 1000.0 / fps
        step = int(elapsed // frame_time)

        if loop:
            return frames[step % len(frames)]
        return frames[min(step, len(frames) - 1)]

    # --------- mutations ----------
    def update_from_mutations(self):
        self.base_variant_key = self.sheet_key
        self.overlay_keys = []
        self._compose_cache.clear()
        self._scaled_cache.clear()

        # self.espece peut être un Individu (runtime) ou une Espece (preview)
        manager = getattr(self.espece, "mutations", None)
        base = getattr(self.espece, "base_mutations", None)
        if manager is None and hasattr(self.espece, "espece"):
            manager = getattr(getattr(self.espece, "espece", None), "mutations", None)
        if base is None and hasattr(self.espece, "espece"):
            base = getattr(getattr(self.espece, "espece", None), "base_mutations", None)

        muts = set()
        muts.update(getattr(manager, "actives", []) or [])
        muts.update(base or [])
        muts_lc = {str(x).strip().lower() for x in muts if str(x).strip()}

        # Mutations du JSON: "Semibipedie", "Bipedie", "Bipedie exclusive"
        if any(k in muts_lc for k in ("semibipedie", "bipedie", "bipedie exclusive")):
            self.base_variant_key = "bipede_blob_idle"

    # --------- composition ----------
    def _compose(self):
        now = pygame.time.get_ticks()
        frame_idx = self._current_frame_index(now)
        variant = self.base_variant_key
        overlays = tuple(self.overlay_keys)
        cache_key = (variant, self.current_anim, frame_idx, overlays)

        if cache_key in self._compose_cache:
            return self._compose_cache[cache_key]

        # Base frame
        ss = self._get_sheet(variant)
        base = ss.get_frame(frame_idx)
        bw, bh = base.get_size()

        blits = [(base, (0, 0))]

        # Overlays centrés sur la base
        for key in overlays:
            img = self._get_img(key, fallback_size=(bw, bh))
            offx, offy = OFFSETS.get(key, (0, 0))
            px = (bw - img.get_width()) // 2 + offx
            py = (bh - img.get_height()) // 2 + offy
            blits.append((img, (px, py)))

        # BBox pour éviter de couper ailes etc.
        minx = min(p[0] for _, p in blits)
        miny = min(p[1] for _, p in blits)
        maxx = max(p[0] + s.get_width() for s, p in blits)
        maxy = max(p[1] + s.get_height() for s, p in blits)

        out = pygame.Surface((max(1, maxx - minx), max(1, maxy - miny)), pygame.SRCALPHA)
        for surf, (px, py) in blits:
            out.blit(surf, (px - minx, py - miny))

        # anchor = bas-centre de la base (pas de l’overlay)
        anchor_x = (0 - minx) + bw / 2
        anchor_y = (0 - miny) + bh

        # On renvoie aussi la hauteur de frame source pour calculer l'échelle interne.
        self._compose_cache[cache_key] = (out, anchor_x, anchor_y, ss.fh)
        return out, anchor_x, anchor_y, ss.fh

    def _get_scaled(self, composed_surf: pygame.Surface, zoom_eff: float):
        # cache scaling (important si beaucoup d'entités)
        key = (id(composed_surf), round(zoom_eff, 4))
        if key in self._scaled_cache:
            return self._scaled_cache[key]

        if abs(zoom_eff - 1.0) < 1e-6:
            scaled = composed_surf
        else:
            w, h = composed_surf.get_size()
            scaled = pygame.transform.smoothscale(
                composed_surf,
                (max(1, int(w * zoom_eff)), max(1, int(h * zoom_eff)))
            )

        self._scaled_cache[key] = scaled
        return scaled

    # --------- API utilisée par le reste du jeu ----------
    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float):
        # 1) compose (frame + overlays)
        composed, anchor_x, anchor_y, base_frame_h = self._compose()

        # 2) zoom effectif = zoom caméra * échelle interne (dépend de la hauteur de frame)
        zoom = float(getattr(view, "zoom", 1.0) or 1.0)
        size_scale = self._resolve_size_scale()
        # Ex: 24/32 pour base_blob_idle, 24/40 pour bipede_blob_idle
        internal_scale = float(self.BASE_SIZE[1]) / float(max(1, int(base_frame_h or 1)))
        zoom_eff = zoom * internal_scale * size_scale
        sprite = self._get_scaled(composed, zoom_eff)

        # 3) projection iso (identique à ton ancien code)
        dx, dy, wall_h = view._proj_consts()
        z = 0
        try:
            i, j = int(tx), int(ty)
            if world and getattr(world, "levels", None):
                z = int(world.levels[j][i])
        except Exception:
            z = 0

        sx, sy = view._world_to_screen(tx, ty, z, dx, dy, wall_h)

        # même repère que ton ancien renderer
        surface_y = sy - int(2 * dy)

        # 4) placement via anchor (plus robuste qu’un FOOT_OFFSET fixe)
        # anchor est en pixels "non zoomés", donc on le multiplie par zoom_eff
        ax = anchor_x * zoom_eff
        ay = anchor_y * zoom_eff

        px = int(sx - ax)
        py = int(surface_y - ay)

        rect = pygame.Rect(px, py, sprite.get_width(), sprite.get_height())

        # En eau: enfonce visuellement les individus de l'espèce joueur.
        if self._is_player_species() and world is not None:
            try:
                is_water = False
                if hasattr(world, "get_tile_snapshot"):
                    snap = world.get_tile_snapshot(int(tx), int(ty), generate=False)
                    if snap is not None:
                        _lvl, _gid, _overlay, bid = snap
                        is_water = int(bid) in (1, 3, 4)
                elif hasattr(world, "get_is_water"):
                    is_water = bool(world.get_is_water(int(tx), int(ty)))
                if is_water:
                    rect.y += int(sprite.get_height() * 0.28)
            except Exception:
                pass
        return sprite, rect

    def render(self, screen, view, world, tx: float, ty: float):
        sprite, rect = self.get_draw_surface_and_rect(view, world, tx, ty)
        screen.blit(sprite, rect.topleft)
