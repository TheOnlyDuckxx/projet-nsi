# Game/espece/renderer.py
import pygame

OFFSETS = {
    "4_yeux_normaux": (0, 1),
    "4_bouche_normale": (0, 1),
    "4_jambe_base": (0, 1),
    "4_corps_base": (0, 0),
    "ailes_grandes": (0, -6),
    "branchies": (0, -2),
    "carapace": (0, 0),
    "poils": (0, 0),
    "camouflage": (0, 0),
    "bioluminescence": (0, 0),
    "pheromone": (0, 0),
}

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

    def __init__(self, espece, assets):
        self.espece = espece
        self.assets = assets

        # --- config base spritesheet ---
        # Pour ne rien casser : si tu ne renseignes rien dans espece, ça marche quand même.
        self.sheet_key = getattr(espece, "sprite_sheet_key", "Sprite_main_blob")
        self.frame_w, self.frame_h = getattr(espece, "sprite_frame_size", (32, 32))

        # Échelle "interne" pour que le passage 20x24 -> 32x32 ne te fasse pas un monstre à l'écran.
        # Par défaut on rapproche la hauteur du vieux système : 24/32 = 0.75
        self.base_scale = float(getattr(espece, "sprite_base_scale", self.BASE_SIZE[1] / self.frame_h))

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

    def _get_sheet(self, key: str) -> SpriteSheet:
        if key in self._sheet_cache:
            return self._sheet_cache[key]
        sheet_img = self._get_img(key, fallback_size=(self.frame_w, self.frame_h))
        ss = SpriteSheet(sheet_img, self.frame_w, self.frame_h)
        self._sheet_cache[key] = ss
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

    # --------- mutations (hook conservé) ----------
    def update_from_mutations(self):
        # IMPORTANT: reset (sinon ça se duplique si tu appelles plusieurs fois)
        self.base_variant_key = self.sheet_key
        self.overlay_keys = []
        self._compose_cache.clear()
        self._scaled_cache.clear()

        # Si plus tard tu fais des variantes complètes (spritesheet différente),
        # tu peux changer base_variant_key ici.
        # Exemple:
        # if "Carapace" in self.espece.mutations.actives:
        #     self.base_variant_key = "Sprite_main_blob_carapace"

        for m in getattr(self.espece.mutations, "actives", []):
            if m == "Carapace": self.overlay_keys.append("carapace")
            elif m == "Peau poilue": self.overlay_keys.append("poils")
            elif m == "Ailes": self.overlay_keys.append("ailes_grandes")
            elif m == "Branchies": self.overlay_keys.append("branchies")
            elif m == "Chromatophores": self.overlay_keys.append("camouflage")
            elif m == "Bioluminescence": self.overlay_keys.append("bioluminescence")
            elif m == "Sécrétion de phéromones": self.overlay_keys.append("pheromone")

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

        self._compose_cache[cache_key] = (out, anchor_x, anchor_y)
        return out, anchor_x, anchor_y

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
        composed, anchor_x, anchor_y = self._compose()

        # 2) zoom effectif = zoom caméra * échelle interne
        zoom = float(getattr(view, "zoom", 1.0) or 1.0)
        zoom_eff = zoom * self.base_scale
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
        return sprite, rect

    def render(self, screen, view, world, tx: float, ty: float):
        sprite, rect = self.get_draw_surface_and_rect(view, world, tx, ty)
        screen.blit(sprite, rect.topleft)
