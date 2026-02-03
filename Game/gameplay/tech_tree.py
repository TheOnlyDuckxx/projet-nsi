from __future__ import annotations

import json
from typing import Callable, Dict, Optional


class TechTreeManager:
    def __init__(self, data_path: str, on_unlock: Optional[Callable[[str, Dict], None]] = None):
        self.data_path = data_path
        self.on_unlock = on_unlock
        self.techs: Dict[str, Dict] = {}
        self.unlocked: set[str] = set()
        self.current_research: Optional[str] = None
        self.current_progress = 0
        self.innovations = 0
        self._load_data()

    def _load_data(self) -> None:
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                self.techs = json.load(f) or {}
        except Exception as exc:
            print(f"[TechTree] Erreur chargement {self.data_path}: {exc}")
            self.techs = {}

    def get_cost(self, tech_id: str) -> int:
        return int(self.techs.get(tech_id, {}).get("cout", 0))

    def get_tech(self, tech_id: str) -> Dict:
        return self.techs.get(tech_id, {})

    def get_dependencies(self, tech_id: str) -> list[str]:
        deps = self.techs.get(tech_id, {}).get("conditions", [])
        return list(deps) if isinstance(deps, list) else []

    def can_start(self, tech_id: str) -> bool:
        if tech_id in self.unlocked:
            return False
        if self.current_research is not None:
            return False
        return all(dep in self.unlocked for dep in self.get_dependencies(tech_id))

    def _apply_innovation(self, amount: int) -> None:
        if self.current_research is None:
            self.innovations += amount
            return

        remaining = max(0, self.get_cost(self.current_research) - self.current_progress)
        used = min(remaining, amount)
        self.current_progress += used
        leftover = amount - used

        if self.current_research and self.current_progress >= self.get_cost(self.current_research):
            tech_id = self.current_research
            self.current_research = None
            self.current_progress = 0
            self.unlocked.add(tech_id)
            if self.on_unlock:
                self.on_unlock(tech_id, self.get_tech(tech_id))

        if leftover > 0:
            self.innovations += leftover

    def start_research(self, tech_id: str) -> bool:
        if not self.can_start(tech_id):
            return False
        self.current_research = tech_id
        self.current_progress = 0
        if self.innovations > 0:
            stored = self.innovations
            self.innovations = 0
            self._apply_innovation(stored)
        return True

    def add_innovation(self, amount: int = 1) -> None:
        if amount <= 0:
            return
        self._apply_innovation(amount)

    def to_dict(self) -> Dict:
        return {
            "unlocked": list(self.unlocked),
            "current_research": self.current_research,
            "current_progress": self.current_progress,
            "innovations": self.innovations,
        }

    def load_state(self, data: Dict) -> None:
        if not data:
            return
        self.unlocked = set(data.get("unlocked") or [])
        self.current_research = data.get("current_research")
        self.current_progress = int(data.get("current_progress") or 0)
        self.innovations = int(data.get("innovations") or 0)
