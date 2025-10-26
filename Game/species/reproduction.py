# Game/espece/reproduction.py
import random

class ReproductionSystem:
    def __init__(self, espece):
        self.espece = espece

    def update(self):
        if random.random() < 0.01:
            self.reproduire()

    def reproduire(self):
        enfant = self.espece.__class__(nom=f"{self.espece.nom}_descendant",
                                       x=self.espece.x, y=self.espece.y,
                                       assets=self.espece.renderer.assets)
        # variation ±5% sur chaque stat connue
        for cat in ["physique", "sens", "mental", "social", "environnement", "genetique"]:
            d_parent = getattr(self.espece, cat, {})
            d_enfant = getattr(enfant, cat, {})
            for stat, val in d_parent.items():
                try:
                    variation = random.uniform(-0.05, 0.05) * float(val)
                except Exception:
                    variation = 0.0
                d_enfant[stat] = max(0, (val if isinstance(val, (int, float)) else 0) + variation)

        print(f"Nouvelle génération : {enfant.nom}")
        return enfant
