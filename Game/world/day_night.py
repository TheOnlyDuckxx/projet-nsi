"""
Système de cycle jour/nuit pour le jeu.
Gère le temps, les transitions et les effets visuels.
"""

import pygame
import math


class DayNightCycle:
    """
    Gère le cycle jour/nuit du jeu.
    
    Le temps est mesuré en secondes de jeu.
    Un cycle complet = durée configurable (par défaut 10 minutes réelles)
    """
    
    def __init__(self, cycle_duration=100):
        """
        Args:
            cycle_duration: Durée d'un cycle complet en secondes réelles (défaut: 600 = 10 min)
        """
        self.cycle_duration = cycle_duration  # durée totale d'un cycle en secondes
        self.time_elapsed = 0  # temps écoulé depuis le début du cycle (0 à cycle_duration)
        
        # Configuration des phases
        self.phases = {
            "aube": (0.0, 0.25),        # plus long
            "jour": (0.25, 0.60),
            "crépuscule": (0.60, 0.85), # plus long
            "nuit": (0.85, 1.0),
        }

        
        # Vitesse d'écoulement du temps (1.0 = temps normal, 2.0 = 2x plus rapide)
        self.time_speed = 2.0
        
        # Pause
        self.paused = False
    
    def update(self, dt):
        """
        Met à jour le cycle en fonction du temps écoulé.
        
        Args:
            dt: Delta time en secondes (temps depuis la dernière frame)
        """
        if self.paused:
            return
        
        self.time_elapsed += dt * self.time_speed
        
        # Boucle le cycle
        if self.time_elapsed >= self.cycle_duration:
            self.time_elapsed = self.time_elapsed % self.cycle_duration
    
    def get_time_ratio(self):
        """Retourne le ratio du temps dans le cycle (0.0 à 1.0)"""
        return self.time_elapsed / self.cycle_duration
    
    def get_current_phase(self):
        """Retourne la phase actuelle ('aube', 'jour', 'crépuscule', 'nuit')"""
        ratio = self.get_time_ratio()
        for phase_name, (start, end) in self.phases.items():
            if start <= ratio < end:
                return phase_name
        
        return "nuit"  # par défaut
    
    def get_phase_progress(self):
        """
        Retourne le progrès dans la phase actuelle (0.0 à 1.0)
        Utile pour les transitions douces.
        """
        ratio = self.get_time_ratio()
        phase = self.get_current_phase()
        start, end = self.phases[phase]
        
        if end == start:
            return 0.0
        
        return (ratio - start) / (end - start)
    
    def is_night(self):
        """Retourne True si c'est la nuit (ou crépuscule)"""
        phase = self.get_current_phase()
        return phase in ["nuit", "crépuscule"]
    
    def is_day(self):
        """Retourne True si c'est le jour (ou aube)"""
        return not self.is_night()
    
    def _ease_in_out(self, t: float) -> float:
        # t in [0,1] -> sortie in [0,1] très progressive
        return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))

    def get_light_level(self, min_light=0.55):
        phase = self.get_current_phase()
        p = self._ease_in_out(self.get_phase_progress())

        if phase == "aube":
            return min_light + (1.0 - min_light) * p
        elif phase == "jour":
            return 1.0
        elif phase == "crépuscule":
            return 1.0 - (1.0 - min_light) * p
        else:  # nuit
            return min_light
    
    def get_ambient_color(self):
        """
        Retourne la couleur ambiante pour teinter le jeu.
        Format: (R, G, B) avec valeurs de 0 à 255
        """
        phase = self.get_current_phase()
        progress = self.get_phase_progress()
        
        # Couleurs de référence
        night_color = (40, 50, 90)      # Bleu nuit
        dawn_color = (255, 200, 150)    # Orange aube
        day_color = (255, 255, 255)     # Blanc jour
        dusk_color = (255, 150, 100)    # Orange/rouge crépuscule
        
        if phase == "aube":
            # Interpolation entre nuit et jour via aube
            return self._lerp_color(night_color, dawn_color, progress * 0.5)
        elif phase == "jour":
            return day_color
        elif phase == "crépuscule":
            # Interpolation entre jour et nuit via crépuscule
            return self._lerp_color(dusk_color, night_color, progress)
        else:  # nuit
            return night_color
    
    def _lerp_color(self, color1, color2, t):
        """Interpolation linéaire entre deux couleurs"""
        return (
            int(color1[0] + (color2[0] - color1[0]) * t),
            int(color1[1] + (color2[1] - color1[1]) * t),
            int(color1[2] + (color2[2] - color1[2]) * t),
        )
    
    def get_clock_angle(self):
        """
        Retourne l'angle pour l'aiguille de l'horloge (en degrés).
        0° = minuit (haut), 90° = 6h, 180° = midi (bas), 270° = 18h
        """
        ratio = self.get_time_ratio()
        # Angle en degrés (0 = haut, sens horaire)
        return ratio * 360
    
    def get_time_string(self):
        """Retourne le temps sous forme de string (format 24h)"""
        ratio = self.get_time_ratio()
        hours = int(ratio * 24)
        minutes = int((ratio * 24 * 60) % 60)
        return f"{hours:02d}:{minutes:02d}"
    
    def set_time(self, hour, minute=0):
        """
        Définit l'heure actuelle.
        
        Args:
            hour: Heure (0-23)
            minute: Minutes (0-59)
        """
        total_minutes = hour * 60 + minute
        ratio = total_minutes / (24 * 60)
        self.time_elapsed = ratio * self.cycle_duration
    
    def toggle_pause(self):
        """Met en pause ou reprend le cycle"""
        self.paused = not self.paused
    
    def set_speed(self, speed):
        """Définit la vitesse d'écoulement du temps"""
        self.time_speed = max(0.1, speed)


