# Game/espece/species.py

from copy import deepcopy
import random
from Game.gameplay.level_up import LevelUp
from .mutations import MutationManager
from .comportement import Comportement
from .reproduction import ReproductionSystem
from .sprite_render import EspeceRenderer


ROLE_CLASSES = ("savant", "pacifiste", "croyant", "belligerant")
ROLE_CLASS_LABELS = {
    "savant": "Savant",
    "pacifiste": "Pacifiste",
    "croyant": "Croyant",
    "belligerant": "Belligerant",
}

MAIN_CLASS_PHYSIQUE_BONUS = {
    "force": 1,
    "endurance": 1,
    "vitesse": 1,
}

def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


class Espece:
    """
    Représente une ESPÈCE (stats globales, XP commune, arbre de phase 3, génétique, etc.)
    Les individus concrets sont des instances de la classe Individu ci-dessous.
    """
    def __init__(self, nom: str):
        self.nom = nom

        # === Stats de base d'espèce ===
        self.base_physique = {
            "taille": 5,
            "force": 5,
            "endurance": 5,
            "vitesse": 5,
            "vitesse de nage": 5,
            "stockage_energetique": 5,
            "weight_limit": 20,
        }

        self.base_sens = {
            "vision": 5,
            "vision_nocturne": 0,
        }

        self.base_mental = {
            "intelligence": 5,
            "dexterite": 5,
            "agressivite": 5,
        }

        self.base_environnement = {
            "resistance_froid": 5,
            "resistance_chaleur": 5,
            "adaptabilite": 5,
        }

        self.base_social = {
            # Réservé pour une future phase sociale. On garde un dict pour compat saves/menus.
        }

        self.genetique = {
            "mutation_rate": 0.10,
        }
        self.mutation_interval = 1  # intervalle actuel entre deux mutations gagnées
        self.next_mutation_level = 2  # premier niveau où une mutation est proposée

        self.arbre_phases3 = {
            "autorité": 5, "strategie": 5, "organisation": 5,
            "culture": 5, "science": 5, "raison": 5,
            "ferveur": 5, "moralité": 5, "harmonie": 5
        }

        # === XP / Niveaux d'espèce ===
        self.species_level = 1
        self.xp = 0
        self.xp_to_next = 100
        self.mutations = MutationManager(self)
        self.lvl_up = LevelUp(self)

        # === Reproduction ===
        self.reproduction_system = ReproductionSystem(self)


        # === Population ===
        self.individus = []
        self.population = 0
        self.main_class = None

    # ---------- API création / gestion d'individus ----------

    def create_individu(self, x: float, y: float, assets):
        """
        Crée un individu appartenant à cette espèce.
        """
        individu = Individu(self, x, y, assets)
        self._apply_main_class_bonus_if_needed(individu)
        return individu

    def remove_individu(self, individu):
        if individu in self.individus:
            self.individus.remove(individu)
            self.population = len(self.individus)

    # ---------- Gestion de l'XP / niveaux d'espèce ----------

    def add_xp(self, amount: float):
        """
        Ajoute de l'XP à l'ESPÈCE (commune à tous les individus).
        À appeler depuis les actions des Individu(s).
        """
        if amount <= 0:
            return

        self.xp += amount
        levels_gained = 0

        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.species_level += 1
            levels_gained += 1

            # Courbe de progression : +25% à chaque niveau (modifiable)
            self.xp_to_next = int(self.xp_to_next * 1.25)

        if levels_gained > 0:
            # Déterminer si une nouvelle mutation doit être proposée (progression ralentissante)
            mutation_popup_triggered = False
            while self.species_level >= self.next_mutation_level:
                target_level = self.next_mutation_level
                self.lvl_up.update_level(target_level)
                mutation_popup_triggered = True

                # L'intervalle augmente progressivement jusqu'à 5 niveaux entre chaque mutation
                self.mutation_interval = min(5, self.mutation_interval + 1)
                self.next_mutation_level += self.mutation_interval

            # Garder current_level cohérent même si aucune mutation n'est déclenchée
            if not mutation_popup_triggered:
                self.lvl_up.current_level = self.species_level

            for _ in range(levels_gained):
                try:
                    self.reproduction_system.on_species_level_up()
                except Exception as e:
                    print(f"[Reproduction] Impossible de créer un œuf: {e}")

    def xp_ratio(self) -> float:
        """
        Ratio 0..1 pour remplir la barre d'XP dans le HUD.
        """
        if self.xp_to_next <= 0:
            return 0.0
        return max(0.0, min(1.0, self.xp / self.xp_to_next))

    def set_main_class(self, class_id: str | None):
        class_id = str(class_id or "").strip().lower()
        if class_id not in ROLE_CLASSES:
            self.main_class = None
            return
        self.main_class = class_id
        for individu in self.individus:
            self._apply_main_class_bonus_if_needed(individu)

    def _apply_main_class_bonus_if_needed(self, individu) -> None:
        if not individu:
            return
        if not self.main_class:
            return
        if getattr(individu, "role_class", None) != self.main_class:
            return
        if getattr(individu, "_main_class_bonus_applied", False):
            return
        physique = getattr(individu, "physique", None)
        if not isinstance(physique, dict):
            return
        for stat, delta in MAIN_CLASS_PHYSIQUE_BONUS.items():
            if stat not in physique or not isinstance(physique.get(stat), (int, float)):
                physique[stat] = 0
            physique[stat] += delta
        if hasattr(individu, "recompute_derived_stats"):
            try:
                individu.recompute_derived_stats(adjust_current=True)
            except Exception:
                pass
        individu._main_class_bonus_applied = True


