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

    def _consume_resources(self, inventory: List[Dict], cost: Dict[str, int]) -> None:
        """
        Enlève les ressources du sac (mutant la liste inventory).
        Hypothèse : _inventory_counts a déjà vérifié qu'on a assez.
        """
        for res_name, needed in cost.items():
            remaining = needed
            for item in list(inventory):  # copie pour pouvoir remove
                key = item.get("id") or item.get("name")
                if key != res_name:
                    continue

                qty = int(item.get("quantity", 1))
                if qty > remaining:
                    item["quantity"] = qty - remaining
                    remaining = 0
                    break
                else:
                    remaining -= qty
                    inventory.remove(item)

            if remaining > 0:
                # En théorie ne devrait pas arriver si on a vérifié avant
                break

    # ---------- Vérification ----------

    def missing_resources(self, craft_id: str, inventory: List[Dict]) -> Dict[str, int]:
        """
        Retourne un dict {ressource: manquant} pour ce craft.
        Vide si on peut crafter.
        """
        craft_def = self.crafts.get(craft_id)
        if not craft_def:
            return {"_unknown_craft": 1}

        cost: Dict[str, int] = craft_def.get("cost", {})
        if not cost:
            return {}

        counts = self._inventory_counts(inventory)
        missing: Dict[str, int] = {}

        for res_name, required in cost.items():
            have = counts.get(res_name, 0)
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
    ) -> bool:
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
        miss = self.missing_resources(craft_id, inv)
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
            self._consume_resources(inv, cost)

        # --- On applique le résultat ---
        if out_type == "prop" and world is not None and tile is not None:
            pid = output.get("pid")
            if pid is None:
                if notify:
                    notify("Craft mal configuré : pas de 'pid'.")
                return False
            world.overlay[tile[1]][tile[0]] = pid

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
        return True


    
    