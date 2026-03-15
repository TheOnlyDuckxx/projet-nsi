import math
from typing import Any

import pygame

from Game.core.utils import Button, ButtonStyle, format_key_label


class TutorialController:
    """Orchestre le tutoriel jouable au-dessus de Phase1."""

    def __init__(self, phase):
        self.phase = phase
        self.app = phase.app
        self.assets = phase.assets
        self.screen = phase.screen

        self.title_font = self.assets.get_font("MightySouly", 34)
        self.body_font = self.assets.get_font("KiwiSoda", 20)
        self.small_font = self.assets.get_font("KiwiSoda", 16)
        self.step_font = self.assets.get_font("MightySouly", 26)

        neutral_style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=18,
            padding_y=10,
            font=self.body_font,
            bg_color=(44, 58, 78),
            hover_bg_color=(62, 82, 108),
            border_color=(124, 146, 176),
            border_width=2,
            hover_zoom=1.0,
        )
        accent_style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=18,
            padding_y=10,
            font=self.body_font,
            bg_color=(66, 118, 82),
            hover_bg_color=(82, 144, 102),
            border_color=(184, 222, 194),
            border_width=2,
            hover_zoom=1.0,
        )
        danger_style = ButtonStyle(
            draw_background=True,
            radius=12,
            padding_x=18,
            padding_y=10,
            font=self.body_font,
            bg_color=(110, 58, 62),
            hover_bg_color=(138, 72, 80),
            border_color=(220, 166, 172),
            border_width=2,
            hover_zoom=1.0,
        )

        self.btn_intro_continue = Button(
            "Continuer",
            (0, 0),
            anchor="center",
            style=accent_style,
            on_click=lambda _b: self._close_intro(),
        )
        self.btn_skip_tutorial = Button(
            "Passer le tutoriel",
            (0, 0),
            anchor="topright",
            style=neutral_style,
            on_click=lambda _b: self._open_summary("skipped"),
        )
        self.btn_pause_resume = Button(
            "Reprendre",
            (0, 0),
            anchor="center",
            style=accent_style,
            on_click=lambda _b: self._close_pause(),
        )
        self.btn_pause_skip_step = Button(
            "Passer l'etape",
            (0, 0),
            anchor="center",
            style=neutral_style,
            on_click=lambda _b: self._complete_current_step(skip=True),
        )
        self.btn_pause_quit = Button(
            "Quitter le tutoriel",
            (0, 0),
            anchor="center",
            style=danger_style,
            on_click=lambda _b: self.app.change_state("MENU"),
        )
        self.btn_summary_new_game = Button(
            "Nouvelle partie",
            (0, 0),
            anchor="center",
            style=accent_style,
            on_click=lambda _b: self.app.change_state("CREATION"),
        )
        self.btn_summary_menu = Button(
            "Retour menu",
            (0, 0),
            anchor="center",
            style=neutral_style,
            on_click=lambda _b: self.app.change_state("MENU"),
        )
        self.btn_summary_replay = Button(
            "Rejouer",
            (0, 0),
            anchor="center",
            style=neutral_style,
            on_click=lambda _b: self.app.change_state("LOADING", preset="Tutorial", tutorial_mode=True),
        )

        self.step_order = [
            "camera",
            "select",
            "move",
            "multi_select",
            "inspect",
            "harvest",
            "build_warehouse",
            "menus_tools",
        ]

        self.step_index = 0
        self.step_intro_open = True
        self.pause_open = False
        self.summary_open = False
        self.summary_mode = "completed"
        self._pulse_t = 0.0
        self._menu_tools_state: dict[str, bool] = {}
        self._current_intro_rect = pygame.Rect(0, 0, 10, 10)
        self._current_pause_rect = pygame.Rect(0, 0, 10, 10)
        self._current_summary_rect = pygame.Rect(0, 0, 10, 10)
        self._completion_recorded = False
        self._camera_zoom_start = float(getattr(self.phase.view, "zoom", 1.0))
        self._camera_cam_start = (
            float(getattr(self.phase.view, "cam_x", 0.0)),
            float(getattr(self.phase.view, "cam_y", 0.0)),
        )
        self._camera_zoom_done = False
        self._camera_pan_done = False
        self._focus_used = False
        self._pause_seen_open = False
        self._pause_seen_close = False
        self._last_opened_menu = None
        self._inspect_ready = False
        self._inspect_ready_delay = 0.0
        self._advance_delay = 0.0
        self._advance_to_summary: str | None = None
        self._prepare_step_runtime()

    def enter(self):
        self.phase.info_windows = []
        self._prepare_step_runtime()

    def leave(self):
        self.phase.info_windows = []

    def on_prop_described(self, payload):
        target = self._target("inspect_prop")
        if not target:
            return
        if tuple(map(int, payload[:2])) == tuple(map(int, target[:2])):
            self._inspect_ready = True
            self._inspect_ready_delay = 0.12

    def on_focus_used(self):
        self._focus_used = True

    def blocks_world_update(self) -> bool:
        return bool(self.step_intro_open or self.pause_open or self.summary_open)

    def handle_input(self, events) -> bool:
        self._layout(self.screen)
        if self.summary_open:
            self.btn_summary_new_game.handle(events)
            self.btn_summary_menu.handle(events)
            self.btn_summary_replay.handle(events)
            return True
        if self.pause_open:
            self.btn_pause_resume.handle(events)
            self.btn_pause_skip_step.handle(events)
            self.btn_pause_quit.handle(events)
            return True
        if self.step_intro_open:
            self.btn_intro_continue.handle(events)
            return True

        consumed = bool(self.btn_skip_tutorial.handle(events))
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if bool(getattr(self.phase, "ui_menu_open", False)) or bool(getattr(self.phase, "rename_active", False)):
                    continue
                self.pause_open = True
                self._pause_seen_open = True
                consumed = True
        return consumed

    def update(self, dt: float):
        self._pulse_t += float(dt)
        if self.summary_open or self.pause_open or self.step_intro_open:
            return
        if self._advance_delay > 0.0:
            self._advance_delay = max(0.0, float(self._advance_delay) - float(dt))
            if self._advance_delay <= 0.0:
                self._finish_queued_advance()
            return

        step_id = self.current_step_id()
        if step_id == "camera":
            self._update_camera_step()
        elif step_id == "select":
            if self._selected_species_members() >= 1:
                self._complete_current_step()
        elif step_id == "move":
            if self._entity_on_target("move_target"):
                self._complete_current_step()
        elif step_id == "multi_select":
            if self._selected_species_members() >= 2:
                self._complete_current_step()
        elif step_id == "inspect":
            self._inspect_ready_delay = max(0.0, float(self._inspect_ready_delay) - float(dt))
            if self._inspect_ready and self._inspect_ready_delay <= 0.0 and self._target_info_window_open():
                self._complete_current_step()
        elif step_id == "harvest":
            if self._harvest_target_completed():
                self._complete_current_step()
        elif step_id == "build_warehouse":
            if self.phase.has_built_warehouse(force_scan=True):
                self._complete_current_step()
        elif step_id == "menus_tools":
            self._update_menu_tools_state()
            if all(self._menu_tools_state.values()):
                self._open_summary("completed")

    def draw(self, screen):
        if not self.summary_open:
            self._draw_step_highlights(screen)
            if not self.step_intro_open and not self.pause_open:
                self._draw_objective_card(screen)
                self.btn_skip_tutorial.draw(screen)

        if self.step_intro_open:
            self._draw_intro_modal(screen)
        elif self.pause_open:
            self._draw_pause_modal(screen)
        elif self.summary_open:
            self._draw_summary_modal(screen)

    def current_step_id(self) -> str:
        return self.step_order[min(self.step_index, len(self.step_order) - 1)]

    def _prepare_step_runtime(self):
        self.step_intro_open = True
        self.pause_open = False
        self._advance_delay = 0.0
        self._advance_to_summary = None
        step_id = self.current_step_id()
        if step_id == "camera":
            self._camera_zoom_start = float(getattr(self.phase.view, "zoom", 1.0))
            self._camera_cam_start = (
                float(getattr(self.phase.view, "cam_x", 0.0)),
                float(getattr(self.phase.view, "cam_y", 0.0)),
            )
            self._camera_zoom_done = False
            self._camera_pan_done = False
        self._inspect_ready = False
        self._inspect_ready_delay = 0.0
        if step_id == "menus_tools":
            self._menu_tools_state = {
                "quest": False,
                "species": False,
                "map": False,
                "focus": False,
                "pause": False,
            }
            self._focus_used = False
            self._pause_seen_open = False
            self._pause_seen_close = False

    def _close_intro(self):
        self.phase.info_windows = []
        self.step_intro_open = False

    def _close_pause(self):
        if self._pause_seen_open:
            self._pause_seen_close = True
        self.pause_open = False

    def _complete_current_step(self, skip: bool = False):
        if self._advance_delay > 0.0:
            return
        if skip:
            self.phase.info_windows = []
            self.step_index += 1
            if self.step_index >= len(self.step_order):
                self._open_summary("completed")
                return
            self._prepare_step_runtime()
            return
        self._advance_delay = 1.0
        self._advance_to_summary = "completed" if self.step_index + 1 >= len(self.step_order) else None

    def _finish_queued_advance(self):
        target_summary = self._advance_to_summary
        self._advance_delay = 0.0
        self._advance_to_summary = None
        self.phase.info_windows = []
        self.step_index += 1
        if target_summary is not None or self.step_index >= len(self.step_order):
            self._open_summary(target_summary or "completed")
            return
        self._prepare_step_runtime()

    def _open_summary(self, mode: str):
        self.phase.info_windows = []
        if getattr(self.phase, "right_hud", None) is not None and getattr(self.phase.right_hud, "is_menu_open", lambda: False)():
            try:
                self.phase.right_hud._close_menu()
            except Exception:
                pass
        self.phase.ui_menu_open = False
        self.phase.paused = False
        self.summary_open = True
        self.summary_mode = str(mode or "completed")
        self.pause_open = False
        self.step_intro_open = False
        if self.summary_mode == "completed" and not self._completion_recorded:
            progression = getattr(self.app, "progression", None)
            if progression is not None:
                try:
                    progression.mark_tutorial_completed()
                except Exception:
                    pass
            self._completion_recorded = True

    def _target(self, key: str) -> Any:
        return (getattr(self.phase, "tutorial_targets", None) or {}).get(key)

    def _selected_species_members(self) -> int:
        count = 0
        for ent in getattr(self.phase, "selected_entities", []) or []:
            if getattr(ent, "espece", None) == getattr(self.phase, "espece", None):
                count += 1
        return count

    def _entity_on_target(self, target_key: str) -> bool:
        target = self._target(target_key)
        if not target:
            return False
        tx, ty = int(target[0]), int(target[1])
        for ent in getattr(self.phase, "entities", []) or []:
            if getattr(ent, "espece", None) != getattr(self.phase, "espece", None):
                continue
            if abs(float(getattr(ent, "x", 0.0)) - tx) <= 0.8 and abs(float(getattr(ent, "y", 0.0)) - ty) <= 0.8:
                return True
        return False

    def _target_info_window_open(self) -> bool:
        for win in getattr(self.phase, "info_windows", []) or []:
            if not getattr(win, "closed", False):
                return True
        return False

    def _harvest_target_completed(self) -> bool:
        target = self._target("inspect_prop")
        if not target:
            return False
        cell = self.phase._get_construction_cell(int(target[0]), int(target[1]), generate=False)
        prop_gone = not cell
        if not prop_gone:
            return False
        for ent in getattr(self.phase, "entities", []) or []:
            if getattr(ent, "espece", None) != getattr(self.phase, "espece", None):
                continue
            for item in getattr(ent, "carrying", []) or []:
                if str(item.get("id") or "") == "wood" and int(item.get("quantity", 0) or 0) > 0:
                    return True
        return False

    def _update_camera_step(self):
        zoom = float(getattr(self.phase.view, "zoom", 1.0))
        cam_x = float(getattr(self.phase.view, "cam_x", 0.0))
        cam_y = float(getattr(self.phase.view, "cam_y", 0.0))
        if abs(zoom - self._camera_zoom_start) >= 0.05:
            self._camera_zoom_done = True
        if math.hypot(cam_x - self._camera_cam_start[0], cam_y - self._camera_cam_start[1]) >= 50.0:
            self._camera_pan_done = True
        if self._camera_zoom_done and self._camera_pan_done:
            self._complete_current_step()

    def _update_menu_tools_state(self):
        active_menu = getattr(getattr(self.phase, "right_hud", None), "active_menu_key", None)
        if active_menu == "quest":
            self._menu_tools_state["quest"] = True
        if active_menu == "species":
            self._menu_tools_state["species"] = True
        if bool(getattr(self.phase, "minimap_visible", False)):
            self._menu_tools_state["map"] = True
        if self._focus_used:
            self._menu_tools_state["focus"] = True
        if self._pause_seen_open and self._pause_seen_close:
            self._menu_tools_state["pause"] = True

    def _layout(self, screen):
        W, H = screen.get_size()
        self.btn_skip_tutorial.move_to((W - 18, 16))

        modal_w = min(int(W * 0.56), 760)
        modal_h = min(int(H * 0.54), 520)
        self._current_intro_rect = pygame.Rect(W // 2 - modal_w // 2, H // 2 - modal_h // 2, modal_w, modal_h)
        self.btn_intro_continue.move_to((self._current_intro_rect.centerx, self._current_intro_rect.bottom - 40))

        pause_w = min(int(W * 0.46), 600)
        pause_h = min(int(H * 0.50), 420)
        self._current_pause_rect = pygame.Rect(W // 2 - pause_w // 2, H // 2 - pause_h // 2, pause_w, pause_h)
        self._layout_button_stack(
            [self.btn_pause_resume, self.btn_pause_skip_step, self.btn_pause_quit],
            self._current_pause_rect,
            bottom_margin=30,
            gap=14,
        )

        summary_w = min(int(W * 0.72), 900)
        summary_h = min(int(H * 0.80), 700)
        self._current_summary_rect = pygame.Rect(W // 2 - summary_w // 2, H // 2 - summary_h // 2, summary_w, summary_h)
        self._layout_button_row(
            [self.btn_summary_menu, self.btn_summary_replay, self.btn_summary_new_game],
            self._current_summary_rect,
            self._current_summary_rect.bottom - 34 - self._button_row_height(
                [self.btn_summary_menu, self.btn_summary_replay, self.btn_summary_new_game]
            ) // 2,
            gap=18,
        )

    def _button_row_height(self, buttons: list[Button]) -> int:
        if not buttons:
            return 0
        return max(btn.rect.height for btn in buttons)

    def _layout_button_row(self, buttons: list[Button], rect: pygame.Rect, center_y: int, gap: int = 16):
        if not buttons:
            return
        total_button_w = sum(btn.rect.width for btn in buttons)
        available_w = max(1, rect.width - 48)
        if len(buttons) > 1:
            max_gap = max(8, (available_w - total_button_w) // (len(buttons) - 1))
            gap = min(gap, max_gap)
        total_w = total_button_w + gap * max(0, len(buttons) - 1)
        cursor_x = rect.centerx - total_w // 2
        for btn in buttons:
            btn.move_to((cursor_x + btn.rect.width // 2, center_y))
            cursor_x += btn.rect.width + gap

    def _layout_button_stack(self, buttons: list[Button], rect: pygame.Rect, bottom_margin: int = 24, gap: int = 12):
        if not buttons:
            return
        total_h = sum(btn.rect.height for btn in buttons) + gap * max(0, len(buttons) - 1)
        cursor_y = rect.bottom - bottom_margin - total_h
        for btn in buttons:
            btn.move_to((rect.centerx, cursor_y + btn.rect.height // 2))
            cursor_y += btn.rect.height + gap

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        raw = str(text or "")
        if not raw.strip():
            return [""]
        words = raw.split()
        if not words:
            return [""]
        lines = [words[0]]
        for word in words[1:]:
            candidate = f"{lines[-1]} {word}"
            if font.size(candidate)[0] <= max_width:
                lines[-1] = candidate
            else:
                lines.append(word)
        return lines

    def _draw_overlay(self, screen, alpha: int = 180):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

    def _draw_modal_panel(self, screen, rect: pygame.Rect):
        pygame.draw.rect(screen, (18, 24, 34), rect, border_radius=18)
        pygame.draw.rect(screen, (108, 132, 164), rect, 2, border_radius=18)

    def _draw_intro_modal(self, screen):
        self._layout(screen)
        self._draw_overlay(screen, alpha=190)
        rect = self._current_intro_rect
        self._draw_modal_panel(screen, rect)

        title = self.title_font.render(self._step_title(self.current_step_id()), True, (238, 242, 246))
        screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 26))

        y = rect.y + 86
        for line in self._step_intro_lines(self.current_step_id()):
            surf = self.body_font.render(line, True, (220, 226, 235))
            screen.blit(surf, (rect.centerx - surf.get_width() // 2, y))
            y += surf.get_height() + 8

        etape = self.small_font.render(
            f"Etape {self.step_index + 1}/{len(self.step_order)}",
            True,
            (168, 182, 200),
        )
        screen.blit(etape, (rect.centerx - etape.get_width() // 2, rect.bottom - 96))
        self.btn_intro_continue.draw(screen)

    def _draw_pause_modal(self, screen):
        self._layout(screen)
        self._draw_overlay(screen, alpha=190)
        rect = self._current_pause_rect
        self._draw_modal_panel(screen, rect)

        title = self.title_font.render("Pause tutoriel", True, (238, 242, 246))
        screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 26))

        body_lines = [
            "Reprenez pour continuer l'etape en cours.",
            "Passez l'etape si vous connaissez deja cette action.",
            "Quittez pour revenir au menu principal.",
        ]
        wrapped_lines: list[str] = []
        for line in body_lines:
            wrapped_lines.extend(self._wrap_text(line, self.body_font, rect.width - 68))
        y = rect.y + 84
        max_y = self.btn_pause_resume.rect.top - 28
        for line in wrapped_lines:
            surf = self.body_font.render(line, True, (214, 220, 230))
            if y + surf.get_height() > max_y:
                break
            screen.blit(surf, (rect.centerx - surf.get_width() // 2, y))
            y += surf.get_height() + 8

        self.btn_pause_resume.draw(screen)
        self.btn_pause_skip_step.draw(screen)
        self.btn_pause_quit.draw(screen)

    def _draw_summary_modal(self, screen):
        self._layout(screen)
        self._draw_overlay(screen, alpha=200)
        rect = self._current_summary_rect
        self._draw_modal_panel(screen, rect)

        title_text = {
            "completed": "Tutoriel termine",
            "skipped": "Tutoriel interrompu",
            "failed": "Tutoriel arrete",
        }.get(self.summary_mode, "Tutoriel")
        title = self.title_font.render(title_text, True, (238, 242, 246))
        screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 24))

        summary_buttons = [self.btn_summary_menu, self.btn_summary_replay, self.btn_summary_new_game]
        buttons_top = min(btn.rect.top for btn in summary_buttons)
        note_lines = self._wrap_text(
            "Rejouer relance le tutoriel. Nouvelle partie ouvre la creation normale.",
            self.small_font,
            rect.width - 56,
        )
        note_h = len(note_lines) * self.small_font.get_height() + max(0, len(note_lines) - 1) * 6
        note_y = buttons_top - note_h - 18
        body_bottom = note_y - 18

        wrapped_lines: list[str] = []
        for line in self._summary_lines():
            if line.startswith("Commandes vues") or line.startswith("Systemes"):
                wrapped_lines.append(line)
                continue
            wrapped_lines.extend(self._wrap_text(line, self.body_font, rect.width - 56))

        y = rect.y + 84
        for line in wrapped_lines:
            color = (214, 220, 230)
            if line.startswith("Commandes vues") or line.startswith("Systemes"):
                color = (244, 228, 166)
            surf = self.body_font.render(line, True, color)
            if y + surf.get_height() > body_bottom:
                break
            screen.blit(surf, (rect.x + 28, y))
            y += surf.get_height() + 8

        note_draw_y = note_y
        for line in note_lines:
            note = self.small_font.render(line, True, (168, 182, 200))
            screen.blit(note, (rect.centerx - note.get_width() // 2, note_draw_y))
            note_draw_y += note.get_height() + 6

        self.btn_summary_menu.draw(screen)
        self.btn_summary_replay.draw(screen)
        self.btn_summary_new_game.draw(screen)

    def _draw_objective_card(self, screen):
        W, _H = screen.get_size()
        card_w = min(int(W * 0.35), 470)
        card_x = 18
        card_y = 16
        if self._advance_delay > 0.0:
            lines = ["Objectif valide. Le prochain objectif arrive dans un instant."]
        else:
            lines = self._step_objective_lines(self.current_step_id())
        line_h = self.small_font.get_height() + 6
        card_h = 76 + max(1, len(lines)) * line_h
        rect = pygame.Rect(card_x, card_y, card_w, card_h)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((18, 26, 38, 220))
        screen.blit(panel, rect.topleft)
        pygame.draw.rect(screen, (106, 132, 164), rect, 2, border_radius=16)

        step = self.step_font.render(
            f"Etape {self.step_index + 1}/{len(self.step_order)}",
            True,
            (244, 228, 166),
        )
        title = self.body_font.render(self._step_title(self.current_step_id()), True, (236, 240, 245))
        screen.blit(step, (rect.x + 14, rect.y + 12))
        screen.blit(title, (rect.x + 14, rect.y + 40))

        y = rect.y + 72
        for line in lines:
            surf = self.small_font.render(line, True, (214, 220, 230))
            screen.blit(surf, (rect.x + 16, y))
            y += line_h

    def _draw_step_highlights(self, screen):
        step_id = self.current_step_id()
        if step_id == "select":
            ent = self._first_player_entity()
            if ent is not None:
                rect = self.phase._entity_screen_rect(ent)
                if rect:
                    self._draw_rect_highlight(screen, rect, (90, 210, 140))
        elif step_id == "move":
            self._draw_tile_highlight(screen, self._target("move_target"))
        elif step_id == "multi_select":
            rects = []
            for ent in self._player_entities()[:2]:
                rect = self.phase._entity_screen_rect(ent)
                if rect:
                    rects.append(rect)
            if rects:
                merged = rects[0].unionall(rects[1:])
                self._draw_rect_highlight(screen, merged.inflate(28, 28), (90, 210, 140))
        elif step_id in {"inspect", "harvest"}:
            self._draw_prop_target(screen)
        elif step_id == "build_warehouse":
            if not self.phase.has_built_warehouse(force_scan=True):
                craft_rect = self.phase.get_craft_button_rect("Entrepot_primitif")
                if craft_rect:
                    self._draw_rect_highlight(screen, craft_rect, (236, 210, 120), pad=10)
                target = self._target("build_target")
                if target:
                    self._draw_tile_highlight(screen, target)
        elif step_id == "menus_tools":
            self._draw_menu_tools_highlights(screen)

    def _draw_menu_tools_highlights(self, screen):
        if not self._menu_tools_state.get("quest", False):
            rect = self.phase.get_left_hud_button_rect("quest")
            if rect:
                self._draw_rect_highlight(screen, rect, (236, 210, 120), pad=8)
            return
        if not self._menu_tools_state.get("species", False):
            rect = self.phase.get_left_hud_button_rect("species")
            if rect:
                self._draw_rect_highlight(screen, rect, (236, 210, 120), pad=8)
            return
        if bool(getattr(self.phase, "minimap_visible", False)):
            rect = self.phase.get_minimap_panel_rect()
            if rect:
                self._draw_rect_highlight(screen, rect, (90, 170, 240), pad=8)

    def _draw_rect_highlight(self, screen, rect: pygame.Rect, color, pad: int = 6):
        pulse = 0.5 + 0.5 * math.sin(self._pulse_t * 4.2)
        width = 2 + int(2 * pulse)
        highlight = rect.inflate(pad * 2, pad * 2)
        pygame.draw.rect(screen, color, highlight, width, border_radius=14)

    def _draw_tile_highlight(self, screen, tile):
        if not tile:
            return
        poly = self.phase.view.tile_surface_poly(int(tile[0]), int(tile[1]))
        if not poly:
            return
        pulse = 70 + int(45 * (0.5 + 0.5 * math.sin(self._pulse_t * 4.0)))
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(overlay, (236, 210, 120, pulse), poly)
        pygame.draw.polygon(overlay, (245, 240, 220, 220), poly, 2)
        screen.blit(overlay, (0, 0))

    def _draw_prop_target(self, screen):
        target = self._target("inspect_prop")
        if not target:
            return
        rect = self.phase.view.prop_draw_rect(int(target[0]), int(target[1]), int(target[2]))
        if rect:
            self._draw_rect_highlight(screen, rect, (236, 210, 120), pad=8)
        else:
            self._draw_tile_highlight(screen, target)

    def _player_entities(self):
        out = []
        for ent in getattr(self.phase, "entities", []) or []:
            if getattr(ent, "espece", None) == getattr(self.phase, "espece", None):
                out.append(ent)
        return out

    def _first_player_entity(self):
        entities = self._player_entities()
        return entities[0] if entities else None

    def _step_title(self, step_id: str) -> str:
        titles = {
            "camera": "Prendre la camera en main",
            "select": "Selectionner un individu",
            "move": "Donner un ordre de deplacement",
            "multi_select": "Selectionner plusieurs individus",
            "inspect": "Inspecter un element",
            "harvest": "Recolter une ressource",
            "build_warehouse": "Placer puis construire un entrepot",
            "menus_tools": "Outils et menus essentiels",
        }
        return titles.get(step_id, "Tutoriel")

    def _step_intro_lines(self, step_id: str) -> list[str]:
        inspect_key = self.phase.get_control_label("controls.inspect_mode", pygame.K_i)
        map_key = self.phase.get_control_label("controls.map_toggle", pygame.K_m)
        focus_key = self.phase.get_control_label("controls.focus_nearest", pygame.K_SPACE)
        lines = {
            "camera": [
                "Utilisez la molette pour zoomer ou dezoomer.",
                "Deplacez ensuite la camera avec les fleches ou le clic molette.",
                "Le tutoriel valide l'etape quand les deux actions ont ete faites.",
            ],
            "select": [
                "Cliquez un individu de votre espece pour le selectionner.",
                "Un marqueur apparaitra autour de lui pour confirmer la selection.",
            ],
            "move": [
                "Avec un individu selectionne, faites un clic droit sur la tuile marquee.",
                "L'individu se deplacera automatiquement jusqu'a cet emplacement.",
            ],
            "multi_select": [
                "Cliquez-glissez pour entourer les deux individus en meme temps.",
                "Vous pourrez ensuite leur donner un ordre commun.",
            ],
            "inspect": [
                f"Maintenez {inspect_key} puis cliquez le prop surligne.",
                "Une fenetre d'information s'ouvrira avec sa description.",
            ],
            "harvest": [
                "Le prop inspecte peut maintenant etre recolte.",
                "Selectionnez un individu puis faites un clic droit dessus.",
            ],
            "build_warehouse": [
                "Choisissez le bouton Entrepot dans le HUD du bas.",
                "Placez-le sur la tuile marquee, puis faites un clic droit dessus pour lancer le chantier.",
            ],
            "menus_tools": [
                "Fin de prise en main: ouvrez les menus utiles et testez les outils rapides.",
                f"Ouvrez Quetes, puis Espece, activez la mini-map avec {map_key},",
                f"recentrez la camera avec {focus_key}, puis ouvrez et refermez la pause du tutoriel.",
            ],
        }
        return lines.get(step_id, [])

    def _step_objective_lines(self, step_id: str) -> list[str]:
        inspect_key = self.phase.get_control_label("controls.inspect_mode", pygame.K_i)
        map_key = self.phase.get_control_label("controls.map_toggle", pygame.K_m)
        focus_key = self.phase.get_control_label("controls.focus_nearest", pygame.K_SPACE)

        if step_id == "camera":
            return [
                self._status_line(self._camera_zoom_done, "Utiliser la molette pour zoomer"),
                self._status_line(self._camera_pan_done, "Deplacer la camera"),
            ]
        if step_id == "select":
            return ["Cliquez un individu de votre espece."]
        if step_id == "move":
            return ["Faites un clic droit sur la tuile marquee."]
        if step_id == "multi_select":
            return ["Cliquez-glissez pour selectionner les deux individus."]
        if step_id == "inspect":
            return [f"Maintenez {inspect_key} puis cliquez le prop surligne."]
        if step_id == "harvest":
            return ["Avec un individu selectionne, faites un clic droit sur le prop."]
        if step_id == "build_warehouse":
            target = self._target("build_target")
            site = None
            if target:
                site = self.phase._get_construction_cell(int(target[0]), int(target[1]), generate=False)
            site_placed = bool(isinstance(site, dict) and str(site.get("craft_id") or "") == "Entrepot_primitif")
            return [
                self._status_line(self.phase.selected_craft == "Entrepot_primitif" or site_placed, "Choisir Entrepot dans le HUD du bas"),
                self._status_line(site_placed, "Placer le batiment sur la tuile marquee"),
                self._status_line(self.phase.has_built_warehouse(force_scan=True), "Terminer la construction"),
            ]
        if step_id == "menus_tools":
            return [
                self._status_line(self._menu_tools_state.get("quest", False), "Ouvrir le menu Quetes"),
                self._status_line(self._menu_tools_state.get("species", False), "Ouvrir le menu Espece"),
                self._status_line(self._menu_tools_state.get("map", False), f"Activer la mini-map ({map_key})"),
                self._status_line(self._menu_tools_state.get("focus", False), f"Utiliser le focus proche ({focus_key})"),
                self._status_line(self._menu_tools_state.get("pause", False), "Ouvrir puis refermer la pause tutoriel"),
            ]
        return []

    def _summary_lines(self) -> list[str]:
        inspect_key = self.phase.get_control_label("controls.inspect_mode", pygame.K_i)
        map_key = self.phase.get_control_label("controls.map_toggle", pygame.K_m)
        focus_key = self.phase.get_control_label("controls.focus_nearest", pygame.K_SPACE)
        transparency_key = self.phase.get_control_label("controls.props_transparency", pygame.K_h)

        status_line = {
            "completed": "Vous avez couvre les controles essentiels du premier jour.",
            "skipped": "Le tutoriel a ete quitte avant la fin. Vous pouvez le rejouer a tout moment.",
            "failed": "Le tutoriel a ete arrete. Vous pouvez le relancer quand vous voulez.",
        }.get(self.summary_mode, "")

        return [
            status_line,
            "",
            "Commandes vues",
            "Molette : zoom camera",
            "Fleches ou clic molette : deplacement camera",
            "Clic gauche : selection",
            "Clic droit : ordre / interaction",
            f"{inspect_key} : mode inspection",
            f"{map_key} : mini-map",
            f"{focus_key} : focus sur un individu proche",
            f"{transparency_key} : transparence temporaire des props",
            f"{format_key_label(pygame.K_n)} : renommer un individu selectionne",
            f"{format_key_label(pygame.K_d)} + clic droit : demonter une construction",
            "",
            "Systemes a decouvrir en vraie partie",
            "Meteo et cycle jour/nuit",
            "Technologies et innovations",
            "Quetes, evenements et historique",
            "Mutations, reproduction et combat",
        ]

    def _status_line(self, ok: bool, label: str) -> str:
        prefix = "[OK]" if ok else "[  ]"
        return f"{prefix} {label}"
