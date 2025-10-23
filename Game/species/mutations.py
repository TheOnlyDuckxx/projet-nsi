import json
from Game.core.utils import resource_path

class MutationManager:
    def __init__(self, espece):
        self.espece = espece
        self.connues = []
        self.actives = []
        self.data = self.load_mutations()

    def load_mutations(self):
        with open(resource_path("/data/mutations.json"), "r", encoding="utf-8") as f:
            return json.load(f)

    def appliquer(self, nom):
        mutation = self.data.get(nom)
        if not mutation:
            return

        for categorie, effets in mutation["effets"].items():
            # On applique à la bonne catégorie de stats (physique, sens, mental, etc.)
            cible = getattr(self.espece, categorie, None)
            if not cible:
                continue
            for stat, val in effets.items():
                if stat in cible:
                    cible[stat] += val
                else:
                    print(f"⚠️ Stat inconnue '{stat}' dans catégorie '{categorie}'")

        self.actives.append(nom)

    def update(self):
        # Pour gérer des effets temporaires ou saisonniers
        pass