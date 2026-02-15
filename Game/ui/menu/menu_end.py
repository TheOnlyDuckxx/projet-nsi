import math
import pygame

from Game.core.config import WIDTH, HEIGHT
from Game.core.utils import Button, ButtonStyle
from Game.ui.menu.menu_main import BaseMenu
from Game.save.progression import PLAYER_POINTS_PER_LEVEL
from Game.save.save import SaveManager


class EndGameScreen(BaseMenu):
    def __init__(self, app):
        super().__init__(app, title="Fin de partie")
        self.summary = {}
        self.reason = ""
        self.xp_gain = 0
        self._anim_remaining = 0.0
        self._xp_rate = 0.0
        self.anim_level = 1
        self.anim_xp = 0.0
        self.anim_xp_to_next = 100
        self.before = None
        self.after = None
        self.levels_gained = 0
        self._anim_done = True
        self._save_path = None

        self.active_tab = "resume"
        self.tab_buttons = {}
        self.stats_tab_enabled = True

        self.title_font = app.assets.get_font("MightySouly", 64)
        self.value_font = app.assets.get_font("MightySouly", 28)
        self.small_font = app.assets.get_font("MightySouly", 22)
        self.graph_font = app.assets.get_font("MightySouly", 18)

        btn_style = ButtonStyle(
            font=app.assets.get_font("MightySouly", 30),
            bg_color=(60, 68, 82),
            hover_bg_color=(78, 88, 106),
            border_color=(130, 150, 170),
            radius=12,
        )
        self.btn_continue = Button(
            "Retour au menu",
            (WIDTH // 2, HEIGHT - 90),
            style=btn_style,
            on_click=lambda _b: self.app.change_state("MENU"),
        )

        self._tab_btn_style = ButtonStyle(
            font=self.graph_font,
            bg_color=(44, 52, 64),
            hover_bg_color=(70, 82, 100),
            border_color=(110, 130, 150),
            radius=10,
            padding_x=14,
            padding_y=8,
        )
        self._init_tab_buttons()

    def _init_tab_buttons(self):
        if self.tab_buttons:
            return
        self.tab_buttons = {
            "resume": Button(
                "Resume",
                (0, 0),
                anchor="topleft",
                style=self._tab_btn_style,
                on_click=lambda _b: self._set_tab("resume"),
            ),
            "stats": Button(
                "Statistiques",
                (0, 0),
                anchor="topleft",
                style=self._tab_btn_style,
                on_click=lambda _b: self._set_tab("stats"),
            ),
        }

    def enter(self, **kwargs):
        self.summary = kwargs.get("summary", {}) or {}
        self.reason = str(kwargs.get("reason", ""))
        self.xp_gain = int(kwargs.get("xp_gain", 0) or 0)
        self._save_path = kwargs.get("save_path")
        self.active_tab = "resume"
        self._init_tab_buttons()

        days_survived = int(self.summary.get("days_survived", 0) or 0)
        self.stats_tab_enabled = days_survived >= 1
        self.tab_buttons["stats"].enabled = self.stats_tab_enabled

        self.before = self.app.progression.get_player_progress()
        result = self.app.progression.add_player_xp(self.xp_gain)
        self.after = result.get("after", self.app.progression.get_player_progress())
        self.levels_gained = int(result.get("levels_gained", 0) or 0)

        self.anim_level = int(self.before.get("level", 1) or 1)
        self.anim_xp = float(self.before.get("xp", 0) or 0)
        self.anim_xp_to_next = int(self.before.get("xp_to_next", 100) or 100)
        self._anim_remaining = float(result.get("gained", 0) or 0)
        self._xp_rate = max(40.0, self._anim_remaining / 2.5) if self._anim_remaining > 0 else 0.0
        self._anim_done = self._anim_remaining <= 0
        if self._save_path:
            SaveManager.delete_save(self._save_path)

    def _make_tab_buttons(self, panel):
        self._init_tab_buttons()
        y = panel.y + 22
        self.tab_buttons["resume"].move_to((panel.x + 20, y), anchor="topleft")
        self.tab_buttons["stats"].move_to((panel.x + 180, y), anchor="topleft")

    def _panel_rect(self):
        panel_w = int(WIDTH * 0.84)
        panel_h = int(HEIGHT * 0.72)
        panel_x = WIDTH // 2 - panel_w // 2
        panel_y = int(HEIGHT * 0.15)
        return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    def _set_tab(self, tab):
        if tab == "stats" and not self.stats_tab_enabled:
            return
        self.active_tab = tab

    def handle_input(self, events):
        self._make_tab_buttons(self._panel_rect())
        self.btn_continue.handle(events)
        for btn in self.tab_buttons.values():
            btn.handle(events)

    def update(self, dt):
        if self._anim_done:
            return
        step = min(self._anim_remaining, self._xp_rate * dt)
        self.anim_xp += step
        self._anim_remaining -= step

        while (
            self.anim_xp >= self.anim_xp_to_next
            and self.after is not None
            and self.anim_level < int(self.after.get("level", self.anim_level))
        ):
            self.anim_xp -= self.anim_xp_to_next
            self.anim_level += 1
            self.anim_xp_to_next = self.app.progression.next_player_xp_to_next(self.anim_xp_to_next)

        if self._anim_remaining <= 0:
            self._anim_done = True
            if self.after is not None:
                self.anim_level = int(self.after.get("level", self.anim_level))
                self.anim_xp = float(self.after.get("xp", self.anim_xp))
                self.anim_xp_to_next = int(self.after.get("xp_to_next", self.anim_xp_to_next))

    def _draw_summary(self, screen, rect):
        lines = []
        species = self.summary.get("species_name", "")
        if species:
            lines.append(f"Espece : {species}")
        if "species_level" in self.summary:
            lines.append(f"Niveau espece : {int(self.summary.get('species_level', 0))}")
        if "days_survived" in self.summary:
            lines.append(f"Jours survecus : {int(self.summary.get('days_survived', 0))}")
        if "deaths" in self.summary:
            lines.append(f"Morts dans l'espece : {int(self.summary.get('deaths', 0))}")
        if "play_time_sec" in self.summary:
            secs = int(self.summary.get("play_time_sec", 0))
            minutes = secs // 60
            lines.append(f"Temps de jeu : {minutes} min")

        if self.reason:
            lines.append(self.reason)

        y = rect.top
        for line in lines:
            surf = self.value_font.render(line, True, (235, 235, 235))
            screen.blit(surf, (rect.left, y))
            y += surf.get_height() + 8

    def _draw_xp_bar(self, screen, rect):
        level_txt = self.value_font.render(f"Niveau joueur : {self.anim_level}", True, (235, 235, 235))
        screen.blit(level_txt, (rect.left, rect.top))

        bar_w = rect.width
        bar_h = 22
        bar_x = rect.left
        bar_y = rect.top + level_txt.get_height() + 10
        bg = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(screen, (25, 28, 36), bg, border_radius=8)
        pygame.draw.rect(screen, (90, 105, 125), bg, 2, border_radius=8)

        ratio = 0.0
        if self.anim_xp_to_next > 0:
            ratio = max(0.0, min(1.0, float(self.anim_xp) / float(self.anim_xp_to_next)))
        fill_w = int((bar_w - 6) * ratio)
        if fill_w > 0:
            fg = pygame.Rect(bar_x + 3, bar_y + 3, fill_w, bar_h - 6)
            pygame.draw.rect(screen, (90, 200, 140), fg, border_radius=6)

        xp_txt = self.small_font.render(
            f"XP : {int(self.anim_xp)}/{int(self.anim_xp_to_next)}  (+{int(self.xp_gain)})",
            True,
            (210, 210, 210),
        )
        screen.blit(xp_txt, (bar_x, bar_y + bar_h + 8))

        if self.levels_gained > 0:
            bonus = self.small_font.render(
                f"Niveaux gagnes : {self.levels_gained} (+{self.levels_gained * PLAYER_POINTS_PER_LEVEL} points)",
                True,
                (120, 210, 160),
            )
            screen.blit(bonus, (bar_x, bar_y + bar_h + 34))

    def _draw_line_graph(self, screen, rect, values, title, color=(130, 210, 245), percent=False):
        pygame.draw.rect(screen, (20, 27, 36), rect, border_radius=10)
        pygame.draw.rect(screen, (70, 96, 125), rect, 1, border_radius=10)
        screen.blit(self.graph_font.render(title, True, (225, 238, 248)), (rect.x + 8, rect.y + 6))

        if not values:
            msg = self.graph_font.render("Aucune donnee", True, (165, 180, 200))
            screen.blit(msg, msg.get_rect(center=rect.center))
            return

        plot = pygame.Rect(rect.x + 8, rect.y + 30, rect.width - 16, rect.height - 42)
        vmin = min(values)
        vmax = max(values)
        span = max(1e-6, vmax - vmin)
        points = []
        for idx, value in enumerate(values):
            t = idx / max(1, len(values) - 1)
            x = int(plot.x + t * plot.width)
            ratio = (value - vmin) / span if span > 0 else 0.0
            y = int(plot.bottom - ratio * plot.height)
            points.append((x, y))
        if len(points) > 1:
            pygame.draw.lines(screen, color, False, points, 2)
        for x, y in points[-3:]:
            pygame.draw.circle(screen, color, (x, y), 3)

        latest = values[-1]
        latest_txt = f"{latest:.2f}" if percent else f"{int(round(latest))}"
        if percent:
            latest_txt += "%"
        screen.blit(self.graph_font.render(f"Derniere valeur : {latest_txt}", True, color), (plot.x, plot.bottom + 2))

    def _draw_radar_species(self, screen, rect):
        pygame.draw.rect(screen, (18, 34, 43), rect, border_radius=10)
        pygame.draw.rect(screen, (72, 140, 170), rect, 1, border_radius=10)
        screen.blit(self.graph_font.render("Statistiques espece (radar)", True, (232, 244, 255)), (rect.x + 8, rect.y + 6))

        species_stats = self.summary.get("species_stats", {}) or {}
        labels = []
        values = []
        for category in ("physique", "sens", "mental", "social", "environnement"):
            data = species_stats.get(category, {}) or {}
            if not data:
                continue
            nums = [float(v) for v in data.values() if isinstance(v, (int, float))]
            if nums:
                labels.append(category.capitalize())
                values.append(sum(nums) / len(nums))
        if not values:
            labels = ["Physique", "Sens", "Mental", "Social", "Env"]
            values = [0, 0, 0, 0, 0]

        cx, cy = rect.centerx, rect.y + int(rect.height * 0.58)
        radius = int(min(rect.width, rect.height) * 0.26)
        max_value = max(20.0, max(values))
        points = []
        for i, value in enumerate(values):
            angle = -math.pi / 2 + i * (2 * math.pi / len(values))
            ratio = max(0.0, min(1.0, value / max_value))
            axis_x = cx + int(math.cos(angle) * radius)
            axis_y = cy + int(math.sin(angle) * radius)
            pygame.draw.line(screen, (60, 88, 108), (cx, cy), (axis_x, axis_y), 1)
            x = cx + int(math.cos(angle) * radius * ratio)
            y = cy + int(math.sin(angle) * radius * ratio)
            points.append((x, y))
            lbl = self.graph_font.render(labels[i], True, (198, 224, 242))
            screen.blit(lbl, (axis_x - lbl.get_width() // 2, axis_y - lbl.get_height() // 2))

        if len(points) >= 3:
            poly = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            shifted = [(x - rect.x, y - rect.y) for x, y in points]
            pygame.draw.polygon(poly, (108, 205, 174, 88), shifted)
            screen.blit(poly, rect.topleft)
            pygame.draw.polygon(screen, (128, 228, 196), points, 2)

    def _draw_stats_tab(self, screen, rect):
        resources = self.summary.get("resources_by_type", {}) or {}
        species_stats = self.summary.get("species_stats", {}) or {}
        daily = self.summary.get("daily_stats", []) or []

        y = rect.y + 8
        x = rect.x + 10
        stats_lines = [
            f"Animaux tues : {int(self.summary.get('animals_killed', 0) or 0)}",
            f"Technologies debloquees : {int(self.summary.get('tech_unlocked', 0) or 0)}",
            f"Habitants max : {int(self.summary.get('max_population', 0) or 0)}",
            f"Habitants total : {int(self.summary.get('total_population', 0) or 0)}",
            f"Innovation maximum : {int(self.summary.get('max_innovation', 0) or 0)}",
            f"Mutations debloquees : {int(self.summary.get('mutations_unlocked', 0) or 0)}",
        ]
        for line in stats_lines:
            surf = self.graph_font.render(line, True, (234, 240, 247))
            screen.blit(surf, (x, y))
            y += surf.get_height() + 4

        screen.blit(self.graph_font.render("Ressources recuperees :", True, (190, 226, 246)), (x, y + 4))
        y += self.graph_font.get_height() + 6
        for res_id, qty in sorted(resources.items(), key=lambda kv: kv[0]):
            surf = self.graph_font.render(f"- {res_id}: {int(qty)}", True, (215, 222, 232))
            screen.blit(surf, (x + 12, y))
            y += surf.get_height() + 2

        species_lines = []
        for cat, values in species_stats.items():
            for key, value in (values or {}).items():
                if isinstance(value, float):
                    species_lines.append(f"{cat}.{key}: {value:.2f}")
                else:
                    species_lines.append(f"{cat}.{key}: {value}")

        right_x = rect.centerx + 20
        ry = rect.y + 8
        screen.blit(self.graph_font.render("Stats de l'espece :", True, (190, 226, 246)), (right_x, ry))
        ry += self.graph_font.get_height() + 4
        for line in species_lines[:14]:
            surf = self.graph_font.render(line, True, (219, 228, 236))
            screen.blit(surf, (right_x, ry))
            ry += surf.get_height() + 2

        graphs_top = rect.y + int(rect.height * 0.40)
        graph_h = int((rect.bottom - graphs_top - 12) * 0.48)
        graph_w = int((rect.width - 24) * 0.33)
        gap = 8

        animals = [int(d.get("animals_killed", 0) or 0) for d in daily]
        resources_daily = [int(d.get("resources_collected", 0) or 0) for d in daily]
        population = [int(d.get("population", 0) or 0) for d in daily]
        birth_rate = [float(d.get("birth_rate", 0.0) or 0.0) * 100.0 for d in daily]
        death_rate = [float(d.get("death_rate", 0.0) or 0.0) * 100.0 for d in daily]

        r1 = pygame.Rect(rect.x + 8, graphs_top, graph_w, graph_h)
        r2 = pygame.Rect(r1.right + gap, graphs_top, graph_w, graph_h)
        r3 = pygame.Rect(r2.right + gap, graphs_top, graph_w, graph_h)
        self._draw_radar_species(screen, r1)
        self._draw_line_graph(screen, r2, animals, "Animaux tues / jour", (226, 146, 127))
        self._draw_line_graph(screen, r3, resources_daily, "Ressources / jour", (145, 210, 159))

        r4 = pygame.Rect(rect.x + 8, r1.bottom + gap, graph_w, graph_h)
        r5 = pygame.Rect(r4.right + gap, r4.y, graph_w, graph_h)
        r6 = pygame.Rect(r5.right + gap, r4.y, graph_w, graph_h)
        self._draw_line_graph(screen, r4, population, "Individus / jour", (138, 194, 247))
        self._draw_line_graph(screen, r5, birth_rate, "Taux natalite / jour", (213, 181, 255), percent=True)
        self._draw_line_graph(screen, r6, death_rate, "Taux mortalite / jour", (255, 168, 168), percent=True)

    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))

        title_surf = self.title_font.render(self.title, True, (230, 230, 230))
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 50))

        panel = self._panel_rect()
        pygame.draw.rect(screen, (24, 28, 38), panel, border_radius=16)
        pygame.draw.rect(screen, (70, 82, 96), panel, 2, border_radius=16)

        self._make_tab_buttons(panel)
        for tab_id, btn in self.tab_buttons.items():
            btn.style.active_bg_color = (85, 115, 150) if tab_id == self.active_tab else btn.style.active_bg_color
            btn.draw(screen)

        if not self.stats_tab_enabled:
            hint = self.graph_font.render("Statistiques disponibles apres 1 jour de partie.", True, (188, 154, 154))
            screen.blit(hint, (panel.x + 350, panel.y + 26))

        content = pygame.Rect(panel.x + 18, panel.y + 70, panel.width - 36, panel.height - 86)
        if self.active_tab == "resume":
            left = pygame.Rect(content.left + 12, content.top + 6, content.width - 24, int(content.height * 0.55))
            right = pygame.Rect(content.left + 12, left.bottom + 10, content.width - 24, int(content.height * 0.35))
            self._draw_summary(screen, left)
            self._draw_xp_bar(screen, right)
        else:
            self._draw_stats_tab(screen, content)

        self.btn_continue.draw(screen)
