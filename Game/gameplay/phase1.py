# --- imports en haut du fichier ---
import pygame, random, heapq
from typing import List, Tuple, Optional
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator
from Game.world.tiles import get_ground_sprite_name
from Game.species.species import Espece
from Game.save.save import SaveManager



class Phase1:
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False

        self.view = IsoMapView(self.assets, self.screen.get_size())
        self.gen = WorldGenerator(tiles_levels=6)
        self.params = None
        self.world = None

        # entités
        self.joueur: Optional[Espece] = None
        self.entities: list = []

        # UI/HUD
        self.show_info = True
        self.font = pygame.font.SysFont("consolas", 16)

        # Sélection actuelle: ("tile",(i,j)) | ("prop",(i,j,pid)) | ("entity",ent)
        self.selected: Optional[tuple] = None
        self.save_message = ""
        self.save_message_timer = 0.0

    # ---- Sauvegarde / Chargement (wrappers pour le menu) ----
    @staticmethod
    def save_exists() -> bool:
        return SaveManager().save_exists()

    def save(self) -> bool:
        return SaveManager().save_phase1(self)

    def load(self) -> bool:
        return SaveManager().load_phase1(self)

    #Cii
    def _ensure_move_runtime(self, ent):
        """S'assure que l'entité a tout le runtime nécessaire au déplacement."""
        if not hasattr(ent, "move_path"):   ent.move_path = []          # liste de (i,j)
        if not hasattr(ent, "move_speed"):  ent.move_speed = 3.5        # tuiles/s
        if not hasattr(ent, "_move_from"):  ent._move_from = None       # (x,y) float
        if not hasattr(ent, "_move_to"):    ent._move_to = None         # (i,j) int
        if not hasattr(ent, "_move_t"):     ent._move_t = 0.0           # 0..1


    # ---------- WORLD LIFECYCLE ----------
    def enter(self, **kwargs):
        # 1) Si on demande explicitement de charger une sauvegarde et qu'elle existe
        if kwargs.get("load_save", False) and self.save_exists():
            if self.load():
                return  # on est prêt (world/params/view/joueur déjà posés)

        # 2) Si le loader nous a déjà donné un monde et des params → on les utilise
        pre_world = kwargs.get("world", None)
        pre_params = kwargs.get("params", None)

        if pre_world is not None:
            self.world = pre_world
            # si params non fournis, tente d'hériter depuis le world, sinon on garde self.params tel quel
            self.params = pre_params or getattr(pre_world, "params", None) or self.params
            self.view.set_world(self.world)

            # s'assurer qu'on a un joueur (si on n'a pas chargé une save)
            if not self.joueur:
                try:
                    sx, sy = self.world.spawn
                except Exception:
                    sx, sy = 0, 0
                from Game.species.species import Espece
                self.joueur = Espece("Hominidé", x=float(sx), y=float(sy), assets=self.assets)
                self.entities = [self.joueur]
            return  # IMPORTANT: on ne tente pas de regénérer ni de charger un preset

        # 3) Sinon, génération classique depuis un preset (avec fallback)
        preset = kwargs.get("preset", "Tropical")
        seed_override = kwargs.get("seed", None)
        try:
            self.params = load_world_params_from_preset(preset)
        except KeyError as ke:
            print(f"[Phase1] {ke} → tentative de fallback de preset…")
            # Petits fallbacks possibles (au cas où ton JSON n'aurait pas 'Tropical')
            for candidate in ("Temperate", "Default", "default", "Tempéré", "Neutre"):
                try:
                    self.params = load_world_params_from_preset(candidate)
                    print(f"[Phase1] Fallback preset = {candidate}")
                    break
                except Exception:
                    pass
            if self.params is None:
                raise  # rien trouvé, on re-propage l'erreur

        self.world = self.gen.generate_island(self.params, rng_seed=seed_override)
        self.view.set_world(self.world)

        try:
            sx, sy = self.world.spawn
        except Exception:
            sx, sy = 0, 0
        if not self.joueur:
            from Game.species.species import Espece
            self.joueur = Espece("Hominidé", x=float(sx), y=float(sy), assets=self.assets)
            self.entities = [self.joueur]
            self._ensure_move_runtime(self.joueur)
            for e in self.entities:
                self._ensure_move_runtime(e)


    def leave(self): ...

    # ---------- INPUT ----------
    def handle_input(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif e.key == pygame.K_i:
                    self.show_info = not self.show_info
                elif e.key == pygame.K_r:
                    self.world = self.gen.generate_island(self.params, rng_seed=random.getrandbits(63))
                    self.view.set_world(self.world)
                    try:
                        sx, sy = self.world.spawn
                    except Exception:
                        sx, sy = 0, 0
                    if self.joueur:
                        self.joueur.x, self.joueur.y = float(sx), float(sy)
                    self.selected = None

            if not self.paused:
                self.view.handle_event(e)

                # --- CLIC GAUCHE = SÉLECTION ---
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # selection via pile de hit
                    hit = self.view.pick_at(mx, my)
                    if hit:
                        kind, payload = hit
                        if kind == "entity":
                            self.selected = ("entity", payload)
                        elif kind == "prop":
                            self.selected = ("prop", payload)  # (i,j,pid)
                        else:
                            self.selected = ("tile", payload)  # (i,j)
                    else:
                        # fallback: pick tuile (beam)
                        i_j = self._fallback_pick_tile(mx, my)
                        self.selected = ("tile", i_j) if i_j else None

                # --- CLIC DROIT = ORDRE DE DÉPLACEMENT (si une créature est sélectionnée) ---
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    if self.selected and self.selected[0] == "entity":
                        ent = self.selected[1]
                        mx, my = pygame.mouse.get_pos()

                        # On vise une tuile de destination
                        hit = self.view.pick_at(mx, my)
                        target = None
                        if hit:
                            k, p = hit
                            if k == "tile":
                                target = p  # (i,j)
                            elif k == "prop":
                                target = (p[0], p[1])
                            elif k == "entity":
                                target = (int(p.x), int(p.y))
                        if not target:
                            target = self._fallback_pick_tile(mx, my)
                        if not target:
                            continue

                        # Pathfinding A*: props/eau bloquent
                        path = self._astar_path((int(ent.x), int(ent.y)), target)
                        if path:
                            # on ignore la première case si c’est la position actuelle
                            if path and path[0] == (int(ent.x), int(ent.y)):
                                path = path[1:]
                            ent.move_path = path
                            ent._move_from = (float(ent.x), float(ent.y))
                            ent._move_to = path[0] if path else None
                            ent._move_t = 0.0

    # ---------- UPDATE ----------
    def update(self, dt: float):
        if self.paused:
            return
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

        for e in self.entities:
            self._ensure_move_runtime(e)
            self._update_entity_movement(e, dt)
        if self.save_message_timer > 0:
            self.save_message_timer -= dt
            if self.save_message_timer <= 0:
                self.save_message = ""


    # ---------- RENDER ----------
    def render(self, screen: pygame.Surface):
        screen.fill((10, 12, 18))
        self.view.begin_hitframe()  # reset pile picking

        # Rendu carte (tu push déjà tuiles/props dans la pile via iso_render)
        self.view.render(screen)

        # Rendu entités + ajout dans la pile (hit approximatif sur la tuile)
        dx, dy, wall_h = self.view._proj_consts()
        sorted_entities = sorted(self.entities,
                                 key=lambda ent: self.view._world_to_screen(ent.x, ent.y, 0, dx, dy, wall_h)[1])
        for ent in sorted_entities:
            try:
                ent.draw(screen, self.view, self.world)
            except Exception as ex:
                print(f"[Phase1] Render entité: {ex}")
            # hitbox “losange” au niveau de la tuile de l'entité
            i, j = int(ent.x), int(ent.y)
            poly = self.view.tile_surface_poly(i, j)
            if poly:
                rect = pygame.Rect(min(p[0] for p in poly), min(p[1] for p in poly),
                                   max(p[0] for p in poly) - min(p[0] for p in poly) + 1,
                                   max(p[1] for p in poly) - min(p[1] for p in poly) + 1)
                self.view.push_hit("entity", ent, rect, None)  # rect suffit pour cliquer la créature

        # Marqueur de sélection (tuile/prop/entité)
        self._draw_selection_marker(screen)

        if self.show_info:
            self._draw_info_panel(screen)
        if self.save_message:
            hud_font = pygame.font.SysFont("consolas", 18)
            txt = hud_font.render(self.save_message, True, (240, 255, 240))
            pad, bg = 10, (0, 0, 0, 170)
            surf = pygame.Surface((txt.get_width() + 2*pad, txt.get_height() + 2*pad), pygame.SRCALPHA)
            surf.fill(bg)
            surf.blit(txt, (pad, pad))
            screen.blit(surf, (self.screen.get_width() - surf.get_width() - 16,
                            self.screen.get_height() - surf.get_height() - 16))


    # ---------- SELECTION MARKER ----------
    def _draw_selection_marker(self, screen: pygame.Surface):
        if not self.selected:
            return
        color = (20, 240, 220)
        thick = 2

        kind, payload = self.selected
        if kind == "tile":
            i, j = payload
            poly = self.view.tile_surface_poly(i, j)
            if poly:
                pygame.draw.polygon(screen, color, poly, width=thick)

        elif kind == "prop":
            i, j, pid = payload
            rect = self.view.prop_draw_rect(i, j, pid)
            if rect:
                pygame.draw.rect(screen, color, rect, width=thick)

        elif kind == "entity":
            ent = payload
            # on encadre la tuile sous l’entité (lisible en iso)
            poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
            if poly:
                pygame.draw.polygon(screen, color, poly, width=thick)

    # ---------- FALLBACK PICK (ancien beam) ----------
    def _fallback_pick_tile(self, mx: int, my: int) -> Optional[tuple[int,int]]:
        dx, dy, _ = self.view._proj_consts()
        base = int(self.view.click_lift_factor * dy) if hasattr(self.view, "click_lift_factor") else int(0.7 * dy)
        for off in (base, int(base*0.66), int(base*0.33), 0):
            t = self.view.pick_tile_at(mx, my - off)
            if t:
                return t
        return None

    # ---------- PATHFINDING & COLLISIONS ----------
    def _is_walkable(self, i: int, j: int) -> bool:
        w = self.world
        if not w: return False
        if i < 0 or j < 0 or i >= w.width or j >= w.height:
            return False
        # props bloquent
        try:
            pid = w.overlay[j][i]
            if pid:  # tout prop considéré solide
                return False
        except Exception:
            pass
        # eau bloque
        # cas 1: carte eau dédiée
        if hasattr(w, "is_water") and w.is_water:
            try:
                if w.is_water[j][i]:
                    return False
            except Exception:
                pass
        # cas 2: heuristique sur le nom de sol
        try:
            gid = w.ground_id[j][i]
        except Exception:
            gid = None
        name = get_ground_sprite_name(gid) if gid is not None else None
        if name:
            lname = name.lower()
            if "water" in lname or "ocean" in lname or "sea" in lname or "lake" in lname:
                return False
        return True

    def _astar_path(self, start: tuple[int,int], goal: tuple[int,int]) -> list[tuple[int,int]]:
        if not self._is_walkable(*goal):
            return []
        sx, sy = start; gx, gy = goal
        if (sx, sy) == (gx, gy): return []

        def h(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])  # Manhattan
        openh = []
        heapq.heappush(openh, (0 + h(start, goal), 0, start))
        came = {start: None}
        gscore = {start: 0}

        neigh = ((1,0),(-1,0),(0,1),(0,-1))  # 4-connexe (iso = grille)
        while openh:
            _, gc, cur = heapq.heappop(openh)
            if cur == goal:
                # reconstitue
                path = []
                while cur and cur in came:
                    path.append(cur); cur = came[cur]
                path.reverse()
                return path
            for dx, dy in neigh:
                nx, ny = cur[0]+dx, cur[1]+dy
                if not self._is_walkable(nx, ny): continue
                ng = gc + 1
                if ng < gscore.get((nx, ny), 1e9):
                    gscore[(nx, ny)] = ng
                    came[(nx, ny)] = cur
                    heapq.heappush(openh, (ng + h((nx,ny), goal), ng, (nx,ny)))
        return []

    def _update_entity_movement(self, ent, dt: float):
        if not ent.move_path:
            return
        # init segment
        if ent._move_to is None:
            if not ent.move_path: return
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = ent.move_path[0]
            ent._move_t = 0.0

        # si la prochaine tuile devient non walkable, stop
        nx, ny = ent._move_to
        if not self._is_walkable(nx, ny):
            ent.move_path = []
            ent._move_to = None
            return

        # avance
        speed = max(0.2, float(getattr(ent, "move_speed", 3.5)))  # tiles/s
        ent._move_t += dt * speed
        if ent._move_t >= 1.0:
            # arrive sur la tuile suivante
            ent.x, ent.y = float(nx), float(ny)
            ent.move_path.pop(0)
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_t = 0.0
            ent._move_to = ent.move_path[0] if ent.move_path else None
        else:
            # interpole
            fx, fy = ent._move_from
            tx, ty = ent._move_to
            ent.x = fx + (tx - fx) * ent._move_t
            ent.y = fy + (ty - fy) * ent._move_t

    # ---------- HUD ----------
    def _draw_info_panel(self, screen):
        lines = [
            f"Phase1 — {self.params.world_name if self.params else '...'}",
            f"Size: {self.world.width}x{self.world.height}" if self.world else "",
            f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
            "Controls: Clic gauche = sélectionner | Clic droit = déplacer la créature sélectionnée | Molette/drag = caméra | R = regénérer | I = HUD",
        ]
        x, y = 10, 10
        for txt in lines:
            if not txt: continue
            surf = self.font.render(txt, True, (220, 230, 240))
            screen.blit(surf, (x, y)); y += 18
