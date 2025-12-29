# Alias pour compatibilité potentielle : la barre latérale est implémentée
# par LeftHUD, même si elle est affichée à droite de l'écran.
from .left_hud import LeftHUD as RightHUD

__all__ = ["RightHUD"]
