# MAP_SAVER.PY
# Système pour sauvegarder et charger des maps préconstruites

# --------------- CONFIGURATION DU PATH (EN PREMIER !) ---------------
import sys
import os

# Pour que le script puisse être lancé depuis n'importe où
script_dir = os.path.dirname(os.path.abspath(__file__))  # Game/core/
game_dir = os.path.dirname(script_dir)                    # Game/
project_root = os.path.dirname(game_dir)                  # racine

# IMPORTANT : Ajouter le chemin AVANT tout import de Game.*
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --------------- MAINTENANT ON PEUT IMPORTER ---------------
from typing import Tuple

print(f"DEBUG - Project root: {project_root}")
print(f"DEBUG - sys.path[0]: {sys.path[0]}")

# Import de Game APRÈS avoir configuré sys.path
from Game.world.world_gen import WorldData, WorldParams
print("✓ Import réussi!")


# --------------- FONCTION DE SAUVEGARDE ---------------
def save_world_to_file(world: WorldData, params: WorldParams, filename: str, output_dir: str = "Game/data/prebuilt_maps"):
    """
    Sauvegarde un monde généré dans un fichier Python réutilisable.
    
    Args:
        world: les données du monde (WorldData)
        params: les paramètres utilisés (WorldParams)
        filename: nom du fichier (sans extension)
        output_dir: dossier de destination
    """
    # Création du dossier si nécessaire
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, f"{filename}.py")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# MAP PRÉCONSTRUITE\n")
        f.write(f"# Générée automatiquement - {filename}\n\n")
        
        f.write("from Game.world.world_gen import WorldData, WorldParams\n\n")
        
        # Fonction qui recrée le monde
        f.write("def create_prebuilt_world():\n")
        f.write("    \"\"\"Recrée le monde préconstruit\"\"\"\n\n")
        
        # Paramètres
        f.write("    # Paramètres du monde\n")
        f.write("    params = WorldParams(\n")
        f.write(f"        seed={params.seed},\n")
        f.write(f"        planet_width={params.planet_width},\n")
        f.write(f"        planet_height={params.planet_height},\n")
        f.write(f"        water_pct={params.water_pct},\n")
        f.write(f"        temperature='{params.temperature}',\n")
        f.write(f"        atmosphere_density={params.atmosphere_density},\n")
        f.write(f"        resource_density={params.resource_density},\n")
        f.write(f"        world_name='{params.world_name}'\n")
        f.write("    )\n\n")
        
        # Données du monde
        f.write("    # Données du monde\n")
        f.write("    world = WorldData(\n")
        f.write(f"        width={world.width},\n")
        f.write(f"        height={world.height},\n")
        f.write(f"        sea_level={world.sea_level},\n")
        f.write(f"        heightmap={repr(world.heightmap)},\n")
        f.write(f"        levels={repr(world.levels)},\n")
        f.write(f"        ground_id={repr(world.ground_id)},\n")
        f.write(f"        moisture={repr(world.moisture)},\n")
        f.write(f"        biome={repr(world.biome)},\n")
        f.write(f"        overlay={repr(world.overlay)},\n")
        f.write(f"        spawn={repr(world.spawn)}\n")
        f.write("    )\n\n")
        
        f.write("    return world, params\n")
    
    print(f"✓ Monde sauvegardé dans: {filepath}")
    print(f"  Taille: {world.width}x{world.height}")
    print(f"  Spawn: {world.spawn}")


# --------------- SCRIPT DE GÉNÉRATION RAPIDE ---------------
if __name__ == "__main__":
    """
    Script pour générer et sauvegarder une map rapidement.
    Usage: python Game/core/map_saver.py
    """
    print("=" * 60)
    print("  GÉNÉRATEUR DE MAP PRÉCONSTRUITE")
    print("=" * 60)
    
    from Game.world.world_gen import WorldGenerator, load_world_params_from_preset
    
    # Choix du preset
    preset_name = "Tropical"  # Changez ici: "Tropical", "Desert", "Arctic", etc.
    map_filename = "default_map1"  # Nom du fichier de sortie
    
    print(f"\n→ Génération d'une map avec le preset '{preset_name}'...")
    
    # Chargement des paramètres
    params = load_world_params_from_preset(preset_name)
    
    # Génération du monde
    generator = WorldGenerator(tiles_levels=6)
    world = generator.generate_island(params)
    
    print(f"✓ Monde généré!")
    print(f"  Taille: {world.width}x{world.height}")
    print(f"  Spawn: {world.spawn}")
    
    # Sauvegarde
    print(f"\n→ Sauvegarde de la map...")
    save_world_to_file(world, params, map_filename)
    
    print("\n" + "=" * 60)
    print("  TERMINÉ!")
    print("=" * 60)
    print(f"\nVous pouvez maintenant lancer le jeu avec:")
    print(f"  python3 launcher_prebuilt.py")