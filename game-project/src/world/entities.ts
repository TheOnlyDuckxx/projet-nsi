// This file manages the entities within the game world, including their creation, updates, and interactions.

interface Entity {
    id: number;
    position: { x: number; y: number };
    components: { [key: string]: any };
}

class EntityManager {
    private entities: Entity[] = [];
    private nextId: number = 1;

    createEntity(position: { x: number; y: number }): Entity {
        const entity: Entity = {
            id: this.nextId++,
            position,
            components: {}
        };
        this.entities.push(entity);
        return entity;
    }

    getEntity(id: number): Entity | undefined {
        return this.entities.find(entity => entity.id === id);
    }

    updateEntity(id: number, position: { x: number; y: number }): void {
        const entity = this.getEntity(id);
        if (entity) {
            entity.position = position;
        }
    }

    removeEntity(id: number): void {
        this.entities = this.entities.filter(entity => entity.id !== id);
    }

    getAllEntities(): Entity[] {
        return this.entities;
    }
}

export { EntityManager, Entity };