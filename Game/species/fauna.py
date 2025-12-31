
from __future__ import annotations

import math
import random
import pygame
from dataclasses import dataclass
from typing import Tuple

from Game.species.species import Espece, Individu


@dataclass(frozen=True)
class RabbitStats:
    """Statistiques par défaut pour un lapin (modifiables facilement)."""

    physique: dict = None
    sens: dict = None
    mental: dict = None
    environnement: dict = None
    social: dict = None
    genetique: dict = None
    move_speed: float = 3.1
    vision_range: float = 10.0
    flee_distance: float = 6.0

    def __post_init__(self):
        # Les dicts par défaut doivent être créés ici pour éviter les références partagées.
        object.__setattr__(
            self,
            "physique",
            self.physique
            or {
                "taille": 2,
                "force": 2,
                "endurance": 4,
                "vitesse": 5,
                "vitesse de nage": 1,
                "stockage_energetique": 8,
                "temperature_corporelle": 38.0,
                "esperance_vie": 3,
                "weight_limit": 6,
            },
        )
        object.__setattr__(
            self,
            "sens",
            self.sens
            or {
                "vision": 6,
                "ouie": 6,
                "odorat": 5,
                "echolocalisation": 0,
                "vision_nocturne": 2,
                "toucher": 2,
            },
        )
        object.__setattr__(
            self,
            "mental",
            self.mental
            or {
                "intelligence": 2,
                "dexterite": 4,
                "agressivite": 0,
                "courage": 2,
                "sociabilite": 4,
                "independance": 4,
                "empathie": 3,
                "creativite": 2,
                "intimidation": 0,
            },
        )
        object.__setattr__(
            self,
            "environnement",
            self.environnement
            or {
                "resistance_froid": 3,
                "resistance_chaleur": 3,
                "resistance_secheresse": 2,
                "resistance_toxines": 2,
                "discretion": 7,
                "adaptabilite": 5,
                "resistance_aux_maladies": 3,
            },
        )
        object.__setattr__(
            self,
            "social",
            self.social
            or {
                "communication": 3,
                "charisme": 2,
                "cohesion": 4,
                "fidelite": 3,
            },
        )
        object.__setattr__(self, "genetique", self.genetique or {"taux_reproduction": 0.4, "mutation_rate": 0.02})


