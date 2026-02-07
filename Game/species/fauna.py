from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Tuple, Sequence, Optional, Dict, List

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
    hp: float = 100.0
    vision_range: float = 8.0
    flee_distance: float = 5.0
    sprite_keys: Sequence[str] = ("rabbit_idle_0", "rabbit_idle_1", "rabbit_idle_2")
    sprite_keys_attack: Sequence[str] = ()
    sprite_sheet_idle: Optional[str] = None
    sprite_sheet_run: Optional[str] = None
    sprite_sheet_attack: Optional[str] = None
    sprite_sheet_frame_size: Tuple[int, int] = (32, 32)
    sprite_sheet_frame_counts: Optional[Dict[str, int]] = None
    sprite_base_scale: Optional[float] = None
    attack_anim_ms: int = 240
    is_aggressive: bool = False

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


@dataclass(frozen=True)
class AggressiveFaunaDefinition(PassiveFaunaDefinition):
    """
    Décrit une espèce agressive (attaque les individus au lieu de fuir).
    """

    attack: float = 8.0
    attack_speed: float = 1.1
    chase_distance: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "is_aggressive", True)
        object.__setattr__(self, "chase_distance", float(self.vision_range))

class PassiveFaunaRenderer:
    """Rendu simple multi-frames (idle/run) avec zoom."""

    BASE_SIZE = (20, 24)

    def __init__(
        self,
        assets,
        sprite_keys: Sequence[str],
        sprite_keys_attack: Sequence[str] | None = None,
        creature=None,
        sprite_sheets: Optional[Dict[str, str]] = None,
        frame_size: Tuple[int, int] = (32, 32),
        frame_counts: Optional[Dict[str, int]] = None,
        base_scale: Optional[float] = None,
        attack_anim_ms: int = 240,
    ):
        self.assets = assets
        self.creature = creature
        self.sprite_sheets = sprite_sheets or {}
        self.frame_w, self.frame_h = frame_size
        self.frame_counts = frame_counts or {}
        self.base_scale = float(base_scale) if base_scale is not None else (self.BASE_SIZE[1] / max(1, self.frame_h))
        self.keys = tuple(sprite_keys) if sprite_keys else ()
        self.attack_keys = tuple(sprite_keys_attack) if sprite_keys_attack else ()

        idle_frames: List[pygame.Surface] = []
        run_frames: List[pygame.Surface] = []
        attack_frames: List[pygame.Surface] = []

        if self.sprite_sheets:
            idle_key = self.sprite_sheets.get("idle")
            run_key = self.sprite_sheets.get("run")
            attack_key = self.sprite_sheets.get("attack")
            if idle_key:
                idle_frames = self._slice_sheet(idle_key, self.frame_counts.get("idle"))
            if run_key:
                run_frames = self._slice_sheet(run_key, self.frame_counts.get("run"))
            if attack_key:
                attack_frames = self._slice_sheet(attack_key, self.frame_counts.get("attack"))

        if not idle_frames:
            idle_frames = [self.assets.get_image(k) for k in self.keys if k in getattr(self.assets, "images", {})]
            if not idle_frames and self.keys:
                idle_frames = [self.assets.get_image(self.keys[0])]

        if not run_frames:
            run_frames = list(idle_frames)
        if not attack_frames:
            if self.attack_keys:
                attack_frames = [self.assets.get_image(k) for k in self.attack_keys if k in getattr(self.assets, "images", {})]
                if not attack_frames and self.attack_keys:
                    attack_frames = [self.assets.get_image(self.attack_keys[0])]
        if not attack_frames:
            attack_frames = list(run_frames) if run_frames else list(idle_frames)

        if not idle_frames:
            surf = pygame.Surface((20, 16), pygame.SRCALPHA)
            surf.fill((220, 220, 220, 255))
            idle_frames = [surf]
        if not run_frames:
            run_frames = list(idle_frames)

        self.idle_frames = idle_frames
        self.run_frames = run_frames
        self.attack_frames = attack_frames
        self.frame_ms = 240
        self.attack_frame_ms = max(60, int(attack_anim_ms))
        self._anim_state = "idle"
        self._anim_start_ms = pygame.time.get_ticks()

    def _slice_sheet(self, key: str, limit: Optional[int] = None) -> List[pygame.Surface]:
        try:
            sheet = self.assets.get_image(key)
        except Exception:
            return []
        sw, sh = sheet.get_width(), sheet.get_height()
        if self.frame_w <= 0 or self.frame_h <= 0:
            return []
        frames: List[pygame.Surface] = []
        for y in range(0, sh, self.frame_h):
            for x in range(0, sw, self.frame_w):
                if limit is not None and len(frames) >= limit:
                    return frames
                rect = pygame.Rect(x, y, self.frame_w, self.frame_h)
                if rect.right <= sw and rect.bottom <= sh:
                    frames.append(sheet.subsurface(rect).copy())
        return frames

    def _is_moving(self) -> bool:
        c = self.creature
        if c is None:
            return False
        if getattr(c, "_move_to", None) is not None and getattr(c, "_move_t", 1.0) < 1.0:
            return True
        if getattr(c, "move_path", None):
            try:
                if len(c.move_path) > 0:
                    return True
            except Exception:
                return True
        state = c.ia.get("etat") if hasattr(c, "ia") else None
        return state in ("se_deplace", "se_deplace_vers_prop", "se_deplace_vers_construction")

    def _current_frame(self) -> pygame.Surface:
        now_ms = pygame.time.get_ticks()
        is_attacking = False
        if self.creature is not None:
            until = getattr(self.creature, "_attack_anim_until_ms", 0)
            is_attacking = bool(until and now_ms < until)

        state = "attack" if is_attacking else ("run" if self._is_moving() else "idle")
        if state == "attack":
            frames = self.attack_frames
        else:
            frames = self.run_frames if state == "run" else self.idle_frames
        if state != self._anim_state:
            self._anim_state = state
            self._anim_start_ms = now_ms
        if len(frames) == 1:
            return frames[0]
        elapsed = max(0, now_ms - self._anim_start_ms)
        step_ms = self.attack_frame_ms if state == "attack" else self.frame_ms
        idx = (elapsed // step_ms) % len(frames)
        return frames[int(idx)]

    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float) -> Tuple[pygame.Surface, pygame.Rect]:
        base = self._current_frame()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        scale = max(0.05, float(zoom) * self.base_scale)
        sprite = pygame.transform.smoothscale(base, (int(base.get_width() * scale), int(base.get_height() * scale)))

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

    def cancel_work(self, reason: str | None = None):
        if getattr(self.creature, "work", None):
            self.creature.work = None

        etat = self.creature.ia.get("etat")
        if etat in (
            "recolte",
            "se_deplace_vers_prop",
            "construction",
            "se_deplace_vers_construction",
            "interaction",
            "demonte",
        ):
            self.creature.ia["etat"] = "idle"

        self.creature.ia["objectif"] = None
        self.creature.ia["order_action"] = None
        self.creature.ia["target_craft_id"] = None


