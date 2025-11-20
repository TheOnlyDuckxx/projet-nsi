# Game/espece/species.py
from .mutations import MutationManager
from .comportement import Comportement
from .reproduction import ReproductionSystem
from .sensors import Sensors
from .sprite_render import EspeceRenderer

class Espece:
    def __init__(self, nom, x, y, assets):
        self.nom = nom
        self.x = float(x)  # coordonnées tuile
        self.y = float(y)

        # === Stats (inchangées, tes dicos séparés) ===
        self.physique = {
            "taille": 5, "force": 5, "endurance": 5,
            "vitesse": 5,"vitesse de nage" : 5, "stockage_energetique": 5,
            "temperature_corporelle": 37.0, "esperance_vie": 5, "weight_limit":2.5
        }
        self.sens = {
            "vision": 5, "ouie": 5, "odorat": 5, "echolocalisation": 0,
            "vision_nocturne": 0, "toucher": 1,
        }
        self.mental = {
            "intelligence": 5, "dexterite": 5,
            "agressivite": 5, "courage": 5, "sociabilite": 5, "independance": 5,
            "empathie": 5, "creativite": 5, "intimidation": 5, 
        }
        self.jauges = {
            "faim": 50, "soif": 50, "energie": self.physique["endurance"], "bonheur": 50,
            "sante": 100,
        }
        self.environnement = {
            "resistance_froid": 5, "resistance_chaleur": 5, "resistance_secheresse": 5,
            "resistance_toxines": 5, "discretion": 5, "adaptabilite": 5,"resistance_aux_maladies": 5,
            "detection" : self.sens["ouie"] * 5 + self.sens["odorat"]* 2 + self.sens["toucher"], "detection_visuelle": self.sens["vision"] * 5,
        }
        self.social = {
            "communication":5,"charisme": 5, "cohesion": 5, "fidelite": 5, 
        }
        self.genetique = {
            "taux_reproduction": 1.0, "mutation_rate": 0.10,
        }
        self.combat = { 
            "attaque_melee": 10+self.physique["force"] * 4+ self.physique["vitesse"] * 2+ self.mental["agressivite"], "attaque_distance": 0, "defense": 5, "agilite": 5,
        }
        self.arbre_phases3 = {
            "autorité" : 5,"strategie": 5, "organisation":5, "culture": 5, "science": 5,"raison": 5, "ferveur": 5,  "moralité": 5, "harmonie": 5
        }
        self.ia = {
            "autonomie": True, "etat": "idle", "objectif": None, "vision_portee": 100,
        }
        self.carrying = []
        self.effets_speciaux = []
        # === Sous-systèmes ===
        self.mutations = MutationManager(self)
        self.comportement = Comportement(self)
        self.reproduction = ReproductionSystem(self)
        self.sensors = Sensors(self)

        self.population = 1
        self.autonomie = True

        # === XP / Niveaux d'espèce ===
        self.species_level = 1
        self.xp = 0
        self.xp_to_next = 100


        # === Rendu ===
        self.renderer = EspeceRenderer(self, assets)


    def update(self, world):
        self.comportement.update(world)
        self.reproduction.update()
        self.mutations.update()

    def draw(self, screen, view, world):
        self.renderer.render(screen, view, world, self.x, self.y)
    def get(self,n):
        return self[n]


    # --- Gestion de l'XP / niveaux d'espèce ---

    def add_xp(self, amount: float):
        """
        Ajoute de l'XP à l'espèce.
        Pour l'instant tu pourras appeler ça depuis les actions importantes
        (récolte réussie, construction d'un bâtiment, découverte, etc.)
        """
        if amount <= 0:
            return

        self.xp += amount

        # Gestion du passage de niveau (progression simple, tu pourras l'affiner)
        leveled_up = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.species_level += 1
            leveled_up = True

            # Courbe de progression : +25% à chaque niveau (modifiable)
            self.xp_to_next = int(self.xp_to_next * 1.25)

        if leveled_up:
            print(f"[XP] {self.nom} passe niveau {self.species_level} (prochain palier : {self.xp_to_next} XP)")

    def xp_ratio(self) -> float:
        """
        Renvoie un ratio 0..1 pour remplir la barre d'XP dans le HUD.
        """
        if self.xp_to_next <= 0:
            return 0.0
        return max(0.0, min(1.0, self.xp / self.xp_to_next))