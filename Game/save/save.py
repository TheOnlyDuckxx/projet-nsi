import os
import pickle
from typing import Any, Dict
from Game.world.fog_of_war import FogOfWar

DEFAULT_SAVE_PATH = os.path.join("Game", "save", "savegame.evosave")
SAVE_VERSION = "1.3"
SAVE_HEADER = b"EVOBYTE"  # petite signature maison


class SaveError(Exception):
    pass


class SaveManager:
    def __init__(self, path: str = DEFAULT_SAVE_PATH):
        self.path = path

    def _serialize_species(self, espece):
        if espece is None:
            return None
        return {
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
            "reproduction": getattr(getattr(espece, "reproduction_system", None), "to_dict", lambda: {})(),
        }

    def _restore_species_from_data(self, espece_data, phase1=None, assets=None):
        if espece_data is None:
            return None
        from Game.species.species import Espece

        espece = Espece(espece_data.get("nom") or "Espece")
        if hasattr(espece, "reproduction_system") and phase1 is not None:
            try:
                espece.reproduction_system.bind_phase(phase1)
            except Exception:
                pass

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
        try:
            repro_state = espece_data.get("reproduction")
            if repro_state is not None and hasattr(espece, "reproduction_system"):
                espece.reproduction_system.load_state(repro_state, assets=assets)
        except Exception as e:
            print(f"[Save] Échec chargement reproduction: {e}")
        return espece

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

        espece_data = self._serialize_species(getattr(phase1, "espece", None))
        species_registry: Dict[str, Any] = {}
        species_keys: Dict[int, str] = {}
        fauna_key = None

        def register_species(key: str, espece_obj):
            if espece_obj is None:
                return
            species_keys[id(espece_obj)] = key
            if key not in species_registry:
                species_registry[key] = self._serialize_species(espece_obj)

        register_species("player", getattr(phase1, "espece", None))
        if getattr(phase1, "fauna_species", None):
            fauna_key = "fauna"
            register_species(fauna_key, phase1.fauna_species)

        # ---------- INDIVIDUS ----------
        individus_data = []
        for ent in getattr(phase1, "entities", []):
            # On ne prend que les "vrais" individus (qui ont une espèce)
            if not hasattr(ent, "espece") or getattr(ent, "is_egg", False):
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

            species_key = species_keys.get(id(getattr(ent, "espece", None)))
            if species_key is None and hasattr(ent, "espece"):
                fallback = f"species_{len(species_registry) + 1}"
                register_species(fallback, ent.espece)
                species_key = species_keys.get(id(ent.espece))

            if species_key:
                ind_data["species_key"] = species_key
            if getattr(ent, "is_fauna", False):
                ind_data["is_fauna"] = True

            individus_data.append(ind_data)

        day_night = getattr(phase1, "day_night", None)
        day_night_data = None
        if day_night is not None:
            day_night_data = {
                "cycle_duration": getattr(day_night, "cycle_duration", None),
                "time_elapsed": getattr(day_night, "time_elapsed", 0.0),
                "time_speed": getattr(day_night, "time_speed", 1.0),
                "paused": getattr(day_night, "paused", False),
                "jour": getattr(day_night, "jour", 0),
            }

        # ---------- BROUILLARD DE GUERRE ----------
        fog_data = None
        fog = phase1.fog

        if fog is not None:
            # On ne sauvegarde que les cases explorées
            fog_data = {
                "width": fog.width,
                "height": fog.height,
                "explored": fog.explored,
            }
        else :
            print("pas de fog :(")

        # ---------- PAYLOAD FINAL ----------
        return {
            "version": SAVE_VERSION,
            "world": phase1.world,
            "params": phase1.params,
            "espece": espece_data,
            "species_registry": species_registry or None,
            "fauna_species_key": fauna_key,
            "individus": individus_data,
            "camera": (phase1.view.cam_x, phase1.view.cam_y),
            "zoom": phase1.view.zoom,
            "fog": fog_data,
            "day_night": day_night_data,   # <-- NEW
            "events": getattr(getattr(phase1, "event_manager", None), "to_dict", lambda: {})(),
            "warehouse": getattr(phase1, "warehouse", None),
            "fauna_spawn_zones": getattr(phase1, "fauna_spawn_zones", []),
            "happiness": getattr(phase1, "happiness", None),
            "death_response_mode": getattr(phase1, "death_response_mode", None),
            "death_event_ready": getattr(phase1, "death_event_ready", False),
            "species_death_count": getattr(phase1, "species_death_count", 0),
            "unlocked_crafts": list(getattr(phase1, "unlocked_crafts", []) or []),
            "food_reserve_capacity": getattr(phase1, "food_reserve_capacity", None),
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

            if phase1.world is not None:
                phase1.fog = FogOfWar(phase1.world.width, phase1.world.height)
                phase1.view.fog = phase1.fog
            # ----------------- Espèce + individus -----------------
            species_registry_data = data.get("species_registry") or {}
            fauna_species_key = data.get("fauna_species_key")
            individus_data = data.get("individus", [])

            phase1.entities = []
            phase1.joueur = None
            phase1.espece = None
            phase1.fauna_species = None

            species_map: Dict[str, Any] = {}
            espece_data = data.get("espece") or species_registry_data.get("player")

            if espece_data is not None:
                espece = self._restore_species_from_data(espece_data, phase1=phase1, assets=phase1.assets)
                phase1.espece = espece
                if espece:
                    species_map["player"] = espece

            for key, sdata in species_registry_data.items():
                if key == "player" and species_map.get("player"):
                    continue
                restored = self._restore_species_from_data(sdata, phase1=phase1, assets=phase1.assets)
                if restored:
                    species_map[key] = restored

            if fauna_species_key and fauna_species_key in species_map:
                phase1.fauna_species = species_map[fauna_species_key]
            elif "fauna" in species_map:
                phase1.fauna_species = species_map["fauna"]

            # ---------- Reconstruction des individus ----------
            for ind_data in individus_data:
                pos = ind_data.get("pos", (0.0, 0.0))
                x, y = float(pos[0]), float(pos[1])

                species_key = ind_data.get("species_key") or ("fauna" if ind_data.get("is_fauna") else "player")
                espece_for_ent = species_map.get(species_key) or phase1.espece
                if espece_for_ent is None:
                    continue

                ent = espece_for_ent.create_individu(x=x, y=y, assets=phase1.assets)

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

                if ind_data.get("is_fauna"):
                    ent.is_fauna = True

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

            # Re-lie la phase aux entités pour les interactions personnalisées
            attach_fn = getattr(phase1, "_attach_phase_to_entities", None)
            if callable(attach_fn):
                attach_fn()

            phase1.fauna_spawn_zones = data.get("fauna_spawn_zones", []) or []
            if phase1.fauna_species is None and hasattr(phase1, "_init_fauna_species"):
                try:
                    phase1._init_fauna_species()
                except Exception:
                    pass
            if not phase1.fauna_spawn_zones and hasattr(phase1, "_generate_fauna_spawn_zones"):
                try:
                    phase1._generate_fauna_spawn_zones()
                except Exception:
                    pass
            # phase1.view.clamp_camera() si tu as ça

            phase1.fauna_spawn_zones = data.get("fauna_spawn_zones", []) or []
            if phase1.fauna_species is None and hasattr(phase1, "_init_fauna_species"):
                try:
                    phase1._init_fauna_species()
                except Exception:
                    pass
            if not phase1.fauna_spawn_zones and hasattr(phase1, "_generate_fauna_spawn_zones"):
                try:
                    phase1._generate_fauna_spawn_zones()
                except Exception:
                    pass
            phase1.fauna_spawn_zones = data.get("fauna_spawn_zones", []) or []
            if phase1.fauna_species is None and hasattr(phase1, "_init_fauna_species"):
                try:
                    phase1._init_fauna_species()
                except Exception:
                    pass
            if not phase1.fauna_spawn_zones and hasattr(phase1, "_generate_fauna_spawn_zones"):
                try:
                    phase1._generate_fauna_spawn_zones()
                except Exception:
                    pass
            # ----------------- Brouillard de guerre -----------------
            fog_data = data.get("fog")
            if fog_data is not None:
                exp = fog_data.get("explored")
                if exp is not None:
                    fog = getattr(phase1, "fog", None)
                    if fog is not None:
                        fog.explored = exp
            
            # ----------------- Évènements -----------------
            events_state = data.get("events")
            if events_state is not None:
                mgr = getattr(phase1, "event_manager", None)
                if mgr is not None:
                    mgr.load_state(events_state)
            
            # ----------------- Entrepôt partagé -----------------
            warehouse_data = data.get("warehouse")
            if warehouse_data is not None:
                phase1.warehouse = dict(warehouse_data)

            # ----------------- Jour / Nuit -----------------
            dn_data = data.get("day_night")
            if dn_data is not None:
                from Game.world.day_night import DayNightCycle

                dn = getattr(phase1, "day_night", None)
                if dn is None:
                    dn = DayNightCycle(cycle_duration=dn_data.get("cycle_duration", 600))
                    phase1.day_night = dn

                # On ne remplace pas forcément l'objet, on le met à jour
                dn.cycle_duration = dn_data.get("cycle_duration", getattr(dn, "cycle_duration", 600))
                dn.time_elapsed = float(dn_data.get("time_elapsed", 0.0)) % max(1e-6, dn.cycle_duration)
                dn.time_speed = float(dn_data.get("time_speed", getattr(dn, "time_speed", 1.0)))
                dn.paused = bool(dn_data.get("paused", False))
                dn.jour = int(dn_data.get("jour", 0))

            # ----------------- Bonheur / décès / crafts -----------------
            phase1.happiness = data.get("happiness", getattr(phase1, "happiness", 10.0))
            phase1.death_response_mode = data.get("death_response_mode")
            phase1.death_event_ready = data.get("death_event_ready", False)
            phase1.species_death_count = data.get("species_death_count", 0)
            phase1.food_reserve_capacity = data.get("food_reserve_capacity", getattr(phase1, "food_reserve_capacity", 100))
            unlocked = data.get("unlocked_crafts")
            if unlocked is not None:
                phase1.unlocked_crafts = set(unlocked)
                if phase1.bottom_hud:
                    phase1.bottom_hud.refresh_craft_buttons()


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
