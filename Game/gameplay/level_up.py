# Game/gameplay/level_up.py

import random
import pygame


class LevelUp:
    """
    Gère le menu de montée de niveau d'ESPÈCE :
    - quand l'espèce monte de niveau, on ouvre un menu
    - le jeu est en pause tant que active == True
    - le joueur choisit une mutation parmi 5 cartes
    """

    def __init__(self, espece):
        self.espece = espece
        self.current_level = espece.species_level

        self.active = False          # True = menu affiché
        self.choices = []            # liste de noms de mutations (clés du JSON)
        self.card_rects = []         # pygame.Rect de base (sans zoom)

        self.font_title = None
        self.font_mutation = None

        # Hover / sélection
        self.hover_index = None      # index de la carte survolée
        self.selected_index = None   # index de la carte cliquée
        self.selection_time_ms = 0   # temps du clic (ms)
        self.selection_duration_ms = 1200  # durée de l'animation (ms)

    # ------------------------------------------------------------------
    # Appelé par Espece.add_xp quand le niveau augmente
    # ------------------------------------------------------------------
    def update_level(self, new_lvl):
        """
        Déclenche un nouveau "level up" :
        génère 5 mutations et active le menu.
        """
        if new_lvl <= self.current_level:
            return

        self.current_level = new_lvl
        self._generate_choices()
        self.active = True
        self.selected_index = None
        self.selection_time_ms = 0

    # ------------------------------------------------------------------
    # Sélection de 5 mutations
    # ------------------------------------------------------------------
    def _generate_choices(self):
        """
        Tire jusqu'à 5 mutations disponibles, sans doublon.
        Utilise le MutationManager de l'espèce.
        """
        manager = self.espece.mutations
        disponibles = manager.mutations_disponibles()

        if not disponibles:
            print("[LevelUp] Aucune mutation disponible 🤷")
            self.choices = []
            return

        random.shuffle(disponibles)
        self.choices = disponibles[:5]

    # ------------------------------------------------------------------
    # Gestion des événements
    # ------------------------------------------------------------------
    def handle_event(self, event, screen):
        """
        À appeler depuis la boucle d'événements Pygame.
        Quand le joueur clique sur une carte, on applique la mutation,
        puis on lance une animation avant de fermer.
        """
        if not self.active:
            return

        # Pendant l'animation de sélection, on ignore les clics
        if self.selected_index is not None:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos

            # recalculer les rectangles avec la taille actuelle de l'écran
            self.card_rects = self._compute_card_rects(screen)

            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(mouse_pos) and i < len(self.choices):
                    mutation_nom = self.choices[i]
                    print(f"[LevelUp] Mutation choisie : {mutation_nom}")
                    # On applique la mutation tout de suite
                    self.espece.mutations.appliquer(mutation_nom)

                    # On lance l'animation de "SFX visuel"
                    self.selected_index = i
                    self.selection_time_ms = pygame.time.get_ticks()
                    return

    # ------------------------------------------------------------------
    # Rendu du menu (overlay + cartes)
    # ------------------------------------------------------------------
    def render(self, screen, assets):
        """
        Dessine l'overlay de montée de niveau + 5 cartes de mutation.
        À appeler à la place du rendu normal quand self.active == True.
        """
        if not self.active:
            return

        if self.font_title is None:
            self.font_title = pygame.font.SysFont("arial", 32, bold=True)
        if self.font_mutation is None:
            self.font_mutation = pygame.font.SysFont("arial", 18)

        w, h = screen.get_size()

        # 1) overlay noir semi-transparent
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # 2) titre
        titre = f"Niveau d'espèce {self.current_level} atteint !"
        txt_surface = self.font_title.render(titre, True, (255, 255, 255))
        txt_rect = txt_surface.get_rect(center=(w // 2, h // 6))
        screen.blit(txt_surface, txt_rect)

        sous_titre_surface = self.font_mutation.render(
            "Choisissez une mutation pour votre espèce",
            True,
            (220, 220, 220),
        )
        sous_titre_rect = sous_titre_surface.get_rect(center=(w // 2, h // 6 + 40))
        screen.blit(sous_titre_surface, sous_titre_rect)

        # 3) cartes de base (sans zoom)
        self.card_rects = self._compute_card_rects(screen)

        # sprite de carte (commun à toutes les mutations)
        card_sprite = assets.get_image("example_mutation")

        # Gestion du temps pour l'animation
        now_ms = pygame.time.get_ticks()
        elapsed_ms = 0
        t_norm = 0.0
        if self.selected_index is not None and self.selection_time_ms:
            elapsed_ms = now_ms - self.selection_time_ms
            t_norm = min(1.0, elapsed_ms / self.selection_duration_ms)

            # Si l'animation est finie, on ferme le menu
            if elapsed_ms >= self.selection_duration_ms:
                self.active = False
                self.selected_index = None
                return

        # Index de la carte survolée (si aucune sélection)
        mouse_pos = pygame.mouse.get_pos()
        self.hover_index = None
        if self.selected_index is None:
            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(mouse_pos):
                    self.hover_index = i
                    break

        # Dessin des cartes
        for i, rect in enumerate(self.card_rects):
            if i >= len(self.choices):
                break

            draw_rect = rect.copy()

            # -------------------------
            # Effet de zoom / animation
            # -------------------------
            scale = 1.0

            if self.selected_index is not None:
                # Animation de la carte sélectionnée
                if i == self.selected_index:
                    # petit "bump" : grossit puis se stabilise un peu
                    # courbe lisse : 1 + 0.25 * (1 - (t-1)^2) ∈ [1, ~1.25]
                    scale = 1.0 + 0.25 * (1.0 - (t_norm - 1.0) ** 2)
                else:
                    # les autres cartes sont légèrement réduites et "éteintes"
                    scale = 0.9
            else:
                # Pas encore de sélection : zoom léger au survol
                if self.hover_index == i:
                    scale = 1.1

            if scale != 1.0:
                new_w = int(rect.width * scale)
                new_h = int(rect.height * scale)
                draw_rect.width = new_w
                draw_rect.height = new_h
                draw_rect.center = rect.center

            # -------------------------
            # Dessin du fond de carte (sprite)
            # -------------------------
            if card_sprite is not None:
                # On garde 30 px en bas pour le texte
                img_h = max(1, draw_rect.height - 30)
                sprite = pygame.transform.smoothscale(
                    card_sprite, (draw_rect.width, img_h)
                )
                screen.blit(sprite, (draw_rect.x, draw_rect.y))
            else:
                # Fallback : simple rectangle gris, sans bord blanc
                card_surface = pygame.Surface((draw_rect.width, draw_rect.height - 30))
                card_surface.fill((80, 80, 80))
                screen.blit(card_surface, (draw_rect.x, draw_rect.y))

            # -------------------------
            # Nom de la mutation sous la carte
            # -------------------------
            nom_mutation = self.choices[i]
            mutation_data = self.espece.mutations.get_mutation(nom_mutation)
            label = mutation_data.get("nom", nom_mutation) if mutation_data else nom_mutation

            text_surface = self.font_mutation.render(label, True, (255, 255, 255))
            text_rect = text_surface.get_rect(
                center=(draw_rect.centerx, draw_rect.bottom - 15)
            )
            screen.blit(text_surface, text_rect)

        # -------------------------
        # Effet "flash" global lors de la sélection (SFX visuel)
        # -------------------------
        if self.selected_index is not None:
            # flash rapide au début, qui s'éteint ensuite
            flash_strength = max(0.0, 1.0 - t_norm * 2.0)  # disparaît vers t ≈ 0.5
            if flash_strength > 0.0:
                flash_alpha = int(80 * flash_strength)
                flash_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                flash_surface.fill((255, 255, 255, flash_alpha))
                screen.blit(flash_surface, (0, 0))

    # ------------------------------------------------------------------
    # Calcul de la position des 5 cartes (rectangles de base)
    # ------------------------------------------------------------------
    def _compute_card_rects(self, screen):
        w, h = screen.get_size()

        card_width = int(w * 0.12)
        card_height = int(h * 0.35)

        total_width = 5 * card_width + 4 * 20  # 20 px de marge entre les cartes
        start_x = (w - total_width) // 2
        y = int(h * 0.35)

        rects = []
        for i in range(5):
            x = start_x + i * (card_width + 20)
            rects.append(pygame.Rect(x, y, card_width, card_height))
        return rects
