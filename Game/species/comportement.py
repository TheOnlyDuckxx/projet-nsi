import random

class Comportement:
    def __init__(self, espece):
        self.espece = espece
        self.ia = self.espece.ia

    def update(self, world):
        faim = self.espece.jauges["faim"]
        energie = self.espece.jauges["energie"]

        if faim > 70:
            self.chercher_nourriture(world)
        elif energie < 20:
            self.dormir()
        else:
            self.explorer(world)

    def chercher_nourriture(self, world):
        self.ia["etat"] = "chercher_nourriture"
        print(f"{self.espece.nom} cherche de la nourriture...")

        # Consomme un peu d’énergie pendant la recherche
        self.espece.jauges["energie"] -= 0.2 * (11 - self.espece.physique["endurance"])

    def dormir(self):
        self.ia["etat"] = "dormir"
        self.espece.jauges["energie"] = min(100, self.espece.jauges["energie"] + 0.5 * self.espece.physique["endurance"])

    def explorer(self, world):
        self.ia["etat"] = "explorer"
        self.espece.jauges["energie"] -= 0.1

