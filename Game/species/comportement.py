import random

class Comportement:
    def __init__(self, espece):
        self.espece = espece
        self.stats = self.espece.ia

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
        self.stats["etat"] = "chercher_nourriture"
        print(f"{self.espece.nom} cherche de la nourriture...")

    def dormir(self):
        self.stats["etat"] = "dormir"
        self.espece.jauges["energie"] += 1

    def explorer(self, world):
        self.stats["etat"] = "explorer"
