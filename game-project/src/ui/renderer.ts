import { GameState } from '../core/engine';
import { PlayerStats } from '../gameplay/mechanics';

export class Renderer {
    private canvas: HTMLCanvasElement;
    private context: CanvasRenderingContext2D;

    constructor(canvasId: string) {
        this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
        this.context = this.canvas.getContext('2d')!;
    }

    public render(gameState: GameState, playerStats: PlayerStats): void {
        this.clearCanvas();
        this.drawHUD(playerStats);
        // Additional rendering logic goes here
    }

    private clearCanvas(): void {
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    private drawHUD(playerStats: PlayerStats): void {
        this.context.fillStyle = 'white';
        this.context.font = '16px Arial';
        this.context.fillText(`Health: ${playerStats.health}`, 10, 20);
        this.context.fillText(`Hunger: ${playerStats.hunger}`, 10, 40);
        // Additional HUD elements can be drawn here
    }
}