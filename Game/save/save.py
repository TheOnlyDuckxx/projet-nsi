import os
import pickle
import time
import json
import random
from datetime import datetime
from typing import Any, Dict
from Game.world.fog_of_war import FogOfWar

DEFAULT_SAVE_PATH = os.path.join("Game", "save", "savegame.evosave")
SAVES_DIR = os.path.join("Game", "save", "slots")
SAVE_VERSION = "1.3"
SAVE_HEADER = b"EVOBYTE"  # petite signature maison


class SaveError(Exception):
    pass


class SaveManager:
    def __init__(self, path: str | None = None, slot_id: str | None = None):
        if path is None and slot_id:
            path = self.slot_path(slot_id)
        self.path = path or DEFAULT_SAVE_PATH

    @classmethod
    def _safe_slot_id(cls, slot_id: str) -> str:
        raw = str(slot_id or "").strip().replace(" ", "_")
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        safe = "".join(ch for ch in raw if ch in allowed)
        return safe or "slot"

    @classmethod
    def slot_path(cls, slot_id: str) -> str:
        return os.path.join(SAVES_DIR, f"{cls._safe_slot_id(slot_id)}.evosave")

    @classmethod
    def create_new_slot_id(cls) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"{random.randint(0, 0xFFFF):04x}"
        return f"save_{stamp}_{suffix}"

    @classmethod
    def create_new_save_path(cls) -> str:
        os.makedirs(SAVES_DIR, exist_ok=True)
        return cls.slot_path(cls.create_new_slot_id())

    @staticmethod
    def _meta_path_for(save_path: str) -> str:
        return f"{save_path}.meta.json"

    @staticmethod
    def _collect_species_meta(payload: Dict[str, Any]) -> tuple[str, int]:
        species_data = payload.get("espece") or {}
        if not species_data:
            species_data = (payload.get("species_registry") or {}).get("player") or {}
        name = str(species_data.get("nom") or "Espèce inconnue")
        try:
            level = int(species_data.get("species_level", 1) or 1)
        except Exception:
            level = 1
        return name, level

    @classmethod
    def _build_metadata(cls, save_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        species_name, species_level = cls._collect_species_meta(payload or {})
        tech_state = payload.get("tech_tree") or {}
        unlocked = tech_state.get("unlocked") or []
        current_research = tech_state.get("current_research")
        now_ts = time.time()
        return {
            "save_version": payload.get("version", SAVE_VERSION),
            "save_path": save_path,
            "slot_id": os.path.splitext(os.path.basename(save_path))[0],
            "species_name": species_name,
            "species_level": species_level,
            "tech_unlocked_count": len(unlocked),
            "tech_current_research": current_research,
            "updated_at": now_ts,
            "updated_at_iso": datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def _extract_metadata_from_save_file(cls, save_path: str) -> Dict[str, Any] | None:
        try:
            with open(save_path, "rb") as f:
                header = f.read(len(SAVE_HEADER))
                if header != SAVE_HEADER:
                    return None
                payload = pickle.load(f)
            if not isinstance(payload, dict):
                return None
            meta = cls._build_metadata(save_path, payload)
            try:
                mtime = os.path.getmtime(save_path)
                meta["updated_at"] = float(mtime)
                meta["updated_at_iso"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            return meta
        except Exception:
            return None

    def _write_metadata(self, payload: Dict[str, Any]) -> None:
        meta_path = self._meta_path_for(self.path)
        meta = self._build_metadata(self.path, payload or {})
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta, mf, ensure_ascii=False, indent=2)

    @classmethod
    def list_saves(cls) -> list[Dict[str, Any]]:
        paths: list[str] = []
        if os.path.isdir(SAVES_DIR):
            for name in os.listdir(SAVES_DIR):
                if not name.lower().endswith(".evosave"):
                    continue
                p = os.path.join(SAVES_DIR, name)
                if os.path.isfile(p):
                    paths.append(p)
        # Compat : ancienne sauvegarde unique.
        if os.path.isfile(DEFAULT_SAVE_PATH):
            paths.append(DEFAULT_SAVE_PATH)

        unique_paths = []
        seen = set()
        for p in paths:
            rp = os.path.realpath(p)
            if rp in seen:
                continue
            seen.add(rp)
            unique_paths.append(p)

        results: list[Dict[str, Any]] = []
        for save_path in unique_paths:
            meta_path = cls._meta_path_for(save_path)
            meta = None
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                except Exception:
                    meta = None
            if not isinstance(meta, dict):
                meta = cls._extract_metadata_from_save_file(save_path)
                if isinstance(meta, dict):
                    try:
                        with open(meta_path, "w", encoding="utf-8") as mf:
                            json.dump(meta, mf, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
            if not isinstance(meta, dict):
                try:
                    mtime = os.path.getmtime(save_path)
                except Exception:
                    mtime = 0.0
                meta = {
                    "save_path": save_path,
                    "slot_id": os.path.splitext(os.path.basename(save_path))[0],
                    "species_name": "Espèce inconnue",
                    "species_level": 1,
                    "updated_at": mtime,
                    "updated_at_iso": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "Inconnu",
                    "save_version": "?",
                    "tech_unlocked_count": 0,
                    "tech_current_research": None,
                }

            meta["save_path"] = save_path
            results.append(meta)

        results.sort(key=lambda d: float(d.get("updated_at", 0.0) or 0.0), reverse=True)
        return results

    @classmethod
    def has_any_save(cls) -> bool:
        if os.path.isfile(DEFAULT_SAVE_PATH):
            return True
        if not os.path.isdir(SAVES_DIR):
            return False
        for name in os.listdir(SAVES_DIR):
            if name.lower().endswith(".evosave"):
                return True
        return False

    @classmethod
    def latest_save_path(cls) -> str | None:
        saves = cls.list_saves()
        if not saves:
            return None
        return str(saves[0].get("save_path") or "")

    @classmethod
    def delete_save(cls, save_path: str) -> bool:
        target = str(save_path or "").strip()
        if not target:
            return False

        removed = False
        try:
            if os.path.isfile(target):
                os.remove(target)
                removed = True
        except Exception:
            pass

        meta_path = cls._meta_path_for(target)
        try:
            if os.path.isfile(meta_path):
                os.remove(meta_path)
                removed = True
        except Exception:
            pass

        return removed

    def _serialize_species(self, espece):
        if espece is None:
            return None
        return {
            "nom": getattr(espece, "nom", None),
            "color_name": getattr(espece, "color_name", None),
            "color_rgb": getattr(espece, "color_rgb", None),
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
        color_name = espece_data.get("color_name")
        color_rgb = espece_data.get("color_rgb")
        if color_name:
            espece.color_name = str(color_name)
        if isinstance(color_rgb, (list, tuple)) and len(color_rgb) == 3:
            try:
                espece.color_rgb = (
                    max(0, min(255, int(color_rgb[0]))),
                    max(0, min(255, int(color_rgb[1]))),
                    max(0, min(255, int(color_rgb[2]))),
                )
            except Exception:
                pass
        try:
            repro_state = espece_data.get("reproduction")
            if repro_state is not None and hasattr(espece, "reproduction_system"):
                espece.reproduction_system.load_state(repro_state, assets=assets)
        except EOFError:
            print("✗ Sauvegarde corrompue ou incomplète (EOF)")
            phase1.save_message = "✗ Sauvegarde corrompue"
            phase1.save_message_timer = 3.0
            return False
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
                "name_locked": getattr(ent, "name_locked", False),
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
                fauna_id = getattr(ent, "fauna_id", None)
                if fauna_id is not None:
                    ind_data["fauna_id"] = fauna_id

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
            fog_data = fog.export_state()
        else:
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
            "happiness": getattr(phase1, "happiness", None),
            "death_response_mode": getattr(phase1, "death_response_mode", None),
            "death_event_ready": getattr(phase1, "death_event_ready", False),
            "species_death_count": getattr(phase1, "species_death_count", 0),
            "unlocked_crafts": list(getattr(phase1, "unlocked_crafts", []) or []),
            "food_reserve_capacity": getattr(phase1, "food_reserve_capacity", None),
            "tech_tree": getattr(getattr(phase1, "tech_tree", None), "to_dict", lambda: {})(),
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
            try:
                self._write_metadata(payload)
            except Exception as e:
                print(f"[Save] Metadata non ecrite: {e}")

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
        start_t = time.perf_counter()
        last_t = start_t
        perf_enabled = bool(getattr(getattr(phase1, "app", None), "settings", None).get("debug.perf_logs", True)) if getattr(getattr(phase1, "app", None), "settings", None) else True

        def log_step(label: str):
            nonlocal last_t
            if not perf_enabled:
                return
            now_t = time.perf_counter()
            print(f"[Perf][SaveLoad] {label} | +{now_t - last_t:.3f}s | total {now_t - start_t:.3f}s")
            last_t = now_t

        try:
            log_step(f"Debut load_phase1 path={self.path}")
            if not self.save_exists():
                print("[Save] Aucune sauvegarde trouvee")
                return False
            log_step("Fichier de sauvegarde detecte")

            with open(self.path, "rb") as f:
                header = f.read(len(SAVE_HEADER))
                if header != SAVE_HEADER:
                    print("[Save] Format de sauvegarde inconnu (header invalide)")
                    return False
                data = pickle.load(f)
            log_step("Header valide + payload deserialize")

            version = data.get("version", "1.0")
            print(f"[Save] Chargement sauvegarde version {version}")

            # ----------------- Monde + params -----------------
            phase1.world = data.get("world")
            phase1.params = data.get("params")
            phase1.view.set_world(phase1.world)
            log_step("Monde + params injectes")

            fog_data = data.get("fog") or {}
            if phase1.world is not None:
                cs = fog_data.get("chunk_size", 64)
                wrap_x = bool(fog_data.get("wrap_x", False))
                phase1.fog = FogOfWar(phase1.world.width, phase1.world.height, chunk_size=cs, wrap_x=wrap_x)
                phase1.view.fog = phase1.fog
            log_step("Fog prepare")

            # ----------------- Espece + individus -----------------
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
            log_step("Espece joueur restauree")

            for key, sdata in species_registry_data.items():
                if key == "player" and species_map.get("player"):
                    continue
                restored = self._restore_species_from_data(sdata, phase1=phase1, assets=phase1.assets)
                if restored:
                    species_map[key] = restored
            log_step(f"Registry especes restaure ({len(species_map)})")

            if fauna_species_key and fauna_species_key in species_map:
                phase1.fauna_species = species_map[fauna_species_key]
            elif "fauna" in species_map:
                phase1.fauna_species = species_map["fauna"]

            # ---------- Reconstruction des individus ----------
            total_individus = len(individus_data)
            for idx, ind_data in enumerate(individus_data, start=1):
                pos = ind_data.get("pos", (0.0, 0.0))
                x, y = float(pos[0]), float(pos[1])

                is_fauna = bool(ind_data.get("is_fauna"))
                species_key = ind_data.get("species_key") or ("fauna" if is_fauna else "player")
                espece_for_ent = species_map.get(species_key) or phase1.espece
                if espece_for_ent is None:
                    continue

                if is_fauna and hasattr(phase1, "_rabbit_definition"):
                    from Game.species.fauna import PassiveFaunaFactory, AggressiveFaunaFactory

                    fauna_id = ind_data.get("fauna_id")
                    definition = phase1.get_fauna_definition(fauna_id) if hasattr(phase1, "get_fauna_definition") else None
                    if definition is None:
                        # Fallback par nom d'espèce (anciens saves)
                        name_guess = getattr(espece_for_ent, "nom", None) or ""
                        name_guess = str(name_guess).strip().lower()
                        if name_guess:
                            catalog = phase1._fauna_definition_catalog() if hasattr(phase1, "_fauna_definition_catalog") else {}
                            if name_guess in catalog:
                                definition = catalog.get(name_guess)
                                fauna_id = name_guess
                            else:
                                for key, defn in (catalog or {}).items():
                                    if defn and str(getattr(defn, "species_name", "")).strip().lower() == name_guess:
                                        definition = defn
                                        fauna_id = key
                                        break
                    if definition is None:
                        definition = phase1._rabbit_definition()
                        fauna_id = fauna_id or "lapin"

                    factory_cls = AggressiveFaunaFactory if getattr(definition, "is_aggressive", False) else PassiveFaunaFactory
                    factory = factory_cls(phase1, phase1.assets, definition)
                    fauna_species = species_map.get(species_key) or phase1.fauna_species
                    if fauna_species is None:
                        fauna_species = factory.create_species()
                        phase1.fauna_species = fauna_species
                        if species_key:
                            species_map[species_key] = fauna_species
                    ent = factory.create_creature(fauna_species, x, y)
                    try:
                        ent.fauna_id = str(fauna_id) if fauna_id is not None else None
                    except Exception:
                        pass
                else:
                    ent = espece_for_ent.create_individu(x=x, y=y, assets=phase1.assets)

                if ind_data.get("nom") is not None:
                    ent.nom = ind_data.get("nom")
                if ind_data.get("name_locked") is not None:
                    ent.name_locked = bool(ind_data.get("name_locked"))

                for attr_name in [
                    "physique", "sens", "mental", "social",
                    "environnement", "combat", "genetique"
                ]:
                    val = ind_data.get(attr_name)
                    if val is not None:
                        setattr(ent, attr_name, val)

                if ind_data.get("jauges") is not None:
                    ent.jauges = ind_data["jauges"]
                if ind_data.get("ia") is not None:
                    ent.ia = ind_data["ia"]
                if ind_data.get("inventaire") is not None:
                    ent.carrying = ind_data["inventaire"]
                if ind_data.get("effets_speciaux") is not None:
                    ent.effets_speciaux = ind_data["effets_speciaux"]

                if is_fauna:
                    ent.is_fauna = True

                if ind_data.get("is_player"):
                    phase1.joueur = ent

                phase1.entities.append(ent)

                if idx % 100 == 0 or idx == total_individus:
                    log_step(f"Reconstruction individus {idx}/{total_individus}")

            if phase1.joueur is None and phase1.entities:
                phase1.joueur = phase1.entities[0]
            log_step(f"Individus restaures ({len(phase1.entities)}), joueur={'ok' if phase1.joueur else 'absent'}")

            # ----------------- Camera + zoom -----------------
            camx, camy = data.get("camera", (0, 0))
            phase1.view.cam_x = camx
            phase1.view.cam_y = camy
            phase1.view.zoom = data.get("zoom", 1.0)
            log_step("Camera + zoom restaures")

            attach_fn = getattr(phase1, "_attach_phase_to_entities", None)
            if callable(attach_fn):
                attach_fn()
            log_step("Entites rattachees a la phase")

            if phase1.fauna_species is None and hasattr(phase1, "_init_fauna_species"):
                try:
                    phase1._init_fauna_species()
                except Exception:
                    pass
            log_step("Faune restauree")

            fog_data = data.get("fog")
            if fog_data is not None:
                fog = getattr(phase1, "fog", None)
                if fog is not None and hasattr(fog, "import_state"):
                    fog.import_state(fog_data)
            log_step("Etat fog importe")

            events_state = data.get("events")
            if events_state is not None:
                mgr = getattr(phase1, "event_manager", None)
                if mgr is not None:
                    mgr.load_state(events_state)
            log_step("Events restaures")

            warehouse_data = data.get("warehouse")
            if warehouse_data is not None:
                phase1.warehouse = dict(warehouse_data)
            log_step("Entrepot restaure")

            dn_data = data.get("day_night")
            if dn_data is not None:
                from Game.world.day_night import DayNightCycle

                dn = getattr(phase1, "day_night", None)
                if dn is None:
                    dn = DayNightCycle(cycle_duration=dn_data.get("cycle_duration", 600))
                    phase1.day_night = dn

                dn.cycle_duration = dn_data.get("cycle_duration", getattr(dn, "cycle_duration", 600))
                dn.time_elapsed = float(dn_data.get("time_elapsed", 0.0)) % max(1e-6, dn.cycle_duration)
                dn.time_speed = float(dn_data.get("time_speed", getattr(dn, "time_speed", 1.0)))
                dn.paused = bool(dn_data.get("paused", False))
                dn.jour = int(dn_data.get("jour", 0))
            log_step("Jour/Nuit restaure")

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

            tech_state = data.get("tech_tree")
            tech_tree = getattr(phase1, "tech_tree", None)
            if tech_tree is not None and tech_state is not None:
                tech_tree.load_state(tech_state)
                for tech_id in tech_tree.unlocked:
                    tech_data = tech_tree.get_tech(tech_id)
                    for craft_id in tech_data.get("craft", []) or []:
                        phase1.unlock_craft(craft_id)
                if phase1.bottom_hud:
                    phase1.bottom_hud.refresh_craft_buttons()
            log_step("Stats globales + tech tree restaures")

            phase1.save_message = "✓ Partie chargée !"
            phase1.save_message_timer = 3.0
            print(f"[Save] Partie chargee depuis {self.path}")
            log_step("Chargement termine")
            return True

        except Exception as e:
            import traceback
            print(f"[Save] Erreur lors du chargement: {e}")
            traceback.print_exc()
            phase1.save_message = "✗ Erreur de chargement"
            phase1.save_message_timer = 3.0
            return False
