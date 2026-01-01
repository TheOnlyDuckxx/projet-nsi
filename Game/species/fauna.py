from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Tuple, Sequence

import pygame

from Game.species.species import Espece, Individu


@dataclass(frozen=True)
class PassiveFaunaDefinition:
    """
    Décrit une espèce passive et inoffensive.
    Peut être instanciée avec d'autres valeurs pour créer de nouvelles espèces.
    """

    species_name: str = "Faune passive"
    entity_name: str = "Créature"
    physique: dict | None = None
    sens: dict | None = None
    mental: dict | None = None
    environnement: dict | None = None
    social: dict | None = None
    genetique: dict | None = None
    move_speed: float = 3.0
    vision_range: float = 8.0
    flee_distance: float = 5.0
    sprite_keys: Sequence[str] = ("rabbit_idle_0", "rabbit_idle_1", "rabbit_idle_2")

    def __post_init__(self):
        def _dict(val, fallback):
            return val if val is not None else fallback

        object.__setattr__(
            self,
            "physique",
            _dict(
                self.physique,
                {
                    "taille": 2,
                    "force": 2,
                    "endurance": 4,
                    "vitesse": 4,
                    "vitesse de nage": 1,
                    "stockage_energetique": 6,
                    "temperature_corporelle": 38.0,
                    "esperance_vie": 3,
                    "weight_limit": 6,
                },
            ),
        )
        object.__setattr__(
            self,
            "sens",
            _dict(
                self.sens,
                {"vision": 6, "ouie": 6, "odorat": 5, "echolocalisation": 0, "vision_nocturne": 2, "toucher": 2},
            ),
        )
        object.__setattr__(
            self,
            "mental",
            _dict(
                self.mental,
                {
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
            ),
        )
        object.__setattr__(
            self,
            "environnement",
            _dict(
                self.environnement,
                {
                    "resistance_froid": 3,
                    "resistance_chaleur": 3,
                    "resistance_secheresse": 2,
                    "resistance_toxines": 2,
                    "discretion": 7,
                    "adaptabilite": 5,
                    "resistance_aux_maladies": 3,
                },
            ),
        )
        object.__setattr__(
            self,
            "social",
            _dict(self.social, {"communication": 3, "charisme": 2, "cohesion": 4, "fidelite": 3}),
        )
        object.__setattr__(self, "genetique", _dict(self.genetique, {"taux_reproduction": 0.4, "mutation_rate": 0.02}))


class PassiveFaunaRenderer:
    """Rendu simple multi-frames (idle) avec zoom."""

    def __init__(self, assets, sprite_keys: Sequence[str]):
        self.assets = assets
        self.keys = tuple(sprite_keys) if sprite_keys else ()
        frames = [self.assets.get_image(k) for k in self.keys if k in getattr(self.assets, "images", {})]
        if not frames and self.keys:
            frames = [self.assets.get_image(self.keys[0])]
        if not frames:
            surf = pygame.Surface((20, 16), pygame.SRCALPHA)
            surf.fill((220, 220, 220, 255))
            frames = [surf]
        self.frames = frames
        self.frame_ms = 240

    def _current_frame(self) -> pygame.Surface:
        if len(self.frames) == 1:
            return self.frames[0]
        idx = (pygame.time.get_ticks() // self.frame_ms) % len(self.frames)
        return self.frames[int(idx)]

    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float) -> Tuple[pygame.Surface, pygame.Rect]:
        base = self._current_frame()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        sprite = pygame.transform.smoothscale(base, (int(base.get_width() * zoom), int(base.get_height() * zoom)))

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


class PassiveFaunaBehavior:
    """IA passive : flâne et fuit le joueur si proche."""

    def __init__(self, creature, phase, vision_range: float, flee_distance: float):
        self.creature = creature
        self.phase = phase
        self.vision_range = vision_range
        self.flee_distance = flee_distance
        self._wander_timer = 0.0

    def try_eating(self):
        self.creature.jauges["faim"] = min(100, self.creature.jauges.get("faim", 100) + 20)

    def _players(self):
        if not self.phase:
            return []
        return [p for p in (getattr(self.phase, "joueur", None), getattr(self.phase, "joueur2", None)) if p]

    def _move_to(self, target: Tuple[int, int]):
        if not self.phase:
            return
        self.phase._ensure_move_runtime(self.creature)
        self.phase._apply_entity_order(
            self.creature,
            target=target,
            etat="se_deplace",
            objectif=None,
            action_mode=None,
            craft_id=None,
        )

    def _flee_from(self, pos: Tuple[float, float]):
        px, py = pos
        dx = self.creature.x - px
        dy = self.creature.y - py
        dist = math.hypot(dx, dy) or 1.0
        nx, ny = dx / dist, dy / dist
        target = (
            int(round(self.creature.x + nx * self.flee_distance)),
            int(round(self.creature.y + ny * self.flee_distance)),
        )
        safe_tile = None
        if self.phase:
            safe_tile = self.phase._find_nearest_walkable(target, forbidden={})
        if safe_tile:
            self._move_to(safe_tile)

    def _wander(self):
        if not self.phase:
            return
        jitter = (random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2))
        tx = int(round(self.creature.x + jitter[0]))
        ty = int(round(self.creature.y + jitter[1]))
        tile = self.phase._find_nearest_walkable((tx, ty), forbidden={})
        if tile:
            self._move_to(tile)

    def update(self, dt: float, world):
        self._wander_timer += dt
        r2 = self.vision_range * self.vision_range
        for p in self._players():
            dx = self.creature.x - p.x
            dy = self.creature.y - p.y
            if dx * dx + dy * dy <= r2:
                self._flee_from((p.x, p.y))
                self._wander_timer = 0.0
                return

        if self._wander_timer >= 4.0:
            self._wander_timer = 0.0
            self._wander()


class PassiveFauna(Individu):
    """Individu générique de faune passive."""

    def __init__(self, espece: Espece, x: float, y: float, assets, phase, definition: PassiveFaunaDefinition):
        super().__init__(espece, x, y, assets)
        self.nom = definition.entity_name
        self.is_fauna = True
        self.move_speed = definition.move_speed
        self.renderer = PassiveFaunaRenderer(assets, definition.sprite_keys)
        self.comportement = PassiveFaunaBehavior(
            self,
            phase,
            vision_range=definition.vision_range,
            flee_distance=definition.flee_distance,
        )


class PassiveFaunaFactory:
    """
    Fabrique paramétrable :
    - Passe une définition pour générer l'espèce (stats/nom),
    - puis crée des individus avec IA passive et rendu dédié.
    """

    def __init__(self, phase, assets, definition: PassiveFaunaDefinition):
        self.phase = phase
        self.assets = assets
        self.definition = definition

    def create_species(self) -> Espece:
        espece = Espece(self.definition.species_name)
        espece.base_physique.update(self.definition.physique)
        espece.base_sens.update(self.definition.sens)
        espece.base_mental.update(self.definition.mental)
        espece.base_environnement.update(self.definition.environnement)
        espece.base_social.update(self.definition.social)
        espece.genetique.update(self.definition.genetique)
        return espece

    def create_creature(self, species: Espece, x: float, y: float) -> PassiveFauna:
        creature = PassiveFauna(species, x, y, self.assets, phase=self.phase, definition=self.definition)
        creature.ia["autonomie"] = True
        creature.phase = self.phase
        return creature
