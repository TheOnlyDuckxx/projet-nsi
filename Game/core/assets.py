# ASSETS.PY
# Gère le chargement des assets et ressources en tout genre


# --------------- IMPORTATION DES MODULES ---------------
import os
import pygame
from Game.core.utils import resource_path


# --------------- CLASSE PRINCIPALE ---------------
class Assets:
    # Extension de fichier pour que la classe prennent en charge un peu tout
    IMG_EXTS  = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    FONT_EXTS = {".ttf", ".otf"}

    def __init__(self):
        self.images = {}
        self._fonts_by_size = {}
        self._font_paths = {}

    # Charge l'image séléctionné
    def load_image(self, key: str, path: str):
        ext = os.path.splitext(path)[1].lower()
        surf = pygame.image.load(path)
        if ext in {".png", ".gif"}:
            surf = surf.convert_alpha()  # garde la transparence PNG
        else:
            surf = surf.convert()
            surf.set_colorkey((0, 0, 0))  # seulement pour BMP/JPG

        self.images[key] = surf
        return surf

    # Enregistre l'image chargé dans un dictionnaire
    def _register_font_path(self, key: str, path: str):
        self._font_paths[key] = path

    # Permet d'accèder aux images chargées
    def get_image(self, key: str) -> pygame.Surface:
        return self.images[key]

    # Permet d'accèder aux polices chargées
    def get_font(self, key: str, size: int) -> pygame.font.Font:
        k = (key, int(size))
        if k not in self._fonts_by_size:
            if key not in self._font_paths:
                raise KeyError(f"Font '{key}' non enregistrée. Clés dispos: {list(self._font_paths.keys())}")
            # s'assurer que les fonts sont prêtes
            if not pygame.font.get_init():
                pygame.font.init()
            self._fonts_by_size[k] = pygame.font.Font(self._font_paths[key], int(size))
        return self._fonts_by_size[k]

    # Permet de charger toutes les ressources dans "Game/assets"
    def load_all(self, base_dir: str, strict_keys: bool = True):
        
        abs_base = resource_path(base_dir) if not os.path.isabs(base_dir) else base_dir

        if not os.path.isdir(abs_base):
            raise FileNotFoundError(f"Dossier assets introuvable: {abs_base}")

        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        loaded_images = 0
        registered_fonts = 0

        for root, _, files in os.walk(abs_base):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                name_no_ext = os.path.splitext(fname)[0]  # -> clé
                full = os.path.join(root, fname)

                try:
                    if ext in self.IMG_EXTS:
                        if strict_keys and name_no_ext in self.images:
                            raise ValueError(f"Clé image en double: '{name_no_ext}' pour '{full}'")
                        self.load_image(name_no_ext, full)
                        loaded_images += 1

                    elif ext in self.FONT_EXTS:
                        if strict_keys and name_no_ext in self._font_paths:
                            raise ValueError(f"Clé font en double: '{name_no_ext}' pour '{full}'")
                        self._register_font_path(name_no_ext, full)
                        registered_fonts += 1

                    # (ON pourras ajouter plus tard: sons, musiques, JSON, etc.)

                except Exception as e:
                    # Petit log pour vérifier les erreurs
                    print(f"[Assets] Échec chargement '{full}': {e}")

        print(f"[Assets] Images chargées: {loaded_images} | Polices détectées: {registered_fonts}")

        return self  # pour chaîner si besoin