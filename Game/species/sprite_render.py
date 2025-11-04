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

class EspeceRenderer:
    BASE_SIZE = (20, 24)  # tuile de référence

    def __init__(self, espece, assets):
        self.espece = espece
        self.assets = assets
        self.layers = {
            "appendices": [],                # ailes, branchies...
            "corps":      ["4_corps_base","4_jambe_base"],    # base obligatoire
            "peau":       [],                # poils, carapace...
            "tete":       ["4_bouche_normale", "4_yeux_normaux"],  # yeux/bouche...
            "effets":     [],                # camo, lueurs, phéromones
        }

    # --- helpers sûrs (aucun crash si asset manquant) ---
    def _placeholder_surface(self, label: str) -> pygame.Surface:
        surf = pygame.Surface(self.BASE_SIZE, pygame.SRCALPHA)
        surf.fill((255, 0, 255, 100))
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            f = pygame.font.SysFont("arial", 8)
            txt = f.render(label[:10], True, (0, 0, 0))
            surf.blit(txt, (1, 1))
        except Exception:
            pass
        return surf

    def _get_img(self, key: str) -> pygame.Surface:
        try:
            img = self.assets.get_image(key)  # ← utilise l’API, pas .images
            if img is None:
                raise KeyError(key)
            return img
        except Exception:
            print(f"[Renderer] Asset manquant: {key}")
            return self._placeholder_surface(key)

    # --- calques visuels dynamiques selon les mutations actives ---
    def update_from_mutations(self):

        for m in self.espece.mutations.actives:
            if m == "Carapace": self.layers["peau"].append("carapace")
            elif m == "Peau poilue": self.layers["peau"].append("poils")
            elif m == "Ailes": self.layers["appendices"].append("ailes_grandes")
            elif m == "Branchies": self.layers["appendices"].append("branchies")
            elif m == "Vision multiple": self.layers["tete"].append("yeux_multiples")
            elif m == "Mâchoire réduite": self.layers["tete"].append("bouche_large")
            elif m == "Chromatophores": self.layers["effets"].append("camouflage")
            elif m == "Bioluminescence": self.layers["effets"].append("bioluminescence")
            elif m == "Sécrétion de phéromones": self.layers["effets"].append("pheromone")

    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float):
        # 1) sprite assemblé puis zoomé
        base = self._assemble_base_sprite()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        if abs(zoom - 1.0) > 1e-6:
            w, h = base.get_size()
            sprite = pygame.transform.smoothscale(base, (int(w * zoom), int(h * zoom)))
        else:
            sprite = base

        # 2) projection iso
        dx, dy, wall_h = view._proj_consts()
        z = 0
        try:
            i, j = int(tx), int(ty)
            if world and getattr(world, "levels", None):
                z = int(world.levels[j][i])
        except Exception:
            z = 0

        sx, sy = view._world_to_screen(tx, ty, z, dx, dy, wall_h)

        # 3) ancrage comme un prop sans dépendre d’un asset de sol
        surface_y = sy - int(2 * dy)
        px = int(sx - sprite.get_width() // 2)
        py = int(surface_y - (sprite.get_height() - 2 * dy))

        rect = pygame.Rect(px, py, sprite.get_width(), sprite.get_height())
        return sprite, rect


    def _assemble_base_sprite(self) -> pygame.Surface:
        sprite = pygame.Surface(self.BASE_SIZE, pygame.SRCALPHA)
        for zone in ["appendices", "corps", "peau", "tete", "effets"]:
            for key in self.layers[zone]:
                img = self._get_img(key)
                x = (self.BASE_SIZE[0] - img.get_width()) // 2
                y = (self.BASE_SIZE[1] - img.get_height()) // 2
                offx, offy = OFFSETS.get(key, (0, 0))  # <-- pas "dx, dy"
                sprite.blit(img, (x + offx, y + offy))

        return sprite

    def render(self, screen, view, world, tx: float, ty: float):
        sprite, rect = self.get_draw_surface_and_rect(view, world, tx, ty)
        screen.blit(sprite, rect.topleft)


class PlayerRenderer(EspeceRenderer):
    def __init__(self, espece, assets,tx,ty,controls):
        super().__init__(espece, assets)
        self.controls=controls
        self.tx = tx
        self.ty = ty
             # --- MOUVEMENT ---

    def handle_input(self):
        keys = pygame.key.get_pressed()
        if keys[self.controls["up"]]:
            self.tx += self.speed
            self.ty -= self.speed
        if keys[self.controls["down"]]:
            self.tx -= self.speed
            self.ty += self.speed
        if keys[self.controls["left"]]:
            self.tx -= self.speed
            self.ty -= self.speed
        if keys[self.controls["right"]]:
            self.tx += self.speed
            self.ty += self.speed
        def render(self, screen, view, world):
            self.EspeceRenderer.render(screen, view, world, self.tx, self.ty)