class Individu:
    """
    Représente un INDIVIDU concret dans le monde (position, jauges, IA, mutations…).
    Il référence une Espece qui porte les stats globales et l'XP.
    """

    def __init__(self, espece: Espece, x: float, y: float, assets):
        self.espece = espece          # Référence à l'espèce
        self.nom = espece.nom         # Pratique pour l'affichage
        self.name_locked = False
        self.role_class = random.choice(ROLE_CLASSES)
        self._main_class_bonus_applied = False

        # --- Position dans le monde ---
        self.x = float(x)
        self.y = float(y)

        # --- Stats individuelles (copie des stats de base d'espèce) ---
        self.physique = deepcopy(espece.base_physique)
        self.sens = deepcopy(espece.base_sens)
        self.mental = deepcopy(espece.base_mental)
        self.social = deepcopy(espece.base_social)
        self.genetique = deepcopy(espece.genetique)
        # environnement et combat dépendent de self.sens / self.physique
        self.environnement = {
            "resistance_froid": float(espece.base_environnement.get("resistance_froid", 5) or 5),
            "resistance_chaleur": float(espece.base_environnement.get("resistance_chaleur", 5) or 5),
            "adaptabilite": float(espece.base_environnement.get("adaptabilite", 5) or 5),
        }
        self.combat = {
            "attaque_melee": 0,
            "defense": 5,
            "agilite": 5,
        }

        # --- Jauges purement individuelles ---
        self.jauges = {
            "faim": 20,
            "soif": 50,
            "bonheur": 10,
            "sante": 100,
        }
        self.max_sante = 100.0

        # --- IA et état local ---
        self.ia = {
            "autonomie": True,
            "etat": "idle",
            "objectif": None,
            "order_action": None,
            "target_craft_id": None,
            "vision_portee": 100,
        }

        self.carrying = []
        self.effets_speciaux = []
        self.faim_timer = 0.0

        # === Sous-systèmes individuels ===
        self.mutations = espece.mutations
        self.comportement = Comportement(self)
        self.reproduction = espece.reproduction_system

        # === Rendu ===
        self.renderer = EspeceRenderer(self, assets)

        self.recompute_derived_stats(adjust_current=False)
        self.jauges["sante"] = float(self.max_sante)

        # Enregistrer l'individu dans l'espèce
        self.espece.individus.append(self)
        self.espece.population = len(self.espece.individus)

    def recompute_derived_stats(self, *, adjust_current: bool = True) -> None:
        """
        Recalcule les stats dérivées:
        - points de vie max (self.max_sante)
        - attaque_melee (dépend de force/vitesse/agressivite)
        """
        phys = self.physique if isinstance(getattr(self, "physique", None), dict) else {}
        ment = self.mental if isinstance(getattr(self, "mental", None), dict) else {}
        comb = self.combat if isinstance(getattr(self, "combat", None), dict) else {}

        force = float(phys.get("force", 5) or 5)
        endurance = float(phys.get("endurance", 5) or 5)
        vitesse = float(phys.get("vitesse", 5) or 5)
        taille = float(phys.get("taille", 5) or 5)
        stockage = float(phys.get("stockage_energetique", 5) or 5)
        agress = float(ment.get("agressivite", 5) or 5)

        prev_max = float(getattr(self, "max_sante", 100.0) or 100.0)
        new_max = 40.0 + endurance * 7.0 + taille * 3.0 + force * 2.0 + stockage * 2.0
        new_max = _clamp(float(new_max), 30.0, 320.0)
        self.max_sante = float(new_max)

        # Met à jour l'attaque mêlée “de base”
        comb["attaque_melee"] = 10.0 + force * 4.0 + vitesse * 2.0 + agress

        if not isinstance(getattr(self, "jauges", None), dict):
            return
        cur = float(self.jauges.get("sante", self.max_sante) or 0.0)
        if cur <= 0:
            self.jauges["sante"] = cur
            return
        if not adjust_current or prev_max <= 0:
            self.jauges["sante"] = min(self.max_sante, cur)
            return

        ratio = _clamp(cur / prev_max, 0.0, 1.0)
        self.jauges["sante"] = max(1.0, min(self.max_sante, ratio * self.max_sante))

    def set_name(self, name: str, *, locked: bool = False) -> None:
        cleaned = (name or "").strip()
        if not cleaned:
            return
        self.nom = cleaned
        if locked:
            self.name_locked = True

    # ---------- Boucle de jeu ----------

    def update(self, world):
        self.comportement.update(world)
        self.reproduction.update()
        self.mutations.update()

    def draw(self, screen, view, world):
        self.renderer.render(screen, view, world, self.x, self.y)

    # ---------- Proxy pour l'XP d'espèce ----------

    def add_xp(self, amount: float):
        """
        Pour ne pas tout casser : si du code appelle joueur.add_xp(),
        on route vers l'espèce.
        """
        self.espece.add_xp(amount)

    def xp_ratio(self) -> float:
        return self.espece.xp_ratio()

    @property
    def species_level(self) -> int:
        return self.espece.species_level

    def find_item_in_inventory(self, item_id: str, min_qty: int = 1):
        inv = self.carrying
        if not inv:
            return None

        for item in inv:
            if item.get("id") == item_id and item.get("quantity", 0) >= min_qty:
                return item

        return None 
