# ASSETS.PY
# Gère le chargement des assets et ressources en tout genre


# --------------- IMPORTATION DES MODULES ---------------
import os
import pygame
from Game.core.utils import resource_path


# --------------- CLASSE PRINCIPALE ---------------
class Assets:
    """
    Gère le chargement des images et polices pour simplifier leur accès 
    dans le reste du code
    """
    # Extension de fichier pour que la classe prennent en charge un peu tout
    IMG_EXTS  = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
    FONT_EXTS = {".ttf", ".otf"}

    def __init__(self):
        self.images = {}
        self._fonts_by_size = {}
        self._font_paths = {}

    def load_image(self, key: str, path: str):
        """Charge l'image selectionné"""
        ext = os.path.splitext(path)[1].lower()
        surf = pygame.image.load(path)
        if ext in {".png", ".gif"}:
            surf = surf.convert_alpha()  # garde la transparence PNG
        else:
            surf = surf.convert()
            surf.set_colorkey((0, 0, 0))  # seulement pour BMP/JPG

        self.images[key] = surf
        return surf

    def _register_font_path(self, key: str, path: str):
        """Enregistre l'image chargé dans un dictionnaire"""
        self._font_paths[key] = path

    def get_image(self, key: str):
        """Permet d'accèder aux images chargées"""
        return self.images[key]

    def get_font(self, key: str, size: int):
        """Permet d'accèder aux polices chargées"""
        k = (key, int(size))
        if k not in self._fonts_by_size:
            self._fonts_by_size[k] = pygame.font.Font(self._font_paths[key], int(size))
        return self._fonts_by_size[k]

    def load_all(self, base_dir: str, strict_keys: bool = True):
        """Permet de charger toutes les ressources dans Game/assets"""
        abs_base = resource_path(base_dir) if not os.path.isabs(base_dir) else base_dir

        if not os.path.isdir(abs_base):
            raise FileNotFoundError(f"Dossier assets introuvable: {abs_base}")
        loaded_images = 0
        registered_fonts = 0

        for root, _, files in os.walk(abs_base):
            for nom_fichier in files:
                ext = os.path.splitext(nom_fichier)[1].lower()
                name_no_ext = os.path.splitext(nom_fichier)[0]  # -> clé
                full = os.path.join(root, nom_fichier)

                if ext in self.IMG_EXTS:
                    self.load_image(name_no_ext, full)
                    loaded_images += 1

                elif ext in self.FONT_EXTS:
                    self._register_font_path(name_no_ext, full)
                    registered_fonts += 1

        print(f"[Assets] Images chargées: {loaded_images} | Polices détectées: {registered_fonts}")
        return self