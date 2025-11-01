# Game/espece/mutations.py
import json
from Game.core.utils import resource_path
class MutationManager:
    def __init__(self, espece):
        self.espece = espece
        self.connues = []
        self.actives = []
        self.data = self.load_mutations()

    def load_mutations(self):
        try:
            with open(resource_path("/data/mutations.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Mutations] Impossible de charger mutations.json : {e}")
            return {}

    def appliquer(self, nom):
        mutation = self.data.get(nom)
        if not mutation:
            print(f"[Mutations] Inconnue : {nom}")
            return

        effets = mutation.get("effets", {})
        for categorie, d in effets.items():
            cible = getattr(self.espece, categorie, None)
            if not isinstance(cible, dict):
                print(f"[Mutations] Catégorie inconnue '{categorie}' pour '{nom}'")
                continue
            for stat, delta in d.items():
                if stat in cible:
                    cible[stat] += delta
                else:
                    print(f"[Mutations] Stat inconnue '{stat}' dans '{categorie}' pour '{nom}'")

        if nom not in self.actives:
            self.actives.append(nom)

    def update(self):
        pass  # effets temporaires/seasonaux plus tard
