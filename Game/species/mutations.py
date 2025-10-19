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
        for cat, effets in mutation["effets"].items():
            for stat, val in effets.items():
                self.espece.stats[cat][stat] += val
        self.actives.append(nom)

    def update(self):
        # pourrait gérer des effets temporaires ou des mutations saisonnières
        pass