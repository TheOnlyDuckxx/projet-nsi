# --- imports en haut du fichier ---
import pygame
import random
import heapq
import json
from typing import Optional
from Game.ui.iso_render import IsoMapView
from world.world_gen import load_world_params_from_preset, WorldGenerator
from Game.world.tiles import get_ground_sprite_name
from Game.species.species import Espece
from Game.save.save import SaveManager
from Game.core.utils import resource_path
from Game.ui.hud.bottom_hud import BottomHUD
from Game.ui.hud.game_hud import draw_inspection_panel, draw_work_bar
from Game.ui.hud.left_hud import LeftHUD
from Game.ui.hud.notification import add_notification
from Game.world.fog_of_war import FogOfWar
from Game.gameplay.craft import Craft
from Game.world.day_night import DayNightCycle
from Game.gameplay.event import EventManager
from Game.ui.hud.draggable_window import DraggableWindow

class Phase1:
    def __init__(self, app):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.paused = False

        self.view = IsoMapView(self.assets, self.screen.get_size())
        self.gen = WorldGenerator(tiles_levels=6,island_margin_frac=0.10)
        self.params = None
        self.world = None
        self.fog=None
        
        # Système jour/nuit
        # Cycle de 10 minutes réelles (600 secondes)
        self.day_night = DayNightCycle(cycle_duration=600)
        self.day_night.set_time(6, 0)  # Commence à 6h du matin
        self.day_night.set_speed(3.0)   # Vitesse normale
        self.event_manager = EventManager()
        
        # entités
        self.espece = None
        self.joueur: Optional[Espece] = None
        self.entities: list = []

        # UI/HUD
        self.bottom_hud: BottomHUD | None = None
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 12)
        self.menu_button_rect = None
        self.ui_menu_open = False
        self.right_hud = LeftHUD(self)


        # Transparence des props (activée via touche H)
        self.props_transparency_active = False

        # Sélection actuelle: ("tile",(i,j)) | ("prop",(i,j,pid)) | ("entity",ent)
        self.selected: Optional[tuple] = None
        self.selected_entities: list = []
        self.save_message = ""
        self.save_message_timer = 0.0
        self.craft_system = Craft()
        self.selected_craft = None
        self.construction_sites: dict[tuple[int, int], dict] = {}
        self.warehouse: dict[str, int] = {}
        self.info_windows: list[DraggableWindow] = []
        self.construction_assign_radius = 12.0
        self.inspect_cursor_path = resource_path("Game/assets/vfx/9.png")
        self.default_cursor_path = resource_path("Game/assets/vfx/1.png")
        self.inspect_mode_active = False

        # Sélection multi via clic + glisser
        self._drag_select_start: Optional[tuple[int, int]] = None
        self._drag_select_rect: Optional[pygame.Rect] = None
        self._dragging_selection = False
        self._drag_threshold = 6
        self._ui_click_blocked = False

    def _attach_phase_to_entities(self):
        if getattr(self, "espece", None) and hasattr(self.espece, "reproduction_system"):
            try:
                self.espece.reproduction_system.bind_phase(self)
            except Exception:
                pass
        for ent in self.entities:
            try:
                ent.phase = self
            except Exception:
                pass
        # Nettoie les fenêtres d'info éventuelles (pour éviter les références périmées)
        self.info_windows = []
        # Réinitialise le curseur
        self._set_cursor(self.default_cursor_path)

    # ---- Sauvegarde / Chargement (wrappers pour le menu) ----
    @staticmethod
    def save_exists() -> bool:
        return SaveManager().save_exists()

    def save(self) -> bool:
        return SaveManager().save_phase1(self)

    def load(self) -> bool:
        return SaveManager().load_phase1(self)

    def _ensure_move_runtime(self, ent):
        """S'assure que l'entité a tout le runtime nécessaire au déplacement."""
        if not hasattr(ent, "move_path"):   ent.move_path = []          # liste de (i,j)
        if not hasattr(ent, "move_speed"):  ent.move_speed = 3.5        # tuiles/s
        if not hasattr(ent, "_move_from"):  ent._move_from = None       # (x,y) float
        if not hasattr(ent, "_move_to"):    ent._move_to = None         # (i,j) int
        if not hasattr(ent, "_move_t"):     ent._move_t = 0.0           # 0..1
        # ---------- Mutations de base de l'espèce ----------

    def _load_mutations_data(self):
        """
        Charge et met en cache le JSON des mutations.
        """
        if hasattr(self, "_mutations_cache"):
            return self._mutations_cache

        try:
            with open(resource_path("Game/data/mutations.json"), "r", encoding="utf-8") as f:
                self._mutations_cache = json.load(f)
        except Exception as e:
            print(f"[Phase1] Impossible de charger mutations.json : {e}")
            self._mutations_cache = {}

        return self._mutations_cache

    def _get_selected_base_mutations(self) -> list[str]:
        """
        Récupère la liste des IDs de mutations de base sélectionnées
        dans l'App ou les settings.
        """
        app = self.app
        # priorité : valeur en mémoire (menu espèce)
        if hasattr(app, "selected_base_mutations") and app.selected_base_mutations:
            return list(app.selected_base_mutations)

        # fallback : config (si tu veux garder un défaut global)
        try:
            return list(app.settings.get("species.base_mutations", []) or [])
        except Exception:
            return []

    def _apply_base_mutations_to_species(self):
        """
        Applique les effets des mutations de base sur les stats de base
        de l'espèce (base_physique, base_sens, etc.).
        À appeler après la création de self.espece, avant create_individu().
        """
        ids = self._get_selected_base_mutations()
        if not ids or not self.espece:
            return

        data_all = self._load_mutations_data()

        # mapping des catégories JSON → attributs de l'espèce
        cat_map = {
            "physique": "base_physique",
            "sens": "base_sens",
            "mental": "base_mental",
            "social": "base_social",
            "environnement": "base_environnement",
            "genetique": "genetique",
        }

        for mut_id in ids:
            m = data_all.get(mut_id)
            if not m:
                print(f"[Phase1] Mutation de base inconnue : {mut_id}")
                continue

            effets = m.get("effets", {})
            for cat, d_stats in effets.items():
                if cat == "combat":
                    # géré plus tard sur les individus
                    continue

                attr = cat_map.get(cat)
                if not attr:
                    print(f"[Phase1] Catégorie '{cat}' non gérée pour mutation '{mut_id}'")
                    continue

                cible = getattr(self.espece, attr, None)
                if not isinstance(cible, dict):
                    print(f"[Phase1] Attribut '{attr}' manquant sur Espece (mutation '{mut_id}')")
                    continue

                for stat, delta in d_stats.items():
                    if stat not in cible:
                        print(f"[Phase1] Stat '{stat}' absente dans '{attr}' (mutation '{mut_id}')")
                        continue
                    try:
                        cible[stat] += delta
                    except Exception:
                        pass

        # On garde la liste sur l'espèce (utile plus tard)
        self.espece.base_mutations = ids

    def _apply_base_mutations_to_individus(self):
        """
        Applique sur les individus déjà créés les effets qui concernent
        par exemple la catégorie 'combat' (attaque à distance, etc.).
        À appeler après la création de self.joueur / self.joueur2.
        """
        ids = getattr(self.espece, "base_mutations", None)
        if not ids:
            return

        data_all = self._load_mutations_data()

        individus = [getattr(self, "joueur", None), getattr(self, "joueur2", None)]
        individus = [ind for ind in individus if ind is not None]

        for mut_id in ids:
            m = data_all.get(mut_id)
            if not m:
                continue

            effets = m.get("effets", {})
            combat_stats = effets.get("combat", {})
            if not combat_stats:
                continue

            for ind in individus:
                if not hasattr(ind, "combat"):
                    continue
                for stat, delta in combat_stats.items():
                    if stat not in ind.combat:
                        print(f"[Phase1] Stat de combat '{stat}' absente sur Individu (mutation '{mut_id}')")
                        continue
                    try:
                        ind.combat[stat] += delta
                    except Exception:
                        pass

    # ---------- WORLD LIFECYCLE ----------
    def enter(self, **kwargs):
        # 1) Si on demande explicitement de charger une sauvegarde et qu'elle existe
        if kwargs.get("load_save", False) and self.save_exists():
            if self.load():
                if self.espece and not self.bottom_hud:
                    self.bottom_hud = BottomHUD(self, self.espece,self.day_night)
                self._set_cursor(self.default_cursor_path)
                return

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
                self.espece = Espece("Hominidé")
                self.joueur = self.espece.create_individu(
                    x=float(sx),
                    y=float(sy),
                    assets=self.assets,
                )

                self.joueur2 = self.espece.create_individu(
                    x=float(sx+1),
                    y=float(sy+1),
                    assets=self.assets,
                )
                self.entities = [self.joueur,self.joueur2]
                self._attach_phase_to_entities()
            if self.bottom_hud is None:
                self.bottom_hud = BottomHUD(self, self.espece,self.day_night)
            else:
                self.bottom_hud.species = self.espece
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
        if self.fog is None:
            self.fog = FogOfWar(self.world.width, self.world.height)
        self.view.fog = self.fog

        try:
            sx, sy = self.world.spawn
        except Exception:
            sx, sy = 0, 0
        if not self.joueur:
            from Game.species.species import Espece
            self.espece = Espece("Hominidé")
            self._apply_base_mutations_to_species()
            self.joueur = self.espece.create_individu(
                x=float(sx),
                y=float(sy),
                assets=self.assets,
            )
            self.joueur2 = self.espece.create_individu(
                    x=float(sx+1),
                    y=float(sy+1),
                    assets=self.assets,
                )
            self._apply_base_mutations_to_individus()
            self.entities = [self.joueur,self.joueur2]
            self._attach_phase_to_entities()
            self._ensure_move_runtime(self.joueur)
            self._ensure_move_runtime(self.joueur2)
            for e in self.entities:
                self._ensure_move_runtime(e)
        if self.bottom_hud is None:
            self.bottom_hud = BottomHUD(self, self.espece,self.day_night)
        else:
            self.bottom_hud.species = self.espece
        self._set_cursor(self.default_cursor_path)

    # ---------- INPUT ----------
    def handle_input(self, events):
        if self.espece and self.espece.lvl_up.active:
            for e in events:
                self.espece.lvl_up.handle_event(e, self.screen)
            return

        if self.bottom_hud is not None:
            self.bottom_hud.handle(events)
        
        if self.right_hud and self.right_hud.handle(events):
            return

        for e in events:
            # Fenêtres d'information : priorité de gestion
            consumed = False
            for win in list(self.info_windows):
                if win.closed:
                    self.info_windows.remove(win)
                    continue
                if win.handle_event(e):
                    consumed = True
                    break
            if consumed:
                continue

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif e.key == pygame.K_h:
                    self.props_transparency_active = True
                    self.view.set_props_transparency(True)
                elif e.key == pygame.K_i:
                    self.inspect_mode_active = True
                    self._set_cursor(self.inspect_cursor_path)
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

            elif e.type == pygame.KEYUP and e.key == pygame.K_h:
                self.props_transparency_active = False
                self.view.set_props_transparency(False)
            elif e.type == pygame.KEYUP and e.key == pygame.K_i:
                self.inspect_mode_active = False
                self._set_cursor(self.default_cursor_path)

            if not self.paused:
                self.view.handle_event(e)

                # --- CLIC GAUCHE ---
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    keys_state = pygame.key.get_pressed()

                    # 1) Mode "placement de craft"
                    if self.selected_craft is not None:
                        tile = None
                        hit = self.view.pick_at(mx, my)
                        if hit:
                            kind, payload = hit
                            if kind == "tile":
                                tile = payload              # (i, j)
                            elif kind == "prop":
                                i, j, _pid = payload
                                tile = (i, j)

                        if tile is None:
                            tile = self._fallback_pick_tile(mx, my)

                        if tile is not None and self.joueur and self.world:
                            if not self._tile_is_visible(tile):
                                add_notification("Tuile hors du champ de vision.")
                                return
                            result = self.craft_system.craft_item(
                                craft_id=self.selected_craft,
                                builder=self.joueur,
                                world=self.world,
                                tile=tile,
                                notify=add_notification,
                                storage=self.warehouse,
                            )
                            if result:
                                self._register_construction_site(result)
                                self.selected_craft = None  # on sort du mode placement
                        self._reset_drag_selection()
                        return  # on ne fait pas la logique de sélection classique

                    if self._ui_captures_click((mx, my)):
                        self._ui_click_blocked = True
                        self._reset_drag_selection()
                        continue

                    if keys_state[pygame.K_i]:
                        hit = self.view.pick_at(mx, my)
                        if hit and hit[0] == "prop":
                            self._describe_craft_prop(hit[1])
                            self._reset_drag_selection()
                            continue

                    self._ui_click_blocked = False
                    self._dragging_selection = True
                    self._drag_select_start = (mx, my)
                    self._drag_select_rect = pygame.Rect(mx, my, 0, 0)

                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    mx, my = e.pos
                    if self._ui_click_blocked:
                        self._ui_click_blocked = False
                        self._reset_drag_selection()
                        continue
                    if self.selected_craft is not None:
                        self._reset_drag_selection()
                        continue
                    if self._dragging_selection and self._drag_select_start:
                        rect = self._drag_select_rect
                        if rect and (rect.width > self._drag_threshold or rect.height > self._drag_threshold):
                            self._select_entities_in_rect(rect)
                        else:
                            self._handle_single_left_click(mx, my)
                    else:
                        self._handle_single_left_click(mx, my)
                    self._reset_drag_selection()

                elif e.type == pygame.MOUSEMOTION and self._dragging_selection:
                    self._update_drag_rect(e.pos)

                # --- CLIC DROIT = ORDRE DE DÉPLACEMENT (si une créature est sélectionnée) ---
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    self.selected_craft = None
                    entities = self._get_order_entities()
                    if not entities:
                        continue
                    mx, my = pygame.mouse.get_pos()
                    hit = self.view.pick_at(mx, my)
                    harvest_mode = pygame.key.get_pressed()[pygame.K_d]
                    self._issue_order_to_entities(entities, hit, harvest_mode, (mx, my))



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
        if self.espece and self.espece.lvl_up.active:
            return
        if self.paused or self.ui_menu_open:
            # Même en pause on continue les timers d'évènements
            self.event_manager.update(dt, self)
            return

        self.event_manager.update(dt, self)
        #mettre a jour le cycle jour/nuit
        self.day_night.update(dt)
        if self.espece and getattr(self.espece, "reproduction_system", None):
            try:
                self.espece.reproduction_system.update(dt)
            except Exception as e:
                print(f"[Reproduction] update error: {e}")
        
        keys = pygame.key.get_pressed()
        self.view.update(dt, keys)

        def get_radius(ent):
            if getattr(ent, "is_egg", False):
                return 1
            vision = ent.sens.get("vision", 5)
            return max(2, int(1 + vision * 0.7))

        if self.fog:
            light_level = self.day_night.get_light_level()  # Niveau de luminosité actuel
            observers = [e for e in self.entities if not getattr(e, "is_egg", False)]
            self.fog.recompute(observers, get_radius, light_level)
        else:
            self.fog = FogOfWar(self.world.width, self.world.height)
        self.view.fog = self.fog


        for e in self.entities:
            if getattr(e, "is_egg", False):
                continue
            self._ensure_move_runtime(e)
            self._update_entity_movement(e, dt)
            e.faim_timer+=dt
            if e.faim_timer>=5.0:
                e.faim_timer=0
                e.jauges["faim"]-=1
                if e.jauges["faim"]<20:
                    e.comportement.try_eating()
            # → progression de la récolte (barre, timer, loot…)
            if hasattr(e, "comportement"):
                e.comportement.update(dt, self.world)

        self._update_construction_sites()

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
        
        # 1) Rendu carte + entités
        self.view.render(screen, world_entities=self.entities)

        self._draw_construction_bars(screen)
        dx, dy, wall_h = self.view._proj_consts()
        for ent in self.entities:
            draw_work_bar(self, screen, ent)

            renderer = getattr(ent, "renderer", None)
            if renderer is None and hasattr(ent, "espece"):
                renderer = getattr(ent.espece, "renderer", None)

            sprite, rect = None, None
            if renderer and hasattr(renderer, "get_draw_surface_and_rect"):
                try:
                    sprite, rect = renderer.get_draw_surface_and_rect(
                        self.view, self.world, ent.x, ent.y
                    )
                except Exception:
                    sprite, rect = None, None

            if rect is None:
                continue

            mask = self.view._mask_for_surface(sprite) if sprite is not None else None
            self.view.push_hit("entity", ent, rect, mask)

        if self.espece and self.espece.lvl_up.active:
            self.espece.lvl_up.render(screen, self.assets)
            return

        # 2) Appliquer le filtre jour/nuit sur TOUT ce qui est déjà dessiné
        self.apply_day_night_lighting(screen)

        # 2bis) Sélection rectangle (drag)
        self._draw_selection_box(screen)

        # 3) Marqueur de sélection
        self._draw_selection_marker(screen)

        # 4) HUD / pause / notifications
        if self.paused and not self.ui_menu_open:
            self.draw_pause_screen(screen)

        if not self.paused and not self.ui_menu_open:
            draw_inspection_panel(self, screen)

        if not self.paused and not self.ui_menu_open and self.bottom_hud is not None:
            self.bottom_hud.draw(screen)

        # HUD droite : toujours visible (et affiche le menu si ouvert)
        if not self.paused and self.right_hud:
            self.right_hud.draw(screen)

        if self.save_message:
            add_notification(self.save_message)
            self.save_message = None

        # Fenêtres d'information
        if self.info_windows:
            for win in list(self.info_windows):
                if win.closed:
                    self.info_windows.remove(win)
                    continue
                win.draw(screen)


    # ---------- SELECTION HELPERS ----------
    def _entity_screen_rect(self, ent) -> Optional[pygame.Rect]:
        poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
        if not poly:
            return None
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        rect = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return rect

    def _set_selected_entities(self, entities: list) -> None:
        valid = [e for e in entities if e in self.entities]
        self.selected_entities = valid
        if valid:
            self.selected = ("entity", valid[0])
        elif self.selected and self.selected[0] == "entity":
            self.selected = None
        if not self.selected and not self.selected_entities:
            self.info_windows = []

    def _select_entities_in_rect(self, rect: pygame.Rect) -> None:
        selected = []
        for ent in self.entities:
            er = self._entity_screen_rect(ent)
            if not er:
                continue
            if rect.colliderect(er) and rect.collidepoint(er.center):
                selected.append(ent)
        self._set_selected_entities(selected)
        if not selected:
            self.selected = None

    def _reset_drag_selection(self):
        self._dragging_selection = False
        self._drag_select_start = None
        self._drag_select_rect = None

    def _update_drag_rect(self, pos: tuple[int, int]):
        if not self._dragging_selection or not self._drag_select_start:
            return
        sx, sy = self._drag_select_start
        ex, ey = pos
        x = min(sx, ex)
        y = min(sy, ey)
        w = abs(ex - sx)
        h = abs(ey - sy)
        self._drag_select_rect = pygame.Rect(x, y, w, h)

    def _ui_captures_click(self, pos: tuple[int, int]) -> bool:
        if self.bottom_hud:
            if self.bottom_hud.context_menu and self.bottom_hud.context_menu.get("rect"):
                if self.bottom_hud.context_menu["rect"].collidepoint(pos):
                    return True
            if self.bottom_hud.visible and self.bottom_hud.panel_rect.collidepoint(pos):
                return True
        for win in self.info_windows:
            if not win.closed and win.rect.collidepoint(pos):
                return True
        return False

    def _set_cursor(self, image_path: str, hotspot=(0, 0)):
        try:
            surf = pygame.image.load(image_path).convert_alpha()
            cursor = pygame.cursors.Cursor(hotspot, surf)
            pygame.mouse.set_cursor(cursor)
        except Exception as e:
            print("[Cursor] Erreur set_cursor_image:", e, "path=", image_path)

    def _get_order_entities(self) -> list:
        if self.selected_entities:
            return [e for e in self.selected_entities if e in self.entities]
        if self.selected and self.selected[0] == "entity" and self.selected[1] in self.entities:
            return [self.selected[1]]
        return []

    def deposit_to_warehouse(self, inventory: list[dict]) -> int:
        """
        Transfère tout l'inventaire fourni dans l'entrepôt partagé.
        Retourne le nombre d'items transférés.
        """
        if not inventory:
            return 0
        moved = 0
        for stack in list(inventory):
            res_id = stack.get("id") or stack.get("name")
            qty = int(stack.get("quantity", 0))
            if not res_id or qty <= 0:
                continue
            self.warehouse[res_id] = self.warehouse.get(res_id, 0) + qty
            moved += qty
        inventory.clear()
        return moved

    def _craft_def_from_cell(self, cell):
        craft_def = None
        if isinstance(cell, dict):
            cid = cell.get("craft_id")
            if cid and self.craft_system:
                craft_def = self.craft_system.crafts.get(cid, {})
            fallback = {
                "name": cell.get("name") or cell.get("craft_id"),
                "craft_id": cell.get("craft_id"),
                "cost": cell.get("cost", {}),
                "interaction": cell.get("interaction"),
            }
            if craft_def:
                merged = dict(fallback)
                merged.update(craft_def)
                return merged
            return fallback if fallback.get("name") or fallback.get("craft_id") else None
        return None

    def _describe_craft_prop(self, payload):
        if not self.world:
            return
        i, j, pid = payload
        try:
            cell = self.world.overlay[j][i]
        except Exception:
            cell = None
        craft_def = self._craft_def_from_cell(cell)
        name = craft_def.get("name") if craft_def else None
        if not name:
            name = f"Prop {pid}"
        desc = craft_def.get("description") if craft_def else None
        interaction = craft_def.get("interaction") if craft_def else None

        content_lines: list[str] = []
        if desc:
            content_lines.extend(desc.split("\n"))
        else:
            content_lines.append("Aucune description.")

        # Infos spéciales entrepôt
        if isinstance(interaction, dict) and interaction.get("type") == "warehouse":
            if not self.warehouse:
                content_lines.append("Entrepôt : aucun stock.")
            else:
                content_lines.append("Contenu de l'entrepôt :")
                for res, qty in self.warehouse.items():
                    content_lines.append(f"- {res} : {qty}")

        title_surf = self.font.render(name, True, (245, 245, 245))
        body_surfs = [self.small_font.render(line, True, (225, 225, 225)) for line in content_lines]

        mx, my = pygame.mouse.get_pos()
        win = DraggableWindow(title_surf, body_surfs, (mx, my))
        self.info_windows.append(win)

    def _handle_single_left_click(self, mx: int, my: int):
        hit = self.view.pick_at(mx, my)
        if hit:
            kind, payload = hit
            if kind == "entity":
                self._set_selected_entities([payload])
            elif kind == "prop":
                self.selected = ("prop", payload)
                self._set_selected_entities([])
            else:
                self.selected = ("tile", payload)
                self._set_selected_entities([])
        else:
            i_j = self._fallback_pick_tile(mx, my)
            self.selected = ("tile", i_j) if i_j else None
            self._set_selected_entities([])
        if not self.selected and not self.selected_entities:
            self.info_windows = []

    def _draw_selection_box(self, screen: pygame.Surface):
        if not self._drag_select_rect or self._drag_select_rect.width <= 0 or self._drag_select_rect.height <= 0:
            return
        rect = self._drag_select_rect
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((80, 180, 120, 60))
        screen.blit(overlay, rect.topleft)
        pygame.draw.rect(screen, (80, 200, 120), rect, 1)

    # ---------- SELECTION MARKER ----------
    def _draw_selection_marker(self, screen: pygame.Surface):
        """
        Affiche un effet visuel autour de l'entité sélectionnée uniquement.
        - Utilise le sprite 'vfx_aura_alpha' centré sur la tuile de l'entité.
        - Ne montre rien pour les tiles / props.
        """
        entities = []
        if self.selected_entities:
            entities = [e for e in self.selected_entities if e in self.entities]
        elif self.selected and self.selected[0] == "entity":
            entities = [self.selected[1]]
        if not entities:
            return

        aura = self.assets.get_image("vfx_aura_alpha")
        if aura is None:
            return

        for ent in entities:
            poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
            if not poly:
                continue

            min_x = min(p[0] for p in poly)
            max_x = max(p[0] for p in poly)
            min_y = min(p[1] for p in poly)
            max_y = max(p[1] for p in poly)

            center_x = (min_x + max_x) // 2
            center_y = (min_y + max_y) // 2

            aura_rect = aura.get_rect(center=(center_x, center_y))
            screen.blit(aura, aura_rect)


    # ---------- FALLBACK PICK (ancien beam) ----------
    def _fallback_pick_tile(self, mx: int, my: int) -> Optional[tuple[int,int]]:
        dx, dy, _ = self.view._proj_consts()
        base = int(self.view.click_lift_factor * dy) if hasattr(self.view, "click_lift_factor") else int(0.7 * dy)
        for off in (base, int(base*0.66), int(base*0.33), 0):
            t = self.view.pick_tile_at(mx, my - off)
            if t:
                return t
        return None

    def _tile_is_visible(self, tile: tuple[int, int]) -> bool:
        if not self.fog:
            return True
        i, j = tile
        try:
            return bool(self.fog.visible[j][i])
        except Exception:
            return True

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

    def _occupied_tiles(self, exclude: list | None = None) -> set[tuple[int, int]]:
        exclude = set(exclude or [])
        occupied = set()
        for ent in self.entities:
            if ent in exclude:
                continue
            occupied.add((int(ent.x), int(ent.y)))
        return occupied

    def _get_construction_cell(self, i: int, j: int):
        try:
            return self.world.overlay[j][i] if self.world else None
        except Exception:
            return None

    def _is_construction_site(self, i: int, j: int) -> bool:
        cell = self._get_construction_cell(i, j)
        return isinstance(cell, dict) and cell.get("state") == "building"

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
        if getattr(ent, "move_path", None) and ent.move_path and ent.ia.get("etat") in ("recolte", "construction", "interaction", "demonte"):
            if hasattr(ent, "comportement"):
                ent.comportement.cancel_work("movement_started")
            else:
                if getattr(ent, "work", None):
                    ent.work = None
                ent.ia["etat"] = "se_deplace"
                ent.ia["objectif"] = None
        if not getattr(ent, "move_path", None) or not ent.move_path:
            if ent.ia["etat"] == "se_deplace_vers_prop":
                action = ent.ia.get("order_action")
                craft_def = self._craft_def_from_order(ent) if action in ("interact", "dismantle") else None
                if hasattr(ent, "comportement"):
                    if action == "interact":
                        ent.comportement.interact_with_craft(ent.ia.get("objectif"), self.world, craft_def)
                    elif action == "dismantle":
                        ent.comportement.dismantle_craft(ent.ia.get("objectif"), self.world, craft_def)
                    else:
                        ent.comportement.recolter_ressource(ent.ia.get("objectif"), self.world)
            elif ent.ia["etat"] == "se_deplace_vers_construction":
                if hasattr(ent, "comportement"):
                    ent.comportement.build_construction(ent.ia.get("objectif"), self.world)
            elif ent.ia["etat"] == "se_deplace":
                ent.ia["etat"] = "idle"
                ent.ia["objectif"] = None
                ent.ia["order_action"] = None
                ent.ia["target_craft_id"] = None

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

    def _find_nearest_walkable(self, target: tuple[int, int], max_radius: int = 8, forbidden: set[tuple[int, int]] | None = None) -> Optional[tuple[int, int]]:
        """Retourne la case libre la plus proche du point cible (si eau/obstacle), en évitant les cases interdites."""
        tx, ty = target
        forbidden = forbidden or set()
        if self._is_walkable(tx, ty) and (tx, ty) not in forbidden:
            return target

        best = None
        best_dist = 9999
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = tx + dx, ty + dy
                    if not self._is_walkable(nx, ny):
                        continue
                    if (nx, ny) in forbidden:
                        continue
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best = (nx, ny)
                        best_dist = d
            if best:
                break
        return best

    def _apply_entity_order(self, ent, target: tuple[int, int], etat: str, objectif, action_mode: str | None, craft_id: str | None):
        if hasattr(ent, "comportement"):
            ent.comportement.cancel_work("player_new_order")
        else:
            if getattr(ent, "work", None):
                ent.work = None
            ent.ia["etat"] = "idle"
            ent.ia["objectif"] = None

        ent.ia["etat"] = etat
        ent.ia["objectif"] = objectif
        ent.ia["order_action"] = action_mode
        ent.ia["target_craft_id"] = craft_id if action_mode in ("interact", "dismantle") else None
        if etat == "se_deplace_vers_construction":
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None

        start_pos = (int(ent.x), int(ent.y))
        raw_path = self._astar_path(start_pos, target)
        if not raw_path:
            if start_pos == target:
                ent.move_path = []
                ent._move_from = (float(ent.x), float(ent.y))
                ent._move_to = None
                ent._move_t = 0.0
                return True
            return False
        if raw_path and raw_path[0] == start_pos:
            raw_path = raw_path[1:]
        waypoints = self._smooth_path(raw_path)
        if waypoints is None:
            waypoints = []
        ent.move_path = waypoints
        ent._move_from = (float(ent.x), float(ent.y))
        ent._move_to = waypoints[0] if waypoints else None
        ent._move_t = 0.0
        return True

    def _issue_order_to_entities(self, entities: list, hit, harvest_mode: bool = False, click_pos: tuple[int, int] | None = None):
        entities = [e for e in entities if e in self.entities]
        if not entities:
            return

        base_target = None
        objectif = None
        etat = "se_deplace"
        action_mode = None
        craft_id = None

        if hit:
            kind, payload = hit
            if kind == "tile":
                base_target = payload
                objectif = None
                etat = "se_deplace"
            elif kind == "entity":
                base_target = (int(payload.x), int(payload.y))
                objectif = None
                etat = "se_deplace"
            elif kind == "prop":
                i, j, pid = payload
                cell = self._get_construction_cell(i, j)
                craft_id = cell.get("craft_id") if isinstance(cell, dict) else None
                if self._is_construction_site(i, j):
                    etat = "se_deplace_vers_construction"
                    objectif = ("construction", (i, j))
                    base_target = (i, j)
                    action_mode = None
                else:
                    etat = "se_deplace_vers_prop"
                    objectif = ("prop", (i, j, pid))
                    base_target = (i, j)
                    if isinstance(cell, dict) and craft_id:
                        action_mode = "dismantle" if harvest_mode else "interact"
                    else:
                        action_mode = None
        if base_target is None:
            cx, cy = click_pos if click_pos else pygame.mouse.get_pos()
            base_target = self._fallback_pick_tile(cx, cy)
            if base_target:
                etat = "se_deplace"
                objectif = None

        if base_target is None:
            return

        reserved = self._occupied_tiles(exclude=entities)
        dismantle_assigned = False
        for ent in entities:
            if action_mode == "dismantle" and dismantle_assigned:
                break
            if objectif and objectif[0] == "prop" and self._same_prop_target(ent, ("prop", objectif[1])):
                continue
            desired = base_target
            forbidden = set(reserved)
            if not self._is_walkable(*desired) or desired in forbidden:
                desired = self._find_nearest_walkable(desired, forbidden=forbidden)
            if not desired:
                continue
            reserved.add(desired)
            ok = self._apply_entity_order(ent, desired, etat, objectif, action_mode, craft_id)
            if ok and action_mode == "dismantle":
                dismantle_assigned = True
    
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

    def _craft_def_from_order(self, ent):
        craft_id = ent.ia.get("target_craft_id")
        objectif = ent.ia.get("objectif")
        cell = None
        if objectif and objectif[0] == "prop":
            i, j, _pid = objectif[1]
            cell = self._get_construction_cell(i, j)
        craft_def = None
        if craft_id and self.craft_system:
            craft_def = self.craft_system.crafts.get(craft_id)
        if isinstance(cell, dict):
            fallback = {
                "cost": cell.get("cost", {}),
                "name": cell.get("name") or cell.get("craft_id") or "Construction",
                "pid": cell.get("pid"),
                "craft_id": cell.get("craft_id"),
                "interaction": cell.get("interaction"),
            }
            if craft_def:
                merged = dict(fallback)
                merged.update(craft_def)
                return merged
            return fallback
        return craft_def

    def _register_construction_site(self, craft_result):
        tile = craft_result.get("tile")
        site = craft_result.get("site")
        if not tile or not site:
            return
        key = (int(tile[0]), int(tile[1]))
        self.construction_sites[key] = {
            "name": site.get("name", site.get("craft_id", "Construction")),
            "work_required": site.get("work_required", 1.0),
            "work_done": site.get("work_done", 0.0),
        }
        self._assign_idle_workers_to_construction(key)

    def _assign_idle_workers_to_construction(self, tile: tuple[int, int], max_workers: int = 3):
        assigned = 0
        reserved = self._occupied_tiles()
        for ent in self.entities:
            if assigned >= max_workers:
                break
            if ent.ia.get("etat") != "idle" or getattr(ent, "work", None):
                continue
            if not self._is_construction_site(*tile):
                break
            # Filtre de distance pour éviter d'envoyer les entités trop loin
            dx = int(ent.x) - tile[0]
            dy = int(ent.y) - tile[1]
            dist2 = dx * dx + dy * dy
            if dist2 > (self.construction_assign_radius ** 2):
                continue
            self._ensure_move_runtime(ent)
            target = self._find_nearest_walkable(tile, forbidden=reserved)
            if not target:
                continue
            reserved.add(target)
            raw_path = self._astar_path((int(ent.x), int(ent.y)), target)
            if not raw_path:
                if (int(ent.x), int(ent.y)) == target:
                    ent.move_path = []
                    ent._move_from = (float(ent.x), float(ent.y))
                    ent._move_to = None
                    ent._move_t = 0.0
                    ent.ia["etat"] = "se_deplace_vers_construction"
                    ent.ia["objectif"] = ("construction", tile)
                    ent.ia["order_action"] = None
                    ent.ia["target_craft_id"] = None
                    assigned += 1
                continue
            if raw_path and raw_path[0] == (int(ent.x), int(ent.y)):
                raw_path = raw_path[1:]
            waypoints = self._smooth_path(raw_path)
            ent.move_path = waypoints
            ent._move_from = (float(ent.x), float(ent.y))
            ent._move_to = waypoints[0] if waypoints else None
            ent._move_t = 0.0
            ent.ia["etat"] = "se_deplace_vers_construction"
            ent.ia["objectif"] = ("construction", tile)
            ent.ia["order_action"] = None
            ent.ia["target_craft_id"] = None
            assigned += 1

    def _update_construction_sites(self):
        if not self.construction_sites:
            return
        finished: list[tuple[int, int]] = []
        for key, meta in list(self.construction_sites.items()):
            i, j = key
            cell = self._get_construction_cell(i, j)
            if isinstance(cell, dict) and cell.get("state") == "building":
                meta["work_done"] = cell.get("work_done", meta.get("work_done", 0.0))
                meta["work_required"] = cell.get("work_required", meta.get("work_required", 1.0))
                continue
            # Construction absente ou terminée
            finished.append(key)
        for key in finished:
            meta = self.construction_sites.pop(key, {})
            cell = self._get_construction_cell(*key)
            if meta and cell not in (None, 0, False):
                add_notification(f"{meta.get('name', 'Construction')} terminée.")

    def _draw_construction_bars(self, screen):
        if not self.construction_sites:
            return
        for (i, j), meta in self.construction_sites.items():
            cell = self._get_construction_cell(i, j)
            if not (isinstance(cell, dict) and cell.get("state") == "building"):
                continue
            required = max(1e-3, float(cell.get("work_required", meta.get("work_required", 1.0))))
            progress = max(0.0, min(1.0, float(cell.get("work_done", meta.get("work_done", 0.0))) / required))
            poly = self.view.tile_surface_poly(int(i), int(j))
            if not poly:
                continue
            cx = sum(p[0] for p in poly) / len(poly)
            top = min(p[1] for p in poly) - 14
            bar_w, bar_h = 54, 7
            bg = pygame.Rect(int(cx - bar_w/2), int(top - bar_h), bar_w, bar_h)
            fg = bg.inflate(-2, -2)
            fg.width = int(fg.width * progress)
            s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 170))
            screen.blit(s, (bg.x, bg.y))
            pygame.draw.rect(screen, (200, 210, 120), fg, border_radius=2)

    def apply_day_night_lighting(self, surface: pygame.Surface):
        light = self.day_night.get_light_level(min_light=0.45)

        # 1) Brightness (gris) : 255 = normal, <255 = sombre
        m = int(255 * light)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((m, m, m, 255))
        surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # 2) Tint (couleur) léger par-dessus (optionnel mais joli)
        r, g, b = self.day_night.get_ambient_color()
        tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # alpha faible sinon ça “salit” l’image
        tint.fill((r, g, b, 35))
        surface.blit(tint, (0, 0))
