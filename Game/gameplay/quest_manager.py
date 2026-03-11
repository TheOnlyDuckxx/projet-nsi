from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from Game.core.utils import resource_path
from Game.ui.hud.notification import add_notification


@dataclass
class QuestSnapshot:
    quest_id: str
    title: str
    description: str
    status: str
    progress: int
    target: int


class QuestManager:
    STATUS_LOCKED = "locked"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"

    def __init__(self, phase, data_path: str = "Game/data/quests_phase1.json"):
        self.phase = phase
        self.data_path = data_path
        self.definitions: Dict[str, Dict[str, Any]] = {}
        self.state: Dict[str, Dict[str, Any]] = {}
        self._load_definitions()
        self._bootstrap_state()

    def _load_definitions(self) -> None:
        try:
            with open(resource_path(self.data_path), "r", encoding="utf-8") as f:
                doc = json.load(f) or {}
            quests = doc.get("quests") or []
            for row in quests:
                qid = str((row or {}).get("id") or "").strip()
                if not qid:
                    continue
                self.definitions[qid] = dict(row)
        except Exception as exc:
            print(f"[Quests] Impossible de charger {self.data_path}: {exc}")
            self.definitions = {}

    def _bootstrap_state(self) -> None:
        self.state = {}
        for qid, definition in self.definitions.items():
            self.state[qid] = {
                "status": self.STATUS_ACTIVE if definition.get("start_active", False) else self.STATUS_LOCKED,
                "progress": 0,
                "target": int(((definition.get("track") or {}).get("target", 1) or 1)),
                "completed_at": None,
            }

    def to_dict(self) -> Dict[str, Any]:
        return {"state": self.state}

    def load_state(self, payload: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        raw_state = payload.get("state") or {}
        if not isinstance(raw_state, dict):
            return

        self._bootstrap_state()
        for qid, row in raw_state.items():
            if qid not in self.state or not isinstance(row, dict):
                continue
            status = str(row.get("status", self.state[qid]["status"]))
            if status not in {self.STATUS_LOCKED, self.STATUS_ACTIVE, self.STATUS_COMPLETED}:
                status = self.state[qid]["status"]
            self.state[qid]["status"] = status
            self.state[qid]["progress"] = int(row.get("progress", self.state[qid]["progress"]) or 0)
            self.state[qid]["target"] = max(1, int(row.get("target", self.state[qid]["target"]) or 1))
            self.state[qid]["completed_at"] = row.get("completed_at")

    def update(self, _dt: float = 0.0) -> None:
        if not self.definitions:
            return
        self._activate_conditional_quests()

        for qid, definition in self.definitions.items():
            row = self.state.get(qid)
            if not row or row.get("status") != self.STATUS_ACTIVE:
                continue

            progress, target, extra = self._compute_progress(definition)
            row["progress"] = max(0, int(progress))
            row["target"] = max(1, int(target))

            if row["progress"] >= row["target"]:
                self._complete_quest(qid, definition, extra or {})

    def _activation_is_ready(self, definition: Dict[str, Any]) -> bool:
        activation = definition.get("activation")
        if not isinstance(activation, dict):
            return False

        atype = activation.get("type")
        if atype == "main_class_is":
            expected = str(activation.get("class") or "").strip()
            species = getattr(self.phase, "espece", None)
            current = str(getattr(species, "main_class", "") or "").strip()
            return bool(expected and current == expected)
        return False

    def _activate_conditional_quests(self) -> None:
        for qid, definition in self.definitions.items():
            row = self.state.get(qid)
            if not row or row.get("status") != self.STATUS_LOCKED:
                continue
            if self._activation_is_ready(definition):
                row["status"] = self.STATUS_ACTIVE
                add_notification(f"Nouvelle quete : {definition.get('title', qid)}")

    def _compute_progress(self, definition: Dict[str, Any]) -> Tuple[int, int, Dict[str, Any]]:
        track = definition.get("track") or {}
        ttype = track.get("type")
        target = max(1, int(track.get("target", 1) or 1))

        if ttype == "warehouse_built":
            return (1 if getattr(self.phase, "has_built_warehouse", lambda: False)() else 0, target, {})

        if ttype == "warehouse_resource_variety":
            storage = getattr(self.phase, "warehouse", {}) or {}
            count = sum(1 for _k, qty in storage.items() if int(qty or 0) > 0)
            return count, target, {}

        if ttype == "tech_unlocked_count":
            tree = getattr(self.phase, "tech_tree", None)
            count = int(len(getattr(tree, "unlocked", []) or [])) if tree else 0
            return count, target, {}

        if ttype == "class_count_same":
            candidate, count = getattr(self.phase, "get_dominant_role_class", lambda min_count=0: (None, 0))(min_count=0)
            extra = {"candidate_class": candidate}
            return int(count), target, extra

        if ttype == "living_class_count":
            class_id = str(track.get("class") or "").strip()
            count = int(getattr(self.phase, "count_living_members_by_class", lambda _c=None: 0)(class_id))
            return count, target, {}

        return 0, target, {}

    def _complete_quest(self, qid: str, definition: Dict[str, Any], extra: Dict[str, Any]) -> None:
        row = self.state.get(qid)
        if not row or row.get("status") == self.STATUS_COMPLETED:
            return

        row["status"] = self.STATUS_COMPLETED
        row["completed_at"] = time.time()
        add_notification(f"Quete terminee : {definition.get('title', qid)}")

        for reward in definition.get("rewards") or []:
            self._apply_reward(reward, extra=extra)

        for next_id in definition.get("next") or []:
            if next_id not in self.state:
                continue
            next_row = self.state[next_id]
            if next_row.get("status") != self.STATUS_LOCKED:
                continue
            if self._activation_is_ready(self.definitions.get(next_id, {})):
                next_row["status"] = self.STATUS_ACTIVE
                add_notification(f"Nouvelle quete : {self.definitions[next_id].get('title', next_id)}")
                continue
            if "activation" not in (self.definitions.get(next_id) or {}):
                next_row["status"] = self.STATUS_ACTIVE
                add_notification(f"Nouvelle quete : {self.definitions[next_id].get('title', next_id)}")

    def _apply_reward(self, reward: Dict[str, Any], extra: Dict[str, Any]) -> None:
        if not isinstance(reward, dict):
            return
        rtype = reward.get("type")

        if rtype == "add_xp":
            amount = float(reward.get("amount", 0) or 0)
            species = getattr(self.phase, "espece", None)
            if amount > 0 and species is not None:
                species.add_xp(amount)
            return

        if rtype == "unlock_non_tech_crafts":
            fn = getattr(self.phase, "unlock_all_non_tech_crafts", None)
            if callable(fn):
                fn(skip={"Statue_de_canard"})
            return

        if rtype == "unlock_craft":
            craft_id = reward.get("craft_id")
            if craft_id and hasattr(self.phase, "unlock_craft"):
                self.phase.unlock_craft(str(craft_id))
            return

        if rtype == "modify_species_stat":
            species = getattr(self.phase, "espece", None)
            if species is None:
                return
            cat = str(reward.get("category") or "").strip()
            stat = str(reward.get("stat") or "").strip()
            amount = float(reward.get("amount", 0) or 0)
            if not cat or not stat or amount == 0:
                return
            container = getattr(species, cat, None)
            if isinstance(container, dict):
                if stat not in container or not isinstance(container.get(stat), (int, float)):
                    return
                container[stat] += amount
                for ent in getattr(species, "individus", []) or []:
                    target = getattr(ent, cat.replace("base_", ""), None)
                    if isinstance(target, dict):
                        if stat not in target or not isinstance(target.get(stat), (int, float)):
                            continue
                        target[stat] += amount
                    if hasattr(ent, "recompute_derived_stats"):
                        try:
                            ent.recompute_derived_stats(adjust_current=True)
                        except Exception:
                            pass
            return

        if rtype == "trigger_class_choice_event":
            mgr = getattr(self.phase, "event_manager", None)
            if mgr is None:
                return
            candidate = extra.get("candidate_class")
            if not candidate:
                candidate, _count = getattr(self.phase, "get_dominant_role_class", lambda min_count=5: (None, 0))(min_count=5)
            if candidate:
                mgr.runtime_flags["class_choice_candidate"] = candidate
                mgr.runtime_flags["class_choice_ready"] = True
            return

        if rtype == "notification":
            msg = reward.get("message")
            if msg:
                add_notification(str(msg))
            return

    def _snapshot_for(self, qid: str) -> Optional[QuestSnapshot]:
        definition = self.definitions.get(qid) or {}
        row = self.state.get(qid) or {}
        if not definition:
            return None
        return QuestSnapshot(
            quest_id=qid,
            title=str(definition.get("title") or qid),
            description=str(definition.get("description") or ""),
            status=str(row.get("status", self.STATUS_LOCKED)),
            progress=int(row.get("progress", 0) or 0),
            target=max(1, int(row.get("target", 1) or 1)),
        )

    def get_active_quests(self) -> List[QuestSnapshot]:
        out: List[QuestSnapshot] = []
        for qid in self.definitions.keys():
            snap = self._snapshot_for(qid)
            if snap is None or snap.status != self.STATUS_ACTIVE:
                continue
            out.append(snap)
        return out

    def get_completed_quests(self) -> List[QuestSnapshot]:
        out: List[QuestSnapshot] = []
        for qid in self.definitions.keys():
            snap = self._snapshot_for(qid)
            if snap is None or snap.status != self.STATUS_COMPLETED:
                continue
            out.append(snap)
        return out
