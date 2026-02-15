import json
import random
import re
import unicodedata
from typing import Optional
from Game.core.utils import resource_path

class MutationManager:
    def __init__(self, espece):
        self.espece = espece
        self.connues = []          # mutations débloquées
        self.actives = []          # mutations permanentes actives
        self.data = self.load_mutations()
        self._id_aliases = self._build_id_aliases(self.data)

    @staticmethod
    def _canonical_id(nom) -> str:
        return str(nom or "").strip()

    @staticmethod
    def _norm_id(value: str) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.casefold()
        s = re.sub(r"[^0-9a-z]+", "", s)
        return s

    @classmethod
    def _build_id_aliases(cls, data: dict) -> dict[str, str]:
        """
        Map d'alias normalisés -> id canonique (clé exacte du JSON).
        Permet de tolérer les incohérences de casse/accents/espaces dans 'conditions'/'incompatibles'.
        """
        aliases: dict[str, str] = {}
        for mid, mdata in (data or {}).items():
            key = str(mid or "").strip()
            if not key:
                continue
            aliases.setdefault(cls._norm_id(key), key)
            if isinstance(mdata, dict):
                nom = mdata.get("nom")
                if nom:
                    aliases.setdefault(cls._norm_id(nom), key)
        return aliases

    def _resolve_mutation_id(self, ref: str) -> str:
        ref = self._canonical_id(ref)
        if not ref:
            return ref
        if ref in (self.data or {}):
            return ref
        resolved = self._id_aliases.get(self._norm_id(ref))
        return resolved or ref

    def _notify_renderers(self) -> None:
        """Rafraîchit les renderers des individus existants (variants/overlays)."""
        for individu in getattr(self.espece, "individus", []) or []:
            renderer = getattr(individu, "renderer", None)
            if renderer is not None and hasattr(renderer, "update_from_mutations"):
                try:
                    renderer.update_from_mutations()
                except Exception:
                    pass

    def _mutations_en_cours(self) -> set[str]:
        """
        Retourne l'ensemble des mutations actuellement appliquées à l'espèce,
        qu'elles soient permanentes ou définies comme mutations de base au démarrage.
        """
        base = getattr(self.espece, "base_mutations", []) or []
        return {self._canonical_id(x) for x in (list(self.actives) + list(base)) if self._canonical_id(x)}

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
        nom = self._resolve_mutation_id(nom)
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

        for categorie, d in (effets or {}).items():
            if not isinstance(d, dict):
                continue
            # 1) appliquer sur l'espèce (si ça a du sens)
            if apply_to_species:
                attr_espece = mapping_espece.get(categorie)
                if attr_espece:
                    cible_espece = getattr(self.espece, attr_espece, None)
                    if isinstance(cible_espece, dict):
                        for stat, delta in d.items():
                            if not isinstance(delta, (int, float)):
                                continue
                            if stat not in cible_espece or cible_espece.get(stat) is None:
                                cible_espece[stat] = 0
                            if isinstance(cible_espece.get(stat), (int, float)):
                                cible_espece[stat] += delta
                            else:
                                print(f"[Mutations] Stat '{stat}' non numérique dans '{attr_espece}' (espèce)")

            # 2) appliquer sur chaque individu existant
            if apply_to_individus:
                for individu in self.espece.individus:
                    cible_individu = getattr(individu, categorie, None)
                    if not isinstance(cible_individu, dict):
                        # ex : combat peut ne pas exister dans certains cas
                        continue
                    for stat, delta in d.items():
                        if not isinstance(delta, (int, float)):
                            continue
                        if stat not in cible_individu or cible_individu.get(stat) is None:
                            cible_individu[stat] = 0
                        if isinstance(cible_individu.get(stat), (int, float)):
                            cible_individu[stat] += delta
                        # Garder compat : detection/detection_visuelle existent parfois dans environnement.
                        if categorie == "sens" and stat in ("detection", "detection_visuelle"):
                            env = getattr(individu, "environnement", None)
                            if isinstance(env, dict) and isinstance(env.get(stat, 0), (int, float)):
                                env[stat] = cible_individu.get(stat, env.get(stat))


    # -------------------------
    # Ajouter une mutation permanente
    # -------------------------
    def appliquer(self, nom):
        nom = self._resolve_mutation_id(nom)
        if not nom:
            return

        # Idempotent: ne jamais ré-appliquer une mutation déjà acquise.
        if nom in self._mutations_en_cours():
            return

        mutation = self.get_mutation(nom)
        if mutation is None:
            return

        effets = mutation.get("effets", {})
        self.apply_effects(effets, nom)

        if nom not in self.actives:
            self.actives.append(nom)
        self._notify_renderers()

        print(f"[Mutations] '{nom}' appliquée")

    def appliquer_temporaire(self, nom):
        """Deprecated: le système d'effets temporaires a été retiré."""
        # On garde la méthode pour compat (éviter crash si appelé par erreur).
        print(f"[Mutations] Effets temporaires supprimés: '{self._canonical_id(nom)}' ignorée.")

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
            mut_id = self._resolve_mutation_id(mut_id)
            if not mut_id:
                continue

            # Idempotent (utile pour preview / rechargements partiels).
            if mut_id in self._mutations_en_cours():
                if mut_id not in applied:
                    applied.append(mut_id)
                continue

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

    def update(self):
        # Le système d'effets temporaires est supprimé: rien à mettre à jour.
        return
    
    def mutation_disponible(self, nom):
        nom = self._resolve_mutation_id(nom)
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
        incompatibles = {self._resolve_mutation_id(x) for x in (set(incompatibles_1) | set(incompatibles_2)) if self._canonical_id(x)}

        # toutes les conditions doivent être remplies
        for cond in conditions:
            cond = self._resolve_mutation_id(cond)
            if cond and cond not in mutations_actuelles:
                return False

        # aucune incompatibilité ne doit être active
        for inc in incompatibles:
            if inc and inc in mutations_actuelles:
                return False

        # Sens inverse: si une mutation déjà acquise déclare nom comme incompatible,
        # on considère aussi que nom n'est pas disponible (JSON parfois non symétrique).
        for active_id in mutations_actuelles:
            active_data = self.get_mutation(active_id)
            if not isinstance(active_data, dict):
                continue
            a_inc1 = active_data.get("incompatibles", []) or []
            a_inc2 = active_data.get("imcompatibles", []) or []
            a_incompat = {self._resolve_mutation_id(x) for x in (set(a_inc1) | set(a_inc2)) if self._canonical_id(x)}
            if nom in a_incompat:
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
