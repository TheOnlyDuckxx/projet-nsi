// This file manages the heads-up display, showing player stats and other relevant information during gameplay.

class HUD {
    private health: number;
    private hunger: number;
    private inventory: string[];

    constructor() {
        this.health = 100; // Default health
        this.hunger = 100; // Default hunger
        this.inventory = []; // Empty inventory
    }

    public updateHealth(amount: number): void {
        this.health = Math.max(0, Math.min(100, this.health + amount));
        this.render();
    }

    public updateHunger(amount: number): void {
        this.hunger = Math.max(0, Math.min(100, this.hunger + amount));
        this.render();
    }

    public addItemToInventory(item: string): void {
        this.inventory.push(item);
        this.render();
    }

    public removeItemFromInventory(item: string): void {
        const index = this.inventory.indexOf(item);
        if (index > -1) {
            this.inventory.splice(index, 1);
        }
        this.render();
    }

    private render(): void {
        console.log(`Health: ${this.health}`);
        console.log(`Hunger: ${this.hunger}`);
        console.log(`Inventory: ${this.inventory.join(', ')}`);
    }
}

export default HUD;