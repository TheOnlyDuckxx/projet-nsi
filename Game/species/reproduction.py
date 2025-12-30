# Game/espece/reproduction.py
import random
from typing import Any, Dict, List, Optional

import pygame

from Game.ui.hud.notification import add_notification


class EggRenderer:
    """Rendu simplifié pour représenter un œuf sur la carte isométrique."""

    BASE_SIZE = (16, 20)

    def __init__(self, assets=None):
        self.assets = assets

    def _placeholder_surface(self) -> pygame.Surface:
        surf = pygame.Surface(self.BASE_SIZE, pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (230, 230, 200), (0, 4, self.BASE_SIZE[0], self.BASE_SIZE[1] - 4))
        pygame.draw.ellipse(surf, (160, 140, 110), (2, 6, self.BASE_SIZE[0] - 4, self.BASE_SIZE[1] - 8), 2)
        pygame.draw.circle(surf, (250, 250, 245), (self.BASE_SIZE[0] // 2, 6), 3)
        return surf

    def _get_img(self) -> pygame.Surface:
        if self.assets is None:
            return self._placeholder_surface()
        try:
            img = self.assets.get_image("egg")
            if img is not None:
                return img
        except Exception:
            pass
        return self._placeholder_surface()

    def get_draw_surface_and_rect(self, view, world, tx: float, ty: float):
        sprite = self._get_img()
        zoom = getattr(view, "zoom", 1.0) or 1.0
        if abs(zoom - 1.0) > 1e-6:
            w, h = sprite.get_size()
            sprite = pygame.transform.smoothscale(sprite, (int(w * zoom), int(h * zoom)))

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
        py = int(surface_y - sprite.get_height() + 4)
        rect = pygame.Rect(px, py, sprite.get_width(), sprite.get_height())
        return sprite, rect

    def render(self, screen, view, world, tx: float, ty: float):
        sprite, rect = self.get_draw_surface_and_rect(view, world, tx, ty)
        screen.blit(sprite, rect.topleft)


class Egg:
    def __init__(
        self,
        espece,
        x: float,
        y: float,
        assets,
        created_at_minutes: float,
        hatch_after_minutes: float,
        durability: float = 50.0,
    ):
        self.espece = espece
        self.nom = f"Œuf de {espece.nom}"
        self.x = float(x)
        self.y = float(y)
        self.is_egg = True
        self.ia = {"etat": "statique"}

        self.max_durability = max(1.0, float(durability))
        self.durability = float(durability)
        self.created_at = float(created_at_minutes)
        self.hatch_time = float(created_at_minutes + hatch_after_minutes)

        self.renderer = EggRenderer(assets)
        self.reproduction = None  # défini par le système après création

    def take_damage(self, amount: float) -> None:
        self.durability = max(0.0, self.durability - max(0.0, float(amount)))

    def is_destroyed(self) -> bool:
        return self.durability <= 0

    def draw(self, screen, view, world):
        if self.renderer:
            self.renderer.render(screen, view, world, self.x, self.y)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pos": (float(self.x), float(self.y)),
            "durability": self.durability,
            "max_durability": self.max_durability,
            "created_at": self.created_at,
            "hatch_time": self.hatch_time,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any], espece, assets) -> "Egg":
        pos = data.get("pos", (0.0, 0.0))
        created = float(data.get("created_at", 0.0))
        hatch_time = float(data.get("hatch_time", created + 24 * 60))
        egg = Egg(
            espece,
            x=float(pos[0]),
            y=float(pos[1]),
            assets=assets,
            created_at_minutes=created,
            hatch_after_minutes=max(0.0, hatch_time - created),
            durability=float(data.get("durability", 50.0)),
        )
        egg.max_durability = float(data.get("max_durability", egg.max_durability))
        egg.hatch_time = hatch_time
        return egg


