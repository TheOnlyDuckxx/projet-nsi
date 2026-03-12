from __future__ import annotations

import math
from typing import Dict, List, Tuple

import pygame

from Game.core.utils import Button, ButtonStyle, resource_path
from Game.ui.hud.notification import add_notification


def _mix_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, float(t)))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


class TechMenu:
    BRANCH_COLORS = {
        "common": (224, 180, 96),
        "savant": (100, 196, 255),
        "pacifiste": (126, 220, 164),
        "croyant": (208, 138, 255),
        "belligerant": (238, 96, 96),
    }

    # Directions visuelles des branches autour du tronc commun.
    BRANCH_DIRECTIONS = {
        "savant": (-1.0, -0.82),
        "croyant": (1.0, -0.82),
        "pacifiste": (-1.0, 0.82),
        "belligerant": (1.0, 0.82),
    }

    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False

        self.title = "Arbre de competences"
        self._layout_key = None
        self._tree_rect = pygame.Rect(0, 0, 0, 0)
        self._layout_centers: Dict[str, Tuple[int, int]] = {}
        self._layout_edges: List[Tuple[str, str]] = []
        self._buttons: Dict[str, Button] = {}
        self._hovered_tech = None
        self._node_radius = 38
        self._last_screen_size = (0, 0)

        if not pygame.font.get_init():
            pygame.font.init()
        self.title_font = pygame.font.SysFont("consolas", 44, bold=True)
        self.node_font = pygame.font.SysFont("consolas", 15, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 16)
        self.tooltip_font = pygame.font.SysFont("consolas", 14)

        style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=16,
            padding_y=10,
            hover_zoom=1.04,
            font=self.small_font,
            bg_color=(35, 39, 47),
            hover_bg_color=(52, 57, 68),
            active_bg_color=(66, 72, 84),
            draw_border=True,
            border_color=(148, 154, 166),
            border_width=2,
        )
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

    def open(self):
        self.active = True

    def close(self):
        self.active = False
        self._hovered_tech = None

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def _load_font(self, rel_path: str, size: int, *, bold_fallback: bool = False):
        try:
            return pygame.font.Font(resource_path(rel_path), int(size))
        except Exception:
            return pygame.font.SysFont("consolas", int(size), bold=bold_fallback)

    def _refresh_fonts(self, screen_size):
        if screen_size == self._last_screen_size:
            return
        self._last_screen_size = screen_size
        _w, h = screen_size
        self.title_font = self._load_font("Game/assets/ui/MightySouly.ttf", max(34, int(h * 0.075)))
        self.node_font = self._load_font("Game/assets/ui/KiwiSoda.ttf", max(12, int(h * 0.021)))
        self.small_font = self._load_font("Game/assets/ui/KiwiSoda.ttf", max(13, int(h * 0.022)))
        self.tooltip_font = self._load_font("Game/assets/ui/KiwiSoda.ttf", max(12, int(h * 0.019)))
        self.back_btn.style.font = self.small_font
        self.back_btn._rebuild_surfaces()
        self._layout_key = None

    def _sorted_tech_ids(self):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return []
        return sorted(
            (getattr(tech_tree, "techs", {}) or {}).keys(),
            key=lambda tid: (tech_tree.get_tech(tid).get("phase", 0), tech_tree.get_tech(tid).get("nom", tid)),
        )

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

            deps = [dep for dep in tech_tree.get_dependencies(tid) if dep in techs]
            if not deps:
                memo[tid] = 0
                return 0
            val = 1 + max(depth(dep, stack) for dep in deps)
            memo[tid] = val
            return val

        for tid in techs.keys():
            depth(tid, set())
        return memo

    def _branch_for_tech(self, tech_id: str) -> str:
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return "common"
        tech = tech_tree.get_tech(tech_id) or {}
        required = str(tech.get("required_main_class") or "").strip().lower()
        if required in self.BRANCH_COLORS:
            return required
        cat = str(tech.get("categorie") or "").strip().lower()
        if cat in self.BRANCH_COLORS:
            return cat
        return "common"

    def _state_for(self, tech_id: str):
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

    def _node_label(self, tech_id: str):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return "?"
        name = str((tech_tree.get_tech(tech_id) or {}).get("nom") or tech_id).strip()
        if not name:
            return "?"
        parts = [p for p in name.split() if p]
        if len(parts) == 1:
            return parts[0][:8].upper()
        initials = "".join(p[0] for p in parts[:3]).upper()
        if len(initials) >= 2:
            return initials
        return name[:8].upper()

    def _fit_layout_in_rect(self, raw_centers: Dict[str, Tuple[float, float]], pad: int):
        if not raw_centers:
            return {}
        xs = [p[0] for p in raw_centers.values()]
        ys = [p[1] for p in raw_centers.values()]
        min_x = min(xs) - pad
        max_x = max(xs) + pad
        min_y = min(ys) - pad
        max_y = max(ys) + pad

        raw_w = max(1.0, max_x - min_x)
        raw_h = max(1.0, max_y - min_y)
        avail_w = max(1.0, float(self._tree_rect.width - 2 * pad))
        avail_h = max(1.0, float(self._tree_rect.height - 2 * pad))
        scale = min(1.0, avail_w / raw_w, avail_h / raw_h)

        cx, cy = self._tree_rect.centerx, self._tree_rect.centery
        mx = (min_x + max_x) / 2.0
        my = (min_y + max_y) / 2.0
        return {tid: ((x - mx) * scale + cx, (y - my) * scale + cy) for tid, (x, y) in raw_centers.items()}

    def _relax_layout(self, centers: Dict[str, Tuple[float, float]], pad: int):
        if not centers:
            return {}
        if len(centers) == 1:
            tid, pos = next(iter(centers.items()))
            return {tid: (int(round(pos[0])), int(round(pos[1])))}

        left = self._tree_rect.left + pad
        right = self._tree_rect.right - pad
        top = self._tree_rect.top + pad
        bottom = self._tree_rect.bottom - pad
        ids = list(centers.keys())
        anchors = {tid: (float(centers[tid][0]), float(centers[tid][1])) for tid in ids}
        positions = {tid: [anchors[tid][0], anchors[tid][1]] for tid in ids}
        min_dist = self._node_radius * 2.22

        for _ in range(72):
            moved = 0.0
            for i, a in enumerate(ids):
                for j in range(i + 1, len(ids)):
                    b = ids[j]
                    ax, ay = positions[a]
                    bx, by = positions[b]
                    vx = bx - ax
                    vy = by - ay
                    d2 = vx * vx + vy * vy
                    if d2 < 1e-6:
                        ang = (i * 37 + j * 53) * 0.07
                        nx = math.cos(ang)
                        ny = math.sin(ang)
                        dist = 1.0
                    else:
                        dist = math.sqrt(d2)
                        nx = vx / dist
                        ny = vy / dist
                    if dist < min_dist:
                        push = (min_dist - dist) * 0.5
                        positions[a][0] -= nx * push
                        positions[a][1] -= ny * push
                        positions[b][0] += nx * push
                        positions[b][1] += ny * push
                        moved += push

            for tid in ids:
                tx, ty = anchors[tid]
                positions[tid][0] += (tx - positions[tid][0]) * 0.09
                positions[tid][1] += (ty - positions[tid][1]) * 0.09
                positions[tid][0] = max(left, min(right, positions[tid][0]))
                positions[tid][1] = max(top, min(bottom, positions[tid][1]))
            if moved < 0.05:
                break

        return {tid: (int(round(pos[0])), int(round(pos[1]))) for tid, pos in positions.items()}

    def _update_layout(self):
        screen = getattr(self.phase, "screen", None)
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not screen or not tech_tree:
            return

        w, h = screen.get_size()
        tech_count = len(getattr(tech_tree, "techs", {}) or {})
        unlocked_count = len(getattr(tech_tree, "unlocked", []) or [])
        key = (w, h, tech_count, unlocked_count, self.node_font.get_height(), self.small_font.get_height())
        if key == self._layout_key:
            return
        self._layout_key = key

        margin = max(16, int(min(w, h) * 0.03))
        header_h = max(84, int(h * 0.14))
        self._tree_rect = pygame.Rect(
            margin,
            margin + header_h,
            w - margin * 2,
            h - margin * 2 - header_h - max(44, int(h * 0.08)),
        )

        node_target = math.sqrt(
            (self._tree_rect.width * self._tree_rect.height) / (max(1, tech_count) * 48.0)
        )
        self._node_radius = max(22, min(34, int(node_target)))
        step = max(self._node_radius * 2.75, min(self._tree_rect.width, self._tree_rect.height) * 0.17)

        tech_ids = self._sorted_tech_ids()
        depths = self._compute_depths()

        branches = {tid: self._branch_for_tech(tid) for tid in tech_ids}
        common_nodes = [tid for tid in tech_ids if branches.get(tid) == "common"]
        split_depth = max((depths.get(tid, 0) for tid in common_nodes), default=0)

        # Layout initial dans un espace local, puis recentrage/scaling.
        raw_centers: Dict[str, Tuple[float, float]] = {}

        common_by_depth: Dict[int, List[str]] = {}
        for tid in common_nodes:
            common_by_depth.setdefault(depths.get(tid, 0), []).append(tid)
        for d in sorted(common_by_depth.keys()):
            nodes = common_by_depth[d]
            nodes.sort(key=lambda tid: ((tech_tree.get_tech(tid) or {}).get("nom", tid), tid))
            x = (d - split_depth) * (step * 1.05)
            count = len(nodes)
            for idx, tid in enumerate(nodes):
                y = (idx - (count - 1) / 2.0) * (self._node_radius * 1.80)
                raw_centers[tid] = (x, y)

        branch_nodes: Dict[str, List[str]] = {k: [] for k in self.BRANCH_DIRECTIONS.keys()}
        for tid in tech_ids:
            b = branches.get(tid, "common")
            if b in branch_nodes:
                branch_nodes[b].append(tid)

        for branch, nodes in branch_nodes.items():
            if not nodes:
                continue
            nodes.sort(key=lambda tid: (depths.get(tid, 0), (tech_tree.get_tech(tid) or {}).get("nom", tid)))
            base_depth = min(depths.get(tid, 0) for tid in nodes)
            dx, dy = self.BRANCH_DIRECTIONS[branch]
            norm = math.sqrt(dx * dx + dy * dy) or 1.0
            dx, dy = dx / norm, dy / norm
            pdx, pdy = -dy, dx

            by_depth: Dict[int, List[str]] = {}
            for tid in nodes:
                by_depth.setdefault(depths.get(tid, 0), []).append(tid)

            for d in sorted(by_depth.keys()):
                layer = by_depth[d]
                layer.sort(key=lambda tid: (tech_tree.get_tech(tid) or {}).get("nom", tid))
                forward = d - base_depth + 1.65
                bx = dx * step * forward
                by = dy * step * forward
                count = len(layer)
                for idx, tid in enumerate(layer):
                    side = (idx - (count - 1) / 2.0) * (self._node_radius * 1.95)
                    raw_centers[tid] = (bx + pdx * side, by + pdy * side)

        pad = self._node_radius + 10
        centers = self._fit_layout_in_rect(raw_centers, pad)
        centers = self._relax_layout(centers, pad)

        # Feu prend l'emplacement visuel d'Organisation_du_clan (swap explicite),
        # sans deplacer tout le reste de l'arbre.
        if "Feu" in centers and "Organisation_du_clan" in centers:
            centers["Feu"], centers["Organisation_du_clan"] = (
                centers["Organisation_du_clan"],
                centers["Feu"],
            )

        edges: List[Tuple[str, str]] = []
        for tid in tech_ids:
            deps = tech_tree.get_dependencies(tid)
            for dep in deps:
                if dep in centers and tid in centers:
                    edges.append((dep, tid))

        self._layout_centers = centers
        self._layout_edges = edges

        btn_style = ButtonStyle(
            draw_background=False,
            draw_border=False,
            padding_x=0,
            padding_y=0,
            font=self.node_font,
        )
        self._buttons = {}
        size = (self._node_radius * 2, self._node_radius * 2)
        for tech_id, center in self._layout_centers.items():
            btn = Button(
                text="",
                pos=center,
                size=size,
                anchor="center",
                style=btn_style,
                on_click=lambda _btn, tid=tech_id: self._start_research(tid),
            )
            self._buttons[tech_id] = btn

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
        if hasattr(tech_tree, "is_class_compatible") and not tech_tree.is_class_compatible(tech_id):
            required = getattr(tech_tree, "get_required_class", lambda _tid: None)(tech_id)
            if required:
                add_notification(f"Technologie reservee a la classe: {required}.")
            else:
                add_notification("Technologie incompatible avec la classe principale.")
            return
        if not tech_tree.can_start(tech_id):
            add_notification("Conditions non remplies pour cette technologie.")
            return
        if self.phase.start_tech_research(tech_id):
            return
        add_notification("Impossible de demarrer la recherche.")

    def handle(self, events):
        if not self.active:
            return
        screen = getattr(self.phase, "screen", None)
        if not screen:
            return
        self._refresh_fonts(screen.get_size())
        self._update_layout()

        self.back_btn.handle(events)
        self._hovered_tech = None
        for tech_id, btn in self._buttons.items():
            btn.handle(events)
            if btn.is_hovered:
                self._hovered_tech = tech_id

    def _hex_points(self, center: Tuple[int, int], radius: float) -> List[Tuple[int, int]]:
        cx, cy = float(center[0]), float(center[1])
        pts = []
        for i in range(6):
            ang = math.radians(30 + i * 60)
            pts.append((int(cx + math.cos(ang) * radius), int(cy + math.sin(ang) * radius)))
        return pts

    def _draw_hex_bg(self, screen):
        w, h = screen.get_size()
        for y in range(h):
            t = y / max(1, h - 1)
            c = _mix_color((22, 24, 30), (11, 13, 18), t)
            pygame.draw.line(screen, c, (0, y), (w, y))

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        r = 24
        dx = int(r * math.sqrt(3))
        dy = int(r * 1.5)
        rows = int(h / dy) + 3
        cols = int(w / dx) + 3
        for row in range(rows):
            oy = row * dy - r
            offset = (row % 2) * (dx // 2)
            for col in range(cols):
                ox = col * dx + offset - r
                pts = self._hex_points((ox, oy), r)
                pygame.draw.polygon(overlay, (108, 114, 126, 34), pts, 1)
        screen.blit(overlay, (0, 0))

    def _draw_header(self, screen):
        w, h = screen.get_size()
        margin = max(16, int(min(w, h) * 0.03))
        header_h = max(84, int(h * 0.14))
        rect = pygame.Rect(margin, margin, w - 2 * margin, header_h)
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel.fill((22, 24, 31, 214))
        screen.blit(panel, rect.topleft)
        pygame.draw.rect(screen, (150, 156, 167), rect, 2, border_radius=16)

        title_surf = self.title_font.render(self.title, True, (239, 240, 244))
        screen.blit(title_surf, (rect.x + 18, rect.y + 8))

        tech_tree = getattr(self.phase, "tech_tree", None)
        current = getattr(tech_tree, "current_research", None) if tech_tree else None
        innovations = int(getattr(tech_tree, "innovations", 0)) if tech_tree else 0
        current_class = str(getattr(getattr(self.phase, "espece", None), "main_class", "") or "").strip() or "aucune"
        info = f"Innovations: {innovations}  |  Classe: {current_class}"
        if current:
            info += f"  |  Recherche: {current}"
        info_surf = self.small_font.render(info, True, (199, 204, 213))
        screen.blit(info_surf, (rect.x + 18, rect.bottom - info_surf.get_height() - 12))

    def _draw_tree_panel(self, screen):
        panel = pygame.Surface((self._tree_rect.width, self._tree_rect.height), pygame.SRCALPHA)
        panel.fill((14, 16, 22, 176))
        screen.blit(panel, self._tree_rect.topleft)
        pygame.draw.rect(screen, (120, 126, 138), self._tree_rect, 2, border_radius=18)

    def _edge_color_for_child(self, child_id: str):
        branch = self._branch_for_tech(child_id)
        base = self.BRANCH_COLORS.get(branch, self.BRANCH_COLORS["common"])
        return _mix_color(base, (212, 218, 230), 0.28)

    def _draw_edges(self, screen):
        for parent, child in self._layout_edges:
            p = self._layout_centers.get(parent)
            c = self._layout_centers.get(child)
            if not p or not c:
                continue
            col = self._edge_color_for_child(child)
            pygame.draw.line(screen, _mix_color(col, (255, 255, 255), 0.30), p, c, 5)
            pygame.draw.line(screen, col, p, c, 2)

    def _draw_nodes(self, screen):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return
        now = pygame.time.get_ticks() / 1000.0
        for tech_id, center in self._layout_centers.items():
            state = self._state_for(tech_id)
            branch = self._branch_for_tech(tech_id)
            base = self.BRANCH_COLORS.get(branch, self.BRANCH_COLORS["common"])

            if state == "unlocked":
                fill = _mix_color(base, (232, 237, 244), 0.44)
                border = _mix_color(base, (245, 248, 252), 0.68)
            elif state == "research":
                pulse = 0.5 + 0.5 * math.sin(now * 4.2)
                fill = _mix_color(base, (210, 222, 242), 0.35 + pulse * 0.18)
                border = _mix_color(base, (255, 255, 255), 0.62)
            elif state == "available":
                fill = _mix_color(base, (24, 29, 37), 0.52)
                border = _mix_color(base, (228, 233, 242), 0.44)
            else:
                fill = _mix_color(base, (12, 14, 20), 0.84)
                border = _mix_color(base, (130, 136, 148), 0.24)

            if self._hovered_tech == tech_id:
                fill = _mix_color(fill, (241, 244, 249), 0.16)
                border = _mix_color(border, (255, 255, 255), 0.24)

            pts_outer = self._hex_points(center, self._node_radius + 3)
            pts_inner = self._hex_points(center, self._node_radius - 1)
            pygame.draw.polygon(screen, _mix_color(border, (255, 255, 255), 0.22), pts_outer)
            pygame.draw.polygon(screen, fill, pts_inner)
            pygame.draw.polygon(screen, border, pts_inner, 2)

            label = self._node_label(tech_id)
            txt = self.node_font.render(label, True, (240, 243, 247))
            screen.blit(txt, txt.get_rect(center=center))

            if state == "research":
                cost = max(0, int(tech_tree.get_cost(tech_id)))
                progress = int(getattr(tech_tree, "current_progress", 0))
                ratio = 1.0 if cost <= 0 else max(0.0, min(1.0, progress / cost))
                ring_r = self._node_radius + 9
                start = -math.pi / 2
                end = start + 2 * math.pi * ratio
                ring_rect = pygame.Rect(center[0] - ring_r, center[1] - ring_r, ring_r * 2, ring_r * 2)
                pygame.draw.arc(screen, (228, 236, 250), ring_rect, start, end, 3)

            if state == "locked":
                required = getattr(tech_tree, "get_required_class", lambda _tid: None)(tech_id)
                if required:
                    marker = (center[0] + self._node_radius - 8, center[1] + self._node_radius - 8)
                    pygame.draw.circle(screen, (20, 22, 28), marker, 6)
                    pygame.draw.circle(screen, (244, 160, 160), marker, 3)

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        words = str(text or "").split()
        if not words:
            return []
        lines = []
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

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
        deps_text = ", ".join(deps) if deps else "Aucun"
        required = getattr(tech_tree, "get_required_class", lambda _tid: None)(self._hovered_tech)
        required_text = required if required else "Toutes"

        lines = [str(tech.get("nom", self._hovered_tech))]
        lines.extend(self._wrap_text(str(tech.get("description", "")), self.tooltip_font, 320))
        lines.append(f"Cout: {tech_tree.get_cost(self._hovered_tech)}")
        lines.append(f"Prerequis: {deps_text}")
        lines.append(f"Classe: {required_text}")

        rendered = [self.tooltip_font.render(line, True, (237, 241, 248)) for line in lines if line]
        if not rendered:
            return

        pad = 10
        width = max(s.get_width() for s in rendered) + pad * 2
        height = sum(s.get_height() for s in rendered) + pad * 2
        mx, my = pygame.mouse.get_pos()
        rect = pygame.Rect(mx + 18, my + 18, width, height)

        sw, sh = screen.get_size()
        if rect.right > sw - 8:
            rect.x = sw - rect.width - 8
        if rect.bottom > sh - 8:
            rect.y = sh - rect.height - 8

        box = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        box.fill((24, 27, 35, 236))
        screen.blit(box, rect.topleft)
        pygame.draw.rect(screen, (156, 164, 178), rect, 2, border_radius=10)

        y = rect.y + pad
        for surf in rendered:
            screen.blit(surf, (rect.x + pad, y))
            y += surf.get_height()

    def draw(self, screen):
        if not self.active:
            return
        self._refresh_fonts(screen.get_size())
        self._update_layout()

        self._draw_hex_bg(screen)
        self._draw_header(screen)
        self._draw_tree_panel(screen)
        self._draw_edges(screen)
        self._draw_nodes(screen)
        self._draw_tooltip(screen)

        margin = max(16, int(min(screen.get_width(), screen.get_height()) * 0.03))
        self.back_btn.move_to((margin, screen.get_height() - margin))
        self.back_btn.draw(screen)