class ClockRenderer:
    """
    Classe utilitaire pour dessiner une horloge animée.
    À utiliser dans le HUD.
    """
    
    def __init__(self, radius=18):
        self.radius = radius
    
    def draw(self, screen, center_x, center_y, day_night_cycle, font=None):
        """
        Dessine l'horloge avec l'aiguille qui indique l'heure.
        
        Args:
            screen: Surface Pygame où dessiner
            center_x, center_y: Position du centre de l'horloge
            day_night_cycle: Instance de DayNightCycle
            font: Police optionnelle pour afficher l'heure en texte
        """
        # Fond de l'horloge (couleur selon jour/nuit)
        phase = day_night_cycle.get_current_phase()
        
        if phase == "nuit":
            bg_color = (20, 25, 50)
            border_color = (80, 90, 140)
        elif phase in ["aube", "crépuscule"]:
            bg_color = (80, 60, 40)
            border_color = (180, 140, 100)
        else:  # jour
            bg_color = (200, 220, 255)
            border_color = (100, 150, 200)
        
        # Cercle de fond
        pygame.draw.circle(screen, bg_color, (center_x, center_y), self.radius)
        pygame.draw.circle(screen, border_color, (center_x, center_y), self.radius, 2)
        
        # Marques pour minuit (haut) et midi (bas)
        pygame.draw.circle(screen, border_color, (center_x, center_y - self.radius + 3), 2)
        pygame.draw.circle(screen, border_color, (center_x, center_y + self.radius - 3), 2)
        
        # Aiguille
        angle = day_night_cycle.get_clock_angle()
        # Convertir en radians (pygame utilise le cercle trigonométrique)
        # On soustrait 90° pour que 0° soit en haut
        angle_rad = math.radians(angle - 90)
        
        # Longueur de l'aiguille
        hand_length = self.radius - 5
        
        # Position de la pointe de l'aiguille
        hand_x = center_x + math.cos(angle_rad) * hand_length
        hand_y = center_y + math.sin(angle_rad) * hand_length
        
        # Couleur de l'aiguille
        hand_color = (220, 220, 220) if phase != "jour" else (50, 50, 50)
        
        # Dessiner l'aiguille
        pygame.draw.line(screen, hand_color, (center_x, center_y), (hand_x, hand_y), 2)
        
        # Point central
        pygame.draw.circle(screen, hand_color, (center_x, center_y), 3)
        
        # Afficher l'heure en texte (optionnel)
        if font:
            time_str = day_night_cycle.get_time_string()
            txt = font.render(time_str, True, (240, 240, 240))
            txt_rect = txt.get_rect(center=(center_x, center_y + self.radius + 12))
            screen.blit(txt, txt_rect)


# Exemple d'utilisation dans Phase1 ou un autre manager:
"""
# Dans __init__:
self.day_night = DayNightCycle(cycle_duration=600)  # 10 minutes par cycle
self.day_night.set_time(6, 0)  # Commence à 6h du matin
self.clock_renderer = ClockRenderer(radius=18)

# Dans update:
self.day_night.update(dt)

# Pour obtenir des infos:
if self.day_night.is_night():
    # Augmenter le danger, réduire la visibilité...
    pass

light_level = self.day_night.get_light_level()
# Utiliser light_level pour ajuster le brouillard de guerre

# Dans le HUD:
self.clock_renderer.draw(screen, cx, cy, self.day_night, self.small_font)
"""