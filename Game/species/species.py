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
            "temperature_corporelle": 5, "esperance_vie": 5,
        }
        self.sens = {
            "vision": 5, "ouie": 5, "odorat": 5, "echolocalisation": 0,
            "vision_nocturne": 0, "toucher": 1,
        }
        self.mental = {
            "intelligence": 5, "dexterité": 5,
            "agressivite": 5, "courage": 5, "sociabilite": 5, "independance": 5,
            "empathie": 5, "creativite": 5, "intimidation": 5, 
        }
        self.jauges = {
            "faim": 50, "soif": 50, "energie": self.physique["endurance"], "bonheur": 50,
            "sante": 100, "temperature": 37.0,
        }
        self.environnement = {
            "resistance_froid": 5, "resistance_chaleur": 5, "resistance_secheresse": 5,
            "resistance_toxines": 5, "discretion": 5, "adaptabilite": 5, "resistance_aux_maladies": 5,"detection" : self.sens["vision"] * 10 + self.sens["ouie"] * 5 + self.sens["odorat"]* 2 + self.sens["toucher"],
        }
        self.social = {
            "communication":5,"charisme": 5, "cohesion": 5, "fidelite": 5, 
        }
        self.genetique = {
            "taux_reproduction": 1.0, "mutation_rate": 0.10,
        }
        self.arbre_phases3 = {"autorité" : 5,"strategie": 5, "organisation":5, "culture": 5, "science": 5,"raison": 5, "ferveur": 5,  "moralité": 5, "harmonie": 5,
                              }
        self.ia = {
            "autonomie": True, "etat": "idle", "objectif": None, "vision_portee": 100,
        }
        
        self.effets_speciaux = []
        # === Sous-systèmes ===
        self.mutations = MutationManager(self)
        self.comportement = Comportement(self)
        self.reproduction = ReproductionSystem(self)
        self.sensors = Sensors(self)

        self.population = 1
        self.autonomie = True

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
