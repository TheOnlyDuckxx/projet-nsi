// src/ecs/components.ts

export interface Health {
    current: number;
    max: number;
}

export interface Hunger {
    current: number;
    max: number;
}

export interface Inventory {
    items: string[];
}

export interface AI {
    behavior: string;
    target: string | null;
}