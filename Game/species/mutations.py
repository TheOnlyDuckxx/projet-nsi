# Game/espece/mutations.py
import json
import random
import time
from typing import Optional
from Game.core.utils import resource_path

class MutationManager:
    def __init__(self, espece):
        self.espece = espece
        self.connues = []          # mutations débloquées
        self.actives = []          # mutations permanentes actives
        self.temporaires = {}      # { nom : timestamp_expiration }
        self.data = self.load_mutations()

    def _mutations_en_cours(self) -> set[str]:
        """
        Retourne l'ensemble des mutations actuellement appliquées à l'espèce,
        qu'elles soient permanentes, temporaires ou définies comme mutations
        de base au démarrage.
        """
        base = getattr(self.espece, "base_mutations", []) or []
        temporaires = self.temporaires.keys()
        return set(self.actives) | set(base) | set(temporaires)

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
    def apply_effects(self, effets, nom, *, apply_to_species: bool = True, apply_to_individus: bool = True):
        """
        Applique les effets :
        - sur les stats de base de l'ESPÈCE (base_physique, base_sens, etc.)
        - sur TOUTES les instances d'Individu déjà existantes.
        """

        # mapping catégorie JSON -> attributs de l'espèce
        mapping_espece = {
            "physique": "base_physique",
            "sens": "base_sens",
            "mental": "base_mental",
            "environnement": "base_environnement",
            "social": "base_social",
            "genetique": "genetique",
            # "combat" : plutôt une stat d'individu, pas de base d'espèce
        }

        for categorie, d in effets.items():
            # 1) appliquer sur l'espèce (si ça a du sens)
            if apply_to_species:
                attr_espece = mapping_espece.get(categorie)
                if attr_espece:
                    cible_espece = getattr(self.espece, attr_espece, None)
                    if isinstance(cible_espece, dict):
                        for stat, delta in d.items():
                            if stat in cible_espece:
                                cible_espece[stat] += delta
                            else:
                                print(f"[Mutations] Stat '{stat}' absente dans '{attr_espece}' (espèce)")

            # 2) appliquer sur chaque individu existant
            if apply_to_individus:
                for individu in self.espece.individus:
                    cible_individu = getattr(individu, categorie, None)
                    if not isinstance(cible_individu, dict):
                        # ex : combat peut ne pas exister dans certains cas
                        continue
                    for stat, delta in d.items():
                        if stat in cible_individu:
                            cible_individu[stat] += delta
                        else:
                            # on ne crash pas, juste un log
                            pass


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

        print(f"[Mutations] '{nom}' appliquée")

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
    # Mutations de base (sélection menu espèce)
    # -------------------------
    def apply_base_mutations(self, ids: list[str], *, apply_to_species: bool = True, apply_to_individus: bool = True):
        """
        Applique et enregistre les mutations sélectionnées lors de la création de partie.
        Les mutations sont marquées comme actives pour être reconnues dans les conditions
        et éviter qu'elles soient reproposées en jeu.
        """
        if not ids:
            self.espece.base_mutations = []
            return []

        applied: list[str] = []
        for mut_id in ids:
            mutation = self.get_mutation(mut_id)
            if mutation is None:
                continue

            effets = mutation.get("effets", {})
            self.apply_effects(
                effets,
                mut_id,
                apply_to_species=apply_to_species,
                apply_to_individus=apply_to_individus,
            )

            if mut_id not in self.actives:
                self.actives.append(mut_id)
            applied.append(mut_id)

        # Mémoriser la liste pour l'espèce (utilisé pour _mutations_en_cours)
        if apply_to_species or not getattr(self.espece, "base_mutations", None):
            self.espece.base_mutations = applied

        return applied


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

                print(f"[Mutations] Effet temporaire '{nom}' terminé")
                to_remove.append(nom)
    
    def mutation_disponible(self, nom):
        mutation = self.get_mutation(nom)
        if mutation is None:
            return False

        # Les mutations réservées à la création de partie ne doivent pas être proposées en jeu
        if mutation.get("base", False):
            return False

        mutations_actuelles = self._mutations_en_cours()

        # déjà acquise → pas proposée
        if nom in mutations_actuelles:
            return False

        conditions = mutation.get("conditions", [])
        incompatibles_1 = mutation.get("incompatibles", [])
        incompatibles_2 = mutation.get("imcompatibles", [])  # faute possible dans le JSON
        incompatibles = set(incompatibles_1) | set(incompatibles_2)

        # toutes les conditions doivent être remplies
        for cond in conditions:
            if cond and cond not in self.actives:
                return False

        # aucune incompatibilité ne doit être active
        for inc in incompatibles:
            if inc in mutations_actuelles:
                return False

        return True

    def mutations_disponibles(self):
        """
        Retourne la liste des clés de mutations qui peuvent être proposées au joueur.
        """
        return [nom for nom in self.data.keys() if self.mutation_disponible(nom)]

    def pick_random_available_mutation(self) -> Optional[str]:
        """
        Retourne une mutation disponible au hasard (exclut les mutations de base).
        """
        disponibles = self.mutations_disponibles()
        if not disponibles:
            return None
        return random.choice(disponibles)
