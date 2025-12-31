# Game/species/comportement.py
import json
import math
import random
from Game.core.utils import resource_path
from Game.ui.hud.notification import add_notification

class Comportement:
    def __init__(self, espece):
        self.e = espece
        self.items_db = self._load_items_db()

    # ---------- Items / poids ----------
    def _load_items_db(self):
        p = resource_path("Game/data/items.json")
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)


    def _item_weight(self, item_id: str) -> float:
        meta = self.items_db.get(item_id, {})
        # accepte "poid" ou "poids"
        return float(meta.get("poids", meta.get("poid", 1.0)))

    def _inventory_weight(self) -> float:
        total = 0.0
        for stack in self.e.carrying:
            qty = stack.get("quantity", stack.get("qty", 0))
            total += self._item_weight(stack["id"]) * qty
        return total


    def _add_to_inventory(self, item_id: str, qty: int) -> int:
        if qty <= 0:
            return 0
        limit = float(self.e.physique.get("weight_limit", 10))
        left_capacity = max(0.0, limit - self._inventory_weight())
        per_unit = max(1e-6, self._item_weight(item_id))
        can_take = int(left_capacity // per_unit)
        take = max(0, min(qty, can_take))
        if take == 0:
            return 0

        # Infos tirées de la base items.json
        meta = self.items_db.get(item_id, {})
        name = meta.get("nom", item_id)
        type_ = meta.get("type", "resource")
        weight = float(meta.get("poids", 1.0))

        for stack in self.e.carrying:
            if stack["id"] == item_id:
                stack["quantity"] += take
                break
        else:
            self.e.carrying.append({
                "id": item_id,
                "name": name,
                "type": type_,
                "weight": weight,
                "quantity": take,
            })
        return take


    # ---------- Tables de loot par prop ----------


    def _drops_for_prop(self,pid):
        """
        Gère le drop des ressources lors de la récolte
        La table gère le nombre de ressource (entre min et max) et la problabilité (p)
        """
        key = pid
        drops = []
        tables = {
            13: [
                {"id": "stone", "min": 1, "max": 3, "p": 1.0},   # toujours
                {"id": "flint", "min": 1, "max": 1, "p": 0.15}   # 15% de chance
            ],

            17:[
                {"id": "berries", "min": 3, "max": 7, "p": 1.0}
            ],

            10:[
                {"id": "wood", "min": 1, "max": 3, "p": 1.0}
            ],
            16: [  # bush
                {"id": "fiber", "min": 1, "max": 3, "p": 0.60},
                {"id": "seed",  "min": 1, "max": 2, "p": 0.25},
                {"id": "straw", "min": 1, "max": 2, "p": 0.30}
            ],

            18: [  # reeds (roseaux)
                {"id": "fiber", "min": 2, "max": 5, "p": 1.0},
                {"id": "straw", "min": 1, "max": 3, "p": 0.50}
            ],

            33: [  # vine (liane)
                {"id": "fiber", "min": 2, "max": 4, "p": 1.0},
                {"id": "rope",  "min": 1, "max": 1, "p": 0.08}  # petit bonus rare
            ],

            34: [  # mushroom
                {"id": "food",  "min": 1, "max": 2, "p": 0.70},
                {"id": "water", "min": 1, "max": 1, "p": 0.10}
                # (si vous gérez des statuts plus tard : 15% "poison" / maladie)
            ],

            36: [  # nest (nid)
                {"id": "seed",  "min": 1, "max": 4, "p": 0.85},
                {"id": "food",  "min": 1, "max": 2, "p": 0.25}
            ],

            37: [  # beehive (ruche)
                {"id": "food",  "min": 2, "max": 5, "p": 0.50}
                # (plus tard : déclenche event "piqûres" si pas équipé)
            ],

            38: [  # freshwater_pool (mare)
                {"id": "water", "min": 2, "max": 6, "p": 1.0}
            ],

            # --- Bois / arbres ---
            21: [  # stump (souche)
                {"id": "wood",      "min": 1, "max": 2, "p": 1.0},
                {"id": "hard_wood", "min": 1, "max": 1, "p": 0.12}
            ],

            22: [  # log (tronc)
                {"id": "wood",      "min": 2, "max": 5, "p": 1.0},
                {"id": "hard_wood", "min": 1, "max": 2, "p": 0.20}
            ],

            19: [  # driftwood (bois flotté)
                {"id": "wood",  "min": 1, "max": 3, "p": 1.0},
                {"id": "fiber", "min": 1, "max": 2, "p": 0.25}
            ],

            12: [  # tree_dead
                {"id": "wood",  "min": 1, "max": 2, "p": 1.0},
                {"id": "flint", "min": 1, "max": 1, "p": 0.05}
            ],

            14: [  # palm
                {"id": "wood",  "min": 1, "max": 3, "p": 1.0},
                {"id": "fiber", "min": 1, "max": 3, "p": 0.45},
                {"id": "seed",  "min": 1, "max": 2, "p": 0.20}
            ],

            15: [  # cactus
                {"id": "water", "min": 1, "max": 2, "p": 0.40},
                {"id": "fiber", "min": 1, "max": 2, "p": 0.30}
                # (plus tard : petit risque de dégâts si récolte sans outil)
            ],

            # --- Roches / minerais ---
            23: [  # boulder (gros rocher)
                {"id": "stone", "min": 2, "max": 6, "p": 1.0},
                {"id": "flint", "min": 1, "max": 2, "p": 0.20}
            ],

            32: [  # clay_pit (argile)
                {"id": "clay",  "min": 2, "max": 6, "p": 1.0},
                {"id": "stone", "min": 1, "max": 2, "p": 0.25}
            ],

            29: [  # ore_copper
                {"id": "copper_ore", "min": 1, "max": 3, "p": 1.0},
                {"id": "stone",      "min": 1, "max": 2, "p": 0.35}
            ],

            30: [  # ore_iron
                {"id": "iron_ore", "min": 1, "max": 3, "p": 1.0},
                {"id": "stone",    "min": 1, "max": 2, "p": 0.35}
            ],

            31: [  # ore_gold (rare)
                {"id": "gold_ore", "min": 1, "max": 2, "p": 1.0},
                {"id": "stone",    "min": 1, "max": 2, "p": 0.50}
            ],

            # --- Loot “squelette / chasse” ---
            35: [  # bone_pile
                {"id": "leather", "min": 1, "max": 2, "p": 0.35},
                {"id": "flint",   "min": 1, "max": 1, "p": 0.10},
                {"id": "stone",   "min": 1, "max": 2, "p": 0.30}
            ]
        }
        try :
            conf = tables[key]
            for entry in conf:
                if random.random() <= entry["p"]:
                    qty = random.randint(entry["min"], entry["max"])
                    drops.append((entry["id"], qty))
            return drops
        except :
            return [("stone",1)]
    # fallback basique

    # ---------- API publique ----------
    def _dismantle_drops(self, craft_def):
        drops = []
        if not craft_def:
            return drops
        cost = craft_def.get("cost", {}) or {}
        for res, amt in cost.items():
            try:
                qty = int(math.ceil(float(amt) * 0.3))
            except Exception:
                qty = 0
            if qty > 0:
                drops.append((res, qty))
        return drops

    def _prop_key(self, i, j, pid):
        # normalise pour comparer proprement
        return (int(i), int(j), str(pid))

    def _construction_cell(self, world, i, j):
        try:
            return world.overlay[int(j)][int(i)] if world and getattr(world, "overlay", None) is not None else None
        except Exception:
            return None

    def build_construction(self, objectif, world):
        if not objectif or objectif[0] != "construction":
            self.e.ia["etat"] = "idle"
            return
        i, j = objectif[1]
        cell = self._construction_cell(world, i, j)
        if not (isinstance(cell, dict) and cell.get("state") == "building"):
            self.e.ia["etat"] = "idle"
            self.e.work = None
            return

        required = max(1e-3, float(cell.get("work_required", 1.0)))
        done = float(cell.get("work_done", 0.0))
        self.e.work = {
            "type": "build",
            "i": int(i),
            "j": int(j),
            "progress": max(0.0, min(1.0, done / required)),
        }
        self.e.ia["etat"] = "construction"

    def recolter_ressource(self, objectif, world):
        if not objectif or objectif[0] != "prop":
            self.e.ia["etat"] = "idle"
            return

        i, j, pid = objectif[1]
        new_key = self._prop_key(i, j, pid)

        w = getattr(self.e, "work", None)
        if w and w.get("type") == "harvest":
            cur_key = self._prop_key(w["i"], w["j"], w["pid"])
            if cur_key == new_key:
                # on force juste l'état si besoin et on sort
                self.e.ia["etat"] = "recolte"
                return

        # Durée de base (s) + accélération par stats (force/dex/endurance)
        base = 2.5
        force = float(self.e.physique.get("force", 5))
        dex   = float(self.e.mental.get("dexterite", 5))
        endu  = float(self.e.physique.get("endurance", 5))

        # facteur ~1.0 à stats moyennes; borné pour éviter les extrêmes
        accel = (0.6 + 0.08 * force + 0.06 * dex + 0.04 * endu) / 5.0
        accel = max(0.3, min(3.0, accel))
        duration = max(0.4, base / accel)

        self.e.work = {
            "type": "harvest",
            "i": int(i), "j": int(j), "pid": pid,
            "t": 0.0, "t_need": float(duration),
            "progress": 0.0,
            "drops": self._drops_for_prop(pid),
        }
        self.e.ia["etat"] = "recolte"
    
    def cancel_work(self, reason: str | None = None):
        """
        Annule immédiatement toute récolte en cours : stoppe la barre,
        nettoie l'objectif, et remet l'IA au neutre.
        """
        # stoppe la progression + barre
        if getattr(self.e, "work", None):
            self.e.work = None

        # si on était en "recolte" ou en chemin vers un prop, repasse idle
        etat = self.e.ia.get("etat")
        if etat in ("recolte", "se_deplace_vers_prop", "construction", "se_deplace_vers_construction", "interaction", "demonte"):
            self.e.ia["etat"] = "idle"

        # on oublie l'objectif lié
        self.e.ia["objectif"] = None
        self.e.ia["order_action"] = None
        self.e.ia["target_craft_id"] = None

    def try_eating(self):
        item = self.e.find_item_in_inventory("berries")
        if item:
            item["quantity"] -= 1
            if item["quantity"] <= 0:
                self.e.carrying.remove(item)
        self.e.jauges["faim"]=100


    def update(self, dt: float, world):
        """
        À appeler chaque frame depuis Phase1.update.
        Fait avancer la barre et, si terminé, distribue le loot,
        puis supprime le prop de la map.
        """
        w = getattr(self.e, "work", None)
        if not w:
            return

        if w.get("type") == "build":
            if self.e.ia.get("etat") != "construction":
                return

            cell = self._construction_cell(world, w.get("i"), w.get("j"))
            if not (isinstance(cell, dict) and cell.get("state") == "building"):
                self.e.work = None
                self.e.ia["etat"] = "idle"
                self.e.ia["objectif"] = None
                return

            required = max(1e-3, float(cell.get("work_required", 1.0)))
            speed = 0.8 + 0.12 * float(self.e.mental.get("dexterite", 5)) \
                + 0.06 * float(self.e.physique.get("force", 5)) \
                + 0.05 * float(self.e.mental.get("intelligence", 5))
            speed = max(0.2, min(6.0, speed))

            cell["work_done"] = float(cell.get("work_done", 0.0)) + dt * speed
            w["progress"] = min(1.0, cell["work_done"] / required)

            if cell["work_done"] >= required:
                # Finalise la construction sur la carte
                pid = cell.get("pid")
                try:
                    world.overlay[int(w["j"])][int(w["i"])] = {
                        "pid": pid,
                        "state": "built",
                        "craft_id": cell.get("craft_id"),
                        "name": cell.get("name"),
                        "built": True,
                        "cost": cell.get("cost"),
                    }
                except Exception:
                    pass
                self.e.work = None
                self.e.ia["etat"] = "idle"
                self.e.ia["objectif"] = None
                self.e.ia["order_action"] = None
                self.e.ia["target_craft_id"] = None
            return

        if w.get("type") == "interact":
            if self.e.ia.get("etat") != "interaction":
                return
            w["t"] = float(w.get("t", 0.0)) + dt
            t_need = max(0.2, float(w.get("t_need", 0.6)))
            w["progress"] = min(1.0, w["t"] / t_need)
            if w["t"] < t_need:
                return

            message = w.get("message")
            if message:
                add_notification(message)

            interaction_conf = w.get("interaction_conf") or {}
            interaction_type = interaction_conf.get("type")
            phase = getattr(self.e, "phase", None)
            if interaction_type == "warehouse" and phase:
                moved = phase.deposit_to_warehouse(self.e.carrying)
                if moved > 0:
                    add_notification(f"{self.e.nom} a stocké {moved} ressources.")
            elif callable(interaction_conf.get("on_complete")):
                try:
                    interaction_conf["on_complete"](self.e, phase)
                except Exception:
                    pass

            self.e.work = None
            self.e.ia["etat"] = "idle"
            self.e.ia["objectif"] = None
            self.e.ia["order_action"] = None
            self.e.ia["target_craft_id"] = None
            return

        if w.get("type") == "dismantle":
            if self.e.ia.get("etat") != "demonte":
                return
            w["t"] = float(w.get("t", 0.0)) + dt
            t_need = max(0.3, float(w.get("t_need", 1.0)))
            w["progress"] = min(1.0, w["t"] / t_need)
            if w["t"] < t_need:
                return

            taken_total = 0
            drops = w.get("drops", [])
            if drops:
                for item_id, qty in drops:
                    took = self._add_to_inventory(item_id, int(qty))
                    taken_total += took
            if taken_total > 0:
                self.e.add_xp(taken_total * 8)
            elif drops:
                add_notification(f"{self.e.nom} : inventaire plein !")

            try:
                if world and getattr(world, "overlay", None):
                    world.overlay[int(w.get("j", 0))][int(w.get("i", 0))] = 0
            except Exception:
                pass

            self.e.work = None
            self.e.ia["etat"] = "idle"
            self.e.ia["objectif"] = None
            self.e.ia["order_action"] = None
            self.e.ia["target_craft_id"] = None
            return

        if self.e.ia.get("etat") != "recolte":
            return

        w["t"] += dt
        w["progress"] = min(1.0, w["t"] / w["t_need"])

        if w["t"] < w["t_need"]:
            return

        # Récolte terminée → ajoute les items (sous limite de poids)
        taken_total = 0
        for item_id, qty in w["drops"]:
            took = self._add_to_inventory(item_id, int(qty))
            taken_total += took
            leftover = int(qty) - int(took)
            if leftover > 0:
                # TODO: à adapter à ton système d'objets au sol
                # ex: world.drop_item(w["i"], w["j"], item_id, leftover)
                pass
        if taken_total <= 0:
            add_notification(f"{self.e.nom} : inventaire plein !")
            self.e.work = None
            self.e.ia["etat"] = "idle"
            self.e.ia["order_action"] = None
            self.e.ia["target_craft_id"] = None
            return
        self.e.add_xp(taken_total*10)

        try:
            if world and getattr(world, "overlay", None):
                if 0 <= w["j"] < len(world.overlay) and 0 <= w["i"] < len(world.overlay[0]):
                    world.overlay[w["j"]][w["i"]] = 0
        except Exception:
            pass

        self.e.work = None
        self.e.ia["etat"] = "idle"
        self.e.ia["order_action"] = None
        self.e.ia["target_craft_id"] = None

    # ---------- Interactions avec les constructions ----------
    def interact_with_craft(self, objectif, world, craft_def=None):
        if not objectif or objectif[0] != "prop":
            self.e.ia["etat"] = "idle"
            self.e.ia["order_action"] = None
            self.e.ia["objectif"] = None
            return

        i, j, pid = objectif[1]
        craft_def = craft_def or {}
        interaction_conf = craft_def.get("interaction")
        message = None
        if isinstance(interaction_conf, dict):
            message = interaction_conf.get("message")
        elif isinstance(interaction_conf, str):
            message = interaction_conf

        duration = 0.6
        self.e.work = {
            "type": "interact",
            "i": int(i),
            "j": int(j),
            "pid": pid,
            "t": 0.0,
            "t_need": float(duration),
            "progress": 0.0,
            "message": message,
            "interaction_conf": interaction_conf if isinstance(interaction_conf, dict) else {},
            "craft_id": craft_def.get("id") or craft_def.get("craft_id"),
        }
        self.e.ia["etat"] = "interaction"
        self.e.ia["order_action"] = "interact"

    def dismantle_craft(self, objectif, world, craft_def=None):
        if not objectif or objectif[0] != "prop":
            self.e.ia["etat"] = "idle"
            self.e.ia["order_action"] = None
            self.e.ia["objectif"] = None
            return
        i, j, pid = objectif[1]
        drops = self._dismantle_drops(craft_def)

        base = 2.4
        force = float(self.e.physique.get("force", 5))
        dex   = float(self.e.mental.get("dexterite", 5))
        endu  = float(self.e.physique.get("endurance", 5))
        accel = (0.6 + 0.08 * force + 0.06 * dex + 0.04 * endu) / 5.0
        accel = max(0.3, min(3.0, accel))
        duration = max(0.5, base / accel)

        self.e.work = {
            "type": "dismantle",
            "i": int(i),
            "j": int(j),
            "pid": pid,
            "t": 0.0,
            "t_need": float(duration),
            "progress": 0.0,
            "drops": drops,
            "craft_name": craft_def.get("name") if craft_def else None,
        }
        self.e.ia["etat"] = "demonte"
        self.e.ia["order_action"] = "dismantle"