class ReproductionSystem:
    FIRST_EGG_EVENT_ID = "protect_first_egg"
    HATCH_DELAY_MINUTES = 24 * 60  # 1 jour de jeu

    def __init__(self, espece):
        self.espece = espece
        self.eggs: List[Egg] = []
        self.phase = None
        self.first_egg_event_triggered = False

    # ---------- Helpers ----------
    def bind_phase(self, phase) -> None:
        """Enregistre la phase pour pouvoir accéder au monde/temps/évènements."""
        self.phase = phase

    def _current_game_minutes(self) -> float:
        if not self.phase:
            return 0.0
        dn = getattr(self.phase, "day_night", None)
        if dn is None:
            return 0.0
        ratio = dn.get_time_ratio()
        hours_float = ratio * 24.0
        hours = int(hours_float)
        minutes_float = (hours_float - hours) * 60.0
        return getattr(dn, "jour", 0) * 24 * 60 + hours * 60 + minutes_float

    def _available_tile_near(self, individu) -> Optional[tuple[int, int]]:
        if not self.phase or not getattr(self.phase, "world", None):
            return int(individu.x), int(individu.y)

        base = (int(individu.x), int(individu.y))
        forbidden = getattr(self.phase, "_occupied_tiles", lambda exclude=None: set())(exclude=[individu])
        offsets = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
        for radius in (1, 2, 3):
            for dx, dy in offsets:
                nx, ny = base[0] + dx * radius, base[1] + dy * radius
                walkable = getattr(self.phase, "_is_walkable", lambda i, j: True)
                if walkable(nx, ny) and (nx, ny) not in forbidden:
                    return nx, ny
        return base

    def _resolve_assets(self, individu) -> Any:
        assets = None
        try:
            assets = individu.renderer.assets
        except Exception:
            assets = None
        if assets is None:
            assets = getattr(self.phase, "assets", None)
        return assets

    def _trigger_first_egg_event(self) -> None:
        if self.first_egg_event_triggered:
            return
        mgr = getattr(self.phase, "event_manager", None)
        if mgr:
            definition = mgr.definitions.get(self.FIRST_EGG_EVENT_ID)
            if definition:
                mgr._trigger_event(definition, self.phase)
            else:
                add_notification("Un œuf vient d'apparaître, protégez-le !")
        self.first_egg_event_triggered = True

    # ---------- Public API ----------
    def on_species_level_up(self) -> Optional[Egg]:
        if not self.phase or not self.espece.individus:
            return None

        parent = random.choice(self.espece.individus)
        tile = self._available_tile_near(parent)
        assets = self._resolve_assets(parent)
        created_at = self._current_game_minutes()
        egg = Egg(
            self.espece,
            x=tile[0],
            y=tile[1],
            assets=assets,
            created_at_minutes=created_at,
            hatch_after_minutes=self.HATCH_DELAY_MINUTES,
            durability=60.0,
        )
        egg.reproduction = self
        self.eggs.append(egg)

        # Rendre visible dans le monde
        try:
            if hasattr(self.phase, "entities"):
                self.phase.entities.append(egg)
            egg.phase = self.phase
        except Exception:
            pass

        add_notification(f"Un œuf apparaît près de {parent.nom} !")
        self._trigger_first_egg_event()
        return egg

    def damage_egg(self, egg: Egg, amount: float) -> None:
        egg.take_damage(amount)

    def _remove_egg(self, egg: Egg) -> None:
        if egg in self.eggs:
            self.eggs.remove(egg)
        try:
            if hasattr(self.phase, "entities") and egg in self.phase.entities:
                self.phase.entities.remove(egg)
        except Exception:
            pass

    def _hatch(self, egg: Egg) -> None:
        assets = self._resolve_assets(self.espece.individus[0]) if self.espece.individus else self._resolve_assets(egg)
        if assets is None and self.phase:
            assets = getattr(self.phase, "assets", None)
        new_ind = self.espece.create_individu(x=egg.x, y=egg.y, assets=assets)
        try:
            if hasattr(self.phase, "entities"):
                self.phase.entities.append(new_ind)
            new_ind.phase = self.phase
        except Exception:
            pass

        add_notification(f"Un nouvel individu {new_ind.nom} éclot de l'œuf !")
        self._remove_egg(egg)

    def update(self, dt: float = 0.0):
        if not self.eggs or not self.phase:
            return

        now = self._current_game_minutes()
        for egg in list(self.eggs):
            if egg.is_destroyed():
                add_notification("Un œuf a été détruit…")
                self._remove_egg(egg)
                continue
            if now >= egg.hatch_time:
                self._hatch(egg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_egg_event_triggered": self.first_egg_event_triggered,
            "eggs": [egg.to_dict() for egg in self.eggs],
        }

    def load_state(self, data: Dict[str, Any], assets=None) -> None:
        self.eggs = []
        if not data:
            return
        self.first_egg_event_triggered = bool(data.get("first_egg_event_triggered", False))
        for egg_data in data.get("eggs", []):
            egg = Egg.from_dict(egg_data, self.espece, assets)
            egg.reproduction = self
            self.eggs.append(egg)
            try:
                if hasattr(self.phase, "entities"):
                    self.phase.entities.append(egg)
                egg.phase = self.phase
            except Exception:
                pass
