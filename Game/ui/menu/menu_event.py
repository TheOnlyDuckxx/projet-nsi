import pygame
from typing import List, Tuple

from Game.core.utils import Button, ButtonStyle


class EventMenu:
    """
    Menu permettant de consulter et résoudre les évènements en cours.
    - Liste triée (non résolus en haut, puis historique)
    - Sélection d'un évènement pour lire le détail
    - Choix associés (grisés si requirements non remplis)
    """

    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False

        if not pygame.font.get_init():
            pygame.font.init()

        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.section_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.text_font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 14)

        style = ButtonStyle(draw_background=True, radius=12, padding_x=16, padding_y=10, hover_zoom=1.04, font=self.text_font)
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

        self.selected_event_id = None
        self.event_rects: List[Tuple[pygame.Rect, str]] = []
        self.choice_buttons: List[Button] = []

    # ---------- API ----------
    def open(self):
        self.active = True

    def close(self):
        self.active = False
        self.selected_event_id = None

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    # ---------- Interaction ----------
    def _refresh_layout(self, screen_size):
        # Recalcule police dépendant de la taille
        w, h = screen_size
        self.title_font = pygame.font.SysFont("consolas", max(30, int(h * 0.06)), bold=True)
        self.section_font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)
        self.text_font = pygame.font.SysFont("consolas", max(14, int(h * 0.03)))
        self.small_font = pygame.font.SysFont("consolas", max(12, int(h * 0.025)))
        self.back_btn.style.font = self.text_font

    def handle(self, events):
        if not self.active:
            return

        screen = self.phase.screen
        self._refresh_layout(screen.get_size())
        self._compute_event_rects(screen.get_size())
        self.back_btn.handle(events)

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                pos = e.pos
                # Sélection d'un évènement dans la liste
                for rect, ev_id in self.event_rects:
                    if rect.collidepoint(pos):
                        self.selected_event_id = ev_id
                        inst = self.phase.event_manager.instances.get(ev_id)
                        if inst:
                            inst.is_new = False
                        break
            # Choix (boutons)
        for btn in self.choice_buttons:
            if btn.handle(events):
                pass

    # ---------- Dessin ----------
    def draw(self, screen):
        if not self.active:
            return

        self._refresh_layout(screen.get_size())
        w, h = screen.get_size()
        margin = int(min(w, h) * 0.04)
        list_w = int(w * 0.38)

        screen.fill((35, 38, 48))

        title_surf = self.title_font.render("Évènements", True, (245, 245, 245))
        screen.blit(title_surf, (margin, margin))

        # Liste des évènements
        events = self.phase.event_manager.get_sorted_events()
        list_rect = pygame.Rect(margin, margin * 2, list_w, h - margin * 3)
        pygame.draw.rect(screen, (45, 48, 60), list_rect, border_radius=12)
        pygame.draw.rect(screen, (90, 95, 110), list_rect, 2, border_radius=12)

        self._draw_event_list(screen, list_rect, events)

        # Zone détail
        detail_rect = pygame.Rect(list_rect.right + margin, margin * 2, w - list_rect.right - 2 * margin, h - margin * 3)
        pygame.draw.rect(screen, (28, 30, 38), detail_rect, border_radius=12)
        pygame.draw.rect(screen, (80, 85, 96), detail_rect, 2, border_radius=12)

        self._draw_detail(screen, detail_rect, events)

        # Bouton retour
        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)

    # ---------- Helpers ----------
    def _draw_event_list(self, screen, list_rect, events):
        self.event_rects = []
        padding = 12
        row_h = 72
        y = list_rect.top + padding

        for inst in events:
            if y + row_h > list_rect.bottom:
                break
            rect = pygame.Rect(list_rect.left + padding, y, list_rect.width - 2 * padding, row_h)
            is_selected = inst.definition_id == self.selected_event_id
            bg = (75, 80, 98) if is_selected else (58, 62, 78)
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            pygame.draw.rect(screen, (120, 126, 150), rect, 1, border_radius=10)

            definition = self.phase.event_manager.get_definition(inst.definition_id)
            title = definition.title if definition else inst.definition_id
            title_surf = self.section_font.render(title, True, (245, 245, 245))
            screen.blit(title_surf, (rect.x + 10, rect.y + 8))

            state_color = (240, 200, 90) if inst.state in {"new", "active"} else (160, 170, 200)
            state_text = inst.state.upper()
            state_surf = self.text_font.render(state_text, True, state_color)
            screen.blit(state_surf, (rect.x + 10, rect.y + 36))

            if inst.is_new and inst.state in {"new", "active"}:
                new_badge = self.small_font.render("NOUVEAU", True, (30, 30, 30))
                badge_bg = pygame.Surface((new_badge.get_width() + 10, new_badge.get_height() + 6))
                badge_bg.fill((120, 230, 150))
                badge_bg.blit(new_badge, (5, 3))
                screen.blit(badge_bg, (rect.right - badge_bg.get_width() - 8, rect.y + 10))

            self.event_rects.append((rect, inst.definition_id))
            y += row_h + padding

    def _wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test_line = current + (" " if current else "") + word
            if font.size(test_line)[0] <= max_width:
                current = test_line
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _compute_event_rects(self, screen_size):
        # Aligné sur le rendu (même calcul que _draw_event_list)
        w, h = screen_size
        margin = int(min(w, h) * 0.04)
        list_w = int(w * 0.38)
        list_rect = pygame.Rect(margin, margin * 2, list_w, h - margin * 3)
        padding = 12
        row_h = 72
        y = list_rect.top + padding
        events = self.phase.event_manager.get_sorted_events()
        rects = []
        for inst in events:
            if y + row_h > list_rect.bottom:
                break
            rect = pygame.Rect(list_rect.left + padding, y, list_rect.width - 2 * padding, row_h)
            rects.append((rect, inst.definition_id))
            y += row_h + padding
        self.event_rects = rects

    def _draw_detail(self, screen, rect, events):
        if not self.selected_event_id and events:
            self.selected_event_id = events[0].definition_id
            events[0].is_new = False
        if not self.selected_event_id:
            info = self.text_font.render("Sélectionnez un évènement pour voir les détails.", True, (210, 210, 210))
            screen.blit(info, info.get_rect(center=rect.center))
            return

        inst = self.phase.event_manager.instances.get(self.selected_event_id)
        definition = self.phase.event_manager.get_definition(self.selected_event_id)
        if inst is None or definition is None:
            info = self.text_font.render("Évènement introuvable.", True, (210, 210, 210))
            screen.blit(info, info.get_rect(center=rect.center))
            return

        padding = 16
        x = rect.x + padding
        y = rect.y + padding
        max_w = rect.width - 2 * padding

        title = self.section_font.render(definition.title, True, (245, 245, 245))
        screen.blit(title, (x, y))
        y += title.get_height() + 8

        state_text = f"État : {inst.state}"
        state_surf = self.text_font.render(state_text, True, (180, 190, 210))
        screen.blit(state_surf, (x, y))
        y += state_surf.get_height() + 12

        lines = self._wrap_text(definition.long_text, self.text_font, max_w)
        for line in lines:
            line_surf = self.text_font.render(line, True, (220, 220, 220))
            screen.blit(line_surf, (x, y))
            y += line_surf.get_height() + 4

        y += 12
        choices_title = self.section_font.render("Choix", True, (245, 245, 245))
        screen.blit(choices_title, (x, y))
        y += choices_title.get_height() + 6

        self.choice_buttons = []
        for choice in definition.choices:
            enabled = True
            if choice.requirements:
                enabled = self.phase.event_manager._evaluate_condition(choice.requirements, self.phase, inst.definition_id)

            btn = Button(
                choice.label,
                pos=(x, y),
                anchor="topleft",
                style=ButtonStyle(
                    draw_background=True,
                    radius=10,
                    padding_x=12,
                    padding_y=8,
                    hover_zoom=1.03,
                    font=self.text_font,
                ),
                on_click=lambda _b, cid=choice.id: self.phase.event_manager.resolve_event(inst.definition_id, cid, self.phase),
                enabled=enabled and inst.state in {"active", "new"},
            )
            btn.draw(screen)
            self.choice_buttons.append(btn)

            y += btn.rect.height + 4
            if choice.description:
                desc_lines = self._wrap_text(choice.description, self.small_font, max_w)
                for dl in desc_lines:
                    d_surf = self.small_font.render(dl, True, (200, 200, 200))
                    screen.blit(d_surf, (x + 6, y))
                    y += d_surf.get_height() + 2
            y += 10
