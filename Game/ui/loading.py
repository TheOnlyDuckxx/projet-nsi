# Game/ui/loading.py
import pygame
import random
import threading
import time

from Game.core.config import WIDTH, HEIGHT
from world.world_gen import load_world_params_from_preset, WorldGenerator


class LoadingState:
    _WORLD_STAGE_SPAN = 0.70
    _RENDER_STAGE_SPAN = 0.20
    _FAUNA_STAGE_SPAN = 0.10

    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.font = app.assets.get_font("MightySouly", 36)
        self.small = pygame.font.SysFont("consolas", 18)

        self.progress = 0.0
        self.phase_txt = "Preparation..."
        self.done = False
        self.failed = None
        self._thread = None

        # visuel simple
        self.bg = pygame.Surface((WIDTH, HEIGHT))
        self.bg.fill((8, 10, 16))
        self.panel = pygame.Surface((520, 160), pygame.SRCALPHA)
        self.panel.fill((0, 0, 0, 0))
        pygame.draw.rect(self.panel, (255, 255, 255, 18), self.panel.get_rect(), border_radius=16)

        # pour passer au state suivant
        self._world = None
        self._params = None
        self._fauna_spawn_zones = []
        self._save_path = None
        self._perf_logs_enabled = True

    def _set_progress(self, value: float, label: str | None = None):
        self.progress = max(0.0, min(1.0, float(value)))
        if label is not None:
            self.phase_txt = str(label)

    def _initial_render_chunk_coords(self, world) -> list[tuple[int, int]]:
        if not world:
            return []

        cs = max(1, int(getattr(world, "chunk_size", 64) or 64))
        sx, sy = getattr(world, "spawn", (world.width // 2, world.height // 2))
        sx = int(sx)
        sy = int(sy)

        # Approximation du viewport initial de la camera.
        half_tiles_x = max(24, WIDTH // 32) + 12
        half_tiles_y = max(18, HEIGHT // 24) + 10

        i_min = max(0, sx - half_tiles_x)
        i_max = min(world.width - 1, sx + half_tiles_x)
        j_min = max(0, sy - half_tiles_y)
        j_max = min(world.height - 1, sy + half_tiles_y)

        cx_min = i_min // cs
        cx_max = i_max // cs
        cy_min = j_min // cs
        cy_max = j_max // cs
        cx_center = sx // cs
        cy_center = sy // cs

        coords: list[tuple[int, int]] = []
        for cy in range(cy_min, cy_max + 1):
            for cx in range(cx_min, cx_max + 1):
                coords.append((cx, cy))

        coords.sort(key=lambda it: abs(it[0] - cx_center) + abs(it[1] - cy_center))
        if not coords:
            return []

        # Limite volontaire: on precharge surtout le premier ecran.
        selected: list[tuple[int, int]] = []
        selected.append(coords[0])  # chunk central

        x_neighbor = next((c for c in coords[1:] if c[0] != cx_center), None)
        if x_neighbor and x_neighbor not in selected:
            selected.append(x_neighbor)

        y_neighbor = next((c for c in coords[1:] if c[1] != cy_center), None)
        if y_neighbor and y_neighbor not in selected:
            selected.append(y_neighbor)

        for c in coords:
            if len(selected) >= 3:
                break
            if c not in selected:
                selected.append(c)
        return selected[:3]

    def _is_walkable_snapshot(self, snap) -> bool:
        if snap is None:
            return False
        _lvl, _gid, overlay, biome_id = snap
        if overlay:
            return False
        return int(biome_id) not in (1, 3, 4)

    def _refine_spawn_from_loaded(self, world, max_radius: int = 36) -> tuple[int, int]:
        sx, sy = getattr(world, "spawn", (world.width // 2, world.height // 2))
        sx = int(sx)
        sy = int(sy)
        best = (sx, sy)

        for r in range(0, max_radius + 1):
            for dx in range(-r, r + 1):
                dy = r - abs(dx)
                candidates = [(sx + dx, sy + dy)]
                if dy != 0:
                    candidates.append((sx + dx, sy - dy))
                for x, y in candidates:
                    if y < 0 or y >= world.height:
                        continue
                    snap = world.get_tile_snapshot(x, y, generate=False) if hasattr(world, "get_tile_snapshot") else None
                    if self._is_walkable_snapshot(snap):
                        return (int(x) % world.width, int(y))

        # Si rien dans les chunks deja charges, on ouvre quelques chunks voisins.
        cs = max(1, int(getattr(world, "chunk_size", 64) or 64))
        cx0 = sx // cs
        cy0 = sy // cs
        width = int(world.width)
        height = int(world.height)
        best_dist = 10**9

        for ring in range(1, 4):
            found_in_ring = False
            for dy in range(-ring, ring + 1):
                for dx in range(-ring, ring + 1):
                    if abs(dx) + abs(dy) != ring:
                        continue
                    cx = cx0 + dx
                    cy = cy0 + dy
                    if cy < 0 or cy * cs >= height:
                        continue
                    tile_x = (int(cx) * cs) % width
                    tile_y = int(cy) * cs
                    world.ensure_chunk_at(tile_x, tile_y)
                    actual_w = min(cs, max(0, width - tile_x))
                    actual_h = min(cs, max(0, height - tile_y))
                    for ly in range(actual_h):
                        wy = tile_y + ly
                        for lx in range(actual_w):
                            wx = (tile_x + lx) % width
                            snap = world.get_tile_snapshot(wx, wy, generate=False) if hasattr(world, "get_tile_snapshot") else None
                            if not self._is_walkable_snapshot(snap):
                                continue
                            found_in_ring = True
                            d = abs(wx - sx) + abs(wy - sy)
                            if d < best_dist:
                                best_dist = d
                                best = (wx, wy)
            if found_in_ring:
                return best
        return best

    def _build_fauna_spawn_zones(
        self,
        world,
        params,
        count: int = 10,
        radius: int = 8,
        chunk_coords: list[tuple[int, int]] | None = None,
    ):
        if not world:
            return []

        base_seed = getattr(params, "seed", 0) if params is not None else 0
        try:
            seed_int = int(base_seed)
        except Exception:
            seed_int = random.getrandbits(32)
        rng = random.Random(seed_int + 4242)

        sx, sy = getattr(world, "spawn", (world.width // 2, world.height // 2))
        sx = int(sx)
        sy = int(sy)
        width = int(world.width)
        height = int(world.height)
        cs = max(1, int(getattr(world, "chunk_size", 64) or 64))

        x_span = min(max(96, width // 22), 200)
        y_span = min(max(96, height // 24), 180)

        x_min = max(0, sx - x_span)
        x_max = min(width - 1, sx + x_span)
        y_min = max(0, sy - y_span)
        y_max = min(height - 1, sy + y_span)

        local_chunk_coords = list(chunk_coords or [])
        if not local_chunk_coords:
            cx = sx // cs
            cy = sy // cs
            local_chunk_coords = [(cx, cy)]

        candidates: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        total_chunks = max(1, len(local_chunk_coords))
        for idx, (cx_raw, cy) in enumerate(local_chunk_coords):
            if cy < 0 or cy * cs >= height:
                continue
            cx = (int(cx_raw) * cs) % width // cs
            tile_x = cx * cs
            tile_y = int(cy) * cs
            actual_w = min(cs, max(0, width - tile_x))
            actual_h = min(cs, max(0, height - tile_y))
            for ly in range(actual_h):
                wy = tile_y + ly
                if wy < y_min or wy > y_max:
                    continue
                for lx in range(actual_w):
                    wx = (tile_x + lx) % width
                    if wx < x_min or wx > x_max:
                        continue
                    key = (wx, wy)
                    if key in seen:
                        continue
                    snap = world.get_tile_snapshot(wx, wy, generate=False) if hasattr(world, "get_tile_snapshot") else None
                    if snap is None:
                        continue
                    if not self._is_walkable_snapshot(snap):
                        continue
                    if abs(wx - sx) + abs(wy - sy) < 8:
                        continue
                    seen.add(key)
                    candidates.append(key)

            local_p = (idx + 1) / total_chunks
            self._set_progress(
                self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN + self._FAUNA_STAGE_SPAN * (0.65 * local_p),
                f"Preparation faune... ({idx + 1}/{total_chunks})",
            )

        rng.shuffle(candidates)
        zones: list[dict] = []
        forbidden = {(sx, sy), (sx + 1, sy), (sx, sy + 1)}
        for idx, (i, j) in enumerate(candidates):
            if (i, j) in forbidden:
                continue
            too_close = any(abs(i - zx) + abs(j - zy) < max(6, radius) for zx, zy in (z["pos"] for z in zones))
            if too_close:
                continue
            zones.append({"pos": (i, j), "radius": int(radius), "spawned": False})
            if len(zones) >= int(count):
                break
            if idx % 16 == 0:
                frac = min(1.0, (idx + 1) / max(1, len(candidates)))
                self._set_progress(
                    self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN + self._FAUNA_STAGE_SPAN * (0.65 + 0.35 * frac),
                    f"Preparation faune... ({len(zones)}/{count})",
                )
        if len(zones) >= int(count):
            return zones

        # Fallback: ouvre quelques chunks voisins si la zone prechargee ne suffit pas.
        cx0 = sx // cs
        cy0 = sy // cs
        extra_chunks: list[tuple[int, int]] = []
        seen_chunks = set(local_chunk_coords)
        for ring in (1, 2):
            for dy in range(-ring, ring + 1):
                for dx in range(-ring, ring + 1):
                    if abs(dx) + abs(dy) != ring:
                        continue
                    cc = (cx0 + dx, cy0 + dy)
                    if cc in seen_chunks:
                        continue
                    seen_chunks.add(cc)
                    extra_chunks.append(cc)
                    if len(extra_chunks) >= 6:
                        break
                if len(extra_chunks) >= 6:
                    break
            if len(extra_chunks) >= 6:
                break

        for idx, (cx_raw, cy) in enumerate(extra_chunks):
            if cy < 0 or cy * cs >= height:
                continue
            cx = (int(cx_raw) * cs) % width // cs
            tile_x = cx * cs
            tile_y = int(cy) * cs
            world.ensure_chunk_at(tile_x, tile_y)
            actual_w = min(cs, max(0, width - tile_x))
            actual_h = min(cs, max(0, height - tile_y))
            for ly in range(actual_h):
                wy = tile_y + ly
                if wy < y_min or wy > y_max:
                    continue
                for lx in range(actual_w):
                    wx = (tile_x + lx) % width
                    if wx < x_min or wx > x_max:
                        continue
                    if (wx, wy) in forbidden:
                        continue
                    snap = world.get_tile_snapshot(wx, wy, generate=False) if hasattr(world, "get_tile_snapshot") else None
                    if not self._is_walkable_snapshot(snap):
                        continue
                    too_close = any(abs(wx - zx) + abs(wy - zy) < max(6, radius) for zx, zy in (z["pos"] for z in zones))
                    if too_close:
                        continue
                    zones.append({"pos": (wx, wy), "radius": int(radius), "spawned": False})
                    if len(zones) >= int(count):
                        return zones
            frac = (idx + 1) / max(1, len(extra_chunks))
            self._set_progress(
                self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN + self._FAUNA_STAGE_SPAN * (0.85 + 0.15 * frac),
                f"Preparation faune... ({len(zones)}/{count})",
            )
        return zones

    def enter(self, **kwargs):
        # kwargs possibles: preset, seed
        self.progress = 0.0
        self.phase_txt = "Chargement..."
        self.done = False
        self.failed = None
        self._world = None
        self._params = None
        self._fauna_spawn_zones = []
        self._save_path = kwargs.get("save_path")
        self._perf_logs_enabled = bool(self.app.settings.get("debug.perf_logs", True))

        def worker():
            try:
                start_t = time.perf_counter()
                last_t = start_t

                def log_step(label: str):
                    nonlocal last_t
                    if not self._perf_logs_enabled:
                        return
                    now_t = time.perf_counter()
                    print(f"[Perf][Loading] {label} | +{now_t - last_t:.3f}s | total {now_t - start_t:.3f}s")
                    last_t = now_t

                preset = kwargs.get("preset", "Custom")
                seed = kwargs.get("seed", None)
                log_step(f"Debut generation world (preset={preset}, seed={seed})")
                overrides = {"seed": seed} if seed is not None else None
                self._params = load_world_params_from_preset(preset, overrides=overrides)
                log_step("Parametres de monde charges")
                gen = WorldGenerator(tiles_levels=6, chunk_size=64, cache_chunks=256)
                log_step("WorldGenerator initialise")

                phase_label = None
                phase_time = time.perf_counter()

                def on_progress(p, label):
                    nonlocal phase_label, phase_time
                    world_p = self._WORLD_STAGE_SPAN * max(0.0, min(1.0, float(p)))
                    current_label = str(label)
                    self._set_progress(world_p, current_label)
                    if self._perf_logs_enabled and current_label != phase_label:
                        now_t = time.perf_counter()
                        print(
                            f"[Perf][Loading] Phase '{current_label}' ({self.progress * 100:.1f}%)"
                            f" | +{now_t - phase_time:.3f}s | total {now_t - start_t:.3f}s"
                        )
                        phase_label = current_label
                        phase_time = now_t

                rng_seed = seed if seed is not None else self._params.seed
                log_step(f"Lancement generate_planet (rng_seed={rng_seed})")
                self._world = gen.generate_planet(self._params, rng_seed=rng_seed, progress=on_progress)
                log_step("Monde genere")
                try:
                    # Evite que la generation lazy des chunks ecrase la progression UI.
                    self._world._progress = None
                    self._world._progress_phases_reported = set()
                except Exception:
                    pass

                # Stage 2: prechargement du premier rendu (chunks proches du spawn).
                chunk_targets = self._initial_render_chunk_coords(self._world)
                if chunk_targets:
                    log_step(f"Prechargement rendu (chunks={len(chunk_targets)})")

                    def on_render_progress(p, label):
                        self._set_progress(
                            self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN * max(0.0, min(1.0, float(p))),
                            label,
                        )

                    self._world.prewarm_chunk_coords(
                        chunk_targets,
                        progress=on_render_progress,
                        phase_label="Prechargement rendu...",
                    )
                else:
                    self._set_progress(self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN, "Prechargement rendu...")
                log_step("Prechargement rendu termine")

                refined_spawn = self._refine_spawn_from_loaded(self._world, max_radius=36)
                self._world.spawn = refined_spawn
                log_step(f"Spawn raffine sur zone chargee ({refined_spawn[0]}, {refined_spawn[1]})")

                # Si le spawn raffine est sorti de la zone prechargee, complete le prechargement.
                final_chunk_targets = self._initial_render_chunk_coords(self._world)
                missing_targets = [c for c in final_chunk_targets if c not in chunk_targets]
                if missing_targets:
                    self._world.prewarm_chunk_coords(
                        missing_targets,
                        progress=None,
                        phase_label="Prechargement rendu final...",
                    )
                    log_step(f"Prechargement rendu ajuste (chunks={len(missing_targets)})")
                chunk_targets = final_chunk_targets

                # Stage 3: preparation des zones de spawn fauna.
                self._set_progress(
                    self._WORLD_STAGE_SPAN + self._RENDER_STAGE_SPAN,
                    "Preparation faune...",
                )
                self._fauna_spawn_zones = self._build_fauna_spawn_zones(
                    self._world,
                    self._params,
                    count=10,
                    radius=8,
                    chunk_coords=chunk_targets,
                )
                log_step(f"Zones de spawn faune pre-calculees ({len(self._fauna_spawn_zones)})")

                self._set_progress(1.0, "Termine !")
                self.done = True
                log_step("Etat LOADING termine")
            except Exception as e:
                self.failed = e

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def handle_input(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                # retour au menu si on veut annuler
                self.app.change_state("MENU")

    def update(self, dt):
        if self.failed:
            print(self.failed)
            self.app.change_state("MENU")
            return
        if self.done and self._world:
            # Passe a PHASE1 avec le world deja pret
            if self._perf_logs_enabled:
                print("[Perf][Loading] Transition vers PHASE1 (debut)")
            self.app.change_state(
                "PHASE1",
                world=self._world,
                params=self._params,
                fauna_spawn_zones=self._fauna_spawn_zones,
                save_path=self._save_path,
            )
            if self._perf_logs_enabled:
                print("[Perf][Loading] Transition vers PHASE1 (fin)")

    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        # titre
        title = self.font.render("Generation du monde...", True, (230, 230, 230))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 140))

        # panneau + barre
        px = WIDTH // 2 - self.panel.get_width() // 2
        py = HEIGHT // 2 - self.panel.get_height() // 2
        screen.blit(self.panel, (px, py))

        # contour barre
        bar_w, bar_h = 440, 28
        bx, by = px + 40, py + 64
        pygame.draw.rect(screen, (220, 220, 230), (bx, by, bar_w, bar_h), width=2, border_radius=10)
        # remplissage
        fill_w = int(bar_w * max(0.0, min(1.0, self.progress)))
        if fill_w > 0:
            pygame.draw.rect(screen, (70, 120, 210), (bx + 2, by + 2, fill_w - 4, bar_h - 4), border_radius=8)

        # label phase
        label = self.small.render(self.phase_txt, True, (200, 205, 215))
        screen.blit(label, (WIDTH // 2 - label.get_width() // 2, by - 28))
