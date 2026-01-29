import json
import os
import time


DEFAULT_PROGRESS_PATH = os.path.join("Game", "save", "progression.json")
DEFAULT_PROGRESS_DATA = {
    "version": 1,
    "games_started": 0,
    "play_time_seconds": 0.0,
    "achievements": 0,
}


class ProgressionManager:
    def __init__(self, path: str = DEFAULT_PROGRESS_PATH):
        self.path = path
        self.data = {}
        self._dirty = False
        self._last_save_t = 0.0
        self._save_interval = 5.0
        self.load()

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
        self.flush()

    def get_stats(self) -> dict:
        return {
            "games_started": int(self.data.get("games_started", 0) or 0),
            "play_time_seconds": float(self.data.get("play_time_seconds", 0.0) or 0.0),
            "achievements": int(self.data.get("achievements", 0) or 0),
        }
