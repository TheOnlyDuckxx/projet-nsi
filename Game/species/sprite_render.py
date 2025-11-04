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
        """
        screen : surface Pygame
        view   : IsoMapView (caméra+zoom)  -> on utilise _proj_consts()/_world_to_screen()
        world  : monde courant (pour connaître z au sol)
        tx,ty  : coordonnées tuile de l'espèce
        """
        # 1) calques depuis mutations
        #self.update_from_mutations()

        # 2) assemble un sprite 20x24, puis scale au zoom courant
        base = self._assemble_base_sprite()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        if abs(zoom - 1.0) > 1e-6:
            w, h = base.get_size()
            sprite = pygame.transform.smoothscale(base, (int(w * zoom), int(h * zoom)))
        else:
            sprite = base

        # 3) récupère constantes de projection (dx,dy,wall_h) via view
        dx, dy, wall_h = view._proj_consts()  # public interne → ok à utiliser ici

        # 4) hauteur z de la tuile du monde (si dispo), sinon 0
        z = 0
        try:
            i, j = int(tx), int(ty)
            if world and world.levels:
                z = world.levels[j][i]
        except Exception:
            z = 0

        # 5) coord écran du "centre" isométrique de la tuile
        sx, sy = view._world_to_screen(tx, ty, z, dx, dy, wall_h)

        # 6) on pose l’entité comme un prop : sur la "surface" du sol (pas au milieu du losange)
        #    cf. ton iso_render pour les props (surface_y = sy - (gimg.h - 2*dy)) :contentReference[oaicite:2]{index=2}
        try:
            base_tile = self.assets.get_image("tile_grass")
            ground_h = int(base_tile.get_height() * zoom)
        except Exception:
            # fallback si l’asset n’existe pas
            ground_h = int(24 * zoom)

        surface_y = sy - (ground_h - 2 * dy)
        px = sx - sprite.get_width() // 2
        py = surface_y - (sprite.get_height() - 2 * dy)

        screen.blit(sprite, (px, py))

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