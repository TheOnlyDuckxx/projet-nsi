import pygame
import time
import textwrap

# Configuration de base
NOTIF_FONT = pygame.font.SysFont("consolas", 18)
NOTIF_MAX_WIDTH = 300  # largeur max pixels
NOTIF_BG_COLOR = (25, 25, 25)
NOTIF_TEXT_COLOR = (255, 255, 255)
NOTIF_BORDER_COLOR = (200, 200, 200)
NOTIF_PADDING = 10
NOTIF_SPACING = 10
NOTIF_DURATION = 3.0  # secondes d'affichage
NOTIF_FADE_TIME = 0.5  # secondes avant disparition

notifications = []  # liste globale de notifs actives


def add_notification(message: str):
    """
    Crée et ajoute une notification à afficher.
    """
    if message in notifications:
        return
    if not message:
        return

    wrapped = _wrap_text(message, NOTIF_FONT, NOTIF_MAX_WIDTH - 2 * NOTIF_PADDING)
    width = min(
        NOTIF_MAX_WIDTH,
        max(NOTIF_FONT.size(line)[0] for line in wrapped) + 2 * NOTIF_PADDING,
    )
    height = len(wrapped) * NOTIF_FONT.get_height() + 2 * NOTIF_PADDING

    notif = {
        "text": wrapped,
        "start": time.time(),
        "width": width,
        "height": height,
    }
    notifications.append(notif)


def _wrap_text(text, font, max_width):
    """
    Coupe le texte pour qu'il tienne dans la largeur max, avec des retours à la ligne automatiques.
    """
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test_line = current + " " + word if current else word
        if font.size(test_line)[0] <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    return lines


def draw_notifications(screen):
    """
    Affiche toutes les notifications actives en bas à droite de l'écran.
    """
    now = time.time()
    screen_width, screen_height = screen.get_size()

    # On part du bas de l'écran vers le haut
    y = screen_height - NOTIF_SPACING

    # On itère à l'envers (pour supprimer sans bug)
    for notif in notifications[:]:
        elapsed = now - notif["start"]

        # Effet de fade-out
        if elapsed > NOTIF_DURATION + NOTIF_FADE_TIME:
            notifications.remove(notif)
            continue
        elif elapsed > NOTIF_DURATION:
            alpha = 255 * (1 - (elapsed - NOTIF_DURATION) / NOTIF_FADE_TIME)
        else:
            alpha = 255

        # Création du fond avec alpha
        surface = pygame.Surface((notif["width"], notif["height"]), pygame.SRCALPHA)
        surface.fill((*NOTIF_BG_COLOR, int(alpha * 0.9)))

        # Bordure
        pygame.draw.rect(surface, NOTIF_BORDER_COLOR, surface.get_rect(), 2)

        # Texte
        text_y = NOTIF_PADDING
        for line in notif["text"]:
            text_surf = NOTIF_FONT.render(line, True, NOTIF_TEXT_COLOR)
            surface.blit(text_surf, (NOTIF_PADDING, text_y))
            text_y += NOTIF_FONT.get_height()

        # Position (bas-droite)
        x = screen_width - notif["width"] - NOTIF_SPACING
        y -= notif["height"]
        screen.blit(surface, (x, y))
        y -= NOTIF_SPACING

def draw_work_bar(self, screen, ent):
        w = getattr(ent, "work", None)
        if not w or ent.ia["etat"] != "recolte":
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

def draw_info_panel(self, screen):
    """Panneau d'infos générales en haut à gauche"""
    lines = [
        f"Phase1 — {self.params.world_name if self.params else '...'}",
        f"Size: {self.world.width}x{self.world.height}" if self.world else "",
        f"Zoom: {self.view.zoom:.2f} (min {self.view.min_zoom}, max {self.view.max_zoom})",
        "Controls: Clic gauche = sélectionner | Clic droit = déplacer | Molette/drag = caméra | R = regénérer | I = HUD",
    ]
    x, y = 10, 10
    for txt in lines:
        if not txt: continue
        surf = self.font.render(txt, True, (220, 230, 240))
        screen.blit(surf, (x, y)); y += 18

def draw_inspection_panel(self, screen):
    """Panneau d'inspection détaillé pour l'entité sélectionnée"""
    if not self.selected or self.selected[0] != "entity":
        return
    
    ent = self.selected[1]
    
    # Configuration du panneau
    panel_width = 350
    panel_height = screen.get_height() - 700
    panel_x = screen.get_width() - panel_width 
    panel_y = 0
    
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
    
    # === TITRE ===
    title = title_font.render(f"🔍 {ent.nom}", True, (220, 240, 255))
    panel_surf.blit(title, (10, y_offset))
    y_offset += 30
    
    # Ligne de séparation
    pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
    y_offset += 10
    
    # === POSITION ===
    pos_text = text_font.render(f"Position: ({int(ent.x)}, {int(ent.y)})", True, (200, 200, 200))
    panel_surf.blit(pos_text, (10, y_offset))
    y_offset += 20
    
    # === JAUGES VITALES ===
    header = header_font.render("⚡ Jauges", True, (255, 220, 100))
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
    
    # === STATS PHYSIQUES ===
    header = header_font.render("💪 Physique", True, (255, 180, 100))
    panel_surf.blit(header, (10, y_offset))
    y_offset += 20
    
    stats_physiques = [
        ("Force", ent.physique.get("force", 0)),
        ("Endurance", ent.physique.get("endurance", 0)),
        ("Vitesse", ent.physique.get("vitesse", 0)),
        ("Taille", ent.physique.get("taille", 0)),
    ]
    
    for label, value in stats_physiques:
        stat_text = text_font.render(f"  {label}: {value}", True, (200, 200, 200))
        panel_surf.blit(stat_text, (15, y_offset))
        y_offset += 16
    
    y_offset += 5
    
    # === STATS MENTALES ===
    header = header_font.render("🧠 Mental", True, (150, 200, 255))
    panel_surf.blit(header, (10, y_offset))
    y_offset += 20
    
    stats_mentales = [
        ("Intelligence", ent.mental.get("intelligence", 0)),
        ("Dextérité", ent.mental.get("dexterité", 0)),
        ("Courage", ent.mental.get("courage", 0)),
        ("Sociabilité", ent.mental.get("sociabilite", 0)),
    ]
    
    for label, value in stats_mentales:
        stat_text = text_font.render(f"  {label}: {value}", True, (200, 200, 200))
        panel_surf.blit(stat_text, (15, y_offset))
        y_offset += 16
    
    y_offset += 10
    
    # === INVENTAIRE ===
    pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
    y_offset += 10
    
    header = header_font.render("🎒 Inventaire", True, (255, 220, 100))
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


            
            # Icône selon le type
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
    
    # === ÉTAT IA ===
    if y_offset < panel_height - 50:
        y_offset += 10
        pygame.draw.line(panel_surf, (80, 120, 160), (10, y_offset), (panel_width - 10, y_offset), 1)
        y_offset += 10
        
        header = header_font.render("🤖 État", True, (150, 255, 150))
        panel_surf.blit(header, (10, y_offset))
        y_offset += 20
        
        etat = ent.ia.get("etat", "idle")
        etat_text = text_font.render(f"  Activité: {etat}", True, (200, 200, 200))
        panel_surf.blit(etat_text, (15, y_offset))
    
    # Afficher le panneau sur l'écran
    screen.blit(panel_surf, (panel_x, panel_y))

