import math
import pygame

from Game.core.utils import Button, ButtonStyle
from Game.ui.hud.notification import add_notification


class TechMenu:
    _GRAPH_ROTATION = [
        ("Population", "population", (124, 218, 146)),
        ("Bonheur", "happiness", (255, 193, 112)),
        ("XP espece", "xp", (137, 181, 250)),
        ("Innovations", "innovations", (216, 150, 255)),
        ("Tech debloquees", "unlocked_techs", (228, 225, 122)),
        ("Crafts debloques", "unlocked_crafts", (126, 227, 218)),
    ]

    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False

        self.scroll_x = 0
        self._max_scroll_x = 0
        self.bubble_buttons = {}
        self.graph_buttons = {}
        self._hovered_tech = None
        self._selected_graph_tech = None

        self._layout_key = None
        self._layout_centers = {}
        self._layout_edges = []
        self._bubble_radius = 40
        self._tree_rect = pygame.Rect(0, 0, 0, 0)
        self._graph_list_rect = pygame.Rect(0, 0, 0, 0)
        self._graph_plot_rect = pygame.Rect(0, 0, 0, 0)

        self._series_max_points = 48
        self._last_capture_ms = 0
        self._metric_series = {
            "population": [],
            "happiness": [],
            "xp": [],
            "innovations": [],
            "unlocked_techs": [],
            "unlocked_crafts": [],
        }

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Menu Technologies"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.btn_font = pygame.font.SysFont("consolas", 22, bold=True)
        self.tooltip_font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 16)

        style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=16,
            padding_y=10,
            hover_zoom=1.04,
            font=self.btn_font,
        )
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

    def open(self):
        self.active = True
        self._capture_metrics(force=True)

    def close(self):
        self.active = False

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def _sorted_tech_ids(self):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return []
        return sorted(
            (getattr(tech_tree, "techs", {}) or {}).keys(),
            key=lambda tid: (tech_tree.get_tech(tid).get("phase", 0), tech_tree.get_tech(tid).get("nom", tid)),
        )

    def _sorted_unlocked(self):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return []
        ordered = self._sorted_tech_ids()
        unlocked = set(getattr(tech_tree, "unlocked", set()) or set())
        return [tid for tid in ordered if tid in unlocked]

    def _capture_metrics(self, force=False):
        now = pygame.time.get_ticks()
        if not force and now - self._last_capture_ms < 400:
            return
        self._last_capture_ms = now

        tech_tree = getattr(self.phase, "tech_tree", None)
        species = getattr(self.phase, "espece", None)

        snapshot = {
            "population": float(getattr(species, "population", 0)),
            "happiness": float(getattr(self.phase, "happiness", 0)),
            "xp": float(getattr(species, "xp", 0) if species else 0),
            "innovations": float(getattr(tech_tree, "innovations", 0) if tech_tree else 0),
            "unlocked_techs": float(len(getattr(tech_tree, "unlocked", []) or [])),
            "unlocked_crafts": float(len(getattr(self.phase, "unlocked_crafts", []) or [])),
        }

        for key, value in snapshot.items():
            series = self._metric_series[key]
            series.append(value)
            if len(series) > self._series_max_points:
                del series[0]

    def _graph_spec_for_tech(self, tech_id):
        unlocked = self._sorted_unlocked()
        if tech_id not in unlocked:
            return None
        idx = unlocked.index(tech_id)
        label, metric, color = self._GRAPH_ROTATION[idx % len(self._GRAPH_ROTATION)]
        return {
            "label": label,
            "metric": metric,
            "color": color,
        }

    def _compute_depths(self):
        tech_tree = getattr(self.phase, "tech_tree", None)
        techs = getattr(tech_tree, "techs", {}) if tech_tree else {}
        memo = {}

        def depth(tid, stack=None):
            if tid in memo:
                return memo[tid]
            stack = stack or set()
            if tid in stack:
                return 0
            stack = set(stack)
            stack.add(tid)

            deps = []
            for dep in tech_tree.get_dependencies(tid):
                if dep in techs:
                    deps.append(dep)
            if not deps:
                memo[tid] = 0
                return 0
            val = 1 + max(depth(dep, stack) for dep in deps)
            memo[tid] = val
            return val

        for tid in techs.keys():
            depth(tid, set())
        return memo

    def _update_layout(self):
        screen = getattr(self.phase, "screen", None)
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not screen or not tech_tree:
            return

        w, h = screen.get_size()
        unlocked_count = len(getattr(tech_tree, "unlocked", []) or [])
        layout_key = (
            w,
            h,
            unlocked_count,
            self.scroll_x,
            len(getattr(tech_tree, "techs", {}) or {}),
            self.btn_font.get_height(),
            self.small_font.get_height(),
        )
        if self._layout_key == layout_key:
            return
        self._layout_key = layout_key

        margin = max(14, int(min(w, h) * 0.03))
        header_h = max(72, int(h * 0.12))
        content_y = margin + header_h + margin // 2
        content_h = h - content_y - int(margin * 1.6)
        content_rect = pygame.Rect(margin, content_y, w - 2 * margin, content_h)

        tree_w = int(content_rect.width * 0.58)
        self._tree_rect = pygame.Rect(content_rect.x, content_rect.y, tree_w, content_rect.height)
        graph_rect = pygame.Rect(content_rect.x + tree_w + margin // 2, content_rect.y, content_rect.width - tree_w - margin // 2, content_rect.height)

        available_w = max(220, graph_rect.width - 32)
        list_w = int(graph_rect.width * 0.36)
        list_w = max(90, min(list_w, max(90, available_w - 130)))
        self._graph_list_rect = pygame.Rect(graph_rect.x + 10, graph_rect.y + 14, list_w, graph_rect.height - 28)
        self._graph_plot_rect = pygame.Rect(
            self._graph_list_rect.right + 12,
            graph_rect.y + 14,
            max(120, available_w - list_w),
            graph_rect.height - 28,
        )

        self._bubble_radius = max(26, int(min(self._tree_rect.width, self._tree_rect.height) * 0.075))
        tech_ids = self._sorted_tech_ids()
        depths = self._compute_depths()
        max_depth = max(depths.values(), default=0)
        layer_gap = max(int(self._tree_rect.width * 0.24), self._bubble_radius * 3)

        required_width = (max_depth + 1) * layer_gap + self._bubble_radius * 2 + 30
        self._max_scroll_x = max(0, required_width - self._tree_rect.width)
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x))

        layers = {}
        for tid in tech_ids:
            d = depths.get(tid, 0)
            layers.setdefault(d, []).append(tid)
        for d in layers:
            layers[d].sort(key=lambda tid: tech_tree.get_tech(tid).get("nom", tid))

        centers = {}
        top = self._tree_rect.y + self._bubble_radius + 12
        bottom = self._tree_rect.bottom - self._bubble_radius - 12
        for d, nodes in layers.items():
            x = self._tree_rect.x + self._bubble_radius + 16 + d * layer_gap - self.scroll_x
            if len(nodes) == 1:
                y_positions = [self._tree_rect.centery]
            else:
                free_h = max(1, bottom - top)
                step = free_h / (len(nodes) - 1)
                y_positions = [int(top + i * step) for i in range(len(nodes))]
            for idx, tid in enumerate(nodes):
                centers[tid] = (int(x), int(y_positions[idx]))

        edges = []
        for tid in tech_ids:
            for dep in tech_tree.get_dependencies(tid):
                if dep in centers:
                    edges.append((dep, tid))

        self._layout_centers = centers
        self._layout_edges = edges

        bubble_style = ButtonStyle(
            draw_background=False,
            draw_border=False,
            padding_x=0,
            padding_y=0,
            font=self.btn_font,
        )
        self.bubble_buttons = {}
        for tech_id, center in self._layout_centers.items():
            btn = Button(
                text="",
                pos=center,
                size=(self._bubble_radius * 2, self._bubble_radius * 2),
                anchor="center",
                style=bubble_style,
                on_click=lambda _btn, tid=tech_id: self._start_research(tid),
            )
            self.bubble_buttons[tech_id] = btn

        self.graph_buttons = {}
        unlocked = self._sorted_unlocked()
        if unlocked and self._selected_graph_tech not in unlocked:
            self._selected_graph_tech = unlocked[0]
        elif not unlocked:
            self._selected_graph_tech = None

        row_h = max(30, int(self._graph_list_rect.height * 0.12))
        btn_style = ButtonStyle(
            draw_background=True,
            bg_color=(36, 58, 74),
            hover_bg_color=(50, 78, 98),
            active_bg_color=(70, 112, 136),
            draw_border=True,
            border_color=(98, 152, 180),
            border_width=2,
            radius=8,
            padding_x=8,
            padding_y=6,
            font=self.small_font,
            hover_zoom=1.02,
        )

        y = self._graph_list_rect.y + 2
        for tid in unlocked:
            label = tech_tree.get_tech(tid).get("nom", tid)
            clipped = label if len(label) <= 14 else f"{label[:12]}.."
            btn = Button(
                text=clipped,
                pos=(self._graph_list_rect.x + 3, y),
                size=(self._graph_list_rect.width - 6, row_h),
                anchor="topleft",
                style=btn_style,
                on_click=lambda _btn, tech_id=tid: self._set_graph_tech(tech_id),
            )
            self.graph_buttons[tid] = btn
            y += row_h + 8

    def _set_graph_tech(self, tech_id):
        if tech_id in self.graph_buttons:
            self._selected_graph_tech = tech_id

    def _start_research(self, tech_id):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return
        if tech_id in tech_tree.unlocked:
            add_notification("Cette technologie est deja debloquee.")
            return
        if tech_tree.current_research and tech_tree.current_research != tech_id:
            add_notification("Une recherche est deja en cours.")
            return
        if not tech_tree.can_start(tech_id):
            add_notification("Conditions non remplies pour cette technologie.")
            return
        if self.phase.start_tech_research(tech_id):
            return
        add_notification("Impossible de demarrer la recherche.")

    def _scroll_tree(self, delta):
        if self._max_scroll_x <= 0:
            self.scroll_x = 0
            return
        self.scroll_x = max(0, min(self.scroll_x + delta, self._max_scroll_x))
        self._layout_key = None

    def _handle_scroll_input(self, events):
        for e in events:
            if e.type != pygame.MOUSEWHEEL:
                continue
            mx, my = pygame.mouse.get_pos()
            if self._tree_rect.collidepoint((mx, my)):
                self._scroll_tree(-e.y * 50)

    def handle(self, events):
        if not self.active:
            return
        self._capture_metrics(force=False)
        self._update_layout()
        self._handle_scroll_input(events)

        self.back_btn.handle(events)
        self._hovered_tech = None

        for tech_id, btn in self.bubble_buttons.items():
            btn.handle(events)
            if btn.is_hovered:
                self._hovered_tech = tech_id

        for btn in self.graph_buttons.values():
            btn.handle(events)

    @staticmethod
    def _bubble_text(label):
        if not label:
            return "?"
        parts = str(label).split()
        if len(parts) == 1:
            return parts[0][:7].upper()
        short = "".join(p[0] for p in parts[:3]).upper()
        if len(short) >= 2:
            return short
        return str(label)[:6].upper()

    def _state_for(self, tech_id):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return "locked"
        if tech_id in tech_tree.unlocked:
            return "unlocked"
        if tech_tree.current_research == tech_id:
            return "research"
        if tech_tree.can_start(tech_id):
            return "available"
        return "locked"

    def _draw_tree(self, screen):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return

        pygame.draw.rect(screen, (20, 35, 48), self._tree_rect, border_radius=16)
        pygame.draw.rect(screen, (86, 137, 168), self._tree_rect, 2, border_radius=16)

        title = self.small_font.render("Arbre technologique", True, (230, 243, 255))
        screen.blit(title, (self._tree_rect.x + 16, self._tree_rect.y + 10))

        clip = screen.get_clip()
        screen.set_clip(self._tree_rect)

        for parent, child in self._layout_edges:
            p = self._layout_centers.get(parent)
            c = self._layout_centers.get(child)
            if not p or not c:
                continue
            pygame.draw.line(screen, (98, 130, 152), p, c, 4)

        bubble_font = pygame.font.SysFont("consolas", max(12, int(self._bubble_radius * 0.44)), bold=True)
        for tech_id, center in self._layout_centers.items():
            tech = tech_tree.get_tech(tech_id)
            state = self._state_for(tech_id)

            # Locked nodes stay colored (not grayscale).
            fill = (87, 112, 139)
            border = (188, 211, 230)
            text_color = (243, 247, 250)
            if state == "unlocked":
                fill = (64, 139, 94)
                border = (182, 241, 201)
            elif state == "research":
                fill = (65, 109, 171)
                border = (170, 208, 255)
            elif state == "available":
                fill = (151, 114, 62)
                border = (236, 208, 161)
            elif state == "locked":
                fill = (124, 82, 73)
                border = (214, 165, 146)

            pygame.draw.circle(screen, fill, center, self._bubble_radius)
            pygame.draw.circle(screen, border, center, self._bubble_radius, 3)

            label = self._bubble_text(tech.get("nom", tech_id))
            txt = bubble_font.render(label, True, text_color)
            screen.blit(txt, txt.get_rect(center=center))

            if state == "research":
                cost = max(1, int(tech_tree.get_cost(tech_id)))
                progress = int(getattr(tech_tree, "current_progress", 0))
                ratio = max(0.0, min(1.0, progress / cost))
                arc_r = self._bubble_radius + 8
                start_angle = -math.pi / 2
                end_angle = start_angle + 2 * math.pi * ratio
                arc_rect = pygame.Rect(center[0] - arc_r, center[1] - arc_r, arc_r * 2, arc_r * 2)
                pygame.draw.arc(screen, (220, 239, 255), arc_rect, start_angle, end_angle, 4)

        screen.set_clip(clip)

    def _draw_metric_graph(self, screen, rect, values, color, title, latest_text):
        pygame.draw.rect(screen, (19, 31, 42), rect, border_radius=12)
        pygame.draw.rect(screen, (86, 137, 168), rect, 2, border_radius=12)

        title_surf = self.small_font.render(title, True, (235, 246, 255))
        screen.blit(title_surf, (rect.x + 12, rect.y + 10))
        latest_surf = self.small_font.render(latest_text, True, color)
        screen.blit(latest_surf, (rect.x + 12, rect.y + 10 + title_surf.get_height() + 2))

        plot = rect.inflate(-24, -84)
        if plot.width <= 4 or plot.height <= 4:
            return

        pygame.draw.rect(screen, (27, 44, 58), plot, border_radius=8)
        pygame.draw.rect(screen, (68, 101, 122), plot, 1, border_radius=8)

        if not values:
            msg = self.tooltip_font.render("Aucune donnee disponible.", True, (200, 210, 220))
            screen.blit(msg, msg.get_rect(center=plot.center))
            return

        if len(values) == 1:
            px = plot.centerx
            py = plot.bottom - int(plot.height * 0.5)
            pygame.draw.circle(screen, color, (px, py), 4)
            return

        v_min = min(values)
        v_max = max(values)
        if abs(v_max - v_min) < 1e-6:
            v_max += 1.0
            v_min -= 1.0

        points = []
        for i, value in enumerate(values):
            x = plot.x + int(i * (plot.width - 1) / max(1, len(values) - 1))
            ratio = (value - v_min) / (v_max - v_min)
            y = plot.bottom - int(ratio * (plot.height - 1))
            points.append((x, y))

        area = pygame.Surface((plot.width, plot.height), pygame.SRCALPHA)
        shifted = [(x - plot.x, y - plot.y) for x, y in points]
        area_points = [(shifted[0][0], plot.height)] + shifted + [(shifted[-1][0], plot.height)]
        pygame.draw.polygon(area, (*color, 70), area_points)
        screen.blit(area, plot.topleft)

        pygame.draw.lines(screen, color, False, points, 3)
        pygame.draw.circle(screen, (245, 245, 245), points[-1], 4)

        min_s = self.tooltip_font.render(f"min {v_min:.1f}", True, (178, 198, 212))
        max_s = self.tooltip_font.render(f"max {v_max:.1f}", True, (178, 198, 212))
        screen.blit(min_s, (plot.x + 6, plot.bottom + 6))
        screen.blit(max_s, (plot.right - max_s.get_width() - 6, plot.bottom + 6))

    def _draw_graph_panel(self, screen):
        panel_rect = self._graph_list_rect.union(self._graph_plot_rect).inflate(20, 18)
        pygame.draw.rect(screen, (20, 35, 48), panel_rect, border_radius=16)
        pygame.draw.rect(screen, (86, 137, 168), panel_rect, 2, border_radius=16)

        list_title = self.small_font.render("Graphes debloques", True, (230, 243, 255))
        screen.blit(list_title, (self._graph_list_rect.x + 8, self._graph_list_rect.y - 12))

        for tech_id, btn in self.graph_buttons.items():
            if tech_id == self._selected_graph_tech:
                pygame.draw.rect(screen, (84, 128, 156), btn.rect.inflate(4, 4), border_radius=10)
            btn.draw(screen)

        tech_tree = getattr(self.phase, "tech_tree", None)
        unlocked = self._sorted_unlocked()
        if not tech_tree or not unlocked:
            msg = self.small_font.render("Debloquez une technologie pour ouvrir un graphe.", True, (212, 220, 228))
            screen.blit(msg, msg.get_rect(center=self._graph_plot_rect.center))
            return

        selected = self._selected_graph_tech if self._selected_graph_tech in unlocked else unlocked[0]
        self._selected_graph_tech = selected
        tech = tech_tree.get_tech(selected)
        spec = self._graph_spec_for_tech(selected)
        if not spec:
            return

        metric_values = self._metric_series.get(spec["metric"], [])
        latest_value = metric_values[-1] if metric_values else 0
        graph_title = f"{tech.get('nom', selected)} - {spec['label']}"
        latest_text = f"Derniere valeur: {latest_value:.1f}"
        self._draw_metric_graph(screen, self._graph_plot_rect, metric_values, spec["color"], graph_title, latest_text)

    def _draw_tooltip(self, screen):
        if not self._hovered_tech:
            return
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return
        tech = tech_tree.get_tech(self._hovered_tech)
        if not tech:
            return

        deps = tech_tree.get_dependencies(self._hovered_tech)
        deps_text = ", ".join(deps) if deps else "Aucune"
        lines = [
            tech.get("nom", self._hovered_tech),
            tech.get("description", ""),
            f"Cout: {tech_tree.get_cost(self._hovered_tech)}",
            f"Prerequis: {deps_text}",
        ]
        rendered = [self.tooltip_font.render(line, True, (240, 242, 248)) for line in lines if line]
        if not rendered:
            return

        padding = 8
        width = max(s.get_width() for s in rendered) + padding * 2
        height = sum(s.get_height() for s in rendered) + padding * 2
        mx, my = pygame.mouse.get_pos()
        rect = pygame.Rect(mx + 16, my + 16, width, height)

        sw, sh = screen.get_size()
        if rect.right > sw - 8:
            rect.x = sw - rect.width - 8
        if rect.bottom > sh - 8:
            rect.y = sh - rect.height - 8

        pygame.draw.rect(screen, (38, 41, 52), rect, border_radius=8)
        pygame.draw.rect(screen, (124, 132, 156), rect, 2, border_radius=8)

        y = rect.y + padding
        for surf in rendered:
            screen.blit(surf, (rect.x + padding, y))
            y += surf.get_height()

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = max(14, int(min(w, h) * 0.03))
        header_h = max(72, int(h * 0.12))

        self.title_font = pygame.font.SysFont("consolas", max(26, int(h * 0.055)), bold=True)
        self.btn_font = pygame.font.SysFont("consolas", max(14, int(h * 0.022)), bold=True)
        self.small_font = pygame.font.SysFont("consolas", max(12, int(h * 0.019)))
        self.tooltip_font = pygame.font.SysFont("consolas", max(12, int(h * 0.017)))
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(16, int(h * 0.03)), bold=True)
        self.back_btn._rebuild_surfaces()

        for y in range(h):
            t = y / max(1, h - 1)
            color = (
                int(14 + 20 * t),
                int(20 + 28 * t),
                int(30 + 34 * t),
            )
            pygame.draw.line(screen, color, (0, y), (w, y))

        header_rect = pygame.Rect(margin, margin, w - 2 * margin, header_h)
        pygame.draw.rect(screen, (17, 48, 64), header_rect, border_radius=16)
        pygame.draw.rect(screen, (94, 160, 190), header_rect, 2, border_radius=16)

        title_surf = self.title_font.render(self.title, True, (244, 252, 255))
        screen.blit(title_surf, (header_rect.x + 18, header_rect.y + 10))

        tech_tree = getattr(self.phase, "tech_tree", None)
        innovations = int(getattr(tech_tree, "innovations", 0)) if tech_tree else 0
        current = getattr(tech_tree, "current_research", None) if tech_tree else None
        sub_txt = f"Innovations: {innovations}"
        if current:
            sub_txt += f" | Recherche: {current}"
        sub_surf = self.small_font.render(sub_txt, True, (190, 224, 240))
        screen.blit(sub_surf, (header_rect.x + 18, header_rect.bottom - sub_surf.get_height() - 12))

        self._update_layout()
        self._draw_tree(screen)
        self._draw_graph_panel(screen)
        self._draw_tooltip(screen)

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
