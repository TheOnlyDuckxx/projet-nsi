# LEVEL_UP.PY
# Gere la montee de niveau de l'espece du joueur

import pygame


_RARITY_COLORS = {
    "commun": (80, 185, 90),       # vert
    "rare": (80, 130, 220),        # bleu
    "epique": (150, 95, 220),      # violet
    "legendaire": (230, 200, 70),  # jaune
}


class LevelUp:
    """
    Gere le menu de montee de niveau d'ESPECE:
    - quand l'espece monte de niveau, on ouvre un menu
    - met le jeu en pause
    - le joueur choisit une mutation parmi 5
    """

    def __init__(self, espece):
        self.espece = espece
        self.current_level = espece.species_level

        self.active = False
        self.choices = []
        self.card_rects = []

        self.font_title = None
        self.font_mutation = None
        self.font_tooltip = None

        # Hover / selection
        self.hover_index = None
        self.selected_index = None
        self.selection_time_ms = 0
        self.selection_duration_ms = 1200

    def update_level(self, new_lvl):
        """
        Declenche un nouveau "level up":
        genere 5 mutations et active le menu.
        """
        if new_lvl <= self.current_level:
            return

        self.current_level = new_lvl
        self._generate_choices()
        self.active = True
        self.selected_index = None
        self.selection_time_ms = 0

    def _generate_choices(self):
        """
        Tire jusqu'a 5 mutations disponibles, sans doublon.
        Utilise le MutationManager de l'espece.
        """
        manager = self.espece.mutations
        self.choices = manager.pick_available_mutations(max_count=5)

    def handle_event(self, event, screen):
        """
        A appeler depuis la boucle d'evenements Pygame.
        Quand le joueur clique sur une carte, on applique la mutation puis on lance une animation avant de fermer.
        """
        if not self.active:
            return

        if self.selected_index is not None:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            self.card_rects = self._compute_card_rects(screen)

            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(mouse_pos) and i < len(self.choices):
                    mutation_nom = self.choices[i]
                    self.espece.mutations.appliquer(mutation_nom)
                    self.selected_index = i
                    self.selection_time_ms = pygame.time.get_ticks()
                    return

    def _rarity_for(self, mutation_data: dict | None) -> str:
        rarity = str((mutation_data or {}).get("rarete", "commun")).strip().lower()
        return rarity if rarity in _RARITY_COLORS else "commun"

    def _positive_effect_lines(self, mutation_data: dict | None) -> list[str]:
        effects = (mutation_data or {}).get("effets", {}) or {}
        lines: list[str] = []
        for category, stats in effects.items():
            if not isinstance(stats, dict):
                continue
            for stat, value in stats.items():
                if not isinstance(value, (int, float)):
                    continue
                if float(value) <= 0:
                    continue
                lines.append(f"{category}.{stat}: +{value:g}")
        return lines

    def _draw_tooltip(self, screen, mouse_pos, mutation_name: str, mutation_data: dict | None):
        if self.font_tooltip is None:
            self.font_tooltip = pygame.font.SysFont("arial", 16)

        label = (mutation_data or {}).get("nom", mutation_name)
        lines = [str(label)]
        rarity = self._rarity_for(mutation_data)
        lines.append(f"Rareté: {rarity}")
        effect_lines = self._positive_effect_lines(mutation_data)
        if effect_lines:
            lines.append("Bonus:")
            lines.extend(effect_lines[:8])
        else:
            lines.append("Aucun bonus direct.")

        rendered = [self.font_tooltip.render(line, True, (245, 245, 245)) for line in lines]
        width = max((surf.get_width() for surf in rendered), default=120) + 16
        line_h = self.font_tooltip.get_height()
        height = max(48, len(rendered) * (line_h + 2) + 12)

        x, y = mouse_pos[0] + 14, mouse_pos[1] + 14
        sw, sh = screen.get_size()
        if x + width > sw - 8:
            x = sw - width - 8
        if y + height > sh - 8:
            y = sh - height - 8

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((18, 22, 30, 235))
        pygame.draw.rect(panel, _RARITY_COLORS[rarity], panel.get_rect(), 2, border_radius=8)

        yy = 8
        for surf in rendered:
            panel.blit(surf, (8, yy))
            yy += line_h + 2

        screen.blit(panel, (x, y))

    def render(self, screen, assets):
        """
        Dessine l'overlay de montee de niveau + 5 cartes de mutation.
        """
        if not self.active:
            return

        if self.font_title is None:
            self.font_title = pygame.font.SysFont("arial", 32, bold=True)
        if self.font_mutation is None:
            self.font_mutation = pygame.font.SysFont("arial", 18)
        if self.font_tooltip is None:
            self.font_tooltip = pygame.font.SysFont("arial", 16)

        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        titre = f"Niveau d'espece {self.current_level} atteint !"
        txt_surface = self.font_title.render(titre, True, (255, 255, 255))
        txt_rect = txt_surface.get_rect(center=(w // 2, h // 6))
        screen.blit(txt_surface, txt_rect)

        sous_titre_surface = self.font_mutation.render(
            "Choisissez une mutation pour votre espece",
            True,
            (220, 220, 220),
        )
        sous_titre_rect = sous_titre_surface.get_rect(center=(w // 2, h // 6 + 40))
        screen.blit(sous_titre_surface, sous_titre_rect)

        self.card_rects = self._compute_card_rects(screen)

        now_ms = pygame.time.get_ticks()
        elapsed_ms = 0
        t_norm = 0.0
        if self.selected_index is not None and self.selection_time_ms:
            elapsed_ms = now_ms - self.selection_time_ms
            t_norm = min(1.0, elapsed_ms / self.selection_duration_ms)
            if elapsed_ms >= self.selection_duration_ms:
                self.active = False
                self.selected_index = None
                return

        mouse_pos = pygame.mouse.get_pos()
        self.hover_index = None
        if self.selected_index is None:
            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(mouse_pos):
                    self.hover_index = i
                    break

        for i, rect in enumerate(self.card_rects):
            if i >= len(self.choices):
                break

            mutation_name = self.choices[i]
            mutation_data = self.espece.mutations.get_mutation(mutation_name)
            rarity = self._rarity_for(mutation_data)
            color = _RARITY_COLORS[rarity]

            draw_rect = rect.copy()
            scale = 1.0

            if self.selected_index is not None:
                if i == self.selected_index:
                    scale = 1.0 + 0.25 * (1.0 - (t_norm - 1.0) ** 2)
                else:
                    scale = 0.9
            elif self.hover_index == i:
                scale = 1.1

            if scale != 1.0:
                new_w = int(rect.width * scale)
                new_h = int(rect.height * scale)
                draw_rect.width = new_w
                draw_rect.height = new_h
                draw_rect.center = rect.center

            body_rect = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.width, max(1, draw_rect.height - 30))
            pygame.draw.rect(screen, color, body_rect, border_radius=12)
            pygame.draw.rect(screen, (245, 245, 245), body_rect, 2, border_radius=12)

            label = mutation_data.get("nom", mutation_name) if mutation_data else mutation_name
            text_surface = self.font_mutation.render(label, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(draw_rect.centerx, draw_rect.bottom - 15))
            screen.blit(text_surface, text_rect)

        if self.hover_index is not None and self.selected_index is None and self.hover_index < len(self.choices):
            mutation_name = self.choices[self.hover_index]
            mutation_data = self.espece.mutations.get_mutation(mutation_name)
            self._draw_tooltip(screen, mouse_pos, mutation_name, mutation_data)

        if self.selected_index is not None:
            flash_strength = max(0.0, 1.0 - t_norm * 2.0)
            if flash_strength > 0.0:
                flash_alpha = int(80 * flash_strength)
                flash_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                flash_surface.fill((255, 255, 255, flash_alpha))
                screen.blit(flash_surface, (0, 0))

    def _compute_card_rects(self, screen):
        """Calcul de la position des cartes."""
        w, h = screen.get_size()

        card_width = int(w * 0.12)
        card_height = int(h * 0.35)

        total_width = 5 * card_width + 4 * 20
        start_x = (w - total_width) // 2
        y = int(h * 0.35)

        rects = []
        for i in range(5):
            x = start_x + i * (card_width + 20)
            rects.append(pygame.Rect(x, y, card_width, card_height))
        return rects