class AggressiveFaunaBehavior:
    """IA agressive : patrouille et attaque les individus proches."""

    def __init__(self, creature, phase, vision_range: float):
        self.creature = creature
        self.phase = phase
        self.vision_range = vision_range
        self._wander_timer = 0.0

    def try_eating(self):
        self.creature.jauges["faim"] = min(100, self.creature.jauges.get("faim", 100) + 10)

    def _targets(self):
        if not self.phase:
            return []
        targets = []
        for ent in getattr(self.phase, "entities", []):
            if ent is self.creature:
                continue
            if getattr(ent, "is_egg", False):
                continue
            if getattr(ent, "_dead_processed", False):
                continue
            if ent.jauges.get("sante", 0) <= 0:
                continue
            if getattr(ent, "is_fauna", False):
                continue
            targets.append(ent)
        return targets

    def _wander(self):
        if not self.phase:
            return
        jitter = (random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0))
        tx = int(round(self.creature.x + jitter[0]))
        ty = int(round(self.creature.y + jitter[1]))
        tile = self.phase._find_nearest_walkable((tx, ty), forbidden={})
        if tile:
            self.phase._ensure_move_runtime(self.creature)
            self.phase._apply_entity_order(
                self.creature,
                target=tile,
                etat="se_deplace",
                objectif=None,
                action_mode=None,
                craft_id=None,
            )

    def _pick_target_in_range(self):
        r2 = self.vision_range * self.vision_range
        best = None
        best_d2 = None
        for ent in self._targets():
            dx = float(ent.x) - float(self.creature.x)
            dy = float(ent.y) - float(self.creature.y)
            d2 = dx * dx + dy * dy
            if d2 <= r2 and (best_d2 is None or d2 < best_d2):
                best = ent
                best_d2 = d2
        return best

    def update(self, dt: float, world):
        self._wander_timer += dt

        if self.phase and self.creature.ia.get("etat") == "combat":
            target = getattr(self.creature, "_combat_target", None)
            if target in getattr(self.phase, "entities", []):
                return

        target = self._pick_target_in_range()
        if target is not None and self.phase:
            self.phase._start_entity_combat(self.creature, target)
            self._wander_timer = 0.0
            return

        if self._wander_timer >= 3.5:
            self._wander_timer = 0.0
            self._wander()

    def cancel_work(self, reason: str | None = None):
        if getattr(self.creature, "work", None):
            self.creature.work = None

        etat = self.creature.ia.get("etat")
        if etat in (
            "recolte",
            "se_deplace_vers_prop",
            "construction",
            "se_deplace_vers_construction",
            "interaction",
            "demonte",
        ):
            self.creature.ia["etat"] = "idle"

        self.creature.ia["objectif"] = None
        self.creature.ia["order_action"] = None
        self.creature.ia["target_craft_id"] = None


