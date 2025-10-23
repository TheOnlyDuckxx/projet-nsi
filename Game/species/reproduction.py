import random

class ReproductionSystem:
    def __init__(self, espece):
        self.espece = espece

    def update(self):
        if random.random() < 0.01:
            self.reproduire()

    def reproduire(self):
        enfant = self.espece.__class__(nom=f"{self.espece.nom}_descendant", x=self.espece.x, y=self.espece.y)

        # Pour chaque catégorie de stats, on copie les valeurs avec variation
        for cat in ["physique", "sens", "mental", "social", "environnement", "genetique"]:
            d_parent = getattr(self.espece, cat)
            d_enfant = getattr(enfant, cat)
            for stat, val in d_parent.items():
                variation = random.uniform(-0.05, 0.05) * val
                d_enfant[stat] = max(0, val + variation)

        print(f"Nouvelle génération : {enfant.nom}")
        return enfant