import pygame
from Game.ui.hud.notification import add_notification


_AI_BUTTON_SPECS = (
    ("harvest", "IA Recolte"),
    ("builder", "IA Build"),
    ("guard", "IA Garde"),
)

_INSPECTION_PANEL_DEFAULT_RATIO = 0.35
_INSPECTION_PANEL_MIN_HEIGHT = 190
_INSPECTION_PANEL_RESIZE_HANDLE_HEIGHT = 12
_INSPECTION_PANEL_RESIZE_SAFE_BOTTOM = 18


def _get_inspected_entity(self):
    ent = None
    if getattr(self, "selected_entities", None):
        if self.selected_entities:
            ent = self.selected_entities[0]
    if ent is None:
        if not self.selected or self.selected[0] != "entity":
            return None
        ent = self.selected[1]
    return ent


def _clamp_inspection_panel_height(screen, height):
    max_height = max(_INSPECTION_PANEL_MIN_HEIGHT, screen.get_height() - 20)
    return max(_INSPECTION_PANEL_MIN_HEIGHT, min(int(height), max_height))


def _get_inspection_panel_height(self, screen):
    default_height = int(screen.get_height() * _INSPECTION_PANEL_DEFAULT_RATIO)
    raw_height = getattr(self, "_inspection_panel_height", default_height)
    clamped = _clamp_inspection_panel_height(screen, raw_height)
    self._inspection_panel_height = clamped
    return clamped


def _update_inspection_panel_resize_drag(self, screen):
    if not getattr(self, "_inspection_panel_resizing", False):
        return
    if not pygame.mouse.get_pressed(3)[0]:
        self._inspection_panel_resizing = False
        return

    mouse_y = pygame.mouse.get_pos()[1]
    grab_offset = int(getattr(self, "_inspection_panel_resize_grab_offset", 0))
    target_height = mouse_y + grab_offset
    self._inspection_panel_height = _clamp_inspection_panel_height(screen, target_height)


def _draw_inspection_resize_handle(self, panel_surf, layout, panel_x, panel_y, panel_width):
    handle_rect = layout["resize_handle_rect"].move(-panel_x, -panel_y)
    handle_hover = layout["resize_handle_rect"].collidepoint(pygame.mouse.get_pos())
    handle_active = getattr(self, "_inspection_panel_resizing", False)
    handle_color = (140, 190, 230) if (handle_hover or handle_active) else (95, 135, 170)
    grip_y = max(2, handle_rect.y + 1)
    pygame.draw.line(panel_surf, handle_color, (12, grip_y), (panel_width - 12, grip_y), 2)
    grip_w = 74
    grip_x = (panel_width - grip_w) // 2
    pygame.draw.line(panel_surf, handle_color, (grip_x, grip_y - 3), (grip_x + grip_w, grip_y - 3), 1)


def _inspection_panel_layout(self, screen):
    _update_inspection_panel_resize_drag(self, screen)
    ent = _get_inspected_entity(self)
    if ent is None:
        self._inspection_panel_resizing = False
        return None

    panel_width = 350
    panel_height = _get_inspection_panel_height(self, screen)
    panel_x = screen.get_width() - panel_width
    panel_y = 0
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    resize_handle_rect = pygame.Rect(
        panel_x,
        panel_y + panel_height - _INSPECTION_PANEL_RESIZE_HANDLE_HEIGHT,
        panel_width,
        _INSPECTION_PANEL_RESIZE_HANDLE_HEIGHT,
    )

    buttons = []
    if not getattr(ent, "is_egg", False):
        gap = 8
        btn_h = 24
        btn_w = (panel_width - 20 - gap * 2) // 3
        btn_y = panel_y + panel_height - btn_h - _INSPECTION_PANEL_RESIZE_SAFE_BOTTOM
        for idx, (mode, label) in enumerate(_AI_BUTTON_SPECS):
            btn_x = panel_x + 10 + idx * (btn_w + gap)
            buttons.append(
                {
                    "mode": mode,
                    "label": label,
                    "rect": pygame.Rect(btn_x, btn_y, btn_w, btn_h),
                }
            )

    return {
        "entity": ent,
        "panel_rect": panel_rect,
        "resize_handle_rect": resize_handle_rect,
        "buttons": buttons,
    }


