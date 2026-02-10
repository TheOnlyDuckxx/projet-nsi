import json
import os
import time


DEFAULT_PROGRESS_PATH = os.path.join("Game", "save", "progression.json")
DEFAULT_PROGRESS_DATA = {
    "version": 1,
    "games_started": 0,
    "play_time_seconds": 0.0,
    "achievements": 0,
    "player_level": 1,
    "player_xp": 0,
    "player_xp_to_next": 100,
    "achievements_data": {},
}

PLAYER_POINTS_PER_LEVEL = 2
PLAYER_XP_GROWTH = 1.35

ACHIEVEMENTS_DEFS = [
    {
        "id": "first_steps",
        "title": "Premiers pas",
        "description": "Lancer ta premiere partie.",
        "source": "progression",
        "stat": "games_started",
        "target": 1,
    },
    {
        "id": "steady_player",
        "title": "Toujours la",
        "description": "Jouer 1 heure cumulee.",
        "source": "progression",
        "stat": "play_time_seconds",
        "target": 3600,
    },
    {
        "id": "evolution_lv5",
        "title": "Evolution rapide",
        "description": "Atteindre le niveau d'espece 5.",
        "source": "session",
        "stat": "species_level",
        "target": 5,
    },
    {
        "id": "survivor_day3",
        "title": "Survivant",
        "description": "Atteindre le jour 3.",
        "source": "session",
        "stat": "days_survived",
        "target": 3,
    },
    {
        "id": "hunter_10",
        "title": "Chasseur",
        "description": "Tuer 10 animaux.",
        "source": "session",
        "stat": "animals_killed",
        "target": 10,
    },
    {
        "id": "collector_100",
        "title": "Recolteur",
        "description": "Collecter 100 ressources.",
        "source": "session",
        "stat": "resources_collected",
        "target": 100,
    },
]


def _build_default_achievement(defn: dict) -> dict:
    return {
        "id": defn.get("id"),
        "title": defn.get("title", ""),
        "description": defn.get("description", ""),
        "unlocked": False,
        "progress": 0,
        "unlocked_at": None,
    }


