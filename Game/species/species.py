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
            "taille": 5, "force": 5, "endurance": 5, "sante": 5,
            "vitesse": 5, "metabolisme": 5, "stockage_energetique": 5,
            "temperature_corporelle": 5, "esperance_vie": 5,
        }
        self.sens = {
            "vision": 5, "ouie": 5, "odorat": 5, "echolocalisation": 0,
            "vision_nocturne": 0, "perception_mouvement": 5, "toucher": 5,
        }
        self.mental = {
            "intelligence": 5, "memoire": 5, "curiosite": 5,
            "agressivite": 5, "courage": 5, "sociabilite": 5,
            "empathie": 5, "creativite": 5, "strategie": 5, "spiritualite": 0,
        }
        self.jauges = {
            "faim": 50, "soif": 50, "energie": 100, "moral": 50,
            "sante_actuelle": 100, "stress": 0, "temperature": 37.0,
        }
        self.environnement = {
            "resistance_froid": 5, "resistance_chaleur": 5, "resistance_secheresse": 5,
            "resistance_toxines": 5, "camouflage": 5, "adaptabilite": 5,
        }
        self.social = {
            "charisme": 5, "cohesion": 5, "fidelite": 5, "controle": 5,
            "harmonie": 5, "culture": 5, "science": 5, "ferveur": 5,
        }
        self.genetique = {
            "mutation_rate": 0.05, "taux_reproduction": 1.0,
            "diversite_genetique": 5, "soin_parental": 5,
        }
        self.ia = {
            "autonomie": True, "etat": "idle", "objectif": None, "vision_portee": 100,
        }

        # === Sous-systèmes ===
        self.mutations = MutationManager(self)
        self.comportement = Comportement(self)
        self.reproduction = ReproductionSystem(self)
        self.sensors = Sensors(self)

        self.population = 1
        self.autonomie = True

        # === Rendu ===
        self.renderer = EspeceRenderer(self, assets)

        # Démo : active quelques mutations sûres si tu veux voir un rendu direct
        # self.mutations.actives = ["Carapace", "Ailes", "Mâchoire réduite"]

    def update(self, world):
        self.comportement.update(world)
        self.reproduction.update()
        self.mutations.update()

    def draw(self, screen, view, world):
        self.renderer.render(screen, view, world, self.x, self.y)
