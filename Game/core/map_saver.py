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

print(f"DEBUG - Project root: {project_root}")
print(f"DEBUG - sys.path[0]: {sys.path[0]}")

# Import de Game APRÈS avoir configuré sys.path
# ruff: noqa: E402
from Game.world.world_gen import WorldData, WorldParams
print("✓ Import réussi!")


# --------------- FONCTION DE SAUVEGARDE AMÉLIORÉE ---------------
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
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# MAP PRÉCONSTRUITE\n")
            f.write(f"# Générée automatiquement - {filename}\n\n")
            
            f.write("import numpy as np\n")
            f.write("from Game.world.world_gen import WorldData, WorldParams\n\n")
            
            # Fonction qui recrée le monde
            f.write("def create_prebuilt_world():\n")
            f.write("    \"\"\"Recrée le monde préconstruit\"\"\"\n\n")
            
            # Paramètres - WorldParams avec la bonne structure
            f.write("    # Paramètres du monde\n")
            f.write("    params = WorldParams(\n")
            
            # Attributs obligatoires
            f.write(f"        seed={params.seed if params.seed is not None else 'None'},\n")
            f.write(f"        Taille={params.Taille},\n")
            f.write(f"        Climat='{params.Climat}',\n")
            f.write(f"        Niveau_des_océans={params.Niveau_des_océans},\n")
            f.write(f"        Ressources='{params.Ressources}',\n")
            f.write(f"        age={params.age},\n")
            
            # Attributs optionnels avec valeurs par défaut
            f.write(f"        atmosphere_density={params.atmosphere_density},\n")
            f.write(f"        world_name='{params.world_name}'\n")
            f.write("    )\n\n")
            
            # Données du monde avec conversion numpy
            f.write("    # Données du monde\n")
            f.write("    world = WorldData(\n")
            f.write(f"        width={world.width},\n")
            f.write(f"        height={world.height},\n")
            f.write(f"        sea_level={world.sea_level},\n")
            
            # Conversion intelligente : détecte si c'est numpy ou liste
            def safe_convert(data, name):
                """Convertit numpy array ou liste en représentation Python"""
                if hasattr(data, 'tolist'):  # C'est un numpy array
                    return f"        {name}=np.array({data.tolist()}),\n"
                elif isinstance(data, (list, tuple)):  # C'est déjà une liste
                    return f"        {name}={repr(data)},\n"
                else:  # Autre type
                    return f"        {name}={repr(data)},\n"
            
            f.write(safe_convert(world.heightmap, 'heightmap'))
            f.write(safe_convert(world.levels, 'levels'))
            f.write(safe_convert(world.ground_id, 'ground_id'))
            f.write(safe_convert(world.moisture, 'moisture'))
            f.write(safe_convert(world.biome, 'biome'))
            f.write(safe_convert(world.overlay, 'overlay'))
            f.write(f"        spawn={tuple(world.spawn)}\n")
            f.write("    )\n\n")
            
            f.write("    return world, params\n")
        
        print(f"✓ Monde sauvegardé dans: {filepath}")
        print(f"  Taille: {world.width}x{world.height}")
        print(f"  Spawn: {world.spawn}")
        
        # Vérification de l'intégrité du fichier
        try:
            with open(filepath, "r") as f:
                content = f.read()
                if not content.endswith("return world, params\n"):
                    raise Exception("Fichier incomplet détecté!")
            print("✓ Vérification d'intégrité: OK")
        except Exception as e:
            print(f"⚠ Attention: {e}")
            
    except Exception as e:
        print(f"✗ ERREUR lors de la sauvegarde: {e}")
        import traceback
        traceback.print_exc()
        raise


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
    preset_name = "Default"  # Changez ici: "Tropical", "Desert", "Arctic", etc.
    map_filename = "default_map1"  # Nom du fichier de sortie
    
    print(f"\n→ Génération d'une map avec le preset '{preset_name}'...")
    
    try:
        # Chargement des paramètres
        params = load_world_params_from_preset(preset_name)
        
        # Génération du monde
        generator = WorldGenerator(tiles_levels=6)
        world = generator.generate_planet(params)
        
        print("✓ Monde généré!")
        print(f"  Taille: {world.width}x{world.height}")
        print(f"  Spawn: {world.spawn}")
        
        # Sauvegarde
        print("\n→ Sauvegarde de la map...")
        save_world_to_file(world, params, map_filename)
        
        print("\n" + "=" * 60)
        print("  TERMINÉ!")
        print("=" * 60)
        print("\nVous pouvez maintenant lancer le jeu avec:")
        print("  python3 Game/laucher_prebuilt.py")
        
    except Exception as e:
        print(f"\n✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
