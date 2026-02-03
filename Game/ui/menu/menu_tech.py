import pygame
from Game.core.utils import Button, ButtonStyle
from Game.ui.hud.notification import add_notification

class TechMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False
        self.scroll_x = 0
        self._max_scroll_x = 0
        self.bubble_buttons = {}
        self._layout_key = None
        self._layout_centers = {}
        self._layout_edges = []
        self._hovered_tech = None

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Menu Technologies"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.btn_font = pygame.font.SysFont("consolas", 26, bold=True)
        self.tooltip_font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 18, bold=True)

        style = ButtonStyle(draw_background=True, radius=12, padding_x=16, padding_y=10, hover_zoom=1.04, font=self.btn_font)
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

    def open(self): self.active = True
    def close(self): self.active = False

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def handle(self, events):
        if self.active:
            self._handle_scroll_input(events)
            self._update_layout()
            self.back_btn.handle(events)
            self._hovered_tech = None
            for tech_id, btn in self.bubble_buttons.items():
                btn.handle(events)
                if btn.is_hovered:
                    self._hovered_tech = tech_id

    def _get_root_techs(self):
        techs = getattr(self.phase, "tech_tree", None)
        if not techs:
            return []
        return [tid for tid, data in techs.techs.items() if not data.get("conditions")]

    def _update_layout(self):
        screen = getattr(self.phase, "screen", None)
        if not screen:
            return
        w, h = screen.get_size()
        bubble_radius = max(28, int(min(w, h) * 0.07))
        tech_tree = getattr(self.phase, "tech_tree", None)
        techs_count = len(getattr(tech_tree, "techs", {}) or {})
        layout_key = (w, h, bubble_radius, techs_count, self.scroll_x)
        if self._layout_key == layout_key:
            return
        self._layout_key = layout_key

        margin = int(min(w, h) * 0.04)
        root_x = margin + bubble_radius + 10
        root_y = int(h * 0.5)
        child_x = root_x + int(w * 0.5)

        roots = self._get_root_techs()
        root_id = roots[0] if roots else None
        children = []
        if root_id and tech_tree:
            for tech_id, data in tech_tree.techs.items():
                if root_id in (data.get("conditions") or []):
                    children.append(tech_id)

        child_offset = int(h * 0.18)
        centers = {}
        edges = []
        if root_id:
            centers[root_id] = (root_x, root_y)
            for idx, tech_id in enumerate(children):
                y = root_y + (idx - (len(children) - 1) / 2) * child_offset
                centers[tech_id] = (child_x, int(y))
                edges.append((root_id, tech_id))

        tree_width = child_x + bubble_radius + margin
        view_width = w - margin
        self._max_scroll_x = max(0, tree_width - view_width)
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x))

        def apply_scroll(center):
            return (center[0] - self.scroll_x, center[1])

        self._layout_centers = {tid: apply_scroll(center) for tid, center in centers.items()}
        self._layout_edges = edges

        bubble_style = ButtonStyle(draw_background=False, draw_border=False, padding_x=0, padding_y=0, font=self.btn_font)
        self.bubble_buttons = {}
        for tech_id, center in self._layout_centers.items():
            btn = Button(
                text="",
                pos=center,
                size=(bubble_radius * 2, bubble_radius * 2),
                anchor="center",
                style=bubble_style,
                on_click=lambda _btn, tid=tech_id: self._start_research(tid),
            )
            self.bubble_buttons[tech_id] = btn

    def _start_research(self, tech_id: str):
        tech_tree = getattr(self.phase, "tech_tree", None)
        if not tech_tree:
            return
        if tech_id in tech_tree.unlocked:
            add_notification("Cette technologie est déjà débloquée.")
            return
        if tech_tree.current_research and tech_tree.current_research != tech_id:
            add_notification("Une recherche est déjà en cours.")
            return
        if not tech_tree.can_start(tech_id):
            add_notification("Conditions non remplies pour cette technologie.")
            return
        if self.phase.start_tech_research(tech_id):
            return
        add_notification("Impossible de démarrer la recherche.")

    def _scroll_tree(self, delta: int):
        if self._max_scroll_x <= 0:
            self.scroll_x = 0
            return
        self.scroll_x = max(0, min(self.scroll_x + delta, self._max_scroll_x))

    def _handle_scroll_input(self, events):
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                # Utiliser la molette pour défiler horizontalement dans l'arbre
                self._scroll_tree(-e.y * 40)

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = int(min(w, h) * 0.04)

        self.title_font = pygame.font.SysFont("consolas", max(28, int(h * 0.06)), bold=True)
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)

        screen.fill((60, 60, 65))  # gris neutre

        title_surf = self.title_font.render(self.title, True, (245, 245, 245))
        title_rect = title_surf.get_rect(midtop=(w // 2, margin))
        screen.blit(title_surf, title_rect)

        bubble_radius = max(28, int(min(w, h) * 0.07))
        bubble_font = pygame.font.SysFont("consolas", max(16, int(bubble_radius * 0.55)), bold=True)
        bubble_color = (90, 90, 95)
        bubble_border = (220, 220, 220)
        line_color = (180, 180, 190)

        self._update_layout()
        for parent, child in self._layout_edges:
            p_center = self._layout_centers.get(parent)
            c_center = self._layout_centers.get(child)
            if p_center and c_center:
                pygame.draw.line(screen, line_color, p_center, c_center, 4)

        def draw_bubble(center, label, state):
            color = bubble_color
            border = bubble_border
            if state == "unlocked":
                color = (70, 130, 70)
            elif state == "research":
                color = (80, 110, 160)
            elif state == "locked":
                color = (70, 70, 75)
            pygame.draw.circle(screen, color, center, bubble_radius)
            pygame.draw.circle(screen, border, center, bubble_radius, 3)
            text = bubble_font.render(label, True, (245, 245, 245))
            text_rect = text.get_rect(center=center)
            screen.blit(text, text_rect)

        tech_tree = getattr(self.phase, "tech_tree", None)
        for tech_id, center in self._layout_centers.items():
            tech = tech_tree.get_tech(tech_id) if tech_tree else {}
            label = tech.get("nom", tech_id)
            state = "locked"
            if tech_tree:
                if tech_id in tech_tree.unlocked:
                    state = "unlocked"
                elif tech_tree.current_research == tech_id:
                    state = "research"
            draw_bubble(center, label.upper(), state)
            if tech_tree and tech_tree.current_research == tech_id:
                cost = tech_tree.get_cost(tech_id)
                progress = tech_tree.current_progress
                progress_text = self.small_font.render(f"{progress}/{cost}", True, (240, 240, 240))
                progress_rect = progress_text.get_rect(midtop=(center[0], center[1] + bubble_radius + 6))
                screen.blit(progress_text, progress_rect)

        if tech_tree:
            info_text = f"Innovations: {tech_tree.innovations}"
            info_surf = self.small_font.render(info_text, True, (240, 240, 240))
            screen.blit(info_surf, (margin, margin + 52))

        if self._hovered_tech and tech_tree:
            tech = tech_tree.get_tech(self._hovered_tech)
            tooltip_lines = [
                tech.get("nom", self._hovered_tech),
                tech.get("description", ""),
            ]
            tooltip_lines = [line for line in tooltip_lines if line]
            if tooltip_lines:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                padding = 10
                rendered = [self.tooltip_font.render(line, True, (240, 240, 240)) for line in tooltip_lines]
                width = max(surf.get_width() for surf in rendered) + padding * 2
                height = sum(surf.get_height() for surf in rendered) + padding * 2
                rect = pygame.Rect(mouse_x + 16, mouse_y + 16, width, height)
                pygame.draw.rect(screen, (40, 40, 45), rect, border_radius=8)
                pygame.draw.rect(screen, (120, 120, 130), rect, 2, border_radius=8)
                y = rect.y + padding
                for surf in rendered:
                    screen.blit(surf, (rect.x + padding, y))
                    y += surf.get_height()

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
