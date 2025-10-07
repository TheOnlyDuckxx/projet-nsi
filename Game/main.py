#Pour que le jeu se lance à la racine
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

#Importation des modules
from Game.core.config import WIDTH, HEIGHT
from Game.core.app import App
from world.world_gen import load_world_params_from_preset, WorldGenerator

#Création du monde commentée car met du temps à charger
#params = load_world_params_from_preset("Default")   # ou "Tropical"/"Arid"/"Glacial"
#gen = WorldGenerator(tiles_levels=6)
#world = gen.generate_island(params)


# Démarrage du jeu :)
game=App()
game.run()