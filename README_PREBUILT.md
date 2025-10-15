# 🎮 Guide d'utilisation - Maps Préconstruites

## 📋 Vue d'ensemble

Ce système vous permet de lancer votre jeu **sans génération procédurale** en chargeant une map pré-générée. Cela accélère considérablement le démarrage du jeu.

---

## 🚀 Utilisation rapide

### 1️⃣ Générer une map préconstruite

```bash
python Game/core/map_saver.py
```

Cette commande va :
- Générer une map avec le preset "Tropical"
- La sauvegarder dans `Game/data/prebuilt_maps/default_map.py`

### 2️⃣ Lancer le jeu avec la map préconstruite

```bash
python launcher_prebuilt.py
```

Le jeu démarre **instantanément** avec la map sauvegardée, sans génération !

---

## 🛠️ Configuration avancée

### Changer le preset de génération

Éditez `Game/core/map_saver.py` ligne 67 :

```python
preset_name = "Desert"  # Au lieu de "Tropical"
```

Presets disponibles (selon votre `world_presets.json`) :
- `Tropical`
- `Desert`
- `Arctic`
- etc.

### Créer plusieurs maps

1. Générez une map :
```python
python Game/core/map_saver.py
```

2. Renommez le fichier :
```
Game/data/prebuilt_maps/default_map.py 
→ Game/data/prebuilt_maps/tropical_map.py
```

3. Modifiez `map_saver.py` pour générer une autre map (changez le preset)

4. Lancez avec une map spécifique :
```bash
python launcher_prebuilt.py tropical
```

---

## 📁 Structure des fichiers

```
Game/
├── core/
│   ├── map_saver.py          # Générateur de maps
│   └── ...
├── data/
│   └── prebuilt_maps/        # Dossier des maps (créé automatiquement)
│       ├── default_map.py    # Map par défaut
│       ├── tropical_map.py   # Map tropicale (exemple)
│       └── desert_map.py     # Map désert (exemple)
└── ...

launcher_prebuilt.py           # Lanceur sans génération
```

---

## 🎯 Fonctionnement technique

### Différence avec le lancement normal

**Lancement normal** (`python Game/main.py`) :
```
Menu → Nouvelle Partie → Loading → Génération procédurale → Phase1
```

**Lancement préconstruit** (`python launcher_prebuilt.py`) :
```
Chargement map → Phase1 (instantané !)
```

### Que contient une map sauvegardée ?

Une map sauvegardée contient **TOUTES** les données générées :
- Heightmap (carte des hauteurs)
- Levels (étages/cubes)
- Ground tiles (types de sol)
- Moisture (humidité)
- Biomes
- Overlay (arbres, rochers)
- Spawn point
- Paramètres originaux

---

## 🔧 Sauvegarder une map depuis le jeu

Si vous voulez sauvegarder une map que vous aimez **pendant que vous jouez** :

### Option 1 : Ajouter une touche de sauvegarde

Éditez `Game/gameplay/phase1.py`, dans la méthode `handle_input`, ajoutez :

```python
if e.key == pygame.K_F5:
    from Game.core.map_saver import save_world_to_file
    save_world_to_file(self.world, self.params, "my_favorite_map")
    print("✓ Map sauvegardée avec succès !")
```

Ensuite, pendant le jeu, appuyez sur **F5** pour sauvegarder !

---

## ❓ FAQ

**Q : Puis-je modifier une map sauvegardée ?**
R : Oui ! Les fichiers `.py` dans `prebuilt_maps/` sont lisibles. Vous pouvez éditer les valeurs manuellement.

**Q : La map sauvegardée est-elle compatible avec les mises à jour du jeu ?**
R : Oui, tant que la structure de `WorldData` ne change pas radicalement.

**Q : Combien d'espace prend une map ?**
R : Une map 200x200 prend environ 5-15 MB selon la complexité.

**Q : Puis-je partager mes maps ?**
R : Oui ! Copiez simplement le fichier `.py` de `prebuilt_maps/`.

---

## 🎨 Exemples d'utilisation

### Créer plusieurs maps thématiques

```bash
# Map 1 : Tropicale
python Game/core/map_saver.py
mv Game/data/prebuilt_maps/default_map.py Game/data/prebuilt_maps/tropical.py

# Map 2 : Désertique (modifiez d'abord preset_name dans map_saver.py)
python Game/core/map_saver.py
mv Game/data/prebuilt_maps/default_map.py Game/data/prebuilt_maps/desert.py

# Lancer une map spécifique
python launcher_prebuilt.py tropical
python launcher_prebuilt.py desert
```

---

## 💡 Conseils

1. **Générez plusieurs maps** et gardez les meilleures
2. **Testez différents presets** pour varier les expériences
3. **Sauvegardez vos maps préférées** avec F5 pendant le jeu
4. **Partagez vos créations** avec votre équipe

Bon jeu ! 🎮✨