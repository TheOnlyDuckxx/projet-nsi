import json

def load_crafts(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

class Craft:

    def __init__(self):
        self.craft = load_crafts("Game/data/crafts.json")

    def check_ressource(self, craftname):
        # Vérifier les ressources nécessaires au craft
        for elt in self.craft[craftname]["cost"]:
            print(elt)
        return True  # Remplacer par une vérification réelle des ressources disponibles

    def craft_item(self, craftname):
        # Fonction pour exécuter le craft
        if self.check_ressource(craftname):
            return craftname  # Retourne le nom du craft réussi pour placer l'objet
        return None

    
    