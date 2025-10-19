import random

class ReproductionSystem:
    def __init__(self, espece):
        self.espece = espece

    def update(self):
        if random.random() < 0.01:
            self.reproduire()

    def reproduire(self):
        enfant = self.espece.__class__(nom=f"{self.espece.nom}_descendant")
        for cat in self.espece.stats:
            for stat, val in self.espece.stats[cat].items():
                variation = random.uniform(-0.05, 0.05) * val
                enfant.stats[cat][stat] = max(0, val + variation)
        print(f"Nouvelle génération : {enfant.nom}")