class RabbitRenderer:
    """Rendu simple avec une petite animation d'idle."""

    def __init__(self, assets):
        self.assets = assets
        self.frames = [self.assets.get_image(key) for key in self._frame_keys() if key in self.assets.images]
        if not self.frames:
            # Au cas où les assets n'auraient pas été chargés.
            placeholder = pygame.Surface((20, 16), pygame.SRCALPHA)
            placeholder.fill((220, 220, 220, 255))
            self.frames = [placeholder]
        self.frame_ms = 240  # durée d'une frame d'animation

    def _frame_keys(self) -> tuple[str, ...]:
        return ("rabbit_idle_0", "rabbit_idle_1", "rabbit_idle_2")

    def _current_frame(self) -> pygame.Surface:
        if len(self.frames) == 1:
            return self.frames[0]
        idx = (pygame.time.get_ticks() // self.frame_ms) % len(self.frames)
        return self.frames[int(idx)]

    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float) -> Tuple[pygame.Surface, pygame.Rect]:
        base = self._current_frame()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        if abs(zoom - 1.0) > 1e-6:
            w, h = base.get_size()
            sprite = pygame.transform.smoothscale(base, (int(w * zoom), int(h * zoom)))
        else:
            sprite = base

        dx, dy, wall_h = view._proj_consts()
        z = 0
        try:
            i, j = int(tx), int(ty)
            if world and getattr(world, "levels", None):
                z = int(world.levels[j][i])
        except Exception:
            z = 0

        sx, sy = view._world_to_screen(tx, ty, z, dx, dy, wall_h)
        surface_y = sy - int(2 * dy)
        px = int(sx - sprite.get_width() // 2)
        py = int(surface_y - sprite.get_height() + 2)
        rect = pygame.Rect(px, py, sprite.get_width(), sprite.get_height())
        return sprite, rect

    def render(self, screen, view, world, tx: float, ty: float):
        sprite, rect = self.get_draw_surface_and_rect(view, world, tx, ty)
        screen.blit(sprite, rect.topleft)


class RabbitBehavior:
    """IA minimaliste : fuit le joueur s'il est proche, sinon flâne un peu."""

    def __init__(self, lapin, phase, vision_range: float, flee_distance: float):
        self.lapin = lapin
        self.phase = phase
        self.vision_range = vision_range
        self.flee_distance = flee_distance
        self._wander_timer = 0.0

    def try_eating(self):
        # Les lapins grignotent régulièrement : on remet simplement la jauge.
        self.lapin.jauges["faim"] = min(100, self.lapin.jauges.get("faim", 100) + 20)

    def _players(self):
        if not self.phase:
            return []
        return [p for p in (getattr(self.phase, "joueur", None), getattr(self.phase, "joueur2", None)) if p]

    def _move_to(self, target: Tuple[int, int]):
        if not self.phase:
            return
        self.phase._ensure_move_runtime(self.lapin)
        self.phase._apply_entity_order(
            self.lapin,
            target=target,
            etat="se_deplace",
            objectif=None,
            action_mode=None,
            craft_id=None,
        )

    def _flee_from(self, pos: Tuple[float, float]):
        px, py = pos
        dx = self.lapin.x - px
        dy = self.lapin.y - py
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            dist = 1.0
            dx = 1.0
        nx, ny = dx / dist, dy / dist
        target = (int(round(self.lapin.x + nx * self.flee_distance)), int(round(self.lapin.y + ny * self.flee_distance)))
        safe_tile = None
        if self.phase:
            safe_tile = self.phase._find_nearest_walkable(target, forbidden={})
        if safe_tile:
            self._move_to(safe_tile)

    def _wander(self):
        if not self.phase:
            return
        jitter = (random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2))
        tx = int(round(self.lapin.x + jitter[0]))
        ty = int(round(self.lapin.y + jitter[1]))
        tile = self.phase._find_nearest_walkable((tx, ty), forbidden={})
        if tile:
            self._move_to(tile)

    def update(self, dt: float, world):
        self._wander_timer += dt
        r2 = self.vision_range * self.vision_range
        for p in self._players():
            dx = self.lapin.x - p.x
            dy = self.lapin.y - p.y
            if dx * dx + dy * dy <= r2:
                self._flee_from((p.x, p.y))
                self._wander_timer = 0.0
                return

        if self._wander_timer >= 4.0:
            self._wander_timer = 0.0
            self._wander()


class Rabbit(Individu):
    """Individu spécialisé pour la faune : comportement de fuite + rendu dédié."""

    def __init__(self, espece: Espece, x: float, y: float, assets, phase, stats: RabbitStats):
        super().__init__(espece, x, y, assets)
        self.nom = "Lapin"
        self.is_fauna = True
        self.move_speed = stats.move_speed
        self.renderer = RabbitRenderer(assets)
        self.comportement = RabbitBehavior(self, phase, vision_range=stats.vision_range, flee_distance=stats.flee_distance)


class RabbitFactory:
    """Fabrique de lapins afin de centraliser stats et création."""

    def __init__(self, phase, species: Espece, stats: RabbitStats | None = None):
        self.phase = phase
        self.species = species
        self.stats = stats or RabbitStats()

    def create_rabbit(self, x: float, y: float, assets):
        lapin = Rabbit(self.species, x, y, assets, phase=self.phase, stats=self.stats)
        lapin.ia["autonomie"] = True
        lapin.phase = self.phase
        return lapin

    @staticmethod
    def apply_stats_to_species(species: Espece, stats: RabbitStats | None = None):
        base = stats or RabbitStats()
        species.base_physique.update(base.physique)
        species.base_sens.update(base.sens)
        species.base_mental.update(base.mental)
        species.base_environnement.update(base.environnement)
        species.base_social.update(base.social)
        species.genetique.update(base.genetique)
        return species