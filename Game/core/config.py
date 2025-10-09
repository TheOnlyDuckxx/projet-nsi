# CONFIG.PY
# Code qui gère les paramètres du jeu et les variables GLOBALES


# --------------- IMPORTATION DES MODULES ---------------

import json, os, pygame

# --------------- VARIABLES GLOBALES ---------------
WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "EvoNSI"
SCALE = 3  # pour sprites 16px → 48px
DEFAULTS = {
    "audio":   {"master_volume": 0.8},
    "video":   {"fullscreen": False, "fps_cap": 60, "vsync": False},
    "gameplay":{"language": "fr"}
}


# --------------- CLASSE QUI GERE LES PARAMETRES PRINCIPAUX ---------------
class Settings:
    def __init__(self, path="Game/data/settings.json"):
        self.path = path
        self.data = {}
        self._listeners = []
        self.load()


    # Charge les paramètres enregistré dans le fichier .json
    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                try :
                    self.data = DEFAULTS | json.load(f)
                except:
                    self.data = {**DEFAULTS, **json.load(f)}
        else:
            self.data = DEFAULTS
            self.save()
        self.apply_all()

    # Sauvegarde les paramètres dans le fichier .json
    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)


    # JSP ça fait quoi mais ça doit être important donc je le laisse la
    def get(self, path, default=None):
        node = self.data
        for k in path.split("."):
            node = node.get(k, {})
        return node if node != {} else default

    # Applique les paramètres après la modification depuis l'UI
    def set(self, path, value, apply=True, save=True):
        # path "audio.master_volume"
        keys = path.split(".")
        node = self.data
        for k in keys[:-1]: node = node.setdefault(k, {})
        node[keys[-1]] = value
        if apply: self.apply(path, value)
        if save:  self.save()
        for cb in self._listeners: cb(path, value)

    def on_change(self, callback):
        self._listeners.append(callback)

    # Application des paramètres côté moteur
    def apply(self, path, value):
        if path == "audio.master_volume":
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(value)
        elif path == "video.fullscreen":
            flags = pygame.FULLSCREEN if value else 0
            scr = pygame.display.get_surface()
            if scr:
                pygame.display.set_mode(scr.get_size(), flags)
        elif path == "video.vsync":
            pass
        elif path == "video.fps_cap":
            pass
        # etc.


    # Applique tous les réglages au lancement
    def apply_all(self):
        self.apply("audio.master_volume", self.data["audio"]["master_volume"])
        self.apply("video.fullscreen",    self.data["video"]["fullscreen"])
        self.apply("video.vsync",         self.data["video"]["vsync"])
        self.apply("video.fps_cap",       self.data["video"]["fps_cap"])