import pygame

from Game.core.utils import Button, ButtonStyle


class QuestMenu:
    def __init__(self, phase, on_close=None):
        self.phase = phase
        self.on_close = on_close
        self.active = False
        self.scroll = 0
        self.max_scroll = 0

        if not pygame.font.get_init():
            pygame.font.init()

        self.title = "Quetes"
        self.title_font = pygame.font.SysFont("consolas", 42, bold=True)
        self.section_font = pygame.font.SysFont("consolas", 26, bold=True)
        self.text_font = pygame.font.SysFont("consolas", 20)
        self.small_font = pygame.font.SysFont("consolas", 16)
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

    def _reward_text(self, rewards):
        if not rewards:
            return "Recompenses: -"
        labels = []
        for reward in rewards[:3]:
            rtype = str((reward or {}).get("type", ""))
            if rtype == "add_xp":
                labels.append(f"+{int((reward or {}).get('amount', 0) or 0)} XP")
            elif rtype == "unlock_craft":
                labels.append(f"Debloque {(reward or {}).get('craft_id', 'craft')}")
            elif rtype == "unlock_non_tech_crafts":
                labels.append("Debloque crafts")
            elif rtype == "modify_species_stat":
                stat = str((reward or {}).get("stat", "stat"))
                amount = (reward or {}).get("amount", 0)
                labels.append(f"+{amount} {stat}")
            elif rtype == "trigger_class_choice_event":
                labels.append("Declenche event classe")
            else:
                labels.append(rtype or "reward")
        return "Recompenses: " + ", ".join(labels)

    def _draw_quest_card(self, screen, rect, title, description, progress, target, reward_line, completed=False):
        bg = (44, 68, 52) if completed else (46, 52, 68)
        border = (96, 165, 120) if completed else (96, 120, 170)
        pygame.draw.rect(screen, bg, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)

        y = rect.y + 8
        title_surf = self.text_font.render(title, True, (240, 245, 250))
        screen.blit(title_surf, (rect.x + 10, y))
        y += title_surf.get_height() + 4

        desc_surf = self.small_font.render(description, True, (205, 215, 230))
        screen.blit(desc_surf, (rect.x + 10, y))
        y += desc_surf.get_height() + 8

        reward_surf = self.small_font.render(reward_line, True, (180, 198, 220))
        screen.blit(reward_surf, (rect.x + 10, y))
        y += reward_surf.get_height() + 6

        ratio = 1.0 if completed else max(0.0, min(1.0, float(progress) / max(1.0, float(target))))
        bar_rect = pygame.Rect(rect.x + 10, y, rect.width - 20, 10)
        pygame.draw.rect(screen, (28, 34, 44), bar_rect, border_radius=4)
        fill = bar_rect.copy()
        fill.width = int(bar_rect.width * ratio)
        if fill.width > 0:
            pygame.draw.rect(screen, (110, 205, 135) if completed else (110, 165, 235), fill, border_radius=4)
        pygame.draw.rect(screen, (105, 125, 155), bar_rect, 1, border_radius=4)

        value_txt = "Terminee" if completed else f"{int(progress)}/{int(target)}"
        value_surf = self.small_font.render(value_txt, True, (220, 230, 240))
        screen.blit(value_surf, (bar_rect.right - value_surf.get_width(), bar_rect.y - 16))

    def draw(self, screen):
        if not self.active:
            return

        w, h = screen.get_size()
        margin = int(min(w, h) * 0.04)

        self.title_font = pygame.font.SysFont("consolas", max(28, int(h * 0.06)), bold=True)
        self.section_font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)
        self.text_font = pygame.font.SysFont("consolas", max(14, int(h * 0.028)))
        self.small_font = pygame.font.SysFont("consolas", max(12, int(h * 0.022)))
        self.back_btn.style.font = pygame.font.SysFont("consolas", max(18, int(h * 0.035)), bold=True)

        screen.fill((34, 40, 48))

        title_surf = self.title_font.render(self.title, True, (245, 245, 245))
        title_rect = title_surf.get_rect(midtop=(w // 2, margin))
        screen.blit(title_surf, title_rect)

        panel_rect = pygame.Rect(margin, title_rect.bottom + 10, w - 2 * margin, h - (title_rect.bottom + 22 + margin * 2))
        pygame.draw.rect(screen, (24, 28, 38), panel_rect, border_radius=12)
        pygame.draw.rect(screen, (76, 96, 122), panel_rect, 2, border_radius=12)

        qmgr = getattr(self.phase, "quest_manager", None)
        if qmgr is None:
            info = self.text_font.render("Systeme de quetes indisponible.", True, (220, 228, 235))
            screen.blit(info, info.get_rect(center=panel_rect.center))
        else:
            active = qmgr.get_active_quests()
            completed = qmgr.get_completed_quests()

            content = pygame.Surface((panel_rect.width - 20, max(1, panel_rect.height - 20)), pygame.SRCALPHA)
            y = 4

            sec_active = self.section_font.render("Quetes actives", True, (210, 230, 255))
            content.blit(sec_active, (6, y))
            y += sec_active.get_height() + 8
            if not active:
                empty = self.small_font.render("Aucune quete active.", True, (170, 180, 195))
                content.blit(empty, (10, y))
                y += empty.get_height() + 10
            else:
                for q in active:
                    card = pygame.Rect(6, y, content.get_width() - 12, 96)
                    rewards = (qmgr.definitions.get(q.quest_id, {}) or {}).get("rewards", []) or []
                    self._draw_quest_card(
                        content,
                        card,
                        q.title,
                        q.description,
                        q.progress,
                        q.target,
                        self._reward_text(rewards),
                        completed=False,
                    )
                    y += card.height + 8

            y += 8
            sec_done = self.section_font.render("Quetes terminees", True, (190, 230, 190))
            content.blit(sec_done, (6, y))
            y += sec_done.get_height() + 8
            if not completed:
                empty = self.small_font.render("Aucune quete terminee.", True, (170, 180, 195))
                content.blit(empty, (10, y))
                y += empty.get_height() + 10
            else:
                for q in completed[-12:]:
                    card = pygame.Rect(6, y, content.get_width() - 12, 96)
                    rewards = (qmgr.definitions.get(q.quest_id, {}) or {}).get("rewards", []) or []
                    self._draw_quest_card(
                        content,
                        card,
                        q.title,
                        q.description,
                        q.target,
                        q.target,
                        self._reward_text(rewards),
                        completed=True,
                    )
                    y += card.height + 8

            visible_h = panel_rect.height - 20
            self.max_scroll = max(0, y - visible_h)
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
