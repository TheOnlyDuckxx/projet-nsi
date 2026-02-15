import math
import pygame

from Game.core.utils import Button, ButtonStyle


class SpeciesMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Menu Espece"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.section_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.text_font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 14)

        style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=16,
            padding_y=10,
            hover_zoom=1.04,
            font=self.text_font,
        )
        self.back_btn = Button("Retour", (0, 0), anchor="bottomleft", style=style, on_click=self._on_back)

        self.mutation_scroll = 0
        self._mutation_scroll_max = 0
        self._mutation_view_rect = pygame.Rect(0, 0, 0, 0)

    def open(self):
        self.active = True
        self.mutation_scroll = 0

    def close(self):
        self.active = False

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def handle(self, events):
        if not self.active:
            return
        self.back_btn.handle(events)

        for e in events:
            if e.type != pygame.MOUSEWHEEL:
                continue
            mx, my = pygame.mouse.get_pos()
            if self._mutation_view_rect.collidepoint((mx, my)):
                self.mutation_scroll = max(
                    0,
                    min(self.mutation_scroll - e.y * 34, self._mutation_scroll_max),
                )

    @staticmethod
    def _safe_number(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _safe_average(values):
        nums = [float(v) for v in values if isinstance(v, (int, float))]
        if not nums:
            return 0.0
        return sum(nums) / len(nums)

    def _wrap_text(self, text, max_width):
        words = str(text or "").split()
        if not words:
            return [""]
        lines = []
        cur = ""
        for word in words:
            candidate = f"{cur} {word}".strip()
            if self.small_font.size(candidate)[0] <= max_width:
                cur = candidate
                continue
            if cur:
                lines.append(cur)
            cur = word
        if cur:
            lines.append(cur)
        return lines

    def _collect_mutations(self, species):
        if not species or not getattr(species, "mutations", None):
            return []

        manager = species.mutations
        ids = []
        ids.extend(getattr(species, "base_mutations", []) or [])
        ids.extend(getattr(manager, "actives", []) or [])

        seen = set()
        out = []
        for mut_id in ids:
            if mut_id in seen:
                continue
            seen.add(mut_id)
            data = (getattr(manager, "data", {}) or {}).get(mut_id, {})
            out.append(
                {
                    "id": mut_id,
                    "nom": data.get("nom", mut_id),
                    "description": data.get("description", "Aucune description."),
                    "categorie": data.get("categorie", "inconnue"),
                }
            )
        return out

    def _competence_profile(self, species):
        if not species:
            return [
                ("Force", 0.0),
                ("Mobilite", 0.0),
                ("Perception", 0.0),
                ("Intellect", 0.0),
                ("Social", 0.0),
                ("Survie", 0.0),
                ("Genetique", 0.0),
            ]

        physique = getattr(species, "base_physique", {}) or {}
        sens = getattr(species, "base_sens", {}) or {}
        mental = getattr(species, "base_mental", {}) or {}
        social = getattr(species, "base_social", {}) or {}
        env = getattr(species, "base_environnement", {}) or {}
        genes = getattr(species, "genetique", {}) or {}

        mutation_rate = self._safe_number(genes.get("mutation_rate", 0.1), 0.1)
        genetics_score = self._safe_number(genes.get("taux_reproduction", 1.0), 1.0) * 8.0
        genetics_score += max(0.0, (1.0 - mutation_rate)) * 8.0

        values = [
            ("Force", self._safe_number(physique.get("force", 0))),
            (
                "Mobilite",
                self._safe_average(
                    [
                        physique.get("vitesse", 0),
                        physique.get("endurance", 0),
                        physique.get("taille", 0),
                    ]
                ),
            ),
            (
                "Perception",
                self._safe_average(
                    [
                        sens.get("vision", 0),
                        sens.get("ouie", 0),
                        sens.get("odorat", 0),
                    ]
                ),
            ),
            (
                "Intellect",
                self._safe_average(
                    [
                        mental.get("intelligence", 0),
                        mental.get("creativite", 0),
                        mental.get("dexterite", 0),
                    ]
                ),
            ),
            (
                "Social",
                self._safe_average(
                    [
                        social.get("communication", 0),
                        social.get("cohesion", 0),
                        social.get("charisme", 0),
                    ]
                ),
            ),
            (
                "Survie",
                self._safe_average(
                    [
                        env.get("adaptabilite", 0),
                        env.get("resistance_aux_maladies", 0),
                        env.get("resistance_chaleur", 0),
                    ]
                ),
            ),
            ("Genetique", genetics_score),
        ]

        clamped = []
        for label, value in values:
            clamped.append((label, max(0.0, min(20.0, float(value)))))
        return clamped

    def _draw_info_card(self, screen, rect, species):
        pygame.draw.rect(screen, (23, 40, 50), rect, border_radius=16)
        pygame.draw.rect(screen, (86, 133, 153), rect, 2, border_radius=16)

        title = self.section_font.render("Identite", True, (238, 246, 255))
        screen.blit(title, (rect.x + 16, rect.y + 14))

        if not species:
            msg = self.text_font.render("Aucune espece chargee.", True, (224, 224, 224))
            screen.blit(msg, (rect.x + 16, rect.y + 58))
            return

        day_cycle = getattr(self.phase, "day_night", None)
        days = int(getattr(day_cycle, "jour", 0)) if day_cycle else 0
        time_string = day_cycle.get_time_string() if day_cycle else "--:--"
        happiness = int(getattr(self.phase, "happiness", 0))

        lines = [
            ("Nom", getattr(species, "nom", "Inconnue")),
            ("Population", f"{getattr(species, 'population', 0)}"),
            ("Niveau", f"{getattr(species, 'species_level', 1)}"),
            ("XP", f"{int(getattr(species, 'xp', 0))}/{int(getattr(species, 'xp_to_next', 1))}"),
            ("Jours ecoules", f"{days}"),
            ("Heure locale", time_string),
            ("Bonheur global", f"{happiness}"),
        ]

        y = rect.y + 54
        for key, value in lines:
            key_surf = self.small_font.render(f"{key} :", True, (156, 200, 221))
            val_surf = self.text_font.render(str(value), True, (245, 245, 245))
            screen.blit(key_surf, (rect.x + 16, y))
            screen.blit(val_surf, (rect.x + 18, y + 18))
            y += max(44, val_surf.get_height() + 26)

    def _draw_radar(self, screen, rect, profile):
        pygame.draw.rect(screen, (18, 34, 43), rect, border_radius=16)
        pygame.draw.rect(screen, (72, 140, 170), rect, 2, border_radius=16)

        title = self.section_font.render("Competences principales", True, (238, 246, 255))
        screen.blit(title, (rect.x + 18, rect.y + 12))

        labels = [label for label, _ in profile]
        values = [value for _, value in profile]
        if not labels:
            return

        center_x = rect.centerx
        center_y = rect.y + int(rect.height * 0.56)
        radius = int(min(rect.width, rect.height) * 0.30)
        max_value = 20.0
        rings = 4

        for ring in range(1, rings + 1):
            rr = int(radius * ring / rings)
            alpha = 60 + ring * 25
            pygame.draw.circle(screen, (63, 106, 130, alpha), (center_x, center_y), rr, 1)

        points = []
        for i, value in enumerate(values):
            angle = -math.pi / 2 + i * (2 * math.pi / len(values))
            ratio = max(0.0, min(1.0, value / max_value))
            x = center_x + int(math.cos(angle) * radius * ratio)
            y = center_y + int(math.sin(angle) * radius * ratio)
            points.append((x, y))

            axis_x = center_x + int(math.cos(angle) * radius)
            axis_y = center_y + int(math.sin(angle) * radius)
            pygame.draw.line(screen, (58, 92, 113), (center_x, center_y), (axis_x, axis_y), 1)

            label_surf = self.small_font.render(labels[i], True, (210, 230, 242))
            lx = center_x + int(math.cos(angle) * (radius + 24)) - label_surf.get_width() // 2
            ly = center_y + int(math.sin(angle) * (radius + 24)) - label_surf.get_height() // 2
            screen.blit(label_surf, (lx, ly))

        if len(points) >= 3:
            shape = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            shifted = [(x - rect.x, y - rect.y) for x, y in points]
            pygame.draw.polygon(shape, (108, 205, 174, 88), shifted)
            screen.blit(shape, rect.topleft)
            pygame.draw.polygon(screen, (128, 228, 196), points, 2)

        for x, y in points:
            pygame.draw.circle(screen, (230, 247, 240), (x, y), 4)

    def _draw_mutations(self, screen, rect, mutations):
        pygame.draw.rect(screen, (22, 34, 46), rect, border_radius=16)
        pygame.draw.rect(screen, (82, 126, 156), rect, 2, border_radius=16)

        title = self.section_font.render("Mutations", True, (238, 246, 255))
        screen.blit(title, (rect.x + 18, rect.y + 12))

        inner = rect.inflate(-20, -56)
        inner.y += 26
        self._mutation_view_rect = inner

        if not mutations:
            self._mutation_scroll_max = 0
            self.mutation_scroll = 0
            msg = self.text_font.render("Aucune mutation active.", True, (208, 208, 208))
            screen.blit(msg, (inner.x + 8, inner.y + 8))
            return

        card_gap = 10
        content_h = 0
        card_heights = []
        for mut in mutations:
            desc_lines = self._wrap_text(mut["description"], max(40, inner.width - 26))
            card_h = 54 + len(desc_lines) * (self.small_font.get_height() + 2)
            card_heights.append((card_h, desc_lines, mut))
            content_h += card_h + card_gap
        content_h = max(0, content_h - card_gap)

        self._mutation_scroll_max = max(0, content_h - inner.height)
        self.mutation_scroll = max(0, min(self.mutation_scroll, self._mutation_scroll_max))

        prev_clip = screen.get_clip()
        screen.set_clip(inner)

        y = inner.y - self.mutation_scroll
        for card_h, desc_lines, mut in card_heights:
            card = pygame.Rect(inner.x + 4, y, inner.width - 8, card_h)
            pygame.draw.rect(screen, (31, 48, 64), card, border_radius=10)
            pygame.draw.rect(screen, (102, 148, 176), card, 1, border_radius=10)

            name_surf = self.text_font.render(mut["nom"], True, (242, 246, 251))
            cat_surf = self.small_font.render(f"categorie: {mut['categorie']}", True, (172, 203, 226))
            screen.blit(name_surf, (card.x + 10, card.y + 8))
            screen.blit(cat_surf, (card.x + 10, card.y + 8 + name_surf.get_height()))

            ty = card.y + 8 + name_surf.get_height() + cat_surf.get_height() + 6
            for line in desc_lines:
                line_surf = self.small_font.render(line, True, (220, 230, 238))
                screen.blit(line_surf, (card.x + 10, ty))
                ty += line_surf.get_height() + 2

            y += card_h + card_gap

        screen.set_clip(prev_clip)

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = max(14, int(min(w, h) * 0.03))
        top_h = max(74, int(h * 0.12))

        self.title_font = pygame.font.SysFont("consolas", max(28, int(h * 0.055)), bold=True)
        self.section_font = pygame.font.SysFont("consolas", max(18, int(h * 0.033)), bold=True)
        self.text_font = pygame.font.SysFont("consolas", max(14, int(h * 0.024)))
        self.small_font = pygame.font.SysFont("consolas", max(12, int(h * 0.019)))
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(16, int(h * 0.03)), bold=True)
        self.back_btn._rebuild_surfaces()

        # Background with a simple vertical gradient.
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(12 + 16 * t)
            g = int(22 + 30 * t)
            b = int(30 + 26 * t)
            pygame.draw.line(screen, (r, g, b), (0, y), (w, y))

        header_rect = pygame.Rect(margin, margin, w - 2 * margin, top_h)
        pygame.draw.rect(screen, (17, 48, 64), header_rect, border_radius=16)
        pygame.draw.rect(screen, (94, 160, 190), header_rect, 2, border_radius=16)

        title_surf = self.title_font.render(self.title, True, (244, 252, 255))
        subtitle_surf = self.small_font.render(
            "Informations detaillees de votre espece actuelle",
            True,
            (190, 224, 240),
        )
        screen.blit(title_surf, (header_rect.x + 18, header_rect.y + 10))
        screen.blit(subtitle_surf, (header_rect.x + 18, header_rect.bottom - subtitle_surf.get_height() - 12))

        content_rect = pygame.Rect(
            margin,
            header_rect.bottom + margin // 2,
            w - 2 * margin,
            h - header_rect.bottom - int(margin * 1.8),
        )

        left_w = int(content_rect.width * 0.34)
        left_rect = pygame.Rect(content_rect.x, content_rect.y, left_w, content_rect.height)
        right_rect = pygame.Rect(content_rect.x + left_w + margin // 2, content_rect.y, content_rect.width - left_w - margin // 2, content_rect.height)

        radar_h = int(right_rect.height * 0.50)
        radar_rect = pygame.Rect(right_rect.x, right_rect.y, right_rect.width, radar_h)
        mutations_rect = pygame.Rect(right_rect.x, radar_rect.bottom + margin // 2, right_rect.width, right_rect.height - radar_h - margin // 2)

        species = getattr(self.phase, "espece", None)
        profile = self._competence_profile(species)
        mutations = self._collect_mutations(species)

        self._draw_info_card(screen, left_rect, species)
        self._draw_radar(screen, radar_rect, profile)
        self._draw_mutations(screen, mutations_rect, mutations)

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
