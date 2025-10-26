import pygame
from Game.core.assets import Assets


class EspeceRenderer:
    """
    Génère un sprite modulaire composé de plusieurs sous-éléments
    par zone anatomique (tête, appendices, peau, etc.)
    """
    BASE_SIZE = (20, 24)

    def __init__(self, espece):
        self.espece = espece
        self.assets = Assets().load_all("Game/assets")

        # Chaque zone contient une liste de parties à afficher
        self.layers = {
            "corps": [],  # toujours présent
            "tete": [], # yeux par défaut
            "appendices": [],         # ailes, branchies, bras, etc.
            "peau": [],               # poils, carapace...
            "effets": []              # phéromones, lueurs...
        }

    # ------------------------------------------------------------------

    def update_from_mutations(self):
        """Active les parties visuelles correspondant aux mutations actives"""
        # On efface les calques spécifiques sauf la base
        for zone in ["tete", "appendices", "peau", "effets"]:
            self.layers[zone] = []

        for mutation in self.espece.mutations.actives:
            # --- Peau et protection ---
            if mutation == "Carapace":
                self.layers["peau"].append("carapace")
            elif mutation == "Peau poilue":
                self.layers["peau"].append("poils")

            # --- Appendices ---
            elif mutation == "Ailes":
                self.layers["appendices"].append("ailes_grandes")
            elif mutation == "Branchies":
                self.layers["appendices"].append("branchies")

            # --- Tête / visage ---
            elif mutation == "Vision multiple":
                self.layers["tete"].append("yeux_multiples")
            elif mutation == "Mâchoire réduite":
                self.layers["tete"].append("bouche_large")

            # --- Effets spéciaux ---
            elif mutation == "Chromatophores":
                self.layers["effets"].append("camouflage")
            elif mutation == "Bioluminescence":
                self.layers["effets"].append("bioluminescence")
            elif mutation == "Sécrétion de phéromones":
                self.layers["effets"].append("pheromone")


        # Toujours au moins un corps et une tête
        
        self.layers["corps"] = ["4_corps_base"]
        self.layers["tete"] = ["4_yeux_normaux","4_bouche_normale"]
        self.layers["appendices"] = ["4_jambe_base"]

    # ------------------------------------------------------------------

    def build_sprite(self):
        """Assemble le sprite complet à partir des listes de calques"""
        sprite = pygame.Surface(self.BASE_SIZE, pygame.SRCALPHA)
        

        # Ordre d’empilement : appendices (derrière), corps, peau, tête, effets
        render_order = ["appendices", "corps", "peau", "tete", "effets"]

        for layer in render_order:
            for key in self.layers[layer]:
                if key not in self.assets.images:
                    continue
                image = self.assets.get_image(key)
                image = pygame.transform.scale(image, (int(image.get_width()*6), int(image.get_height()*6)))
                x = (self.BASE_SIZE[0] - image.get_width()) // 2
                y = (self.BASE_SIZE[1] - image.get_height()) // 2
                sprite.blit(image, (x, y))

        return sprite

    # ------------------------------------------------------------------

    def render(self, surface, position):
        """Dessine l’espèce sur la surface Pygame donnée"""
        self.update_from_mutations()
        sprite = self.build_sprite()
        surface.blit(sprite, position)