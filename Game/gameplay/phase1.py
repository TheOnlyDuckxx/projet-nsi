# --- imports en haut du fichier ---
import pygame, random, heapq
from typing import List, Tuple, Optional
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator
from Game.world.tiles import get_ground_sprite_name
from Game.species.species import Espece
from Game.save.save import SaveManager
from Game.ui.hud import add_notification



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
        self.menu_button_rect = None

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
                        hit = self.view.pick_at(mx, my)

                        if hit and hit[0] == "prop" and self._same_prop_target(ent, hit):
                            return  # on laisse la progression continuer

                        # Sinon, on peut annuler le job précédent et poser le nouvel ordre
                        if hasattr(ent, "comportement"):
                            ent.comportement.cancel_work("player_new_order")
                        else:
                            if getattr(ent, "work", None):
                                ent.work = None
                            ent.ia["etat"] = "idle"
                            ent.ia["objectif"] = None
                        # --- FIN NEW ---

                        # On vise une tuile de destination
                        hit = self.view.pick_at(mx, my)
                        target = None
                        if hit:
                            k, p = hit
                            if k == "tile":
                                target = p  # (i,j)
                                ent.ia["etat"] = "se_deplace"       # NEW (cohérent)
                                ent.ia["objectif"] = None           # NEW
                            elif k == "prop":
                                target = (p[0], p[1])
                                ent.ia["etat"] = "se_deplace_vers_prop"
                                ent.ia["objectif"] = hit
                            elif k == "entity":
                                target = (int(p.x), int(p.y))
                                ent.ia["etat"] = "se_deplace"       # NEW
                                ent.ia["objectif"] = None           

                        if not target:
                            target = self._fallback_pick_tile(mx, my)
                        if not target:
                            continue

                        if not self._is_walkable(*target):
                            target = self._find_nearest_walkable(target)
                            

                        if not target:
                            continue

                        raw_path = self._astar_path((int(ent.x), int(ent.y)), target)
                        if raw_path:
                            # Ignore la première case si c'est la position actuelle
                            if raw_path and raw_path[0] == (int(ent.x), int(ent.y)):
                                raw_path = raw_path[1:]
                            # Lissage + waypoints flottants
                            waypoints = self._smooth_path(raw_path)
                            # Stocke des points (x,y) flottants dans move_path
                            ent.move_path = waypoints
                            ent._move_from = (float(ent.x), float(ent.y))
                            ent._move_to = waypoints[0] if waypoints else None
                            ent._move_t = 0.0



            if self.paused and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.menu_button_rect and self.menu_button_rect.collidepoint(e.pos):
                    self.paused = False  # pour éviter que le rendu de pause bloque tout

                    # --- Sauvegarde avant retour au menu ---
                    try:
                        ok = self.save()
                        if ok:
                            self.save_message = "Sauvegarde effectuée !"
                        else:
                            print("[Phase1] Sauvegarde échouée.")
                            self.save_message = "Erreur de sauvegarde."
                    except Exception as ex:
                        print(f"[Phase1] Erreur lors de la sauvegarde: {ex}")
                        self.save_message = "Erreur de sauvegarde."

                    self.save_message_timer = 2.5
                    pygame.display.flip()  # force un dernier rendu avant de changer d'état
                    pygame.time.wait(300)

                    # --- Quitte proprement vers le menu principal ---
                    self.app.change_state("MENU")
                    return

    # ---------- UPDATE ----------
    def update(self, dt: float):
        if self.paused:
            return
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)
    
        for e in self.entities:
            self._ensure_move_runtime(e)
            self._update_entity_movement(e, dt)
            # → progression de la récolte (barre, timer, loot…)
            if hasattr(e, "comportement"):
                e.comportement.update(dt, self.world)

        if self.save_message_timer > 0:
            self.save_message_timer -= dt
            if self.save_message_timer <= 0:
                self.save_message = ""

    def draw_pause_screen(self, screen):
            """Affiche l'écran de pause avec le bouton de retour au menu"""
            # Overlay semi-transparent
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            # Titre "PAUSE"
            font_title = pygame.font.SysFont(None, 60)
            text = font_title.render("PAUSE", True, (255, 255, 255))
            text_rect = text.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 - 100))
            screen.blit(text, text_rect)
            
            # Bouton "Retour au menu"
            button_width = 300
            button_height = 60
            button_x = screen.get_width() / 2 - button_width / 2
            button_y = screen.get_height() / 2 + 40
            
            self.menu_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            
            # Effet hover
            mouse_pos = pygame.mouse.get_pos()
            is_hover = self.menu_button_rect.collidepoint(mouse_pos)
            button_color = (80, 80, 120) if is_hover else (60, 60, 90)
            border_color = (150, 150, 200) if is_hover else (100, 100, 150)
            
            # Dessiner le bouton
            pygame.draw.rect(screen, button_color, self.menu_button_rect, border_radius=10)
            pygame.draw.rect(screen, border_color, self.menu_button_rect, 3, border_radius=10)
            
            # Texte du bouton
            font_button = pygame.font.SysFont(None, 36)
            button_text = font_button.render("Retour au menu principal", True, (255, 255, 255))
            button_text_rect = button_text.get_rect(center=self.menu_button_rect.center)
            screen.blit(button_text, button_text_rect)


    # ---------- RENDER ----------
    def render(self, screen: pygame.Surface):
        screen.fill((10, 12, 18))
        self.view.begin_hitframe()
        
        # Rendu carte
        self.view.render(screen, world_entities=self.entities)
        
        # Rendu entités + ajout dans la pile
        dx, dy, wall_h = self.view._proj_consts()
        for ent in self.entities:
            self._draw_work_bar(screen, ent)
            i, j = int(ent.x), int(ent.y)
            poly = self.view.tile_surface_poly(i, j)
            if poly:
                rect = pygame.Rect(min(p[0] for p in poly), min(p[1] for p in poly),
                                max(p[0] for p in poly) - min(p[0] for p in poly) + 1,
                                max(p[1] for p in poly) - min(p[1] for p in poly) + 1)
                self.view.push_hit("entity", ent, rect, None)
        
        # Marqueur de sélection
        self._draw_selection_marker(screen)
        
        # HUD et panneaux
        if self.paused:
            self.draw_pause_screen(screen)
        if not self.paused and self.show_info:
            self._draw_info_panel(screen)
        
        # NOUVEAU : Panneau d'inspection si une entité est sélectionnée
        if not self.paused:
            self._draw_inspection_panel(screen)
        
        # Message de sauvegarde
        if self.save_message:
            add_notification(self.save_message)
            self.save_message = None


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
        if (sx, sy) == (gx, gy):
            return []

        # Heuristique octile (8-connexe, coût diag = sqrt(2))
        import math
        def h(a, b):
            dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
            return (dx + dy) + (math.sqrt(2) - 2.0) * min(dx, dy)

        openh = []
        heapq.heappush(openh, (h(start, goal), 0.0, start))
        came = {start: None}
        gscore = {start: 0.0}

        neigh = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        import math
        while openh:
            _, gc, cur = heapq.heappop(openh)
            if cur == goal:
                path = []
                while cur in came and cur is not None:
                    path.append(cur); cur = came[cur]
                path.reverse()
                return path

            for dx, dy in neigh:
                nx, ny = cur[0] + dx, cur[1] + dy
                if not self._is_walkable(nx, ny):
                    continue
                step_cost = math.sqrt(2.0) if dx != 0 and dy != 0 else 1.0
                ng = gc + step_cost
                if ng < gscore.get((nx, ny), 1e18):
                    gscore[(nx, ny)] = ng
                    came[(nx, ny)] = cur
                    f = ng + h((nx, ny), goal)
                    heapq.heappush(openh, (f, ng, (nx, ny)))
        return []

    def _los_clear(self, a: tuple[float,float], b: tuple[float,float]) -> bool:
        """
        Line-of-sight grossière : on échantillonne la droite AB et on vérifie
        que chaque sample tombe sur une case walkable. Suffisant pour lisser.
        """
        import math
        ax, ay = a; bx, by = b
        dx, dy = bx - ax, by - ay
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return True
        steps = int(dist * 4) + 1  # sur-échantillonnage léger
        for s in range(steps + 1):
            t = s / max(1, steps)
            x = ax + dx * t
            y = ay + dy * t
            if not self._is_walkable(int(x), int(y)):
                return False
        return True

    def _smooth_path(self, nodes: list[tuple[int,int]]) -> list[tuple[float,float]]:
        """
        String-pulling simple : on garde le point courant, on pousse aussi loin
        que possible en conservant la visibilité, puis on place un waypoint au
        centre de la case retenue.
        """
        if not nodes:
            return []
        # Convertit nodes -> centres flottants
        pts = [(i + 0.5, j + 0.5) for (i, j) in nodes]
        smoothed = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            # recule tant que la LOS échoue
            while j > i + 1 and not self._los_clear(pts[i], pts[j]):
                j -= 1
            smoothed.append(pts[j])
            i = j
        return smoothed


    def _update_entity_movement(self, ent, dt: float):
        # Rien à faire ?
        if getattr(ent, "move_path", None) and ent.move_path and ent.ia.get("etat") == "recolte":
            if hasattr(ent, "comportement"):
                ent.comportement.cancel_work("movement_started")
            else:
                if getattr(ent, "work", None):
                    ent.work = None
                ent.ia["etat"] = "se_deplace"
                ent.ia["objectif"] = None
        if not getattr(ent, "move_path", None) or not ent.move_path:
            if ent.ia["etat"] == "se_deplace_vers_prop":
                # ent.ia["objectif"] est du type ("prop", (i, j, pid))
                if hasattr(ent, "comportement"):
                    ent.comportement.recolter_ressource(ent.ia.get("objectif"), self.world)

        # Init du segment courant
        if ent._move_to is None:
            if not ent.move_path:
                return
            # _move_from est la position actuelle (flottante)
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = ent.move_path[0]  # (x, y) flottant désormais
            ent._move_t = 0.0

        tx, ty = ent._move_to
        fx, fy = ent._move_from

        # Longueur du segment en coordonnées monde (pas "1 tuile" supposée)
        seg_len = max(1e-6, ((tx - fx)**2 + (ty - fy)**2) ** 0.5)

        # Vitesse monde = "tuiles par seconde" mais on l'applique en distance euclidienne
        speed = max(0.2, float(getattr(ent, "move_speed", 3.5)))
        # t progresse à la bonne vitesse quelle que soit l'orientation
        ent._move_t += (dt * speed) / seg_len

        if ent._move_t >= 1.0:
            # On arrive exactement au point visé
            ent.x, ent.y = float(tx), float(ty)
            # Passe au waypoint suivant
            if ent.move_path:
                ent.move_path.pop(0)
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_t = 0.0
            ent._move_to = ent.move_path[0] if ent.move_path else None
        else:
            # Interpolation linéaire
            ent.x = fx + (tx - fx) * ent._move_t
            ent.y = fy + (ty - fy) * ent._move_t


    def _find_nearest_walkable(self, target: tuple[int, int], max_radius: int = 8) -> Optional[tuple[int, int]]:
        """Retourne la case libre la plus proche du point cible (si eau/obstacle)."""
        tx, ty = target
        if self._is_walkable(tx, ty):
            return target

        best = None
        best_dist = 9999
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = tx + dx, ty + dy
                    if not self._is_walkable(nx, ny):
                        continue
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best = (nx, ny)
                        best_dist = d
            if best:
                break
        return best
    
    def _draw_work_bar(self, screen, ent):
        w = getattr(ent, "work", None)
        if not w or ent.ia["etat"] != "recolte":
            return
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return
        # centre au-dessus de la tuile de l’entité
        cx = sum(p[0] for p in poly) / len(poly)
        top = min(p[1] for p in poly) - 10

        bar_w, bar_h = 44, 6
        bg = pygame.Rect(int(cx - bar_w/2), int(top - bar_h), bar_w, bar_h)
        fg = bg.inflate(-2, -2)
        fg.width = int(fg.width * float(w.get("progress", 0.0)))

        # fond
        s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        screen.blit(s, (bg.x, bg.y))
        # barre
        pygame.draw.rect(screen, (80, 200, 120), fg, border_radius=2)
    
    def _same_prop_target(self, ent, hit):
        if not hit or hit[0] != "prop":
            return False
        i, j, pid = hit[1]
        tgt = (int(i), int(j), str(pid))

        # compare à l'objectif courant (si on est en chemin vers le prop)
        cur = ent.ia.get("objectif")
        if cur and cur[0] == "prop":
            ci, cj, cpid = cur[1]
            if (int(ci), int(cj), str(cpid)) == tgt:
                return True

        # compare au job en cours (si déjà en train de récolter)
        w = getattr(ent, "work", None)
        if w and w.get("type") == "harvest":
            if (w["i"], w["j"], str(w["pid"])) == tgt:
                return True
        return False
    



    # ---------- HUD ----------
    # Ajout dans la classe Phase1

    def _draw_info_panel(self, screen):
        """Panneau d'infos générales en haut à gauche"""
        lines = [
            f"Phase1 — {self.params.world_name if self.params else '...'}",
            f"Size: {self.world.width}x{self.world.height}" if self.world else "",
            f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
            "Controls: Clic gauche = sélectionner | Clic droit = déplacer | Molette/drag = caméra | R = regénérer | I = HUD",
        ]
        x, y = 10, 10
        for txt in lines:
            if not txt: continue
            surf = self.font.render(txt, True, (220, 230, 240))
            screen.blit(surf, (x, y)); y += 18

    def _draw_inspection_panel(self, screen):
        """Panneau d'inspection détaillé pour l'entité sélectionnée"""
        if not self.selected or self.selected[0] != "entity":
            return
        
        ent = self.selected[1]
        
        # Configuration du panneau
        panel_width = 320
        panel_height = screen.get_height() - 700
        panel_x = screen.get_width() - panel_width 
        panel_y = 0
        
        # Fond semi-transparent
        panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surf.fill((20, 25, 35, 220))
        
        # Bordure
        pygame.draw.rect(panel_surf, (80, 120, 160), (0, 0, panel_width, panel_height), 2, border_radius=8)
        
        # Police pour le panneau
        title_font = pygame.font.SysFont("consolas", 18, bold=True)
        header_font = pygame.font.SysFont("consolas", 14, bold=True)
        text_font = pygame.font.SysFont("consolas", 12)
        
        y_offset = 10
        
        # === TITRE ===
        title = title_font.render(f"🔍 {ent.nom}", True, (220, 240, 255))
        panel_surf.blit(title, (10, y_offset))
        y_offset += 30
        
        # Ligne de séparation
        pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
        y_offset += 10
        
        # === POSITION ===
        pos_text = text_font.render(f"Position: ({int(ent.x)}, {int(ent.y)})", True, (200, 200, 200))
        panel_surf.blit(pos_text, (10, y_offset))
        y_offset += 20
        
        # === JAUGES VITALES ===
        header = header_font.render("⚡ Jauges", True, (255, 220, 100))
        panel_surf.blit(header, (10, y_offset))
        y_offset += 20
        
        jauges_display = [
            ("Santé", ent.jauges.get("sante", 0), 100, (220, 50, 50)),
            ("Énergie", ent.jauges.get("energie", 0), ent.physique["endurance"], (100, 200, 255)),
            ("Faim", ent.jauges.get("faim", 0), 100, (255, 180, 50)),
            ("Soif", ent.jauges.get("soif", 0), 100, (100, 180, 255)),
        ]
        
        for label, value, max_val, color in jauges_display:
            # Label
            label_surf = text_font.render(f"{label}:", True, (180, 180, 180))
            panel_surf.blit(label_surf, (15, y_offset))
            
            # Barre
            bar_x = 85
            bar_y = y_offset + 2
            bar_width = 200
            bar_height = 12
            
            # Fond de la barre
            pygame.draw.rect(panel_surf, (40, 40, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=3)
            
            # Barre de progression
            fill_width = int((value / max(1, max_val)) * bar_width)
            if fill_width > 0:
                pygame.draw.rect(panel_surf, color, (bar_x, bar_y, fill_width, bar_height), border_radius=3)
            
            # Bordure
            pygame.draw.rect(panel_surf, (100, 100, 120), (bar_x, bar_y, bar_width, bar_height), 1, border_radius=3)
            
            # Valeur texte
            value_text = text_font.render(f"{int(value)}/{int(max_val)}", True, (220, 220, 220))
            panel_surf.blit(value_text, (bar_x + bar_width + 5, y_offset))
            
            y_offset += 18
        
        y_offset += 5
        
        # === STATS PHYSIQUES ===
        header = header_font.render("💪 Physique", True, (255, 180, 100))
        panel_surf.blit(header, (10, y_offset))
        y_offset += 20
        
        stats_physiques = [
            ("Force", ent.physique.get("force", 0)),
            ("Endurance", ent.physique.get("endurance", 0)),
            ("Vitesse", ent.physique.get("vitesse", 0)),
            ("Taille", ent.physique.get("taille", 0)),
        ]
        
        for label, value in stats_physiques:
            stat_text = text_font.render(f"  {label}: {value}", True, (200, 200, 200))
            panel_surf.blit(stat_text, (15, y_offset))
            y_offset += 16
        
        y_offset += 5
        
        # === STATS MENTALES ===
        header = header_font.render("🧠 Mental", True, (150, 200, 255))
        panel_surf.blit(header, (10, y_offset))
        y_offset += 20
        
        stats_mentales = [
            ("Intelligence", ent.mental.get("intelligence", 0)),
            ("Dextérité", ent.mental.get("dexterité", 0)),
            ("Courage", ent.mental.get("courage", 0)),
            ("Sociabilité", ent.mental.get("sociabilite", 0)),
        ]
        
        for label, value in stats_mentales:
            stat_text = text_font.render(f"  {label}: {value}", True, (200, 200, 200))
            panel_surf.blit(stat_text, (15, y_offset))
            y_offset += 16
        
        y_offset += 10
        
        # === INVENTAIRE ===
        pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
        y_offset += 10
        
        header = header_font.render("🎒 Inventaire", True, (255, 220, 100))
        panel_surf.blit(header, (10, y_offset))
        y_offset += 20
        
        # Poids porté
        total_weight = sum(item.get("weight", 0) for item in ent.carrying)
        weight_limit = ent.physique.get("weight_limit", 10)
        weight_text = text_font.render(
            f"Poids: {total_weight:.1f} / {weight_limit:.1f} kg",
            True,
            (255, 200, 100) if total_weight <= weight_limit else (255, 100, 100)
        )
        panel_surf.blit(weight_text, (15, y_offset))
        y_offset += 20
        
        # Liste des items
        if not ent.carrying:
            empty_text = text_font.render("  (vide)", True, (150, 150, 150))
            panel_surf.blit(empty_text, (15, y_offset))
            y_offset += 18
        else:
            # Limiter l'affichage pour éviter le débordement
            max_items_display = 10
            for i, item in enumerate(ent.carrying[:max_items_display]):
                item_name = item.get("name", "Item inconnu")
                item_qty = item.get("quantity", 1)
                item_weight = item.get("weight", 0)
                
                # Icône selon le type
                item_type = item.get("type", "misc")
                icon = {"food": "🍖", "tool": "🔧", "resource": "📦", "weapon": "⚔️"}.get(item_type, "📦")
                
                # Texte de l'item
                if item_qty > 1:
                    item_text = text_font.render(
                        f"  {icon} {item_name} x{item_qty}",
                        True,
                        (220, 220, 220)
                    )
                else:
                    item_text = text_font.render(
                        f"  {icon} {item_name}",
                        True,
                        (220, 220, 220)
                    )
                
                panel_surf.blit(item_text, (15, y_offset))
                
                # Poids à droite
                weight_surf = text_font.render(
                    f"{item_weight:.1f}kg",
                    True,
                    (160, 160, 160)
                )
                panel_surf.blit(weight_surf, (panel_width - 70, y_offset))
                
                y_offset += 16
            
            # Si plus d'items que l'affichage
            if len(ent.carrying) > max_items_display:
                more_text = text_font.render(
                    f"  ... et {len(ent.carrying) - max_items_display} autre(s)",
                    True,
                    (150, 150, 150)
                )
                panel_surf.blit(more_text, (15, y_offset))
                y_offset += 16
        
        # === ÉTAT IA ===
        if y_offset < panel_height - 50:
            y_offset += 10
            pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
            y_offset += 10
            
            header = header_font.render("🤖 État", True, (150, 255, 150))
            panel_surf.blit(header, (10, y_offset))
            y_offset += 20
            
            etat = ent.ia.get("etat", "idle")
            etat_text = text_font.render(f"  Activité: {etat}", True, (200, 200, 200))
            panel_surf.blit(etat_text, (15, y_offset))
        
        # Afficher le panneau sur l'écran
        screen.blit(panel_surf, (panel_x, panel_y))