def inspection_panel_contains_point(self, pos, screen=None):
    surface = screen or self.screen
    if not surface:
        return False
    layout = _inspection_panel_layout(self, surface)
    if not layout:
        return False
    return layout["panel_rect"].collidepoint(pos)


def handle_inspection_panel_click(self, pos, screen=None):
    surface = screen or self.screen
    if not surface:
        return False
    layout = _inspection_panel_layout(self, surface)
    if not layout:
        return False
    if not layout["panel_rect"].collidepoint(pos):
        return False

    resize_handle_rect = layout["resize_handle_rect"]
    if resize_handle_rect.collidepoint(pos):
        self._inspection_panel_resizing = True
        self._inspection_panel_resize_grab_offset = layout["panel_rect"].bottom - pos[1]
        return True

    ent = layout["entity"]
    if getattr(ent, "is_egg", False):
        return True

    for button in layout["buttons"]:
        if not button["rect"].collidepoint(pos):
            continue
        if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
            return True

        mode = button["mode"]
        if mode == "harvest":
            active = ent.ia.get("auto_mode") == "harvest"
            if active:
                ent.ia["auto_mode"] = None
                add_notification(f"{ent.nom} : IA recolte desactivee.")
            else:
                ent.ia["auto_mode"] = "harvest"
                ent.ia["auto_next_decision_in"] = 0.0
                add_notification(f"{ent.nom} : IA recolte activee.")
            return True

        ent.ia["auto_mode"] = mode
        add_notification(f"{button['label']} : mode pas encore implemente.")
        return True

    return True


def draw_work_bar(self, screen, ent):
    w = getattr(ent, "work", None)
    if not w or ent.ia["etat"] not in ("recolte", "interaction", "demonte"):
        return
    poly = self.view.tile_surface_poly(int(ent.x), int(ent.y))
    if not poly:
        return
    # centre au-dessus de la tuile de l’entité
    cx = sum(p[0] for p in poly) / len(poly)
    top = min(p[1] for p in poly) - 10

    bar_w, bar_h = 44, 6
    bg = pygame.Rect(int(cx - bar_w/2), int(top - bar_h), bar_w, bar_h)
    fg = bg.inflate(-2, -2)
    fg.width = int(fg.width * float(w.get("progress", 0.0)))

    # fond
    s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
    s.fill((0, 0, 0, 160))
    screen.blit(s, (bg.x, bg.y))
    # barre
    pygame.draw.rect(screen, (80, 200, 120), fg, border_radius=2)


