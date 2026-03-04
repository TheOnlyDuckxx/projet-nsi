import pygame

from Game.core.utils import Button, ButtonStyle


class HistoryMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False
        self.scroll = 0
        self.max_scroll = 0

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Historique"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.text_font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.btn_font = pygame.font.SysFont("consolas", 26, bold=True)

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

    def close(self):
        self.active = False
        self.scroll = 0

    def _on_back(self, _btn):
        if self.on_close:
            self.on_close()

    def _scroll(self, delta):
        self.scroll = max(0, min(self.scroll + int(delta), self.max_scroll))

    def handle(self, events):
        if not self.active:
            return
        self.back_btn.handle(events)
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                self._scroll(-e.y * 40)
            elif e.type == pygame.KEYDOWN and e.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                self._scroll(40)
            elif e.type == pygame.KEYDOWN and e.key in (pygame.K_UP, pygame.K_PAGEUP):
                self._scroll(-40)

    def _entry_text(self, entry: dict) -> str:
        day = int(entry.get("day", 0) or 0)
        hour = int(entry.get("hour", 0) or 0)
        minute = int(entry.get("minute", 0) or 0)
        category = str(entry.get("category", "event"))
        message = str(entry.get("message", ""))
        return f"Jour {day} - {hour:02d}:{minute:02d} [{category}] {message}"

    def _fit_line(self, text: str, max_width: int) -> str:
        out = str(text or "")
        if self.text_font.size(out)[0] <= max_width:
            return out
        while out and self.text_font.size(out + "...")[0] > max_width:
            out = out[:-1]
        return (out + "...").strip()

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = int(min(w, h) * 0.04)

        self.title_font = pygame.font.SysFont("consolas", max(28, int(h * 0.06)), bold=True)
        self.text_font = pygame.font.SysFont("consolas", max(14, int(h * 0.03)))
        self.small_font = pygame.font.SysFont("consolas", max(12, int(h * 0.024)))
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)

        screen.fill((30, 34, 42))

        title_surf = self.title_font.render(self.title, True, (245, 245, 245))
        title_rect = title_surf.get_rect(midtop=(w // 2, margin))
        screen.blit(title_surf, title_rect)

        panel_rect = pygame.Rect(margin, title_rect.bottom + 10, w - 2 * margin, h - (title_rect.bottom + 22 + margin * 2))
        pygame.draw.rect(screen, (22, 27, 36), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (80, 98, 122), panel_rect, 2, border_radius=12)

        history = list(getattr(self.phase, "world_history", []) or [])
        history.reverse()  # plus recent en haut

        line_h = max(self.text_font.get_linesize(), self.small_font.get_linesize())
        content_h = max(1, max(panel_rect.height - 20, 10 + len(history[:500]) * (line_h + 8)))
        content = pygame.Surface((panel_rect.width - 20, content_h), pygame.SRCALPHA)
        y = 6

        if not history:
            empty = self.text_font.render("Aucun evenement enregistre.", True, (210, 220, 235))
            content.blit(empty, (10, y))
            y += empty.get_height() + 10
        else:
            max_w = content.get_width() - 20
            for idx, entry in enumerate(history[:500]):
                line = self._fit_line(self._entry_text(entry), max_w)
                col = (220, 230, 242) if idx % 2 == 0 else (196, 210, 228)
                text = self.text_font.render(line, True, col)
                content.blit(text, (10, y))
                y += line_h + 6
                pygame.draw.line(content, (65, 78, 98), (10, y), (content.get_width() - 10, y), 1)
                y += 2

        visible_h = panel_rect.height - 20
        self.max_scroll = max(0, content_h - visible_h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))

        prev_clip = screen.get_clip()
        screen.set_clip(panel_rect.inflate(-10, -10))
        screen.blit(content, (panel_rect.x + 10, panel_rect.y + 10 - self.scroll))
        screen.set_clip(prev_clip)

        if self.max_scroll > 0:
            track = pygame.Rect(panel_rect.right - 8, panel_rect.y + 14, 4, panel_rect.height - 28)
            pygame.draw.rect(screen, (50, 56, 68), track, border_radius=3)
            thumb_h = max(28, int(track.height * (visible_h / max(visible_h, y))))
            thumb_y = track.y + int((track.height - thumb_h) * (self.scroll / max(1, self.max_scroll)))
            thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
            pygame.draw.rect(screen, (125, 145, 175), thumb, border_radius=3)

        self.back_btn.move_to((margin, h - margin))
        self.back_btn.draw(screen)
