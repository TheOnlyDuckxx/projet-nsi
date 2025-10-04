from __future__ import annotations
import os, sys
import pygame
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Literal

def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


Color = Tuple[int, int, int]
Anchor = Literal[
    "center","topleft","topright","bottomleft","bottomright",
    "midtop","midleft","midright","midbottom"
]

@dataclass
class ButtonStyle:
    # Apparence
    draw_background: bool = True            # False => texte seul (pas de rectangle)
    bg_color: Color = (40, 44, 52)
    hover_bg_color: Color = (55, 60, 72)
    active_bg_color: Color = (30, 144, 255)

    # Bordure
    draw_border: bool = True
    border_color: Color = (90, 100, 120)
    border_width: int = 2
    radius: int = 12                        # coins arrondis

    # Texte / police
    font: Optional[pygame.font.Font] = None
    text_color: Color = (235, 235, 235)
    hover_text_color: Optional[Color] = None
    active_text_color: Optional[Color] = None
    antialias: bool = True
    padding_x: int = 18
    padding_y: int = 10

    # Ombre optionnelle
    shadow: bool = False
    shadow_offset: Tuple[int, int] = (2, 2)
    shadow_color: Color = (0, 0, 0)
    shadow_alpha: int = 80

    # Curseur main au survol
    mouse_cursor_hand: bool = True
    hover_zoom: float = 1.0      # 1.0 = désactivé ; ex: 1.08 pour +8% au survol
    zoom_speed: float = 0.20     # easing (0.1 = lent / 0.35 = rapide)

