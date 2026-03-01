#LEVEL_UP.PY
# Gère la montée de niveau de l'espèce du joueur

# --------------- IMPORTATION DES MODULES ---------------
import pygame

# --------------- CLASSE PRINCIPALE ---------------
class LevelUp:
    """
    Gère le menu de montée de niveau d'ESPÈCE :
    - quand l'espèce monte de niveau, on ouvre un menu
    - met le jeu en pause
    - le joueur choisit une mutation parmi 5
    """

    def __init__(self, espece):
        self.espece = espece
        self.current_level = espece.species_level

        self.active = False
        self.choices = []
        self.card_rects = []

        self.font_title = None
        self.font_mutation = None

        # Hover / sélection
        self.hover_index = None
        self.selected_index = None
        self.selection_time_ms = 0
        self.selection_duration_ms = 1200


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

    def _generate_choices(self):
        """
        Tire jusqu'à 5 mutations disponibles, sans doublon.
        Utilise le MutationManager de l'espèce.
        """
        manager = self.espece.mutations
        self.choices = manager.pick_available_mutations(max_count=5)

    def handle_event(self, event, screen):
        """
        À appeler depuis la boucle d'événements Pygame.
        Quand le joueur clique sur une carte, on applique la mutation puis on lance une animation avant de fermer.
        """
        if not self.active:
            return

        # on ignore les clics
        if self.selected_index is not None:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos

            # recalculer les rectangles avec la taille actuelle de l'écran
            self.card_rects = self._compute_card_rects(screen)

            for i, rect in enumerate(self.card_rects):
                if rect.collidepoint(mouse_pos) and i < len(self.choices):
                    mutation_nom = self.choices[i]
                    self.espece.mutations.appliquer(mutation_nom)
                    self.selected_index = i
                    self.selection_time_ms = pygame.time.get_ticks()
                    return

    def render(self, screen, assets):
        """
        Dessine l'overlay de montée de niveau + 5 cartes de mutation.
        """
        if not self.active:
            return

        if self.font_title is None:
            self.font_title = pygame.font.SysFont("arial", 32, bold=True)
        if self.font_mutation is None:
            self.font_mutation = pygame.font.SysFont("arial", 18)

        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

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

        self.card_rects = self._compute_card_rects(screen)

        card_sprite = assets.get_image("example_mutation")

        now_ms = pygame.time.get_ticks()
        elapsed_ms = 0
        t_norm = 0.0
        if self.selected_index is not None and self.selection_time_ms:
            elapsed_ms = now_ms - self.selection_time_ms
            t_norm = min(1.0, elapsed_ms / self.selection_duration_ms)
            if elapsed_ms >= self.selection_duration_ms:
                self.active = False
                self.selected_index = None
                return

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
            scale = 1.0

            if self.selected_index is not None:
                if i == self.selected_index:
                    scale = 1.0 + 0.25 * (1.0 - (t_norm - 1.0) ** 2)
                else:
                    scale = 0.9
            else:
                if self.hover_index == i:
                    scale = 1.1

            if scale != 1.0:
                new_w = int(rect.width * scale)
                new_h = int(rect.height * scale)
                draw_rect.width = new_w
                draw_rect.height = new_h
                draw_rect.center = rect.center

            img_h = max(1, draw_rect.height - 30)
            sprite = pygame.transform.smoothscale(
                card_sprite, (draw_rect.width, img_h)
            )
            screen.blit(sprite, (draw_rect.x, draw_rect.y))
            

            # Nom de la mutation sous la carte
            nom_mutation = self.choices[i]
            mutation_data = self.espece.mutations.get_mutation(nom_mutation)
            label = mutation_data.get("nom", nom_mutation) if mutation_data else nom_mutation

            text_surface = self.font_mutation.render(label, True, (255, 255, 255))
            text_rect = text_surface.get_rect(
                center=(draw_rect.centerx, draw_rect.bottom - 15)
            )
            screen.blit(text_surface, text_rect)

        # sfx "flash"
        if self.selected_index is not None:
            flash_strength = max(0.0, 1.0 - t_norm * 2.0)
            if flash_strength > 0.0:
                flash_alpha = int(80 * flash_strength)
                flash_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                flash_surface.fill((255, 255, 255, flash_alpha))
                screen.blit(flash_surface, (0, 0))

    def _compute_card_rects(self, screen):
        """Calcul de la position des cartes"""
        w, h = screen.get_size()

        card_width = int(w * 0.12)
        card_height = int(h * 0.35)

        total_width = 5 * card_width + 4 * 20
        start_x = (w - total_width) // 2
        y = int(h * 0.35)

        rects = []
        for i in range(5):
            x = start_x + i * (card_width + 20)
            rects.append(pygame.Rect(x, y, card_width, card_height))
        return rects
