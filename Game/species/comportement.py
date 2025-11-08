# Game/species/comportement.py
import os, json, random
from Game.core.utils import resource_path

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
        for stack in self.e.carrying:  # [{'id':..., 'qty':...}]
            total += self._item_weight(stack["id"]) * stack["qty"]
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
        for stack in self.e.carrying:
            if stack["id"] == item_id:
                stack["qty"] += take
                break
        else:
            self.e.carrying.append({"id": item_id, "qty": take})
        return take

    # ---------- Tables de loot par prop ----------


    def _drops_for_prop(self,pid):
        """
        Gère le drop des ressources lors de la récolte
        La table gère le nombre de ressource (entre min et max) et la problabilité (p)
        """
        key = str(pid)
        drops = []
        tables = {
            "rock": [
                {"id": "stone", "min": 1, "max": 3, "p": 1.0},   # toujours
                {"id": "flint", "min": 1, "max": 1, "p": 0.15}   # 15% de chance
            ]
        }

        conf = tables.get(key, [])
        for entry in conf:
            if random.random() <= entry.get("p", 1.0):
                qty = random.randint(entry["min"], entry["max"])
                drops.append((entry["id"], qty))
        return drops or [("stone", 1)]  # fallback
    # fallback basique

    # ---------- API publique ----------
    def _prop_key(self, i, j, pid):
        # normalise pour comparer proprement
        return (int(i), int(j), str(pid))

    def recolter_ressource(self, objectif, world):
        if not objectif or objectif[0] != "prop":
            self.e.ia["etat"] = "idle"
            return

        i, j, pid = objectif[1]
        new_key = self._prop_key(i, j, pid)

        # 🔒 Anti-reset : si on travaille déjà sur CE prop, ne rien réinitialiser
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
        dex   = float(self.e.mental.get("dexterité", 5))
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
        if etat in ("recolte", "se_deplace_vers_prop"):
            self.e.ia["etat"] = "idle"

        # on oublie l'objectif lié
        self.e.ia["objectif"] = None


    def update(self, dt: float, world):
        """
        À appeler chaque frame depuis Phase1.update.
        Fait avancer la barre et, si terminé, distribue le loot,
        puis supprime le prop de la map.
        """
        w = getattr(self.e, "work", None)
        if not w or self.e.ia.get("etat") != "recolte":
            return

        w["t"] += dt
        w["progress"] = min(1.0, w["t"] / w["t_need"])

        if w["t"] < w["t_need"]:
            return

        # Récolte terminée → ajoute les items (sous limite de poids)
        for item_id, qty in w["drops"]:
            self._add_to_inventory(item_id, int(qty))

        # Supprime le prop de la carte
        try:
            if world and getattr(world, "overlay", None):
                if 0 <= w["j"] < len(world.overlay) and 0 <= w["i"] < len(world.overlay[0]):
                    world.overlay[w["j"]][w["i"]] = 0
        except Exception:
            pass

        self.e.work = None
        self.e.ia["etat"] = "idle"


