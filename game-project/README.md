# Game Project

## Overview
This project is a game developed using TypeScript. It features a modular architecture that separates different aspects of the game into distinct folders, making it easier to manage and extend.

## Directory Structure
- **src/**: Contains all the source code for the game.
  - **core/**: Core functionalities including the game engine and utility functions.
  - **world/**: Manages the game world, including map generation and entities.
  - **ecs/**: Implements the Entity-Component-System architecture for game logic.
  - **gameplay/**: Contains gameplay mechanics and event handling.
  - **ui/**: Responsible for the user interface and heads-up display.
  - **data/**: Holds configuration and level data in JSON format.
  - **assets/**: Contains game assets such as sprites and sounds.

## Files
- **src/core/engine.ts**: Main game loop and state management.
- **src/core/utils.ts**: Utility functions for asset loading and global constants.
- **src/world/map.ts**: Procedural generation of the game map and biomes.
- **src/world/entities.ts**: Management of game entities and their interactions.
- **src/ecs/systems.ts**: Definitions for various game systems.
- **src/ecs/components.ts**: Component definitions for entities.
- **src/gameplay/mechanics.ts**: Implements gameplay mechanics.
- **src/gameplay/events.ts**: Handles gameplay events.
- **src/ui/renderer.ts**: Renders the user interface.
- **src/ui/hud.ts**: Manages the heads-up display.
- **src/data/levels.json**: Level data for the game.
- **src/data/config.json**: Global configuration settings.
- **src/assets/sprites/**: Directory for sprite images.
- **src/assets/sounds/**: Directory for sound effects and music files.
- **package.json**: npm configuration file.
- **tsconfig.json**: TypeScript configuration file.

## Getting Started
To get started with the project, clone the repository and install the dependencies using npm:

```bash
npm install
```

After installing the dependencies, you can run the game using:

```bash
npm start
```

## Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for details.