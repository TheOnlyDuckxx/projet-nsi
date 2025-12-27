# CONFIG.PY
# Code qui gère les paramètres du jeu et les variables GLOBALES
# --------------- IMPORTATION DES MODULES ---------------
import json, os, pygame
# --------------- VARIABLES GLOBALES ---------------
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
infoObject = pygame.display.Info()
WIDTH = infoObject.current_w
HEIGHT = infoObject.current_h
FPS = 60
TITLE = "EvoNSI"
SCALE = 3  # pour sprites 16px → 48px
DEFAULTS = {
    "audio": {
        "enabled": True,
        "master_volume": 0.8,
        "music_volume": 0.8,
        "sfx_volume": 0.9
    },
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
        
        if not os.path.exists(self.path):
            print(f"⚠️ Fichier de configuration introuvable, création avec valeurs par défaut")
            self.data = DEFAULTS.copy()
            self.save()
            self.apply_all()
            return
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
                # Vérifier si le fichier est vide
                if not content:
                    print(f"⚠️ Fichier de configuration vide, réinitialisation")
                    self.data = DEFAULTS.copy()
                    self.save()
                    self.apply_all()
                    return
                
                # Charger le JSON
                loaded_data = json.loads(content)
                
                # Fusionner avec les valeurs par défaut (compatibilité Python 3.8)
                self.data = {**DEFAULTS, **loaded_data}
                
                print(f"✓ Configuration chargée depuis {self.path}")
                
        except json.JSONDecodeError as e:
            print(f"Erreur de lecture du fichier de configuration: {e}")
            print(f"   Le fichier sera réinitialisé avec les valeurs par défaut")
            self.data = DEFAULTS.copy()
            self.save()
            
        except Exception as e:
            print(f"Erreur inattendue lors du chargement de la configuration: {e}")
            self.data = DEFAULTS.copy()
            self.save()
        
        self.apply_all()
    
    # Sauvegarde les paramètres dans le fichier .json
    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde de la configuration: {e}")
    
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
        for k in keys[:-1]: 
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        if apply: 
            self.apply(path, value)
        if save:  
            self.save()
        for cb in self._listeners: 
            cb(path, value)
    
    def on_change(self, callback):
        self._listeners.append(callback)
    
    # Application des paramètres côté moteur
    def apply(self, path, value):
        try:
            if path.startswith("audio."):
                if pygame.mixer.get_init():
                    enabled = self.get("audio.enabled", True)
                    if not enabled:
                        pygame.mixer.music.set_volume(0.0)
                    else:
                        master = float(self.get("audio.master_volume", 0.8))
                        musicv = float(self.get("audio.music_volume", 0.8))
                        pygame.mixer.music.set_volume(master * musicv)
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
        except Exception as e:
            print(f"⚠️ Erreur lors de l'application du paramètre '{path}': {e}")
    
    # Applique tous les réglages au lancement
    def apply_all(self):
        try:
            self.apply("audio.master_volume", self.data["audio"]["master_volume"])
            self.apply("video.fullscreen",    self.data["video"]["fullscreen"])
            self.apply("video.vsync",         self.data["video"]["vsync"])
            self.apply("video.fps_cap",       self.data["video"]["fps_cap"])
        except KeyError as e:
            print(f"⚠️ Clé de configuration manquante: {e}")
            print(f"   Réinitialisation des valeurs par défaut")
            self.data = DEFAULTS.copy()
            self.save()