# Game/core/audio.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pygame


AUDIO_EXTS = {".wav", ".ogg", ".mp3"}


def _norm_key(rel_path: Path) -> str:
    """
    Transforme un chemin relatif en clé:
    ui/click.wav -> "ui.click"
    """
    parts = list(rel_path.parts)
    if parts:
        parts[-1] = rel_path.stem  # enlève extension
    return ".".join(p.lower() for p in parts)


@dataclass
class AudioVolumes:
    enabled: bool = True
    master: float = 0.8
    music: float = 0.8
    sfx: float = 0.9


class AudioManager:
    """
    - Musiques: stocke les chemins (lecture via pygame.mixer.music)
    - SFX: charge en pygame.mixer.Sound
    """

    def __init__(self, base_dir: str | Path, *, num_channels: int = 24):
        self.base_dir = Path(base_dir)
        self.num_channels = num_channels

        self.music_paths: dict[str, str] = {}
        self.sfx: dict[str, pygame.mixer.Sound] = {}

        self.vol = AudioVolumes()
        self._warned_missing: set[str] = set()

        # Petites réservations utiles (optionnel)
        self._reserved_channels = {
            "ui": 0,
            "ambient": 1,
        }

    def load_all(self) -> "AudioManager":
        if not pygame.mixer.get_init():
            raise RuntimeError("pygame.mixer n'est pas initialisé (mixer.get_init() == None).")

        pygame.mixer.set_num_channels(self.num_channels)

        # charge / indexe
        self._load_music_dir(self.base_dir / "music")
        self._load_sfx_dir(self.base_dir / "sfx")

        # applique volumes initiaux
        self.apply_volumes()
        return self

    def _load_music_dir(self, folder: Path) -> None:
        if not folder.exists():
            return
        for p in folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                rel = p.relative_to(folder)
                key = _norm_key(rel)  # ex: "phase1.day"
                self.music_paths[key] = str(p.as_posix())

    def _load_sfx_dir(self, folder: Path) -> None:
        if not folder.exists():
            return
        for p in folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                rel = p.relative_to(folder)
                key = _norm_key(rel)  # ex: "ui.click"
                self.sfx[key] = pygame.mixer.Sound(str(p.as_posix()))

    # -------------------- Volumes --------------------

    def set_volumes(
        self,
        *,
        enabled: bool | None = None,
        master: float | None = None,
        music: float | None = None,
        sfx: float | None = None,
    ) -> None:
        if enabled is not None:
            self.vol.enabled = bool(enabled)
        if master is not None:
            self.vol.master = float(max(0.0, min(1.0, master)))
        if music is not None:
            self.vol.music = float(max(0.0, min(1.0, music)))
        if sfx is not None:
            self.vol.sfx = float(max(0.0, min(1.0, sfx)))

        self.apply_volumes()

    def apply_volumes(self) -> None:
        if not pygame.mixer.get_init():
            return

        if not self.vol.enabled:
            pygame.mixer.music.set_volume(0.0)
            for snd in self.sfx.values():
                snd.set_volume(0.0)
            return

        pygame.mixer.music.set_volume(self.vol.master * self.vol.music)
        for snd in self.sfx.values():
            snd.set_volume(self.vol.master * self.vol.sfx)

    # -------------------- Play helpers --------------------

    def play_music(self, key: str, *, loops: int = -1, fade_ms: int = 800, start: float = 0.0) -> None:
        if not self.vol.enabled:
            return
        path = self.music_paths.get(key)
        if not path:
            self._warn_missing(f"music:{key}")
            return

        # transition douce
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except Exception:
            pass

        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(self.vol.master * self.vol.music)
        pygame.mixer.music.play(loops=loops, start=start, fade_ms=fade_ms)

    def stop_music(self, *, fade_ms: int = 600) -> None:
        try:
            pygame.mixer.music.fadeout(fade_ms)
        except Exception:
            pygame.mixer.music.stop()

    def play_sfx(self, key: str, *, volume: float = 1.0, channel: str | None = None) -> None:
        if not self.vol.enabled:
            return
        snd = self.sfx.get(key)
        if not snd:
            self._warn_missing(f"sfx:{key}")
            return

        vol = (self.vol.master * self.vol.sfx) * float(max(0.0, min(1.0, volume)))

        if channel in self._reserved_channels:
            ch = pygame.mixer.Channel(self._reserved_channels[channel])
            ch.set_volume(vol)
            ch.play(snd)
            return

        ch = pygame.mixer.find_channel(True)
        if ch:
            ch.set_volume(vol)
            ch.play(snd)

    def _warn_missing(self, name: str) -> None:
        # évite de spam la console
        if name in self._warned_missing:
            return
        self._warned_missing.add(name)
        print(f"Audio introuvable: {name}")
