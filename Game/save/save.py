# Game/save/save.py
import os
import pickle
from typing import Any, Dict, Optional

DEFAULT_SAVE_PATH = os.path.join("Game", "save", "savegame.evosave")
SAVE_VERSION = "1.0"
SAVE_HEADER = b"EVOBYTE"  # petite signature maison

class SaveError(Exception):
    pass

class SaveManager:
    def __init__(self, path: str = DEFAULT_SAVE_PATH):
        self.path = path

    def save_exists(self) -> bool:
        return os.path.exists(self.path)

    def _build_phase1_payload(self, phase1) -> Dict[str, Any]:
        joueur_data = None
        if phase1.joueur:
            joueur_data = {
                "pos": (phase1.joueur.x, phase1.joueur.y),
                "nom": getattr(phase1.joueur, "nom", None),
                "stats": getattr(phase1.joueur, "stats", None),
            }

        return {
            "version": SAVE_VERSION,
            "world": phase1.world,
            "params": phase1.params,
            "joueur": joueur_data,
            "camera": (phase1.view.cam_x, phase1.view.cam_y),
            "zoom": phase1.view.zoom,
        }

    def save_phase1(self, phase1) -> bool:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            payload = self._build_phase1_payload(phase1)

            with open(self.path, "wb") as f:
                # petite signature + pickle
                f.write(SAVE_HEADER)
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

            # message côté phase1 (facultatif, mais pratique)
            phase1.save_message = "✓ Partie sauvegardée !"
            phase1.save_message_timer = 3.0
            print(f"✓ Partie sauvegardée dans {self.path}")
            return True
        except Exception as e:
            print(f"✗ Erreur lors de la sauvegarde: {e}")
            phase1.save_message = "✗ Erreur de sauvegarde"
            phase1.save_message_timer = 3.0
            return False

    def load_phase1(self, phase1) -> bool:
        try:
            if not self.save_exists():
                print("✗ Aucune sauvegarde trouvée")
                return False

            with open(self.path, "rb") as f:
                header = f.read(len(SAVE_HEADER))
                if header != SAVE_HEADER:
                    # Anciennes sauvegardes sans header ? on tente quand même
                    # en repositionnant au début si besoin.
                    f.seek(0)
                data = pickle.load(f)

            version = data.get("version", "1.0")
            print(f"→ Chargement sauvegarde version {version}")

            # Monde + params
            phase1.world = data.get("world")
            phase1.params = data.get("params")
            phase1.view.set_world(phase1.world)

            # Joueur
            j = data.get("joueur")
            if j and j.get("pos"):
                x, y = j["pos"]
                nom = j.get("nom") or "Hominidé"
                from Game.species.species import Espece  # import local pour éviter cycles
                phase1.joueur = Espece(nom, x=x, y=y, assets=phase1.assets)
                if j.get("stats") is not None:
                    phase1.joueur.stats = j["stats"]
                phase1.entities = [phase1.joueur]

            # Caméra + zoom
            camx, camy = data.get("camera", (0, 0))
            phase1.view.cam_x = camx
            phase1.view.cam_y = camy
            phase1.view.zoom = data.get("zoom", 1.0)
            # Si tu as une méthode pour borner la caméra, appelle-la ici:
            # phase1.view.clamp_camera()

            phase1.save_message = "✓ Partie chargée !"
            phase1.save_message_timer = 3.0
            print(f"✓ Partie chargée depuis {self.path}")
            return True

        except Exception as e:
            import traceback
            print(f"✗ Erreur lors du chargement: {e}")
            traceback.print_exc()
            phase1.save_message = "✗ Erreur de chargement"
            phase1.save_message_timer = 3.0
            return False
