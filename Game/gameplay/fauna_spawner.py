from __future__ import annotations

import json
import math
import random
from typing import Any

from Game.species.fauna import PassiveFaunaFactory

try:
    from world.world_gen import BIOME_ID_TO_NAME
except Exception:
    BIOME_ID_TO_NAME = {}


class FaunaSpawner:
    """
    Spawn passif piloté par biome autour des individus non-faune.
    - Budget de spawn/despawn borné pour lisser les perfs.
    - Placement dans le fog non exploré (quand dispo).
    - Index spatial en buckets pour compter localement sans scanner toute la map.
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._rng = random.Random()
        self._spawn_timer = 0.0
        self._despawn_timer = 0.0
        self._anchor_cursor = 0
        self._bucket_size = 16
        self._fauna_buckets: dict[tuple[int, int], list] = {}
        self._config: dict[str, float | int] = {}
        self._default_pool: list[tuple[str, float]] = []
        self._biome_pools: dict[str, list[tuple[str, float]]] = {}
        self._load_config()

    def reset(self):
        self._spawn_timer = 0.0
        self._despawn_timer = 0.0
        self._anchor_cursor = 0
        self._fauna_buckets = {}

    def _load_config(self):
        raw: dict[str, Any] = {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
        except Exception:
            raw = {}

        settings = raw.get("settings", {}) if isinstance(raw, dict) else {}
        self._config = {
            "spawn_interval_sec": float(settings.get("spawn_interval_sec", 0.45)),
            "spawn_interval_jitter_sec": float(settings.get("spawn_interval_jitter_sec", 0.2)),
            "max_global_fauna": int(settings.get("max_global_fauna", 90)),
            "anchor_scan_per_cycle": int(settings.get("anchor_scan_per_cycle", 2)),
            "max_spawn_per_cycle": int(settings.get("max_spawn_per_cycle", 2)),
            "local_target_per_anchor": int(settings.get("local_target_per_anchor", 5)),
            "local_count_radius_tiles": float(settings.get("local_count_radius_tiles", 26.0)),
            "spawn_ring_min_tiles": float(settings.get("spawn_ring_min_tiles", 12.0)),
            "spawn_ring_max_tiles": float(settings.get("spawn_ring_max_tiles", 28.0)),
            "spawn_attempts_per_anchor": int(settings.get("spawn_attempts_per_anchor", 8)),
            "despawn_interval_sec": float(settings.get("despawn_interval_sec", 1.6)),
            "despawn_distance_tiles": float(settings.get("despawn_distance_tiles", 68.0)),
            "max_despawn_per_cycle": int(settings.get("max_despawn_per_cycle", 10)),
            "bucket_size_tiles": int(settings.get("bucket_size_tiles", 16)),
        }
        self._bucket_size = max(4, int(self._config["bucket_size_tiles"]))
        self._default_pool = self._normalize_pool(raw.get("default"))
        self._biome_pools = {}
        for biome_name, pool in (raw.get("biomes", {}) or {}).items():
            self._biome_pools[str(biome_name).lower()] = self._normalize_pool(pool)

    def update(self, dt: float, phase) -> None:
        if not phase or not getattr(phase, "world", None):
            return

        self._spawn_timer -= dt
        if self._spawn_timer <= 0.0:
            self._run_spawn_cycle(phase)
            base = max(0.05, float(self._config["spawn_interval_sec"]))
            jitter = max(0.0, float(self._config["spawn_interval_jitter_sec"]))
            self._spawn_timer = base + self._rng.uniform(0.0, jitter)

        self._despawn_timer -= dt
        if self._despawn_timer <= 0.0:
            self._run_despawn_cycle(phase)
            self._despawn_timer = max(0.2, float(self._config["despawn_interval_sec"]))

    # ---------- Spawn ----------
    def _run_spawn_cycle(self, phase):
        anchors = self._anchors(phase)
        if not anchors:
            return

        fauna = self._fauna_entities(phase)
        max_global = int(self._config["max_global_fauna"])
        if len(fauna) >= max_global:
            return

        self._refresh_spatial_index(fauna)

        anchor_scan = max(1, int(self._config["anchor_scan_per_cycle"]))
        max_spawn = max(1, int(self._config["max_spawn_per_cycle"]))
        attempts_per_anchor = max(1, int(self._config["spawn_attempts_per_anchor"]))
        local_target = max(1, int(self._config["local_target_per_anchor"]))
        local_radius = max(4.0, float(self._config["local_count_radius_tiles"]))

        selected_anchors = self._next_anchors(anchors, anchor_scan)
        occupied = {
            (int(getattr(e, "x", 0)), int(getattr(e, "y", 0)))
            for e in phase.entities
            if not getattr(e, "_dead_processed", False)
        }

        spawned = 0
        for anchor in selected_anchors:
            if spawned >= max_spawn:
                break
            if len(fauna) + spawned >= max_global:
                break

            ax, ay = float(anchor.x), float(anchor.y)
            nearby = self._count_fauna_near(ax, ay, local_radius)
            if nearby >= local_target:
                continue

            for _ in range(attempts_per_anchor):
                candidate = self._find_spawn_candidate(phase, ax, ay, occupied)
                if candidate is None:
                    continue
                tx, ty, biome_name = candidate
                species_id = self._pick_species_for_biome(biome_name)
                if not species_id:
                    continue
                ent = self._spawn_entity(phase, species_id, tx, ty)
                if ent is None:
                    continue
                occupied.add((tx, ty))
                fauna.append(ent)
                bkey = self._bucket_key(tx, ty)
                self._fauna_buckets.setdefault(bkey, []).append(ent)
                spawned += 1
                break

    def _find_spawn_candidate(self, phase, ax: float, ay: float, occupied: set[tuple[int, int]]):
        world = phase.world
        min_d = max(4.0, float(self._config["spawn_ring_min_tiles"]))
        max_d = max(min_d + 1.0, float(self._config["spawn_ring_max_tiles"]))

        ang = self._rng.uniform(0.0, math.tau)
        dist = self._rng.uniform(min_d, max_d)
        tx = int(round(ax + math.cos(ang) * dist))
        ty = int(round(ay + math.sin(ang) * dist))

        if tx < 0 or ty < 0 or tx >= int(getattr(world, "width", 0)) or ty >= int(getattr(world, "height", 0)):
            return None
        if (tx, ty) in occupied:
            return None
        if not phase._is_walkable(tx, ty, generate=False):
            return None
        if not self._tile_is_spawn_hidden(phase, tx, ty):
            return None

        biome_name = self._biome_name_at(world, tx, ty)
        return tx, ty, biome_name

    def _spawn_entity(self, phase, species_id: str, x: int, y: int):
        definition = phase.get_fauna_definition(species_id)
        if definition is None:
            return None

        species = phase._init_fauna_species(definition)
        if species is None:
            return None

        factory = PassiveFaunaFactory(phase, phase.assets, definition)
        ent = factory.create_creature(species, float(x), float(y))
        phase._ensure_move_runtime(ent)
        phase.entities.append(ent)
        return ent

    # ---------- Despawn ----------
    def _run_despawn_cycle(self, phase):
        fauna = self._fauna_entities(phase)
        if not fauna:
            return

        anchors = self._anchors(phase)
        if not anchors:
            return

        max_remove = max(1, int(self._config["max_despawn_per_cycle"]))
        despawn_dist = max(8.0, float(self._config["despawn_distance_tiles"]))
        d2 = despawn_dist * despawn_dist
        removed = 0

        for ent in list(fauna):
            if removed >= max_remove:
                break
            if getattr(ent, "_dead_processed", False):
                continue
            if ent.jauges.get("sante", 0) <= 0:
                continue
            if self._is_engaged_in_combat(phase, ent):
                continue

            ex, ey = float(ent.x), float(ent.y)
            near_anchor = False
            for a in anchors:
                dx = ex - float(a.x)
                dy = ey - float(a.y)
                if dx * dx + dy * dy <= d2:
                    near_anchor = True
                    break
            if near_anchor:
                continue

            # Évite les disparitions visibles à l'écran.
            fog = getattr(phase, "fog", None)
            if fog is not None:
                try:
                    if fog.is_visible(int(ex), int(ey)):
                        continue
                except Exception:
                    pass

            self._despawn_entity(phase, ent)
            removed += 1

    def _despawn_entity(self, phase, ent):
        try:
            phase._stop_entity_combat(ent, stop_motion=False)
        except Exception:
            pass

        for other in list(getattr(phase, "entities", [])):
            if other is ent:
                continue
            if getattr(other, "_combat_target", None) is ent:
                try:
                    phase._stop_entity_combat(other)
                except Exception:
                    pass

        if ent in phase.entities:
            phase.entities.remove(ent)
        if getattr(ent, "espece", None) is not None:
            try:
                ent.espece.remove_individu(ent)
            except Exception:
                pass

        selected = getattr(phase, "selected_entities", None)
        if isinstance(selected, list) and ent in selected:
            selected.remove(ent)
        if getattr(phase, "selected", None) and phase.selected[0] == "entity" and phase.selected[1] is ent:
            phase.selected = None

    # ---------- Helpers ----------
    def _normalize_pool(self, entries: Any) -> list[tuple[str, float]]:
        pool: list[tuple[str, float]] = []
        if not isinstance(entries, list):
            return pool
        for row in entries:
            if not isinstance(row, dict):
                continue
            species = str(row.get("species", "")).strip().lower()
            if not species:
                continue
            try:
                weight = float(row.get("weight", 1.0))
            except Exception:
                weight = 1.0
            if weight <= 0:
                continue
            pool.append((species, weight))
        return pool

    def _pick_species_for_biome(self, biome_name: str) -> str | None:
        pool = self._biome_pools.get(str(biome_name).lower()) or self._default_pool
        if not pool:
            return None
        total = sum(weight for _, weight in pool)
        if total <= 0:
            return pool[0][0]
        roll = self._rng.uniform(0.0, total)
        acc = 0.0
        for species, weight in pool:
            acc += weight
            if roll <= acc:
                return species
        return pool[-1][0]

    def _anchors(self, phase) -> list:
        return [
            e for e in phase.entities
            if not getattr(e, "is_egg", False)
            and not getattr(e, "is_fauna", False)
            and not getattr(e, "_dead_processed", False)
            and e.jauges.get("sante", 0) > 0
        ]

    def _next_anchors(self, anchors: list, count: int) -> list:
        if not anchors:
            return []
        picked = []
        n = len(anchors)
        for _ in range(min(count, n)):
            picked.append(anchors[self._anchor_cursor % n])
            self._anchor_cursor += 1
        return picked

    def _fauna_entities(self, phase) -> list:
        return [
            e for e in phase.entities
            if getattr(e, "is_fauna", False)
            and not getattr(e, "_dead_processed", False)
            and e.jauges.get("sante", 0) > 0
        ]

    def _is_engaged_in_combat(self, phase, ent) -> bool:
        for other in phase.entities:
            if other is ent:
                continue
            if getattr(other, "_combat_target", None) is ent:
                return True
        return False

    def _bucket_key(self, x: float, y: float) -> tuple[int, int]:
        return int(x) // self._bucket_size, int(y) // self._bucket_size

    def _refresh_spatial_index(self, fauna_entities: list) -> None:
        buckets: dict[tuple[int, int], list] = {}
        for ent in fauna_entities:
            key = self._bucket_key(ent.x, ent.y)
            buckets.setdefault(key, []).append(ent)
        self._fauna_buckets = buckets

    def _count_fauna_near(self, x: float, y: float, radius: float) -> int:
        r = max(1.0, float(radius))
        r2 = r * r
        bx0 = int((x - r) // self._bucket_size)
        bx1 = int((x + r) // self._bucket_size)
        by0 = int((y - r) // self._bucket_size)
        by1 = int((y + r) // self._bucket_size)
        total = 0
        for by in range(by0, by1 + 1):
            for bx in range(bx0, bx1 + 1):
                for ent in self._fauna_buckets.get((bx, by), []):
                    dx = float(ent.x) - x
                    dy = float(ent.y) - y
                    if dx * dx + dy * dy <= r2:
                        total += 1
        return total

    def _tile_is_spawn_hidden(self, phase, x: int, y: int) -> bool:
        fog = getattr(phase, "fog", None)
        if fog is None:
            return True
        try:
            if fog.is_visible(x, y):
                return False
            return not fog.is_explored(x, y)
        except Exception:
            return False

    def _biome_name_at(self, world, x: int, y: int) -> str:
        if hasattr(world, "get_tile_snapshot"):
            snap = world.get_tile_snapshot(x, y, generate=False)
            if snap is not None and len(snap) >= 4:
                bid = int(snap[3])
                if bid in BIOME_ID_TO_NAME:
                    return str(BIOME_ID_TO_NAME[bid])
        try:
            return str(world.get_biome_name(x, y))
        except Exception:
            return "unknown"
