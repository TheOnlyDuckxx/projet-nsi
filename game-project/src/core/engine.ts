class GameEngine {
    private currentState: GameState;

    constructor() {
        this.currentState = new MainMenuState();
    }

    public start(): void {
        this.gameLoop();
    }

    private gameLoop(): void {
        this.update();
        this.render();
        requestAnimationFrame(() => this.gameLoop());
    }

    private update(): void {
        this.currentState.update();
    }

    private render(): void {
        this.currentState.render();
    }

    public changeState(newState: GameState): void {
        this.currentState = newState;
        this.currentState.init();
    }
}

interface GameState {
    init(): void;
    update(): void;
    render(): void;
}

class MainMenuState implements GameState {
    init(): void {
        // Initialize main menu
    }

    update(): void {
        // Update main menu logic
    }

    render(): void {
        // Render main menu
    }
}

// Additional game states can be defined here, such as PlayState, PauseState, etc.

const gameEngine = new GameEngine();
gameEngine.start();