class AchievementsManager:
    def __init__(self, progression_manager: "ProgressionManager"):
        self._pm = progression_manager

    def _now_text(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _progress_percent(self, value: float, target: float) -> int:
        try:
            value = float(value)
            target = float(target)
        except Exception:
            return 0
        if target <= 0:
            return 0
        ratio = max(0.0, min(1.0, value / target))
        return int(round(ratio * 100))

    def _ensure_records(self) -> dict:
        data = self._pm.data.get("achievements_data")
        if not isinstance(data, dict):
            data = {}
            self._pm.data["achievements_data"] = data

        changed = False
        for defn in ACHIEVEMENTS_DEFS:
            aid = defn.get("id")
            if not aid:
                continue
            rec = data.get(aid)
            if not isinstance(rec, dict):
                data[aid] = _build_default_achievement(defn)
                changed = True
                continue
            if rec.get("title") != defn.get("title"):
                rec["title"] = defn.get("title", "")
                changed = True
            if rec.get("description") != defn.get("description"):
                rec["description"] = defn.get("description", "")
                changed = True
            if "unlocked" not in rec:
                rec["unlocked"] = False
                changed = True
            if "progress" not in rec:
                rec["progress"] = 0
                changed = True
            if "unlocked_at" not in rec:
                rec["unlocked_at"] = None
                changed = True

            rec["unlocked"] = bool(rec.get("unlocked", False))
            try:
                rec["progress"] = max(0, min(100, int(rec.get("progress", 0) or 0)))
            except Exception:
                rec["progress"] = 0
                changed = True

        if changed:
            self._pm._dirty = True
        return data

    def update(self, session: dict | None = None):
        data = self._ensure_records()
        if not data:
            return

        progression_stats = {
            "games_started": int(self._pm.data.get("games_started", 0) or 0),
            "play_time_seconds": float(self._pm.data.get("play_time_seconds", 0.0) or 0.0),
            "player_level": int(self._pm.data.get("player_level", 1) or 1),
        }
        session_stats = session if isinstance(session, dict) else None

        changed = False
        unlocked_now = False

        for defn in ACHIEVEMENTS_DEFS:
            aid = defn.get("id")
            if not aid or aid not in data:
                continue
            source = defn.get("source", "progression")
            if source == "session" and session_stats is None:
                continue

            stat = defn.get("stat")
            target = defn.get("target", 0)
            if source == "session":
                value = session_stats.get(stat, 0) if session_stats else 0
            else:
                value = progression_stats.get(stat, 0)

            progress = self._progress_percent(value, target)
            rec = data[aid]

            if rec.get("unlocked"):
                if rec.get("progress") != 100:
                    rec["progress"] = 100
                    changed = True
                continue

            stored_progress = int(rec.get("progress", 0) or 0)
            new_progress = max(stored_progress, progress)
            if new_progress != stored_progress:
                rec["progress"] = new_progress
                changed = True

            if progress >= 100:
                rec["unlocked"] = True
                rec["progress"] = 100
                if not rec.get("unlocked_at"):
                    rec["unlocked_at"] = self._now_text()
                changed = True
                unlocked_now = True

        unlocked_count = 0
        for rec in data.values():
            if isinstance(rec, dict) and rec.get("unlocked"):
                unlocked_count += 1
        if int(self._pm.data.get("achievements", 0) or 0) != unlocked_count:
            self._pm.data["achievements"] = unlocked_count
            changed = True

        if changed:
            self._pm._dirty = True
            if unlocked_now:
                self._pm.flush(force=True)

    def list(self, sorted_list: bool = True) -> list[dict]:
        data = self._ensure_records()
        items = []
        for rec in data.values():
            if isinstance(rec, dict):
                items.append(dict(rec))
        if sorted_list:
            items.sort(key=lambda r: (not bool(r.get("unlocked")), -int(r.get("progress", 0) or 0), str(r.get("title", ""))))
        return items


class ProgressionManager:
    def __init__(self, path: str = DEFAULT_PROGRESS_PATH):
        self.path = path
        self.data = {}
        self._dirty = False
        self._last_save_t = 0.0
        self._save_interval = 5.0
        self.load()
        self.achievements = AchievementsManager(self)
        self.achievements.update()

    def _merge_defaults(self, loaded):
        merged = dict(DEFAULT_PROGRESS_DATA)
        if isinstance(loaded, dict):
            for key in merged.keys():
                if key in loaded:
                    merged[key] = loaded[key]

        try:
            merged["games_started"] = max(0, int(merged.get("games_started", 0) or 0))
        except Exception:
            merged["games_started"] = 0
        try:
            merged["achievements"] = max(0, int(merged.get("achievements", 0) or 0))
        except Exception:
            merged["achievements"] = 0
        try:
            merged["play_time_seconds"] = float(merged.get("play_time_seconds", 0.0) or 0.0)
        except Exception:
            merged["play_time_seconds"] = 0.0
        try:
            merged["player_level"] = max(1, int(merged.get("player_level", 1) or 1))
        except Exception:
            merged["player_level"] = 1
        try:
            merged["player_xp"] = max(0, int(merged.get("player_xp", 0) or 0))
        except Exception:
            merged["player_xp"] = 0
        try:
            merged["player_xp_to_next"] = max(25, int(merged.get("player_xp_to_next", 100) or 100))
        except Exception:
            merged["player_xp_to_next"] = 100
        if not isinstance(merged.get("achievements_data"), dict):
            merged["achievements_data"] = {}
        return merged

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        if not os.path.exists(self.path):
            self.data = dict(DEFAULT_PROGRESS_DATA)
            self.save()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                self.data = dict(DEFAULT_PROGRESS_DATA)
                self.save()
                return
            loaded = json.loads(content)
            self.data = self._merge_defaults(loaded)
        except Exception:
            self.data = dict(DEFAULT_PROGRESS_DATA)
            self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Progression] Erreur sauvegarde: {e}")

    def flush(self, force: bool = False):
        if not self._dirty and not force:
            return
        now = time.monotonic()
        if not force and (now - self._last_save_t) < self._save_interval:
            return
        self.save()
        self._dirty = False
        self._last_save_t = now

    def on_game_start(self):
        self.data["games_started"] = int(self.data.get("games_started", 0) or 0) + 1
        self._dirty = True
        self.update_achievements()
        self.flush(force=True)

    def add_play_time(self, dt: float):
        try:
            dt = float(dt)
        except Exception:
            return
        if dt <= 0:
            return
        self.data["play_time_seconds"] = float(self.data.get("play_time_seconds", 0.0) or 0.0) + dt
        self._dirty = True

    def tick(self, dt: float, active: bool):
        if not active:
            return
        self.add_play_time(dt)
        self.update_achievements()
        self.flush()

    def update_achievements(self, session: dict | None = None):
        if hasattr(self, "achievements") and self.achievements is not None:
            self.achievements.update(session)

    def get_achievements(self, sorted_list: bool = True) -> list[dict]:
        if hasattr(self, "achievements") and self.achievements is not None:
            return self.achievements.list(sorted_list=sorted_list)
        return []

    def get_stats(self) -> dict:
        return {
            "games_started": int(self.data.get("games_started", 0) or 0),
            "play_time_seconds": float(self.data.get("play_time_seconds", 0.0) or 0.0),
            "achievements": int(self.data.get("achievements", 0) or 0),
        }

    def get_player_progress(self) -> dict:
        level = int(self.data.get("player_level", 1) or 1)
        xp = int(self.data.get("player_xp", 0) or 0)
        xp_to_next = int(self.data.get("player_xp_to_next", 100) or 100)
        return {
            "level": level,
            "xp": xp,
            "xp_to_next": xp_to_next,
            "bonus_points": max(0, (level - 1) * PLAYER_POINTS_PER_LEVEL),
        }

    def next_player_xp_to_next(self, current: int) -> int:
        try:
            current = int(current)
        except Exception:
            current = 100
        current = max(25, current)
        return int(max(25, round(current * PLAYER_XP_GROWTH)))

    def add_player_xp(self, amount: float) -> dict:
        try:
            amount = float(amount)
        except Exception:
            return {"gained": 0, "levels_gained": 0}
        if amount <= 0:
            return {"gained": 0, "levels_gained": 0}

        before = self.get_player_progress()
        gained = int(round(amount))
        level = before["level"]
        xp = before["xp"] + gained
        xp_to_next = before["xp_to_next"]
        levels_gained = 0

        while xp >= xp_to_next:
            xp -= xp_to_next
            level += 1
            levels_gained += 1
            xp_to_next = self.next_player_xp_to_next(xp_to_next)

        self.data["player_level"] = int(level)
        self.data["player_xp"] = int(xp)
        self.data["player_xp_to_next"] = int(xp_to_next)
        self._dirty = True
        self.flush(force=True)

        return {
            "gained": gained,
            "levels_gained": levels_gained,
            "before": before,
            "after": self.get_player_progress(),
        }
