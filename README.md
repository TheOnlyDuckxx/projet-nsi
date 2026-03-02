# Keystone : The Long Evolution

[![Statut](https://img.shields.io/badge/statut-en%20developpement-blue)]([LIEN_BADGE_STATUT])
[![Python](https://img.shields.io/badge/python-3.11%2B-green)]([LIEN_BADGE_PYTHON])
[![License](https://img.shields.io/badge/license-GPL3.0-lightgrey)](https://www.gnu.org/licenses/gpl-3.0.en.html)

Keystone : The Long Evolution est un jeu de simulation/évolution développé en Python avec Pygame.
Le joueur crée son espèce, la fait survivre dans un monde procédural, débloque des mutations, gère sa progression technologique et affronte des événements dynamiques.

Placeholders médias:
- Bannière: `[IMAGE_BANNIERE]`
- Trailer: `[LIEN_TRAILER]`
- Captures: `[LIEN_SCREENSHOTS]`

---

## Sommaire

- [Vision du jeu](#vision-du-jeu)
- [Fonctionnalités principales](#fonctionnalites-principales)
- [Gameplay](#gameplay)
- [Architecture du projet](#architecture-du-projet)
- [Installation](#installation)
- [Lancement](#lancement)
- [Configuration](#configuration)
- [Sauvegarde et progression](#sauvegarde-et-progression)
- [Contrôles](#controles)
- [Roadmap](#roadmap)
- [Qualité et debug](#qualite-et-debug)
- [Contribuer](#contribuer)
- [Crédits](#credits)
- [Licence](#licence)

---

## Vision du jeu

Objectif design:
- proposer une boucle de progression longue (survie -> spécialisation -> technologie),
- faire émerger des histoires via les événements du monde,
- mélanger systèmes macro (espèce, tech, quêtes, météo) et micro (individus, combat, récolte, inventaire).

Pitch court:
- vous dirigez une espèce en évolution,
- chaque individu a des stats, une classe et des comportements,
- vos choix impactent durablement la civilisation en construction.

---

## Fonctionnalités principales

- Génération procédurale de monde.
- Cycle jour/nuit et système météo dynamique.
- Système d’espèce complet:
  - statistiques de base (physique, sens, mental, social, environnement),
  - XP d’espèce et montée de niveau,
  - mutations permanentes.
- Système de classes d’individus:
  - `savant`, `pacifiste`, `croyant`, `belligerant`,
  - classe principale d’espèce via événement dédié,
  - bonus de classe principale (placeholder équilibrage).
- Événements monde:
  - horde hostile temporelle,
  - choix de classe principale,
  - autres événements data-driven.
- Système de quêtes data-driven:
  - progression en chaînes,
  - récompenses XP/déblocages,
  - branchement selon la classe principale.
- Craft et construction:
  - placements de structures,
  - progression de chantier,
  - dépendances de progression (ex: entrepôt requis).
- IA et combat:
  - IA récolte,
  - IA chasse,
  - auto-défense des individus attaqués,
  - ennemis agressifs avec priorités de cibles.
- Historique persistant des événements du monde.
- Menus complets in-game (espèce, événements, tech, quêtes, historique).
- Écran de fin de partie avec statistiques.

---

## Gameplay

Boucle de jeu principale:
1. Créer une espèce (nom, couleur, paramètres initiaux).
2. Surveiller les besoins et la survie des individus.
3. Récolter des ressources et construire les premiers bâtiments.
4. Débloquer mutations et technologies.
5. Gérer les événements aléatoires et les crises (hordes, pertes, etc.).
6. Développer la population et orienter la spécialisation de la société.

Systèmes de progression:
- **Mutations**: proposées lors des paliers de niveau d’espèce.
- **Technologies**: arbre de progression avec déblocages de crafts.
- **Quêtes**: objectifs guidés débloquant étapes et récompenses.

---

## Architecture du projet

Structure simplifiée:

```text
Game/
  core/         # boucle app, config, assets, audio, utilitaires
  gameplay/     # phase de jeu, combat, événements, quêtes, craft, tech
  species/      # espèce, individus, IA comportementale, mutations, reproduction
  world/        # génération du monde, fog of war, jour/nuit, météo
  ui/           # menus, HUD, rendu isométrique
  data/         # json de configuration gameplay (mutations, crafts, tech, quêtes...)
  save/         # sauvegarde de run + progression joueur
```

Points d’entrée:
- Lancement jeu: `Game/main.py`
- Application principale: `Game/core/app.py`
- Gameplay phase principale: `Game/gameplay/phase1.py`

---

## Installation

### Pré-requis

- Python `3.11+` (testé dans cet environnement avec Python `3.13.7`).
- `pip`
- Environnement graphique compatible Pygame.

### Dépendances

Le projet utilise principalement:
- `pygame`

Installation rapide:

```bash
python -m pip install --upgrade pip
python -m pip install pygame
```

Optionnel (environnement virtuel recommandé):

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install pygame
```

---

## Lancement

Depuis la racine du dépôt:

```bash
python Game/main.py
```

Si vous utilisez un venv:

```bash
source .venv/bin/activate
python Game/main.py
```

---

## Configuration

Fichier de configuration utilisateur:
- `Game/data/settings.json`

Paramètres notables:
- audio (`master`, `music`, `sfx`),
- vidéo (`fullscreen`, `fps_cap`, `vsync`),
- debug (`perf_logs`),
- contrôles rebindables (transparence props, mode inspection, focus individu proche).

Le jeu fusionne automatiquement les nouvelles clés de config avec les valeurs par défaut.

---

## Sauvegarde et progression

Système de sauvegarde de run:
- dossier: `Game/save/slots/`
- format: `.evosave`
- métadonnées associées: `.meta.json`

Progression joueur (hors run):
- stockée séparément via le gestionnaire de progression.

Éléments persistés du run (exemples):
- monde, entités, espèce, inventaires,
- météo, quêtes, événements,
- historique du monde,
- état des hordes/classes,
- statistiques journalières et globales.

---

## Contrôles

Contrôles par défaut:
- `H`: transparence des props (maintien)
- `I`: mode inspection (maintien)
- `ESPACE`: focus caméra sur un individu proche
- `ECHAP`: pause/menu

Notes:
- les raccourcis principaux sont modifiables depuis le menu Options,
- certaines interactions dépendent du contexte de sélection (entité/tuile/prop).

---

## Roadmap

Axes de développement prévus:
- équilibrage combat/classes/mutations,
- enrichissement des quêtes spécifiques à chaque classe,
- amélioration UX/UI (lisibilité, onboarding),
- optimisation performance sur grands mondes,
- extension du contenu (faune, événements, crafts, technologies).

Roadmap détaillée: `[LIEN_ROADMAP]`

Changelog: `[LIEN_CHANGELOG]`

---

## Qualité et debug

Vérification syntaxe Python:

```bash
python -m py_compile $(rg --files Game -g '*.py')
```

Logs utiles:
- logs perf `Phase1` (chargement/update),
- logs debug endgame,
- notifications runtime in-game.

Bonnes pratiques recommandées:
- valider les JSON de `Game/data/` avant commit,
- tester une nouvelle partie + chargement d’une save,
- vérifier les impacts UI sur plusieurs résolutions.

---

## Contribuer

Workflow proposé:
1. Créer une branche feature/fix.
2. Implémenter et tester localement.
3. Vérifier qu’aucune régression de sauvegarde n’est introduite.
4. Ouvrir une Pull Request avec:
   - contexte,
   - changements,
   - impacts gameplay,
   - captures ou logs si pertinent.

Template PR: `[LIEN_TEMPLATE_PR]`

Conventions recommandées:
- commits atomiques,
- messages de commit explicites,
- éviter les changements non liés dans une même PR.

---

## Crédits

Équipe projet:
- `[NOM_MEMBRE_1]`
- `[NOM_MEMBRE_2]`
- `[NOM_MEMBRE_3]`

Remerciements:
- `[MENTION_PROF / ENCADRANT]`
- `[SOURCE_ASSETS / LIBRAIRIES / INSPIRATIONS]`
