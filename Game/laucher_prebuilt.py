# LAUNCHER_PREBUILT.PY
# Lance le jeu avec une map préconstruite (sans génération procédurale)

# --------------- IMPORTATION DES MODULES ---------------
import sys
import os

# Pour que le jeu se lance à la racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

import pygame
from Game.core.app import App
from Game.world.world_gen import WorldParams, WorldData


# --------------- FONCTION DE CHARGEMENT DE MAP ---------------
def load_prebuilt_map(map_name: str = "default") -> tuple:
    """
    Charge une map préconstruite depuis un fichier Python.
    
    Args:
        map_name: nom de la map à charger (ex: "default", "tropical", "desert")
    
    Returns:
        tuple: (WorldData, WorldParams)
    """
    # Importation dynamique de la map
    try:
        import importlib.util
        
        # Chemin vers le fichier de map
        map_path = os.path.join("Game", "data", "prebuilt_maps", f"{map_name}.py")
        
        if not os.path.exists(map_path):
            raise FileNotFoundError(f"Le fichier '{map_path}' n'existe pas")
        
        # Chargement dynamique du module
        spec = importlib.util.spec_from_file_location(f"map_{map_name}", map_path)
        map_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(map_module)
        
        # Récupération de la fonction
        world_data, world_params = map_module.create_prebuilt_world()
        
        print(f"✓ Map '{map_name}' chargée avec succès !")
        print(f"  Taille: {world_data.width}x{world_data.height}")
        print(f"  Spawn: {world_data.spawn}")
        return world_data, world_params
        
    except FileNotFoundError as e:
        print(f"\n✗ ERREUR: Map '{map_name}' introuvable !")
        print(f"  Fichier attendu: {map_path}")
        print(f"\n💡 Solution: Générez d'abord une map avec:")
        print(f"     python Game/core/map_saver.py")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ Erreur lors du chargement de la map '{map_name}'")
        print(f"  Détails: {e}")
        sys.exit(1)


# --------------- CLASSE APP MODIFIÉE ---------------
class PrebuiltApp(App):
    """Version modifiée de App qui charge directement une map préconstruite"""
    
    def __init__(self, map_name: str = "default"):
        # Chargement de la map AVANT l'initialisation de pygame
        self.prebuilt_world, self.prebuilt_params = load_prebuilt_map(map_name)
        
        # Initialisation normale de l'app
        super().__init__()
        
        # Lancement direct en Phase1 avec la map préconstruite
        print("→ Lancement du jeu avec la map préconstruite...")
        self.change_state("PHASE1", world=self.prebuilt_world, params=self.prebuilt_params)


# --------------- LANCEMENT DU JEU ---------------
if __name__ == "__main__":
    # Choix de la map (vous pouvez passer un argument en ligne de commande)
    map_to_load = "default_map1"
    
    if len(sys.argv) > 1:
        map_to_load = sys.argv[1]
    
    print("=" * 60)
    print("  EVONSI - LAUNCHER MAP PRÉCONSTRUITE")
    print("=" * 60)
    print(f"Map sélectionnée: {map_to_load}")
    print("-" * 60)
    
    # Création et lancement du jeu
    game = PrebuiltApp(map_to_load)
    game.run()
    
    print("\nJeu fermé. À bientôt !")