class Button:
    """
    Bouton modulaire :
    - Texte seul ou avec rectangle (draw_background=False/True)
    - Taille auto (à partir du texte) OU forcée via size=(w,h)
    - Position par ancre (center, topleft, etc.)
    - Couleurs hover/active, bordure on/off, rayon, ombre, icône optionnelle
    - Callback on_click OU détection par retour bool de handle()
    - Hotkey clavier optionnelle (pygame.K_RETURN, etc.)
    """
    def __init__(
        self,
        text: str,
        pos: Tuple[int, int],
        *,
        size: Optional[Tuple[int, int]] = None,
        anchor: Anchor = "center",
        style: Optional[ButtonStyle] = None,
        on_click: Optional[Callable[["Button"], None]] = None,
        hotkey: Optional[int] = None,
        icon: Optional[pygame.Surface] = None,      # icône à gauche du texte
        icon_gap: int = 8,
        enabled: bool = True,
        name: Optional[str] = None,
    ):
        self.text = text
        self.pos = pos
        self.size = size
        self.anchor = anchor
        self.style = style or ButtonStyle()
        self.on_click = on_click
        self.hotkey = hotkey
        self.icon = icon
        self.icon_gap = icon_gap
        self.enabled = enabled
        self.name = name or text
        

        # États internes
        self.is_hovered = False
        self.is_pressed = False
        self._cursor_set = False
        self.scale = 1.0

        # Police de secours si non fournie
        if self.style.font is None:
            self.style.font = pygame.font.Font(None, 28)

        # Pré-rendu texte (re-fait si texte change)
        self._render_cache = None  # (normal, hover, active)
        self._rebuild_surfaces()

        # Calcul rect initial
        self.rect = self._compute_rect()
        self._apply_anchor()

    # ---------- Construction / mise à jour taille ----------
    def _rebuild_surfaces(self):
        s = self.style
        txt = self.text

        # Couleurs de fallback
        hover_text_color = s.hover_text_color or s.text_color
        active_text_color = s.active_text_color or s.text_color

        text_normal = s.font.render(txt, s.antialias, s.text_color)
        text_hover = s.font.render(txt, s.antialias, hover_text_color)
        text_active = s.font.render(txt, s.antialias, active_text_color)
        self._render_cache = (text_normal, text_hover, text_active)

        # Mesure contenu (icône + texte)
        self._content_w = text_normal.get_width()
        self._content_h = text_normal.get_height()
        if self.icon:
            self._content_w += self.icon.get_width() + self.icon_gap
            self._content_h = max(self._content_h, self.icon.get_height())

    def _compute_rect(self) -> pygame.Rect:
        s = self.style
        if self.size is None:
            w = self._content_w + (0 if not s.draw_background else 2 * s.padding_x)
            h = self._content_h + (0 if not s.draw_background else 2 * s.padding_y)
        else:
            w, h = self.size
        return pygame.Rect(0, 0, int(w), int(h))

    def _apply_anchor(self):
        setattr(self.rect, self.anchor, self.pos)

    # ---------- API publique ----------
    def set_text(self, new_text: str):
        self.text = new_text
        self._rebuild_surfaces()
        if self.size is None:
            # Ajuste la taille si auto
            prev_anchor_pos = getattr(self.rect, self.anchor)
            self.rect = self._compute_rect()
            setattr(self.rect, self.anchor, prev_anchor_pos)

    def handle(self, events) -> bool:
        """Retourne True si cliqué ce frame (et déclenche on_click si fourni)."""
        clicked = False
        mouse_pos = pygame.mouse.get_pos()
        left_pressed = pygame.mouse.get_pressed(num_buttons=3)[0]

        self.is_hovered = self.rect.collidepoint(mouse_pos) and self.enabled

        # Gestion du curseur main
        if self.style.mouse_cursor_hand:
            if self.is_hovered and not self._cursor_set:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                self._cursor_set = True
            elif not self.is_hovered and self._cursor_set:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                self._cursor_set = False

        for e in events:
            # Hotkey clavier
            if self.enabled and self.hotkey and e.type == pygame.KEYDOWN and e.key == self.hotkey:
                clicked = True

            if not self.enabled:
                continue

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.is_hovered:
                self.is_pressed = True

            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if self.is_pressed and self.is_hovered:
                    clicked = True
                self.is_pressed = False

        if clicked and self.on_click:
            self.on_click(self)

        return clicked
        
    def draw(self, surface: pygame.Surface):
        s = self.style

        # Couleurs selon l'état (comme avant)
        if not self.enabled:
            bg = tuple(max(0, c - 40) for c in s.bg_color)
            fg = (160, 160, 160)
        elif self.is_pressed:
            bg = s.active_bg_color
            fg = (s.active_text_color or s.text_color)
        elif self.is_hovered:
            bg = s.hover_bg_color
            fg = (s.hover_text_color or s.text_color)
        else:
            bg = s.bg_color
            fg = s.text_color

        # Ombre & fond (inchangé)
        if s.shadow and s.draw_background:
            shadow_rect = self.rect.copy()
            shadow_rect.move_ip(*s.shadow_offset)
            shadow_surf = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
            shadow_surf.fill((*s.shadow_color, s.shadow_alpha))
            surface.blit(shadow_surf, shadow_rect.topleft)

        if s.draw_background:
            pygame.draw.rect(surface, bg, self.rect, border_radius=s.radius)
            if s.draw_border and s.border_width > 0:
                pygame.draw.rect(surface, s.border_color, self.rect, width=s.border_width, border_radius=s.radius)

        # --- Sélection surface de texte selon l'état ---
        text_normal, text_hover, text_active = self._render_cache
        if not self.enabled:
            base_text = self.style.font.render(self.text, self.style.antialias, fg)
        elif self.is_pressed:
            base_text = text_active
        elif self.is_hovered:
            base_text = text_hover
        else:
            base_text = text_normal

        # --- Zoom fluide : easing vers hover_zoom ou 1.0 ---
        target_scale = s.hover_zoom if (self.is_hovered and self.enabled) else 1.0
        self.scale += (target_scale - self.scale) * s.zoom_speed

        # On évite de scaler à 0 (sécurité numérique)
        scale = max(0.01, self.scale)

        # --- Dimensions internes dispo ---
        x = self.rect.x + (0 if not s.draw_background else s.padding_x)
        y = self.rect.y + (0 if not s.draw_background else s.padding_y)
        avail_w = self.rect.width - (0 if not s.draw_background else 2 * s.padding_x)
        avail_h = self.rect.height - (0 if not s.draw_background else 2 * s.padding_y)

        # --- Mesures contenu (icône + texte) avec zoom uniquement sur le texte ---
        text_w, text_h = base_text.get_size()
        scaled_text_w, scaled_text_h = int(text_w * scale), int(text_h * scale)
        icon_w = self.icon.get_width() if self.icon else 0
        icon_h = self.icon.get_height() if self.icon else 0
        content_w = scaled_text_w + (icon_w + self.icon_gap if self.icon else 0)
        content_h = max(scaled_text_h, icon_h)

        # Centrage du bloc (icône + texte)
        content_x = x + (avail_w - content_w) // 2
        content_y = y + (avail_h - content_h) // 2

        # Icône (non zoomée)
        cur_x = content_x
        if self.icon:
            icon_y = content_y + (content_h - icon_h) // 2
            surface.blit(self.icon, (cur_x, icon_y))
            cur_x += icon_w + self.icon_gap

        # Texte (zoomé)
        if scale != 1.0:
            text_surf = pygame.transform.smoothscale(base_text, (scaled_text_w, scaled_text_h))
        else:
            text_surf = base_text

        text_y = content_y + (content_h - scaled_text_h) // 2
        surface.blit(text_surf, (cur_x, text_y))

    # Pratique : déplacer le bouton tout en gardant l'ancre
    def move_to(self, pos: Tuple[int, int]):
        self.pos = pos
        self._apply_anchor()

    # Hitbox (utile pour tooltips)
    def get_rect(self) -> pygame.Rect:
        return self.rect