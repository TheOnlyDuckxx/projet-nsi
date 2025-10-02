import { Entity } from '../world/entities';
import { Health, Hunger, Inventory, AI } from './components';

export class MovementSystem {
    update(entities: Entity[], deltaTime: number) {
        entities.forEach(entity => {
            // Movement logic here
        });
    }
}

export class AISystem {
    update(entities: Entity[], deltaTime: number) {
        entities.forEach(entity => {
            // AI logic here
        });
    }
}

export class RenderSystem {
    render(entities: Entity[]) {
        entities.forEach(entity => {
            // Rendering logic here
        });
    }
}