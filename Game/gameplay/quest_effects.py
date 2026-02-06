from __future__ import annotations

import random
from typing import Any, Dict, Iterable, Optional


_STAT_CONTAINERS = (
    ("base_physique", "physique"),
    ("base_sens", "sens"),
    ("base_mental", "mental"),
    ("base_environnement", "environnement"),
    ("base_social", "social"),
    ("genetique", "genetique"),
    ("arbre_phases3", "arbre_phases3"),
)


def apply_quest_effect(phase: Any, effect: Dict[str, Any]) -> bool:
    """Applique un effet de quête centré sur les stats d'espèce.

    Retourne True si l'effet a été pris en charge.
    """
    if not isinstance(effect, dict):
        return False
    etype = effect.get("type")
    if etype == "modify_stat":
        stat = effect.get("stat")
        amount = _parse_amount(effect.get("amount"))
        if stat and amount is not None:
            return _apply_species_stat(phase, stat, amount)
        return False
    if etype == "modify_intelligence":
        amount = _parse_amount(effect.get("amount"))
        if amount is None:
            return False
        return _apply_species_stat(phase, "intelligence", amount)
    if etype == "rename_inhabitant":
        name = effect.get("name")
        if not name:
            return False
        return _rename_random_inhabitant(phase, str(name), locked=True)
    return False


def _parse_amount(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
    return None


def _apply_species_stat(phase: Any, stat: str, amount: float) -> bool:
    espece = getattr(phase, "espece", None)
    if espece is None:
        return False

    applied = False
    for base_attr, indiv_attr in _STAT_CONTAINERS:
        base_stats = getattr(espece, base_attr, None)
        if isinstance(base_stats, dict) and stat in base_stats:
            base_stats[stat] += amount
            _apply_to_individus(getattr(espece, "individus", []), indiv_attr, stat, amount)
            applied = True

    if not applied:
        base_stats = getattr(espece, "arbre_phases3", None)
        if isinstance(base_stats, dict):
            base_stats[stat] = base_stats.get(stat, 0) + amount
            applied = True

    return applied


def _apply_to_individus(individus: Iterable[Any], attr: str, stat: str, amount: float) -> None:
    for individu in individus:
        stats = getattr(individu, attr, None)
        if isinstance(stats, dict) and stat in stats:
            stats[stat] += amount


def _rename_random_inhabitant(phase: Any, name: str, *, locked: bool = False) -> bool:
    espece = getattr(phase, "espece", None)
    if espece is None:
        return False
    candidates = [
        ind for ind in getattr(espece, "individus", [])
        if not getattr(ind, "is_fauna", False) and not getattr(ind, "is_egg", False)
    ]
    if not candidates:
        return False
    target = random.choice(candidates)
    if hasattr(target, "set_name"):
        target.set_name(name, locked=locked)
    else:
        target.nom = name
        if locked:
            target.name_locked = True
    return True
