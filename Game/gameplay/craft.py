import json
from typing import Dict, List, Tuple, Optional, Callable


def load_crafts(file_path: str) -> Dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


class Craft:
    """
    Système de craft :
    - lit les recettes depuis crafts.json
    - vérifie l'inventaire de l'entité
    - consomme les ressources
    - place le résultat (prop ou item)
    """

    def __init__(self, crafts_file: str = "Game/data/crafts.json"):
        self.crafts: Dict = load_crafts(crafts_file)

    def _compute_work_required(self, craft_def: Dict) -> float:
        """
        Évalue la quantité de travail nécessaire pour terminer une construction.
        Basé principalement sur le coût en ressources, avec un minimum pour les crafts gratuits.
        """
        if "work_required" in craft_def:
            try:
                return float(craft_def["work_required"])
            except Exception:
                pass
        cost = craft_def.get("cost", {}) or {}
        total_cost = sum(max(0, float(v)) for v in cost.values())
        return float(8.0 + total_cost * 1.5)

    # ---------- Utils inventaire ----------

    def _inventory_counts(self, inventory: List[Dict]) -> Dict[str, int]:
        """Regroupe les quantités par nom/id d'item."""
        counts: Dict[str, int] = {}
        for item in inventory:
            key = item.get("id") or item.get("name")
            if not key:
                continue
            qty = int(item.get("quantity", 1))
            counts[key] = counts.get(key, 0) + qty
        return counts

    def _consume_resources(self, inventory: List[Dict], cost: Dict[str, int], storage: Dict[str, int] | None = None) -> None:
        """
        Enlève les ressources en priorisant le stockage partagé (entrepôt),
        puis dans le sac du builder.
        """
        shared = storage if storage is not None else {}

        # 1) Dépense dans le stockage
        remaining = dict(cost)
        for res_name, needed in list(remaining.items()):
            if res_name not in shared:
                continue
            take = min(shared.get(res_name, 0), needed)
            shared[res_name] = max(0, shared.get(res_name, 0) - take)
            remaining[res_name] -= take
            if remaining[res_name] <= 0:
                remaining.pop(res_name, None)

        if not remaining:
            return

        # 2) Puis dans l'inventaire individuel
        for res_name, needed in list(remaining.items()):
            rem = needed
            for item in list(inventory):  # copie pour pouvoir remove
                key = item.get("id") or item.get("name")
                if key != res_name:
                    continue

                qty = int(item.get("quantity", 1))
                if qty > rem:
                    item["quantity"] = qty - rem
                    rem = 0
                    break
                else:
                    rem -= qty
                    inventory.remove(item)

            remaining[res_name] = rem
            if remaining[res_name] <= 0:
                remaining.pop(res_name, None)

        # Nettoie les stacks vides
        inventory[:] = [it for it in inventory if it.get("quantity", 0) > 0]

    # ---------- Vérification ----------

    def missing_resources(self, craft_id: str, inventory: List[Dict], storage: Dict[str, int] | None = None) -> Dict[str, int]:
        """
        Retourne un dict {ressource: manquant} pour ce craft.
        Vide si on peut crafter. Les ressources peuvent provenir
        de l'inventaire du builder ET d'un stockage partagé.
        """
        craft_def = self.crafts.get(craft_id)
        if not craft_def:
            return {"_unknown_craft": 1}

        cost: Dict[str, int] = craft_def.get("cost", {})
        if not cost:
            return {}

        counts = self._inventory_counts(inventory)
        shared = storage or {}
        missing: Dict[str, int] = {}

        for res_name, required in cost.items():
            have = counts.get(res_name, 0) + int(shared.get(res_name, 0))
            if have < required:
                missing[res_name] = required - have

        return missing

    # ---------- Craft principal ----------

    def craft_item(
        self,
        craft_id: str,
        builder,
        world=None,
        tile: Optional[Tuple[int, int]] = None,
        notify: Optional[Callable[[str], None]] = None,
        storage: Dict[str, int] | None = None,
    ) -> Optional[Dict]:
        """
        Tente de crafter et de placer le résultat.
        - builder : entité qui porte l'inventaire (builder.carrying)
        - world   : monde avec .width, .height, .overlay
        - tile    : (i, j) où placer un prop
        - notify  : fonction de notification (ex: add_notification)
        """
        craft_def = self.crafts.get(craft_id)
        if not craft_def:
            if notify:
                notify(f"Craft inconnu : {craft_id}")
            return False

        inv = getattr(builder, "carrying", [])
        miss = self.missing_resources(craft_id, inv, storage)
        if miss:
            if notify:
                if "_unknown_craft" in miss:
                    notify(f"Craft inconnu : {craft_id}")
                else:
                    txt = "Ressources manquantes : " + ", ".join(
                        f"{res} x{n}" for res, n in miss.items()
                    )
                    notify(txt)
            return False

        # Vérif de la case si on veut poser un prop
        output = craft_def.get("output", {})
        out_type = output.get("type", "prop")

        if out_type == "prop":
            if world is None or tile is None:
                if notify:
                    notify("Impossible de placer le craft : pas de monde ou de tuile.")
                return False

            i, j = tile
            if not (0 <= i < world.width and 0 <= j < world.height):
                if notify:
                    notify("Tuile hors du monde.")
                return False

            # On évite de construire sur une tuile occupée
            if getattr(world, "overlay", None) is not None:
                if world.overlay[j][i]:
                    if notify:
                        notify("Impossible de construire ici : la tuile est déjà occupée.")
                    return False

        # --- On consomme les ressources ---
        cost = craft_def.get("cost", {})
        if cost:
            self._consume_resources(inv, cost, storage)

        # --- On applique le résultat ---
        if out_type == "prop" and world is not None and tile is not None:
            pid = output.get("pid")
            if pid is None:
                if notify:
                    notify("Craft mal configuré : pas de 'pid'.")
                return False
            site = {
                "pid": pid,
                "state": "building",
                "work_done": 0.0,
                "work_required": self._compute_work_required(craft_def),
                "name": craft_def.get("name", craft_id),
                "craft_id": craft_id,
                "interaction": craft_def.get("interaction"),
                "cost": cost,
            }
            world.overlay[tile[1]][tile[0]] = site
            if notify:
                notify(f"Construction lancée : {craft_def.get('name', craft_id)}")
            return {"tile": tile, "site": site, "craft_id": craft_id}

        elif out_type == "item":
            # Exemple pour des crafts d'objets à ajouter dans l'inventaire
            item_def = output.get("item", {})
            if item_def:
                builder.carrying.append(
                    {
                        "id": item_def.get("id"),
                        "name": item_def.get("name", item_def.get("id", "Objet")),
                        "quantity": item_def.get("quantity", 1),
                        "type": item_def.get("item_type", "resource"),
                        "weight": item_def.get("weight", 0.0),
                    }
                )

        if notify:
            notify(f"{craft_def.get('name', craft_id)} construit.")
        return {"tile": tile, "site": None, "craft_id": craft_id}


    
    
