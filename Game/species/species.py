# Game/espece/species.py

from copy import deepcopy
from Game.gameplay.level_up import LevelUp
from .mutations import MutationManager
from .comportement import Comportement
from .reproduction import ReproductionSystem
from .sensors import Sensors
from .sprite_render import EspeceRenderer


class Espece:
    """
    Représente une ESPÈCE (stats globales, XP commune, arbre de phase 3, génétique, etc.)
    Les individus concrets sont des instances de la classe Individu ci-dessous.
    """
    def __init__(self, nom: str):
        self.nom = nom

        # === Stats de base d'espèce ===
        self.base_physique = {
            "taille": 5, "force": 5, "endurance": 5,
            "vitesse": 5, "vitesse de nage": 5, "stockage_energetique": 5,
            "temperature_corporelle": 37.0, "esperance_vie": 5, "weight_limit": 20
        }

        self.base_sens = {
            "vision": 5, "ouie": 5, "odorat": 5, "echolocalisation": 0,
            "vision_nocturne": 0, "toucher": 1,
        }

        self.base_mental = {
            "intelligence": 5, "dexterite": 5,
            "agressivite": 5, "courage": 5, "sociabilite": 5, "independance": 5,
            "empathie": 5, "creativite": 5, "intimidation": 5,
        }

        self.base_environnement = {
            "resistance_froid": 5, "resistance_chaleur": 5, "resistance_secheresse": 5,
            "resistance_toxines": 5, "discretion": 5, "adaptabilite": 5,
            "resistance_aux_maladies": 5,
            # detection / detection_visuelle seront recalculées côté Individu
        }

        self.base_social = {
            "communication": 5, "charisme": 5, "cohesion": 5, "fidelite": 5,
        }

        self.genetique = {
            "taux_reproduction": 1.0, "mutation_rate": 0.10,
        }

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


        # === Population ===
        self.individus = []
        self.population = 0

    # ---------- API création / gestion d'individus ----------

    def create_individu(self, x: float, y: float, assets):
        """
        Crée un individu appartenant à cette espèce.
        """
        individu = Individu(self, x, y, assets)
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
        leveled_up = False

        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.species_level += 1
            leveled_up = True

            # Courbe de progression : +25% à chaque niveau (modifiable)
            self.xp_to_next = int(self.xp_to_next * 1.25)

        if leveled_up:
            self.lvl_up.update_level(self.species_level)

    def xp_ratio(self) -> float:
        """
        Ratio 0..1 pour remplir la barre d'XP dans le HUD.
        """
        if self.xp_to_next <= 0:
            return 0.0
        return max(0.0, min(1.0, self.xp / self.xp_to_next))


class Individu:
    """
    Représente un INDIVIDU concret dans le monde (position, jauges, IA, mutations…).
    Il référence une Espece qui porte les stats globales et l'XP.
    """

    def __init__(self, espece: Espece, x: float, y: float, assets):
        self.espece = espece          # Référence à l'espèce
        self.nom = espece.nom         # Pratique pour l'affichage

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
            "resistance_froid": espece.base_environnement["resistance_froid"],
            "resistance_chaleur": espece.base_environnement["resistance_chaleur"],
            "resistance_secheresse": espece.base_environnement["resistance_secheresse"],
            "resistance_toxines": espece.base_environnement["resistance_toxines"],
            "discretion": espece.base_environnement["discretion"],
            "adaptabilite": espece.base_environnement["adaptabilite"],
            "resistance_aux_maladies": espece.base_environnement["resistance_aux_maladies"],
            "detection": self.sens["ouie"] * 5 + self.sens["odorat"] * 2 + self.sens["toucher"],
            "detection_visuelle": self.sens["vision"] * 5,
        }
        self.combat = {
            "attaque_melee": 10
                + self.physique["force"] * 4
                + self.physique["vitesse"] * 2
                + self.mental["agressivite"],
            "attaque_distance": 0,
            "defense": 5,
            "agilite": 5,
        }

        # --- Jauges purement individuelles ---
        self.jauges = {
            "faim": 20,
            "soif": 50,
            "energie": self.physique["endurance"],
            "bonheur": 50,
            "sante": 100,
        }

        # --- IA et état local ---
        self.ia = {
            "autonomie": True,
            "etat": "idle",
            "objectif": None,
            "vision_portee": 100,
        }

        self.carrying = []
        self.effets_speciaux = []
        self.faim_timer = 0.0

        # === Sous-systèmes individuels ===
        self.mutations = espece.mutations
        self.comportement = Comportement(self)
        self.reproduction = ReproductionSystem(self)
        self.sensors = Sensors(self)

        # === Rendu ===
        self.renderer = EspeceRenderer(self, assets)

        # Enregistrer l'individu dans l'espèce
        self.espece.individus.append(self)
        self.espece.population = len(self.espece.individus)

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
