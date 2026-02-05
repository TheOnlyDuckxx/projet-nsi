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

        self.title_font = app.assets.get_font("MightySouly", 64)
        self.value_font = app.assets.get_font("MightySouly", 28)
        self.small_font = app.assets.get_font("MightySouly", 22)

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

    def enter(self, **kwargs):
        self.summary = kwargs.get("summary", {}) or {}
        self.reason = str(kwargs.get("reason", ""))
        self.xp_gain = int(kwargs.get("xp_gain", 0) or 0)
        self._save_path = kwargs.get("save_path")

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

    def handle_input(self, events):
        self.btn_continue.handle(events)

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

    def render(self, screen):
        screen.blit(self.bg, (0, 0))
        screen.blit(self._overlay, (0, 0))

        title_surf = self.title_font.render(self.title, True, (230, 230, 230))
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 50))

        panel_w = int(WIDTH * 0.48)
        panel_h = int(HEIGHT * 0.55)
        panel_x = WIDTH // 2 - panel_w // 2
        panel_y = int(HEIGHT * 0.2)
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(screen, (24, 28, 38), panel, border_radius=16)
        pygame.draw.rect(screen, (70, 82, 96), panel, 2, border_radius=16)

        left = pygame.Rect(panel.left + 30, panel.top + 30, panel.width - 60, int(panel.height * 0.55))
        right = pygame.Rect(panel.left + 30, left.bottom + 10, panel.width - 60, int(panel.height * 0.35))

        self._draw_summary(screen, left)
        self._draw_xp_bar(screen, right)

        self.btn_continue.draw(screen)
