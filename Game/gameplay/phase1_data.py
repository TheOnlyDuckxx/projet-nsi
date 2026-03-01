from __future__ import annotations

import json

from Game.core.utils import resource_path


def load_prop_descriptions(path: str = "Game/data/props_descriptions.json") -> dict:
    """Charge les descriptions des props depuis le fichier JSON."""
    data = {"by_id": {}}

    with open(resource_path(path), "r", encoding="utf-8") as f:
        payload = json.load(f)

    by_id = {}
    raw_by_id = payload.get("by_id") if isinstance(payload, dict) else None
    if isinstance(raw_by_id, dict):
        for key, value in raw_by_id.items():
            if not isinstance(value, dict):
                continue
            pid = str(key).strip()
            if not pid:
                continue
            by_id[pid] = {
                "name": str(value.get("name", "") or "").strip(),
                "description": str(value.get("description", "") or "").strip(),
            }
    elif isinstance(payload, dict) and isinstance(payload.get("props"), list):
        for item in payload.get("props") or []:
            if not isinstance(item, dict):
                continue
            pid = item.get("id")
            if pid is None:
                continue
            pid = str(pid).strip()
            by_id[pid] = {
                "name": str(item.get("name", "") or "").strip(),
                "description": str(item.get("description", "") or "").strip(),
            }

    data["by_id"] = by_id
    return data


def get_prop_description_entry(prop_descriptions: dict, pid: int):
    """Récupère la description d'un prop à partir de son ID."""
    by_id = (prop_descriptions or {}).get("by_id", {})
    return by_id.get(str(int(pid)))


def collect_species_stats(species) -> dict:
    """Récupère les stats de base d'une espèce."""
    if not species:
        return {}
    categories = {
        "physique": dict(getattr(species, "base_physique", {}) or {}),
        "sens": dict(getattr(species, "base_sens", {}) or {}),
        "mental": dict(getattr(species, "base_mental", {}) or {}),
        "social": dict(getattr(species, "base_social", {}) or {}),
        "environnement": dict(getattr(species, "base_environnement", {}) or {}),
        "genetique": dict(getattr(species, "genetique", {}) or {}),
    }
    cleaned = {}
    for cat, values in categories.items():
        cleaned[cat] = {}
        for key, value in values.items():
            if isinstance(value, (int, float)):
                cleaned[cat][str(key)] = float(value)
            else:
                cleaned[cat][str(key)] = value
    return cleaned
