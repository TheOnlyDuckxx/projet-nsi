#Pour que le jeu se lance à la racine
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

#Importation des modules
from Game.core.app import App


# Démarrage du jeu :)
game=App()
game.run()