# Game/espece/mutations.py
import json
import time
from Game.core.utils import resource_path

class MutationManager:
    def __init__(self, espece):
        self.espece = espece
        self.connues = []          # mutations débloquées
        self.actives = []          # mutations permanentes actives
        self.temporaires = {}      # { nom : timestamp_expiration }
        self.data = self.load_mutations()

    # -------------------------
    # Chargement JSON
    # -------------------------
    def load_mutations(self):
        try:
            with open(resource_path("Game/data/mutations.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Mutations] Impossible de charger mutations.json : {e}")
            return {}

    # -------------------------
    # Vérification mutation
    # -------------------------
    def get_mutation(self, nom):
        mutation = self.data.get(nom)
        if mutation is None:
            print(f"[Mutations] Mutation inconnue : {nom}")
            return None
        return mutation

    # -------------------------
    # Application brute des effets
    # -------------------------
    def apply_effects(self, effets, nom):
        for categorie, d in effets.items():
            cible = getattr(self.espece, categorie, None)

            if not isinstance(cible, dict):
                print(f"[Mutations] Catégorie '{categorie}' inconnue pour '{nom}'")
                continue

            for stat, delta in d.items():
                if stat not in cible:
                    print(f"[Mutations] Stat '{stat}' absente dans catégorie '{categorie}'")
                    continue
                cible[stat] += delta

    # -------------------------
    # Ajouter une mutation permanente
    # -------------------------
    def appliquer(self, nom):
        mutation = self.get_mutation(nom)
        if mutation is None:
            return

        effets = mutation.get("effets", {})
        self.apply_effects(effets, nom)

        if nom not in self.actives:
            self.actives.append(nom)

        print(f"[Mutations] '{nom}' appliquée 👍")

    # -------------------------
    # Ajouter une mutation temporaire
    # -------------------------
    def appliquer_temporaire(self, nom):
        mutation = self.get_mutation(nom)
        if mutation is None:
            return

        temp = mutation.get("effets_temporaire")
        if not temp:
            print(f"[Mutations] Pas d'effet temporaire dans : {nom}")
            return

        duree = temp.get("durée", 0)
        effets = temp.get("effets", {})

        # appliquer les effets
        self.apply_effects(effets, nom)

        # enregistrer l'expiration
        fin = time.time() + duree
        self.temporaires[nom] = {
            "expire": fin,
            "effets": effets
        }

        print(f"[Mutations] Effet temporaire '{temp.get('nom')}' activé pour {duree} sec.")


    # -------------------------
    # Mise à jour des effets temporaires
    # -------------------------
    def update(self):
        now = time.time()
        to_remove = []

        for nom, info in self.temporaires.items():
            if now >= info["expire"]:
                # inverser les effets
                effets = info["effets"]
                effets_inverse = {
                    cat: {stat: -delta for stat, delta in d.items()}
                    for cat, d in effets.items()
                }
                self.apply_effects(effets_inverse, nom)

                print(f"[Mutations] Effet temporaire '{nom}' terminé ❌")
                to_remove.append(nom)