class PassiveFauna(Individu):
    """Individu générique de faune passive."""

    def __init__(self, espece: Espece, x: float, y: float, assets, phase, definition: PassiveFaunaDefinition):
        super().__init__(espece, x, y, assets)
        self.nom = definition.entity_name
        self.is_fauna = True
        self.max_sante = max(1.0, float(definition.hp))
        self.jauges["sante"] = self.max_sante
        self.attack_anim_ms = int(getattr(definition, "attack_anim_ms", 240))
        self.move_speed = definition.move_speed
        sprite_sheets = {}
        if definition.sprite_sheet_idle:
            sprite_sheets["idle"] = definition.sprite_sheet_idle
        if definition.sprite_sheet_run:
            sprite_sheets["run"] = definition.sprite_sheet_run
        if definition.sprite_sheet_attack:
            sprite_sheets["attack"] = definition.sprite_sheet_attack
        self.renderer = PassiveFaunaRenderer(
            assets,
            definition.sprite_keys,
            sprite_keys_attack=getattr(definition, "sprite_keys_attack", ()),
            creature=self,
            sprite_sheets=sprite_sheets,
            frame_size=definition.sprite_sheet_frame_size,
            frame_counts=definition.sprite_sheet_frame_counts,
            base_scale=definition.sprite_base_scale,
            attack_anim_ms=self.attack_anim_ms,
        )
        self.comportement = PassiveFaunaBehavior(
            self,
            phase,
            vision_range=definition.vision_range,
            flee_distance=definition.flee_distance,
        )

    @property
    def hp(self) -> float:
        return float(self.jauges.get("sante", 0.0))

    @hp.setter
    def hp(self, value: float) -> None:
        self.jauges["sante"] = max(0.0, float(value))


class AggressiveFauna(PassiveFauna):
    """Individu de faune agressive."""

    def __init__(self, espece: Espece, x: float, y: float, assets, phase, definition: AggressiveFaunaDefinition):
        super().__init__(espece, x, y, assets, phase, definition)
        self.is_aggressive = True
        self.combat["attaque"] = float(definition.attack)
        self.combat["attaque_speed"] = float(definition.attack_speed)
        self.chase_distance = float(getattr(definition, "chase_distance", 0.0) or 0.0)
        self.comportement = AggressiveFaunaBehavior(
            self,
            phase,
            vision_range=definition.vision_range,
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


class AggressiveFaunaFactory(PassiveFaunaFactory):
    """Fabrique pour la faune agressive."""

    def __init__(self, phase, assets, definition: AggressiveFaunaDefinition):
        super().__init__(phase, assets, definition)

    def create_creature(self, species: Espece, x: float, y: float) -> AggressiveFauna:
        creature = AggressiveFauna(species, x, y, self.assets, phase=self.phase, definition=self.definition)
        creature.ia["autonomie"] = True
        creature.phase = self.phase
        return creature
