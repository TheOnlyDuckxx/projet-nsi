import os
import pickle
from typing import Any, Dict, Optional

DEFAULT_SAVE_PATH = os.path.join("Game", "save", "savegame.evosave")
SAVE_VERSION = "1.1"
SAVE_HEADER = b"EVOBYTE"  # petite signature maison


class SaveError(Exception):
    pass


class SaveManager:
    def __init__(self, path: str = DEFAULT_SAVE_PATH):
        self.path = path

    def save_exists(self) -> bool:
        return os.path.exists(self.path)

    # ------------------------------------------------------------------
    # CONSTRUCTION DU PAYLOAD PHASE 1
    # ------------------------------------------------------------------
    def _build_phase1_payload(self, phase1) -> Dict[str, Any]:
        """
        Construit un dict purement sérialisable (pickle safe) représentant
        l'état de la Phase 1.
        """
        joueur = getattr(phase1, "joueur", None)

        # ---------- ESPÈCE (stats globales + XP) ----------
        espece_data = None
        if joueur is not None and hasattr(joueur, "espece"):
            espece = joueur.espece
            espece_data = {
                "nom": getattr(espece, "nom", None),
                "base_physique": getattr(espece, "base_physique", None),
                "base_sens": getattr(espece, "base_sens", None),
                "base_mental": getattr(espece, "base_mental", None),
                "base_environnement": getattr(espece, "base_environnement", None),
                "base_social": getattr(espece, "base_social", None),
                "genetique": getattr(espece, "genetique", None),
                "arbre_phases3": getattr(espece, "arbre_phases3", None),
                "species_level": getattr(espece, "species_level", 1),
                "xp": getattr(espece, "xp", 0),
                "xp_to_next": getattr(espece, "xp_to_next", 100),
            }

        # ---------- INDIVIDUS ----------
        individus_data = []
        for ent in getattr(phase1, "entities", []):
            # On ne prend que les "vrais" individus (qui ont une espèce)
            if not hasattr(ent, "espece"):
                continue

            ind_data = {
                "pos": (float(getattr(ent, "x", 0.0)),
                        float(getattr(ent, "y", 0.0))),
                "nom": getattr(ent, "nom", None),
                "is_player": (ent is joueur),

                # Stats individuelles
                "physique": getattr(ent, "physique", None),
                "sens": getattr(ent, "sens", None),
                "mental": getattr(ent, "mental", None),
                "social": getattr(ent, "social", None),
                "environnement": getattr(ent, "environnement", None),
                "combat": getattr(ent, "combat", None),
                "genetique": getattr(ent, "genetique", None),

                # État interne
                "jauges": getattr(ent, "jauges", None),
                "ia": getattr(ent, "ia", None),
                "effets_speciaux": getattr(ent, "effets_speciaux", None),
            }

            # Inventaire : on prend "carrying" en priorité, sinon "inventaire"
            inv = getattr(ent, "carrying", None)
            if inv is None:
                inv = getattr(ent, "inventaire", None)
            ind_data["inventaire"] = inv

            individus_data.append(ind_data)

        # ---------- BROUILLARD DE GUERRE ----------
        fog_data = None
        fog = getattr(phase1, "fog_of_war", None)
        if fog is None:
            # au cas où tu l'aies nommé self.fog
            fog = getattr(phase1, "fog", None)

        if fog is not None:
            # On ne sauvegarde que les cases explorées
            fog_data = {
                "width": fog.width,
                "height": fog.height,
                "explored": fog.explored,
            }

        # ---------- PAYLOAD FINAL ----------
        return {
            "version": SAVE_VERSION,
            "world": phase1.world,
            "params": phase1.params,
            "espece": espece_data,
            "individus": individus_data,
            "camera": (phase1.view.cam_x, phase1.view.cam_y),
            "zoom": phase1.view.zoom,
            "fog": fog_data,
        }

    # ------------------------------------------------------------------
    # SAUVEGARDE
    # ------------------------------------------------------------------
    def save_phase1(self, phase1) -> bool:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            payload = self._build_phase1_payload(phase1)

            with open(self.path, "wb") as f:
                # petite signature + pickle
                f.write(SAVE_HEADER)
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

            phase1.save_message = "✓ Partie sauvegardée !"
            phase1.save_message_timer = 3.0
            print(f"✓ Partie sauvegardée dans {self.path}")
            return True
        except Exception as e:
            print(f"✗ Erreur lors de la sauvegarde: {e}")
            phase1.save_message = "✗ Erreur de sauvegarde"
            phase1.save_message_timer = 3.0
            return False

    # ------------------------------------------------------------------
    # CHARGEMENT
    # ------------------------------------------------------------------
    def load_phase1(self, phase1) -> bool:
        try:
            if not self.save_exists():
                print("✗ Aucune sauvegarde trouvée")
                return False

            with open(self.path, "rb") as f:
                header = f.read(len(SAVE_HEADER))
                if header != SAVE_HEADER:
                    # Anciennes sauvegardes sans header : on abandonne
                    print("✗ Format de sauvegarde inconnu (header invalide)")
                    return False

                data = pickle.load(f)

            version = data.get("version", "1.0")
            print(f"→ Chargement sauvegarde version {version}")

            # ----------------- Monde + params -----------------
            phase1.world = data.get("world")
            phase1.params = data.get("params")
            phase1.view.set_world(phase1.world)

            # ----------------- Espèce + individus -----------------
            from Game.species.species import Espece

            espece_data = data.get("espece")
            individus_data = data.get("individus", [])

            phase1.entities = []
            phase1.joueur = None
            phase1.espece = None

            if espece_data is not None:
                # Reconstruire l'espèce
                nom_espece = espece_data.get("nom") or "Espece"
                espece = Espece(nom_espece)

                # Restaure les stats globales si présentes
                for attr_name in [
                    "base_physique", "base_sens", "base_mental",
                    "base_environnement", "base_social",
                    "genetique", "arbre_phases3"
                ]:
                    val = espece_data.get(attr_name)
                    if val is not None:
                        setattr(espece, attr_name, val)

                espece.species_level = espece_data.get("species_level", 1)
                espece.xp = espece_data.get("xp", 0)
                espece.xp_to_next = espece_data.get("xp_to_next", 100)

                phase1.espece = espece

                # ---------- Reconstruction des individus ----------
                for ind_data in individus_data:
                    pos = ind_data.get("pos", (0.0, 0.0))
                    x, y = float(pos[0]), float(pos[1])

                    ent = espece.create_individu(x=x, y=y, assets=phase1.assets)

                    # Stats individuelles
                    for attr_name in [
                        "physique", "sens", "mental", "social",
                        "environnement", "combat", "genetique"
                    ]:
                        val = ind_data.get(attr_name)
                        if val is not None:
                            setattr(ent, attr_name, val)

                    # Jauges & IA
                    if ind_data.get("jauges") is not None:
                        ent.jauges = ind_data["jauges"]
                    if ind_data.get("ia") is not None:
                        ent.ia = ind_data["ia"]

                    # Inventaire
                    if ind_data.get("inventaire") is not None:
                        ent.carrying = ind_data["inventaire"]

                    # Effets spéciaux
                    if ind_data.get("effets_speciaux") is not None:
                        ent.effets_speciaux = ind_data["effets_speciaux"]

                    # Joueur ?
                    if ind_data.get("is_player"):
                        phase1.joueur = ent

                    phase1.entities.append(ent)

                # Si aucun individu n'est marqué joueur, on prend le premier
                if phase1.joueur is None and phase1.entities:
                    phase1.joueur = phase1.entities[0]

            # ----------------- Caméra + zoom -----------------
            camx, camy = data.get("camera", (0, 0))
            phase1.view.cam_x = camx
            phase1.view.cam_y = camy
            phase1.view.zoom = data.get("zoom", 1.0)
            # phase1.view.clamp_camera() si tu as ça

            # ----------------- Brouillard de guerre -----------------
            fog_data = data.get("fog")
            if fog_data is not None:
                exp = fog_data.get("explored")
                if exp is not None:
                    fog = getattr(phase1, "fog_of_war", None)
                    if fog is None:
                        fog = getattr(phase1, "fog", None)
                    if fog is not None:
                        # On suppose que dimensions = même monde
                        fog.explored = exp

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
