// This file is responsible for procedural generation of the game map and biomes. It defines the structure and layout of the world.

class Map {
    width: number;
    height: number;
    tiles: number[][];

    constructor(width: number, height: number) {
        this.width = width;
        this.height = height;
        this.tiles = this.generateMap();
    }

    generateMap(): number[][] {
        const map: number[][] = [];
        for (let y = 0; y < this.height; y++) {
            const row: number[] = [];
            for (let x = 0; x < this.width; x++) {
                row.push(this.generateTile(x, y));
            }
            map.push(row);
        }
        return map;
    }

    generateTile(x: number, y: number): number {
        // Simple procedural generation logic
        // 0: empty, 1: grass, 2: water, 3: forest, etc.
        if (y < this.height / 3) {
            return 1; // grass
        } else if (y < (2 * this.height) / 3) {
            return 2; // water
        } else {
            return 3; // forest
        }
    }

    getTile(x: number, y: number): number {
        if (x < 0 || x >= this.width || y < 0 || y >= this.height) {
            throw new Error("Coordinates out of bounds");
        }
        return this.tiles[y][x];
    }
}

export default Map;