def draw_inspection_panel(self, screen):
    """Panneau d'inspection détaillé pour l'entité sélectionnée"""
    layout = _inspection_panel_layout(self, screen)
    if not layout:
        return
    ent = layout["entity"]
    panel_rect = layout["panel_rect"]
    panel_x, panel_y = panel_rect.x, panel_rect.y
    panel_width, panel_height = panel_rect.width, panel_rect.height
    ai_buttons = layout["buttons"]

    # Fond semi-transparent
    panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    panel_surf.fill((20, 25, 35, 220))

    # Bordure
    pygame.draw.rect(panel_surf, (80, 120, 160), (0, 0, panel_width, panel_height), 2, border_radius=8)

    # Police pour le panneau
    title_font = pygame.font.SysFont("consolas", 18, bold=True)
    header_font = pygame.font.SysFont("consolas", 14, bold=True)
    text_font = pygame.font.SysFont("consolas", 12)

    y_offset = 10

    if getattr(ent, "is_egg", False):
        title = title_font.render(f"{ent.nom}", True, (220, 240, 255))
        panel_surf.blit(title, (10, y_offset))
        y_offset += 30

        pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
        y_offset += 12

        pos_text = text_font.render(f"Position: ({int(ent.x)}, {int(ent.y)})", True, (200, 200, 200))
        panel_surf.blit(pos_text, (10, y_offset))
        y_offset += 22

        dur_percent = ent.durability / max(1.0, ent.max_durability)
        dur_text = text_font.render(
            f"Durabilité: {ent.durability:.0f}/{ent.max_durability:.0f}",
            True,
            (220, 200, 120)
        )
        panel_surf.blit(dur_text, (10, y_offset))
        y_offset += 18
        bar_w, bar_h = 240, 12
        bar_x, bar_y = 10, y_offset
        pygame.draw.rect(panel_surf, (40, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pygame.draw.rect(panel_surf, (180, 210, 120), (bar_x, bar_y, int(bar_w * dur_percent), bar_h), border_radius=3)
        pygame.draw.rect(panel_surf, (100, 100, 120), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)
        y_offset += 22

        rem_min = ent.remaining_hatch_minutes() if hasattr(ent, "remaining_hatch_minutes") else None
        if rem_min is not None:
            hours = int(rem_min // 60)
            minutes = int(rem_min % 60)
            time_text = text_font.render(
                f"Éclosion dans ~ {hours}h {minutes:02d}m",
                True,
                (200, 220, 255),
            )
            panel_surf.blit(time_text, (10, y_offset))
            y_offset += 20

        hint_text = text_font.render("Protégez l'œuf jusqu'à l'éclosion.", True, (180, 180, 200))
        panel_surf.blit(hint_text, (10, y_offset))

        _draw_inspection_resize_handle(self, panel_surf, layout, panel_x, panel_y, panel_width)
        screen.blit(panel_surf, (panel_x, panel_y))
        return

    # === TITRE ===
    title = title_font.render(f"{ent.nom}", True, (220, 240, 255))
    panel_surf.blit(title, (10, y_offset))
    y_offset += 30

    # Ligne de séparation
    pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
    y_offset += 10

    # === JAUGES VITALES ===
    header = header_font.render("Jauges", True, (255, 220, 100))
    panel_surf.blit(header, (10, y_offset))
    y_offset += 20

    jauges_display = [
        ("Santé", ent.jauges.get("sante", 0), 100, (220, 50, 50)),
        ("Énergie", ent.jauges.get("energie", 0), ent.physique["endurance"], (100, 200, 255)),
        ("Faim", ent.jauges.get("faim", 0), 100, (255, 180, 50)),
        ("Soif", ent.jauges.get("soif", 0), 100, (100, 180, 255)),
    ]

    for label, value, max_val, color in jauges_display:
        # Label
        label_surf = text_font.render(f"{label}:", True, (180, 180, 180))
        panel_surf.blit(label_surf, (15, y_offset))

        # Barre
        bar_x = 85
        bar_y = y_offset + 2
        bar_width = 200
        bar_height = 12

        # Fond de la barre
        pygame.draw.rect(panel_surf, (40, 40, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=3)

        # Barre de progression
        fill_width = int((value / max(1, max_val)) * bar_width)
        if fill_width > 0:
            pygame.draw.rect(panel_surf, color, (bar_x, bar_y, fill_width, bar_height), border_radius=3)

        # Bordure
        pygame.draw.rect(panel_surf, (100, 100, 120), (bar_x, bar_y, bar_width, bar_height), 1, border_radius=3)

        # Valeur texte
        value_text = text_font.render(f"{int(value)}/{int(max_val)}", True, (220, 220, 220))
        panel_surf.blit(value_text, (bar_x + bar_width + 5, y_offset))

        y_offset += 18

    y_offset += 5

    # === INVENTAIRE ===
    pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
    y_offset += 10

    header = header_font.render("Inventaire", True, (255, 220, 100))
    panel_surf.blit(header, (10, y_offset))
    y_offset += 20

    # Poids porté
    total_weight = sum(item.get("weight", 0) * item.get("quantity", 1) for item in ent.carrying)
    weight_limit = ent.physique.get("weight_limit", 10)
    weight_text = text_font.render(
        f"Poids: {total_weight:.1f} / {weight_limit:.1f} kg",
        True,
        (255, 200, 100) if total_weight <= weight_limit else (255, 100, 100)
    )
    panel_surf.blit(weight_text, (15, y_offset))
    y_offset += 20

    # Liste des items
    if not ent.carrying:
        empty_text = text_font.render("  (vide)", True, (150, 150, 150))
        panel_surf.blit(empty_text, (15, y_offset))
        y_offset += 18
    else:
        # Limiter l'affichage pour éviter le débordement
        max_items_display = 10
        for i, item in enumerate(ent.carrying[:max_items_display]):
            item_name = item.get("name", "Item inconnu")
            item_qty = item.get("quantity", 1)
            item_weight = item.get("weight", 0) * item.get("quantity", 1)

            # Icone selon le type
            item_type = item.get("type", "misc")
            icon = {"food": "🍖", "tool": "🔧", "resource": "📦", "weapon": "⚔️"}.get(item_type, "📦")

            # Texte de l'item
            if item_qty > 1:
                item_text = text_font.render(
                    f"  {icon} {item_name} x{item_qty}",
                    True,
                    (220, 220, 220)
                )
            else:
                item_text = text_font.render(
                    f"  {icon} {item_name}",
                    True,
                    (220, 220, 220)
                )

            panel_surf.blit(item_text, (15, y_offset))

            # Poids à droite
            weight_surf = text_font.render(f"{item_weight:.1f}kg", True, (160, 160, 160))
            panel_surf.blit(weight_surf, (panel_width - 70, y_offset))

            y_offset += 16

        # Si plus d'items que l'affichage
        if len(ent.carrying) > max_items_display:
            more_text = text_font.render(
                f"  ... et {len(ent.carrying) - max_items_display} autre(s)",
                True,
                (150, 150, 150)
            )
            panel_surf.blit(more_text, (15, y_offset))
            y_offset += 16

    # Afficher le panneau sur l'écran
    if ai_buttons:
        auto_mode = ent.ia.get("auto_mode") if hasattr(ent, "ia") else None
        separator_y = ai_buttons[0]["rect"].y - panel_y - 8
        pygame.draw.line(panel_surf, (80, 120, 160), (10, separator_y), (panel_width - 10, separator_y), 1)
        title = text_font.render("Auto IA", True, (185, 205, 235))
        panel_surf.blit(title, (10, max(0, separator_y - 14)))

        mouse_pos = pygame.mouse.get_pos()
        for button in ai_buttons:
            abs_rect = button["rect"]
            rect = abs_rect.move(-panel_x, -panel_y)
            is_hovered = abs_rect.collidepoint(mouse_pos)
            is_active = auto_mode == button["mode"]
            is_placeholder = button["mode"] != "harvest"

            bg = (45, 95, 55) if is_active else ((56, 74, 98) if is_hovered else (42, 54, 72))
            border = (130, 210, 140) if is_active else (90, 130, 170)
            if is_placeholder and not is_active:
                bg = (38, 44, 58)
                border = (70, 90, 120)

            pygame.draw.rect(panel_surf, bg, rect, border_radius=5)
            pygame.draw.rect(panel_surf, border, rect, 1, border_radius=5)
            label = text_font.render(button["label"], True, (235, 240, 245))
            panel_surf.blit(label, label.get_rect(center=rect.center))

    # Poignee de redimensionnement (tirer vers le bas)
    _draw_inspection_resize_handle(self, panel_surf, layout, panel_x, panel_y, panel_width)

    screen.blit(panel_surf, (panel_x, panel_y))
