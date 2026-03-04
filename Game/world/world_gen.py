# world_gen.py
# Monde entier procédural : génération par chunks.
#
# Objectifs :
# - Monde très grand, mais chargé au fur et à mesure (chunk cache).
# - Biomes variés, déterministes avec seed.
# - Les paramètres du monde influencent la génération (eau, climat, ressources, biodiversité, tectonique, etc.).
#
# Compat :
# - world.width / world.height
# - world.ground_id[y][x], world.levels[y][x], world.overlay[y][x]
# - world.biome[y][x] (nom), world.heightmap[y][x], world.moisture[y][x]
# - world.spawn  -> (x, y)
#
# Notes :
# - Wrap horizontal (longitude): x est modulo width (comme une planète).
# - Clamp vertical (latitude): y est borné [0..height-1].
# - overlay est modifiable : world.overlay[y][x] = ... (int prop_id, dict, None, etc.)
#   => seules les modifications sont stockées (overrides), pas une grille énorme.

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from array import array
from collections import OrderedDict
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from Game.world.tiles import get_tile_id

ProgressCb = Optional[Callable[[float, str], None]]


# --------------------------------------------------------------------------------------
# Props helpers (IDs)
# --------------------------------------------------------------------------------------

_PROP_ID_MAP = {
    "tree_3": 8,
    "tree_1": 9,
    "tree_2": 10,
    "tree_dead": 12,
    "rock": 13,
    "palm": 14,
    "cactus": 15,
    "bush": 16,
    "berry_bush": 17,
    "reeds": 18,
    "driftwood": 19,
    "flower": 20,
    "stump": 21,
    "log": 22,
    "boulder": 23,
    "flower2": 25,
    "flower3": 26,
    "blueberry_bush": 28,
    "ore_copper": 29,
    "ore_iron": 30,
    "ore_gold": 31,
    "clay_pit": 32,
    "vine": 33,
    "mushroom1": 34,
    "mushroom2": 35,
    "mushroom3": 36,
    "bone_pile": 37,
    "nest": 38,
    "beehive": 39,
    "freshwater_pool": 40,

    #Craft
    "feu":101,
    "entrepot": 102,
    "duck":103,
    "taniere": 104,
    "farm":105,
    "spike":106,
}


def get_prop_id(name: str) -> int:
    return _PROP_ID_MAP.get(name, _PROP_ID_MAP["tree_2"])

_RANDOM_SEED_LABELS = {"", "Aléatoire", "Aleatoire", "Random", "random"}

_SIZE_LABEL_TO_TAILLE = {
    "petite": 256,
    "moyenne": 384,
    "grande": 512,
    "gigantesque": 768,
}
_CLIMATE_LABEL_TO_CLIMAT = {
    "glaciaire": "Glaciaire",
    "froid": "Froid",
    "tempere": "Tempéré",
    "tempéré": "Tempéré",
    "chaud": "Chaud",
    "tropical": "Tropical",
    "aride": "Aride",
    "ardent": "Chaud",  # compat anciennes valeurs de menu
}
_WATER_LABEL_TO_OCEANS = {
    "aride": 25,
    "tempere": 50,
    "tempéré": 50,
    "oceanique": 75,
    "océanique": 75,
}
_RESOURCE_LABEL_TO_CANON = {
    "faible": "Faible",
    "pauvre": "Faible",  # compat ancien menu
    "moyenne": "Moyenne",
    "normale": "Moyenne",
    "elevee": "Élevée",
    "élevée": "Élevée",
    "haute": "Haute",
    "riche": "Élevée",   # compat ancien menu
    "instable": "Moyenne",  # compat ancien menu
}
_BIODIV_LABEL_TO_CANON = {
    "faible": "Faible",
    "moyenne": "Moyenne",
    "elevee": "Élevée",
    "élevée": "Élevée",
    "haute": "Élevée",
    "extreme": "Élevée",
    "extrême": "Élevée",  # compat ancien menu
}
_TECTONIC_LABEL_TO_CANON = {
    "stable": "Stable",
    "moderee": "Modérée",
    "modérée": "Modérée",
    "moyenne": "Modérée",   # compat ancien menu
    "instable": "Instable",
    "chaotique": "Violente",  # compat ancien menu
    "violente": "Violente",
}
_GRAVITY_LABEL_TO_CANON = {
    "faible": "Faible",
    "basse": "Faible",
    "moyenne": "Moyenne",
    "forte": "Forte",
    "elevee": "Forte",
    "élevée": "Forte",
    "haute": "Forte",
}

_TEMPERATURE_BIAS = {
    "Glaciaire": -0.35,
    "Froid": -0.20,
    "Tempéré": 0.0,
    "Chaud": 0.20,
    "Aride": 0.25,
    "Tropical": 0.18,
}
_BIODIVERSITY_MUL = {"Faible": 0.65, "Moyenne": 1.0, "Élevée": 1.25}
_TECTONIC_RUGGED = {"Stable": 0.9, "Modérée": 1.0, "Instable": 1.2, "Violente": 1.35}
_RESOURCE_MUL = {"Faible": 0.75, "Moyenne": 1.0, "Élevée": 1.2, "Haute": 1.2}


def _norm_label(v: Any) -> str:
    return str(v or "").strip().casefold()


def _parse_seed_value(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() in _RANDOM_SEED_LABELS:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _normalize_taille(raw: Any) -> int:
    if isinstance(raw, (int, float)):
        return int(raw)
    s = str(raw or "").strip()
    if s.isdigit():
        return int(s)
    return _SIZE_LABEL_TO_TAILLE.get(_norm_label(raw), 384)


def _normalize_climat(raw: Any) -> str:
    return _CLIMATE_LABEL_TO_CLIMAT.get(_norm_label(raw), "Tempéré")


def _normalize_oceans(raw: Any) -> int:
    if isinstance(raw, (int, float)):
        return max(0, min(100, int(raw)))
    s = str(raw or "").strip()
    if s.isdigit():
        return max(0, min(100, int(s)))
    return _WATER_LABEL_TO_OCEANS.get(_norm_label(raw), 50)


def _normalize_resource(raw: Any) -> str:
    return _RESOURCE_LABEL_TO_CANON.get(_norm_label(raw), "Moyenne")


def _normalize_biodiversity(raw: Any) -> str:
    return _BIODIV_LABEL_TO_CANON.get(_norm_label(raw), "Moyenne")


def _normalize_tectonic(raw: Any) -> str:
    return _TECTONIC_LABEL_TO_CANON.get(_norm_label(raw), "Stable")


def _normalize_gravity(raw: Any) -> str:
    return _GRAVITY_LABEL_TO_CANON.get(_norm_label(raw), "Moyenne")

# --------------------------------------------------------------------------------------
# World parameters
# --------------------------------------------------------------------------------------

@dataclass
class WorldParams:
    seed: Optional[int]
    Taille: int
    Climat: str
    Niveau_des_océans: int
    Ressources: str

    biodiversity: str = "Moyenne"
    tectonic_activity: str = "Stable"
    gravity: str = "Moyenne"
    world_name: str = "Nouveau Monde"

    chunk_noise_step: int = 16

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "WorldParams":
        raw_seed = d.get("seed", None)
        raw_size = d.get("world_size", d.get("Taille", 384))
        raw_climate = d.get("temperature", d.get("Climat", "Tempéré"))
        raw_oceans = d.get("water_coverage", d.get("Niveau des océans", d.get("Niveau_des_océans", 50)))
        raw_resources = d.get("resource_density", d.get("Ressources", "Moyenne"))
        raw_biodiv = d.get("biodiversity", "Moyenne")
        raw_tectonic = d.get("tectonic_activity", "Stable")
        raw_gravity = d.get("gravity", "Moyenne")
        raw_noise_step = d.get("chunk_noise_step", 16)
        try:
            noise_step = max(1, int(raw_noise_step or 16))
        except Exception:
            noise_step = 16
        return WorldParams(
            seed=_parse_seed_value(raw_seed),
            Taille=_normalize_taille(raw_size),
            Climat=_normalize_climat(raw_climate),
            Niveau_des_océans=_normalize_oceans(raw_oceans),
            Ressources=_normalize_resource(raw_resources),
            biodiversity=_normalize_biodiversity(raw_biodiv),
            tectonic_activity=_normalize_tectonic(raw_tectonic),
            gravity=_normalize_gravity(raw_gravity),
            world_name=str(d.get("world_name", "Nouveau Monde")),
            chunk_noise_step=noise_step,
        )


    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_world_params_from_preset(
    preset_name: str,
    path: str = "Game/data/world_presets.json",
    overrides: Optional[Dict[str, Any]] = None,
) -> WorldParams:
    """Charge un preset et le normalise vers le schéma de génération courant."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Preset file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    preset = doc.get("presets", {}).get(preset_name)
    if preset is None:
        raise KeyError(f"Preset '{preset_name}' not found in {path}")

    d: Dict[str, Any] = dict(preset)
    if overrides:
        d.update(overrides)
    d.setdefault("world_name", preset_name)
    return WorldParams.from_dict(d)


def load_world_params_from_menu_dict(menu_dict: Dict[str, Any]) -> WorldParams:
    """Compat API: normalise un dict de menu vers `WorldParams`."""
    return WorldParams.from_dict(menu_dict)


# --------------------------------------------------------------------------------------
# Deterministic seed helpers
# --------------------------------------------------------------------------------------

def _seed_int(v: Any) -> int:
    if v is None:
        return random.getrandbits(63)

    if isinstance(v, str):
        s = v.strip()
        if s in _RANDOM_SEED_LABELS:
            return random.getrandbits(63)
        try:
            return int(s) & 0x7FFF_FFFF_FFFF_FFFF
        except Exception:
            return random.getrandbits(63)

    try:
        return int(v) & 0x7FFF_FFFF_FFFF_FFFF
    except Exception:
        return random.getrandbits(63)



def make_final_seed(base_seed: int, params: WorldParams) -> int:
    """Seed finale = hash(seed de base + paramètres ayant un effet direct sur la génération)."""
    sig = (
        f"{int(base_seed)}|{int(params.Taille)}|{params.Climat}|{int(params.Niveau_des_océans)}|"
        f"{params.Ressources}|{params.biodiversity}|{params.tectonic_activity}|{params.gravity}|{int(params.chunk_noise_step)}"
    ).encode("utf-8")
    h = hashlib.blake2b(sig, digest_size=8).digest()
    return int.from_bytes(h, "little", signed=False)


def _hash_u32(x: int) -> int:
    x &= 0xFFFF_FFFF
    x ^= (x >> 16)
    x = (x * 0x7FEB_352D) & 0xFFFF_FFFF
    x ^= (x >> 15)
    x = (x * 0x846C_A68B) & 0xFFFF_FFFF
    x ^= (x >> 16)
    return x


def _rand01_from_u32(u: int) -> float:
    return (u & 0xFFFF_FFFF) / 0x1_0000_0000


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _wrap_lon_x(x: int, width: int) -> int:
    if width <= 0:
        return 0
    return x % width


def _clamp_lat_y(y: int, height: int) -> int:
    if y < 0:
        return 0
    if y >= height:
        return height - 1
    return y


# --------------------------------------------------------------------------------------
# Simple value noise / fbm (deterministic)
# --------------------------------------------------------------------------------------

def _val_noise_2d(x: float, y: float, seed: int) -> float:
    """
    value noise déterministe ~[-1,1]
    """
    xi = int(x)
    yi = int(y)
    xf = x - xi
    yf = y - yi

    def h(ix: int, iy: int) -> float:
        u = _hash_u32(seed ^ _hash_u32(ix * 0x9E37) ^ _hash_u32(iy * 0x85EB))
        return _rand01_from_u32(u) * 2.0 - 1.0

    def smooth(t: float) -> float:
        return t * t * (3.0 - 2.0 * t)

    u = smooth(xf)
    v = smooth(yf)

    n00 = h(xi, yi)
    n10 = h(xi + 1, yi)
    n01 = h(xi, yi + 1)
    n11 = h(xi + 1, yi + 1)

    nx0 = n00 + (n10 - n00) * u
    nx1 = n01 + (n11 - n01) * u
    return nx0 + (nx1 - nx0) * v


def _fbm(x: float, y: float, seed: int, octaves: int = 5) -> float:
    """
    fractal brownian motion ~[-1,1]
    """
    val = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(max(1, int(octaves))):
        val += amp * _val_noise_2d(x * freq, y * freq, seed)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return val / (norm if norm > 1e-9 else 1.0)


# --------------------------------------------------------------------------------------
# Perlin gradient noise / fbm
# --------------------------------------------------------------------------------------

def _perlin_grad(hash_u: int, x: float, y: float) -> float:
    h = hash_u & 7
    u = x if h < 4 else y
    v = y if h < 4 else x
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


def _perlin_noise_2d(x: float, y: float, seed: int) -> float:
    """
    Perlin gradient noise déterministe ~[-1,1]
    """
    xi = math.floor(x)
    yi = math.floor(y)
    xf = x - xi
    yf = y - yi

    def h(ix: int, iy: int) -> int:
        return _hash_u32(seed ^ _hash_u32(ix * 0x9E37) ^ _hash_u32(iy * 0x85EB))

    def fade(t: float) -> float:
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    u = fade(xf)
    v = fade(yf)

    n00 = _perlin_grad(h(int(xi), int(yi)), xf, yf)
    n10 = _perlin_grad(h(int(xi + 1), int(yi)), xf - 1.0, yf)
    n01 = _perlin_grad(h(int(xi), int(yi + 1)), xf, yf - 1.0)
    n11 = _perlin_grad(h(int(xi + 1), int(yi + 1)), xf - 1.0, yf - 1.0)

    nx0 = n00 + (n10 - n00) * u
    nx1 = n01 + (n11 - n01) * u
    return nx0 + (nx1 - nx0) * v


def _fbm_perlin(x: float, y: float, seed: int, octaves: int = 5) -> float:
    """
    fractal brownian motion Perlin ~[-1,1]
    """
    val = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(max(1, int(octaves))):
        val += amp * _perlin_noise_2d(x * freq, y * freq, seed)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return val / (norm if norm > 1e-9 else 1.0)


# --------------------------------------------------------------------------------------
# Biomes (IDs + names)
# --------------------------------------------------------------------------------------

BIOME_OCEAN = 1
BIOME_COAST = 2  # legacy: ancien biome plage (plus généré)
BIOME_LAKE = 3
BIOME_RIVER = 4

BIOME_PLAINS = 10
BIOME_FOREST = 11
BIOME_RAINFOREST = 12
BIOME_SAVANNA = 13
BIOME_DESERT = 14
BIOME_TAIGA = 15
BIOME_TUNDRA = 16
BIOME_SNOW = 17

# Extras (plus de variété, sans forcer des nouveaux tiles)
BIOME_SWAMP = 18
BIOME_MANGROVE = 19
BIOME_ROCK = 20
BIOME_ALPINE = 21
BIOME_VOLCANIC = 22
BIOME_MYSTIC = 23
BIOME_CORRUPT = 24

BIOME_ID_TO_NAME: Dict[int, str] = {
    BIOME_OCEAN: "ocean",
    BIOME_COAST: "plains",
    BIOME_LAKE: "lake",
    BIOME_RIVER: "river",
    BIOME_PLAINS: "plains",
    BIOME_FOREST: "forest",
    BIOME_RAINFOREST: "rainforest",
    BIOME_SAVANNA: "savanna",
    BIOME_DESERT: "desert",
    BIOME_TAIGA: "taiga",
    BIOME_TUNDRA: "tundra",
    BIOME_SNOW: "snow",
    BIOME_SWAMP: "swamp",
    BIOME_MANGROVE: "mangrove",
    BIOME_ROCK: "rock",
    BIOME_ALPINE: "alpine",
    BIOME_VOLCANIC: "volcanic",
    BIOME_MYSTIC: "mystic",
    BIOME_CORRUPT: "corrupt",
}

def _safe_ground_gid(name: str) -> int:
    try:
        return int(get_tile_id(name))
    except Exception:
        try:
            return int(get_tile_id("grass"))
        except Exception:
            return 0


_BIOME_TO_GROUND_NAME = {
    BIOME_SNOW: "snow",
    BIOME_TUNDRA: "taiga",
    BIOME_DESERT: "desert",
    BIOME_SAVANNA: "steppe",
    BIOME_PLAINS: "grass",
    BIOME_FOREST: "forest",
    BIOME_TAIGA: "taiga",
    BIOME_RAINFOREST: "rainforest",
    BIOME_SWAMP: "swamp",
    BIOME_MANGROVE: "mangrove",
    BIOME_ROCK: "rock",
    BIOME_ALPINE: "alpine",
    BIOME_VOLCANIC: "volcanic",
    BIOME_MYSTIC: "mystic",
    BIOME_CORRUPT: "corrupt",
}

_GID_OCEAN = _safe_ground_gid("ocean")
_GID_LAKE = _safe_ground_gid("lake")
_GID_RIVER = _safe_ground_gid("river")
_GID_GRASS = _safe_ground_gid("grass")
_GID_CORRUPT = _safe_ground_gid("corrupt")

_BIOME_TO_GROUND_GID = {bid: _safe_ground_gid(name) for bid, name in _BIOME_TO_GROUND_NAME.items()}


# --------------------------------------------------------------------------------------
# Grid proxies (compat world.xxx[y][x])
# --------------------------------------------------------------------------------------

class _RowProxy:
    def __init__(self, grid: "_GridProxy", y: int):
        self._g = grid
        self._y = int(y)

    def __len__(self) -> int:
        return self._g.width

    def __getitem__(self, x: int):
        return self._g._getter(int(x), self._y)

    def __setitem__(self, x: int, v):
        if self._g._setter is None:
            raise TypeError("This grid is read-only")
        self._g._setter(int(x), self._y, v)


class _GridProxy:
    def __init__(self, width: int, height: int, getter, setter=None):
        self.width = int(width)
        self.height = int(height)
        self._getter = getter
        self._setter = setter

    def __len__(self) -> int:
        return self.height

    def __getitem__(self, y: int) -> _RowProxy:
        return _RowProxy(self, int(y))


# --------------------------------------------------------------------------------------
# Chunked world
# --------------------------------------------------------------------------------------

class _Chunk:
    """
    Chunk data compact, taille chunk_size x chunk_size.
    """
    __slots__ = (
        "cx", "cy", "cs",
        "height_u8", "temp_u8", "moist_u8",
        "levels_u8", "ground_u16", "overlay_obj", "biome_u8",
    )

    def __init__(self, cx: int, cy: int, chunk_size: int):
        self.cx = int(cx)
        self.cy = int(cy)
        self.cs = int(chunk_size)
        n = self.cs * self.cs
        self.height_u8 = array("B", [0]) * n
        self.temp_u8 = array("B", [0]) * n
        self.moist_u8 = array("B", [0]) * n
        self.levels_u8 = array("B", [0]) * n
        self.ground_u16 = array("H", [0]) * n
        # overlay peut contenir int prop_id (base) mais aussi 0
        self.overlay_obj = array("H", [0]) * n
        self.biome_u8 = array("B", [0]) * n

    def idx(self, lx: int, ly: int) -> int:
        return int(ly) * self.cs + int(lx)


class ChunkedWorld:
    """
    Monde énorme mais généré en chunks à la demande.

    - Cache LRU des chunks (cache_chunks).
    - overlay modifiable via overrides.
    """
    def __init__(
        self,
        width: int,
        height: int,
        seed: int,
        params: WorldParams,
        tiles_levels: int = 6,
        chunk_size: int = 64,
        cache_chunks: int = 2048,
        progress: ProgressCb = None,   # <-- nouveau
    ):

        self.width = int(width)
        self.height = int(height)
        if not isinstance(seed, int):
            raise TypeError(f"ChunkedWorld seed must be int, got {seed!r}")
        self.seed = seed

        self.params = params
        self.tiles_levels = int(tiles_levels)
        self.chunk_size = int(chunk_size)
        self.cache_chunks = int(cache_chunks)

        self.sea_level = self._sea_level_from_params(params)

        # LRU cache chunks
        self._chunks: "OrderedDict[Tuple[int,int], _Chunk]" = OrderedDict()

        # overlay overrides: ne stocke que les modifications
        self._NO = object()
        self._overlay_overrides: Dict[Tuple[int, int], Any] = {}
        self._ground_overrides: Dict[Tuple[int, int], int] = {}
        self._biome_overrides: Dict[Tuple[int, int], int] = {}

        # Proxies pour compat (world.ground_id[y][x], etc.)
        self.heightmap = _GridProxy(self.width, self.height, self.get_height01)
        self.moisture = _GridProxy(self.width, self.height, self.get_moisture01)
        self.levels = _GridProxy(self.width, self.height, self.get_level)
        self.ground_id = _GridProxy(self.width, self.height, self.get_ground_id)
        self.biome = _GridProxy(self.width, self.height, self.get_biome_name)
        self.overlay = _GridProxy(self.width, self.height, self.get_overlay, self.set_overlay)
        self.max_levels = tiles_levels

        self._progress = progress
        self._progress_phases_reported: set[str] = set()

        # Spawn (déterminé rapidement)
        self.spawn = self._find_spawn(progress=progress)

    def __getstate__(self):
        # Empêche de sérialiser un callback local (non picklable).
        state = dict(self.__dict__)
        state["_progress"] = None
        state["_progress_phases_reported"] = set()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if "_progress" not in self.__dict__:
            self._progress = None
        if "_progress_phases_reported" not in self.__dict__:
            self._progress_phases_reported = set()
        if "_NO" not in self.__dict__:
            self._NO = object()
        if "_overlay_overrides" not in self.__dict__:
            self._overlay_overrides = {}
        if "_ground_overrides" not in self.__dict__:
            self._ground_overrides = {}
        if "_biome_overrides" not in self.__dict__:
            self._biome_overrides = {}


    # ------------------- tile ids safe -------------------

    def _safe_tile_id(self, name: str) -> int:
        try:
            return int(get_tile_id(name))
        except Exception:
            try:
                return int(get_tile_id("grass"))
            except Exception:
                return 0

    def _report_phase(self, key: str, p: float, label: str) -> None:
        if not self._progress or key in self._progress_phases_reported:
            return
        self._progress_phases_reported.add(key)
        self._progress(p, label)

    # ------------------- parameters -> knobs -------------------

    def _sea_level_from_params(self, params: WorldParams) -> float:
        v = float(getattr(params, "Niveau_des_océans", 50))
        v = max(0.0, min(100.0, v))
        # 0% -> mer basse (-0.10), 100% -> mer haute (+0.10) en hauteur signée
        return ((v - 50.0) / 100.0) * 0.20

    def _knobs(self):
        p = self.params
        temp_label = str(getattr(p, "Climat", "Tempéré"))
        temp_bias = _TEMPERATURE_BIAS.get(temp_label, 0.0)

        water_v = float(getattr(p, "Niveau_des_océans", 50))
        water_bias = (water_v - 50.0) / 100.0  # -0.5..+0.5

        biodiv = str(getattr(p, "biodiversity", "Moyenne"))
        biodiv_mul = _BIODIVERSITY_MUL.get(biodiv, 1.0)

        tect = str(getattr(p, "tectonic_activity", "Stable"))
        rugged = _TECTONIC_RUGGED.get(tect, 1.0)

        res_label = str(getattr(p, "Ressources", "Moyenne"))
        res_mul = _RESOURCE_MUL.get(res_label, 1.0)

        return {
            "temp_bias": temp_bias,
            "water_bias": water_bias,
            "biodiv_mul": biodiv_mul,
            "rugged": rugged,
            "res_mul": res_mul,
        }

    # ------------------- overlay (writable) -------------------

    def get_overlay(self, x: int, y: int):
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        v = self._overlay_overrides.get((x, y), self._NO)
        if v is not self._NO:
            return v  # peut être None, int, dict...
        ch, lx, ly = self._get_chunk(x, y)
        pid = int(ch.overlay_obj[ch.idx(lx, ly)])
        return None if pid == 0 else pid

    def set_overlay(self, x: int, y: int, value):
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        self._overlay_overrides[(x, y)] = value
        return value

    def set_ground_id(self, x: int, y: int, gid: int) -> int:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        self._ground_overrides[(x, y)] = int(gid)
        return int(gid)

    def set_biome_id(self, x: int, y: int, bid: int) -> int:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        self._biome_overrides[(x, y)] = int(bid)
        return int(bid)

    def set_tile_corrupt(self, x: int, y: int, clear_natural_props: bool = True) -> bool:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)

        current_bid = int(self.get_biome_id(x, y))
        if current_bid in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER):
            return False

        self.set_biome_id(x, y, BIOME_CORRUPT)
        self.set_ground_id(x, y, _GID_CORRUPT)

        if clear_natural_props:
            cell = self.get_overlay(x, y)
            if isinstance(cell, int) and 0 < int(cell) < 100:
                self.set_overlay(x, y, None)

        return True

    # ------------------- getters (read-only) -------------------

    def get_height01(self, x: int, y: int) -> float:
        ch, lx, ly = self._get_chunk_xy(x, y)
        return ch.height_u8[ch.idx(lx, ly)] / 255.0

    def get_moisture01(self, x: int, y: int) -> float:
        ch, lx, ly = self._get_chunk_xy(x, y)
        return ch.moist_u8[ch.idx(lx, ly)] / 255.0

    def get_temp01(self, x: int, y: int) -> float:
        ch, lx, ly = self._get_chunk_xy(x, y)
        return ch.temp_u8[ch.idx(lx, ly)] / 255.0

    def get_level(self, x: int, y: int) -> int:
        ch, lx, ly = self._get_chunk_xy(x, y)
        return int(ch.levels_u8[ch.idx(lx, ly)])

    def get_ground_id(self, x: int, y: int) -> int:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        ov = self._ground_overrides.get((x, y), self._NO)
        if ov is not self._NO:
            return int(ov)
        ch, lx, ly = self._get_chunk(x, y)
        return int(ch.ground_u16[ch.idx(lx, ly)])

    def get_biome_id(self, x: int, y: int) -> int:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        ov = self._biome_overrides.get((x, y), self._NO)
        if ov is not self._NO:
            return int(ov)
        ch, lx, ly = self._get_chunk(x, y)
        return int(ch.biome_u8[ch.idx(lx, ly)])

    def get_biome_name(self, x: int, y: int) -> str:
        return BIOME_ID_TO_NAME.get(self.get_biome_id(x, y), "unknown")

    def get_is_water(self, x: int, y: int) -> bool:
        bid = self.get_biome_id(x, y)
        return bid in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER)

    # ------------------- chunk management -------------------

    def _get_chunk_xy(self, x: int, y: int):
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        return self._get_chunk(x, y)

    def _peek_chunk(self, cx: int, cy: int) -> Optional[_Chunk]:
        key = (int(cx), int(cy))
        ch = self._chunks.get(key)
        if ch is not None:
            self._chunks.move_to_end(key)
        return ch

    def get_tile_snapshot(self, x: int, y: int, generate: bool = True):
        """
        Retourne un snapshot compact d'une tuile:
          (level:int, ground_id:int, overlay:any, biome_id:int)
        Si generate=False et que le chunk n'est pas en cache, renvoie None.
        """
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)

        cs = self.chunk_size
        cx = x // cs
        cy = y // cs
        lx = x - cx * cs
        ly = y - cy * cs

        ch = self._peek_chunk(cx, cy) if not generate else None
        if ch is None:
            if not generate:
                return None
            ch, _, _ = self._get_chunk(x, y)

        k = ch.idx(lx, ly)
        ov = self._overlay_overrides.get((x, y), self._NO)
        if ov is self._NO:
            pid = int(ch.overlay_obj[k])
            overlay = None if pid == 0 else pid
        else:
            overlay = ov
        g_ov = self._ground_overrides.get((x, y), self._NO)
        b_ov = self._biome_overrides.get((x, y), self._NO)
        ground = int(ch.ground_u16[k]) if g_ov is self._NO else int(g_ov)
        biome = int(ch.biome_u8[k]) if b_ov is self._NO else int(b_ov)
        return (
            int(ch.levels_u8[k]),
            ground,
            overlay,
            biome,
        )

    def ensure_chunk_at(self, x: int, y: int) -> None:
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        self._get_chunk(x, y)

    def prewarm_chunk_coords(
        self,
        chunk_coords: list[tuple[int, int]],
        progress: ProgressCb = None,
        phase_label: str = "Préchargement rendu…",
    ) -> None:
        total = max(1, len(chunk_coords))
        for idx, (cx_raw, cy) in enumerate(chunk_coords):
            if cy < 0 or cy * self.chunk_size >= self.height:
                continue
            cx = (int(cx_raw) * self.chunk_size) % self.width // self.chunk_size
            self._get_chunk(cx * self.chunk_size, int(cy) * self.chunk_size)
            if progress:
                progress((idx + 1) / total, f"{phase_label} ({idx + 1}/{total})")

    def _get_chunk(self, x: int, y: int):
        cs = self.chunk_size
        cx = x // cs
        cy = y // cs
        key = (cx, cy)

        ch = self._chunks.get(key)
        if ch is not None:
            self._chunks.move_to_end(key)
        else:
            ch = self._generate_chunk(cx, cy)
            self._chunks[key] = ch
            self._chunks.move_to_end(key)
            if len(self._chunks) > self.cache_chunks:
                self._chunks.popitem(last=False)

        lx = x - cx * cs
        ly = y - cy * cs
        return ch, lx, ly

    # ------------------- chunk generation -------------------

    def _generate_chunk(self, cx: int, cy: int) -> _Chunk:
        cs = self.chunk_size
        ch = _Chunk(cx, cy, cs)

        start_x = cx * cs
        start_y = cy * cs
        actual_w = min(cs, max(0, self.width - start_x))
        actual_h = min(cs, max(0, self.height - start_y))
        if actual_w <= 0 or actual_h <= 0:
            return ch

        # -------- paramètres -> multiplicateurs --------
        temp_label = str(getattr(self.params, "Climat", "Tempéré"))
        temp_bias = _TEMPERATURE_BIAS.get(temp_label, 0.0)

        water_v = float(getattr(self.params, "Niveau_des_océans", 50))
        water_bias = (water_v - 50.0) / 100.0  # -0.5..+0.5

        biodiv = str(getattr(self.params, "biodiversity", "Moyenne"))
        biodiv_mul = _BIODIVERSITY_MUL.get(biodiv, 1.0)

        tect = str(getattr(self.params, "tectonic_activity", "Stable"))
        rugged = _TECTONIC_RUGGED.get(tect, 1.0)

        res_label = str(getattr(self.params, "Ressources", "Moyenne"))
        res_mul = _RESOURCE_MUL.get(res_label, 1.0)

        base = int(self.seed)

        # échelles (IMPORTANT : ne plus dépendre de cx/cy)
        cont_scale   = 0.0011 * rugged
        detail_scale = 0.0100 * rugged

        macro_scale = 0.00035 * rugged
        macro_amp = 0.55 * rugged

        warp_amp   = 140.0 * rugged     # en tuiles
        warp_scale = 0.0009             # fréquence du warp

        peak_scale = 0.0045 * rugged    # fréquence montagnes
        micro_scale = 0.025             # micro-relief

        # petite variation de côte (continue) pour casser les rivages trop lisses
        coast_var_scale = 0.0035
        coast_var_amp   = 0.030  # +/- 0.03 sur la hauteur de mer

        raw_step = getattr(self.params, "chunk_noise_step", 8)
        try:
            noise_step = int(raw_step) if raw_step is not None else 8
        except Exception:
            noise_step = 8
        noise_step = max(1, min(cs, noise_step))

        # Points d'échantillonnage (0..actual_w / 0..actual_h, + bord pour interpolation)
        xs = list(range(0, actual_w + 1, noise_step))
        if xs[-1] != actual_w:
            xs.append(actual_w)
        ys = list(range(0, actual_h + 1, noise_step))
        if ys[-1] != actual_h:
            ys.append(actual_h)
        nx = len(xs)
        ny = len(ys)

        # LUT interpolation par coordonnée locale (évite divisions dans la boucle principale)
        x0_idx = [0] * actual_w
        x_frac = [0.0] * actual_w
        xi = 0
        for lx in range(actual_w):
            while xi + 1 < nx - 1 and xs[xi + 1] <= lx:
                xi += 1
            x0_idx[lx] = xi
            denom = xs[xi + 1] - xs[xi]
            x_frac[lx] = 0.0 if denom <= 0 else (lx - xs[xi]) / denom

        y0_idx = [0] * actual_h
        y_frac = [0.0] * actual_h
        yi = 0
        for ly in range(actual_h):
            while yi + 1 < ny - 1 and ys[yi + 1] <= ly:
                yi += 1
            y0_idx[ly] = yi
            denom = ys[yi + 1] - ys[yi]
            y_frac[ly] = 0.0 if denom <= 0 else (ly - ys[yi]) / denom

        # Échantillons bruités (valeurs "brutes" interpolables)
        n_samp = nx * ny
        height_s = [0.0] * n_samp
        peak_s = [0.0] * n_samp
        tnoise_s = [0.0] * n_samp
        mnoise_s = [0.0] * n_samp
        lake_s = [0.0] * n_samp
        lake_mod_s = [0.0] * n_samp
        river_s = [0.0] * n_samp

        clamp01 = _clamp01
        fbm = _fbm
        fbm_perlin = _fbm_perlin

        # Pré-calcul : un bruit "cher" sur une grille grossière, puis interpolation.
        for sy_i, lsy in enumerate(ys):
            gy = start_y + int(lsy)
            if gy >= self.height:
                gy = self.height - 1
            gyf = float(gy)
            for sx_i, lsx in enumerate(xs):
                gx = start_x + int(lsx)
                if gx >= self.width:
                    gx = self.width - 1
                gxf = float(gx)

                # --- domain warp (rend formes + naturelles, casse l’alignement chunk/grid) ---
                wx = gxf + warp_amp * fbm_perlin(gxf * warp_scale, gyf * warp_scale, base + 90001, octaves=3)
                wy = gyf + warp_amp * fbm_perlin((gxf + 1337.0) * warp_scale, (gyf - 7331.0) * warp_scale, base + 90002, octaves=3)

                # --- élévation (CONTINUE, Perlin gradient noise) ---
                h1 = fbm_perlin(wx * cont_scale,   wy * cont_scale,   base + 11,  octaves=5)
                h2 = fbm_perlin(wx * detail_scale, wy * detail_scale, base + 97,  octaves=4)
                base_h = 0.72 * h1 + 0.28 * h2

                macro = fbm_perlin(wx * macro_scale, wy * macro_scale, base + 4001, octaves=3)

                height = (base_h + macro * macro_amp) / (1.0 + macro_amp)
                height -= self.sea_level

                height += coast_var_amp * fbm_perlin(wx * coast_var_scale, wy * coast_var_scale, base + 9991, octaves=2)

                h01 = clamp01((height + 1.0) * 0.5)

                # montagnes (ridged)
                n = fbm_perlin(wx * peak_scale, wy * peak_scale, base + 7777, octaves=4)
                r = 1.0 - abs(n)
                r = clamp01(r)
                r = r * r  # sharpen
                mount_mask = clamp01((h01 - 0.50) / 0.50)
                height += (0.38 * rugged) * r * (mount_mask * mount_mask)

                micro = fbm_perlin(wx * micro_scale, wy * micro_scale, base + 4242, octaves=3)
                height += 0.05 * micro

                height -= 0.06 * water_bias

                idx = sy_i * nx + sx_i
                height_s[idx] = height
                peak_s[idx] = r
                tnoise_s[idx] = fbm(wx * 0.003, wy * 0.003, base + 201, octaves=3)
                mnoise_s[idx] = fbm(wx * 0.004, wy * 0.004, base + 333, octaves=4)
                lake_base = fbm(wx * 0.0065, wy * 0.0065, base + 6060, octaves=3)
                lake_s[idx] = 1.0 - abs(lake_base)
                lake_mod_s[idx] = fbm(wx * 0.0016, wy * 0.0016, base + 6061, octaves=2)
                river_s[idx] = abs(fbm(wx * 0.008, wy * 0.008, base + 7070, octaves=3))

        # Constantes eau
        lake_level = 0.07 + 0.04 * water_bias
        lake_level = max(0.03, min(0.14, lake_level))
        lake_cut_base = 0.62 - 0.10 * water_bias
        lake_cut_base = max(0.45, min(0.85, lake_cut_base))
        river_th = 0.032 + 0.014 * max(0.0, water_bias)

        # Pré-calc latitude par ligne
        inv_hm1 = 1.0 / max(1.0, float(self.height - 1))
        lat_abs_row = [0.0] * actual_h
        for ly in range(actual_h):
            gy = start_y + ly
            lat = (gy * inv_hm1) * 2.0 - 1.0
            lat_abs_row[ly] = abs(lat)

        inner = max(1, self.tiles_levels - 1)
        biome_gid = _BIOME_TO_GROUND_GID
        prop_ids = _PROP_ID_MAP
        gid_grass = _GID_GRASS
        gid_ocean = _GID_OCEAN
        gid_lake = _GID_LAKE
        gid_river = _GID_RIVER

        for ly in range(actual_h):
            sy0 = y0_idx[ly]
            fy = y_frac[ly]
            row0 = sy0 * nx
            row1 = (sy0 + 1) * nx
            lat_abs = lat_abs_row[ly]

            for lx in range(actual_w):
                sx0 = x0_idx[lx]
                fx = x_frac[lx]
                i00 = row0 + sx0
                i10 = row0 + (sx0 + 1)
                i01 = row1 + sx0
                i11 = row1 + (sx0 + 1)

                # --- interpolation bilinéaire ---
                h00 = height_s[i00]; h10 = height_s[i10]; h01v = height_s[i01]; h11 = height_s[i11]
                hx0 = h00 + (h10 - h00) * fx
                hx1 = h01v + (h11 - h01v) * fx
                height = hx0 + (hx1 - hx0) * fy

                p00 = peak_s[i00]; p10 = peak_s[i10]; p01 = peak_s[i01]; p11 = peak_s[i11]
                px0 = p00 + (p10 - p00) * fx
                px1 = p01 + (p11 - p01) * fx
                peak = px0 + (px1 - px0) * fy

                tn00 = tnoise_s[i00]; tn10 = tnoise_s[i10]; tn01 = tnoise_s[i01]; tn11 = tnoise_s[i11]
                tnx0 = tn00 + (tn10 - tn00) * fx
                tnx1 = tn01 + (tn11 - tn01) * fx
                tnoise = tnx0 + (tnx1 - tnx0) * fy

                mn00 = mnoise_s[i00]; mn10 = mnoise_s[i10]; mn01 = mnoise_s[i01]; mn11 = mnoise_s[i11]
                mnx0 = mn00 + (mn10 - mn00) * fx
                mnx1 = mn01 + (mn11 - mn01) * fx
                mnoise = mnx0 + (mnx1 - mnx0) * fy

                lk00 = lake_s[i00]; lk10 = lake_s[i10]; lk01 = lake_s[i01]; lk11 = lake_s[i11]
                lkx0 = lk00 + (lk10 - lk00) * fx
                lkx1 = lk01 + (lk11 - lk01) * fx
                lake_noise = lkx0 + (lkx1 - lkx0) * fy

                lm00 = lake_mod_s[i00]; lm10 = lake_mod_s[i10]; lm01 = lake_mod_s[i01]; lm11 = lake_mod_s[i11]
                lmx0 = lm00 + (lm10 - lm00) * fx
                lmx1 = lm01 + (lm11 - lm01) * fx
                lake_mod = lmx0 + (lmx1 - lmx0) * fy

                rv00 = river_s[i00]; rv10 = river_s[i10]; rv01 = river_s[i01]; rv11 = river_s[i11]
                rvx0 = rv00 + (rv10 - rv00) * fx
                rvx1 = rv01 + (rv11 - rv01) * fx
                river_noise = rvx0 + (rvx1 - rvx0) * fy

                # --- température (CONTINUE) ---
                t01 = clamp01((1.0 - lat_abs) + 0.25 * tnoise + temp_bias)

                # --- humidité (CONTINUE) ---
                m01 = clamp01((mnoise + 1.0) * 0.5)
                m01 = clamp01(m01 - 0.45 * max(0.0, height))

                # RNG par tuile (utile pour biomes/props)
                gx = start_x + lx
                gy = start_y + ly
                tile_seed = _hash_u32(base ^ _hash_u32(gx * 912367) ^ _hash_u32(gy * 972541))
                r0 = _rand01_from_u32(tile_seed)
                r1 = _rand01_from_u32(_hash_u32(tile_seed ^ 0xA5A5A5A5))
                r2 = _rand01_from_u32(_hash_u32(tile_seed ^ 0xC3C3C3C3))

                h01 = clamp01((height + 1.0) * 0.5)

                # --- eau douce (pas d'océans/mer) ---
                lake_cut = max(0.45, min(0.85, lake_cut_base + 0.08 * lake_mod))
                is_lake = (lake_noise > lake_cut) and (height < lake_level) and (height >= 0.0)
                is_river = (river_noise < river_th) and (height < 0.55) and (height >= 0.0)
                is_ocean = False

                # --- biome ---
                if is_ocean:
                    bid = BIOME_OCEAN
                elif is_lake:
                    bid = BIOME_LAKE
                elif is_river:
                    bid = BIOME_RIVER
                else:
                    # Hautes altitudes -> rocheux/alpin/volcanique
                    if h01 > 0.84 or peak > 0.84:
                        if t01 < 0.22:
                            bid = BIOME_SNOW
                        elif t01 < 0.32:
                            bid = BIOME_ALPINE
                        elif t01 > 0.62 and peak > 0.86 and r1 < 0.35:
                            bid = BIOME_VOLCANIC
                        else:
                            bid = BIOME_ROCK
                    # Bas-fonds humides -> marais/mangrove
                    elif m01 > 0.74 and h01 < 0.42:
                        if (lake_noise > (lake_cut - 0.04)) and h01 < 0.30 and r2 < 0.70:
                            bid = BIOME_MANGROVE
                        else:
                            bid = BIOME_SWAMP
                    # Biome mystique (rare)
                    elif tnoise < -0.45 and mnoise > 0.55 and r0 < 0.03:
                        bid = BIOME_MYSTIC
                    else:
                        # Neige plus fréquente + effet altitude
                        if t01 < 0.22 or (h01 > 0.78 and t01 < 0.32):
                            bid = BIOME_SNOW
                        elif t01 < 0.34:
                            bid = BIOME_TAIGA if m01 > 0.35 else BIOME_TUNDRA
                        else:
                            if m01 < 0.22:
                                bid = BIOME_DESERT if t01 > 0.45 else BIOME_TUNDRA
                            elif m01 < 0.42:
                                bid = BIOME_SAVANNA if t01 > 0.45 else BIOME_PLAINS
                            elif m01 < 0.58:
                                bid = BIOME_PLAINS if t01 < 0.62 else BIOME_FOREST
                            else:
                                bid = BIOME_RAINFOREST if t01 > 0.62 else BIOME_FOREST

                # --- niveau + sol ---
                if bid == BIOME_OCEAN:
                    level = 0
                    gid = gid_ocean
                elif bid == BIOME_LAKE:
                    level = 0
                    gid = gid_lake
                elif bid == BIOME_RIVER:
                    level = 0
                    gid = gid_river
                else:
                    land01 = clamp01(height / 1.0)
                    jitter = r2 * 2.0 - 1.0
                    land01 = clamp01(land01 + 0.03 * jitter)

                    level = 1 + int(round(land01 * inner))
                    if peak > 0.78 and level < self.tiles_levels:
                        level += 1
                    level = max(1, min(self.tiles_levels, level))

                    gid = biome_gid.get(bid, gid_grass)

                # --- props (seed par tuile) ---
                prop = 0
                if bid not in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER):
                    base_p = 0.02 * biodiv_mul
                    if bid in (BIOME_FOREST, BIOME_RAINFOREST, BIOME_TAIGA):
                        base_p *= 2.2
                    elif bid == BIOME_SAVANNA:
                        base_p *= 1.2
                    elif bid == BIOME_PLAINS:
                        base_p *= 0.9
                    elif bid in (BIOME_SNOW, BIOME_TUNDRA):
                        base_p *= 0.35
                    elif bid == BIOME_DESERT:
                        base_p *= 0.25

                    ore_p = 0.0045 * res_mul
                    if level >= 4:
                        ore_p *= 1.25

                    if r0 < ore_p:
                        if level >= 5 and r1 < 0.18:
                            prop = prop_ids["ore_gold"]
                        elif r1 < 0.55:
                            prop = prop_ids["ore_iron"]
                        else:
                            prop = prop_ids["ore_copper"]
                    elif r0 < ore_p + base_p:
                        if bid == BIOME_DESERT:
                            if r1 < 0.55:
                                prop = prop_ids["cactus"]
                            elif r1 < 0.8:
                                prop = prop_ids["boulder"]
                            else:
                                prop = prop_ids["rock"]
                        elif bid in (BIOME_TUNDRA, BIOME_SNOW):
                            prop = prop_ids["rock"] if r1 < 0.55 else prop_ids["boulder"]
                        elif bid in (BIOME_FOREST, BIOME_RAINFOREST, BIOME_TAIGA):
                            if r1 < 0.55:
                                prop = prop_ids["tree_1"] if r2 < 0.33 else (prop_ids["tree_2"] if r2 < 0.66 else prop_ids["tree_3"])
                            elif r1 < 0.78:
                                prop = prop_ids["mushroom1"] if r2 < 0.34 else (prop_ids["mushroom2"] if r2 < 0.67 else prop_ids["mushroom3"])
                            elif r1 < 0.9:
                                prop = prop_ids["log"]
                            else:
                                prop = prop_ids["stump"]
                        elif bid == BIOME_SAVANNA:
                            if r1 < 0.45:
                                prop = prop_ids["cactus"]
                            elif r1 < 0.8:
                                prop = prop_ids["bush"]
                            else:
                                prop = prop_ids["tree_dead"]
                        elif bid == BIOME_PLAINS:
                            if r1 < 0.6:
                                prop = prop_ids["flower"] if r2 < 0.34 else (prop_ids["flower2"] if r2 < 0.67 else prop_ids["flower3"])
                            elif r1 < 0.85:
                                prop = prop_ids["bush"]
                            else:
                                prop = prop_ids["berry_bush"] if r2 < 0.5 else prop_ids["blueberry_bush"]
                        elif bid in (BIOME_ROCK, BIOME_ALPINE, BIOME_VOLCANIC):
                            prop = prop_ids["rock"] if r1 < 0.65 else prop_ids["boulder"]
                        elif bid in (BIOME_SWAMP, BIOME_MANGROVE):
                            prop = prop_ids["reeds"] if r1 < 0.6 else prop_ids["bush"]
                        else:
                            prop = prop_ids["bush"] if r1 < 0.6 else prop_ids["flower"]

                # écrit chunk
                k = ch.idx(lx, ly)
                ch.height_u8[k] = int(clamp01((height + 1.0) * 0.5) * 255.0)
                ch.temp_u8[k] = int(clamp01(t01) * 255.0)
                ch.moist_u8[k] = int(clamp01(m01) * 255.0)
                ch.levels_u8[k] = int(level)
                ch.ground_u16[k] = int(gid)
                ch.overlay_obj[k] = int(prop)
                ch.biome_u8[k] = int(bid)

        self._smooth_chunk_levels(ch.levels_u8, cs, actual_w, actual_h, iterations=3)

        return ch

    def _smooth_chunk_levels(
        self,
        levels: array,
        stride: int,
        width: int,
        height: int,
        iterations: int = 3,
    ) -> None:
        if width <= 1 or height <= 1:
            return
        for _ in range(iterations):
            changed = False
            # horizontal neighbors
            for y in range(height):
                row = y * stride
                for x in range(width - 1):
                    idx = row + x
                    nidx = idx + 1
                    a = int(levels[idx])
                    b = int(levels[nidx])
                    if a - b > 1:
                        levels[idx] = b + 1
                        changed = True
                    elif b - a > 1:
                        levels[nidx] = a + 1
                        changed = True
            # vertical neighbors
            for y in range(height - 1):
                row = y * stride
                next_row = row + stride
                for x in range(width):
                    idx = row + x
                    nidx = next_row + x
                    a = int(levels[idx])
                    b = int(levels[nidx])
                    if a - b > 1:
                        levels[idx] = b + 1
                        changed = True
                    elif b - a > 1:
                        levels[nidx] = a + 1
                        changed = True
            if not changed:
                break

    # ------------------- spawn -------------------

    def _estimate_spawn_score(self, wx: int, wy: int) -> Optional[float]:
        """
        Estimation rapide de qualité de spawn, sans génération de chunk.
        Retourne None si case probablement non adaptée (eau/props denses).
        """
        base = int(self.seed)
        knobs = self._knobs()
        rugged = float(knobs.get("rugged", 1.0))
        temp_bias = float(knobs.get("temp_bias", 0.0))
        water_bias = float(knobs.get("water_bias", 0.0))
        biodiv_mul = float(knobs.get("biodiv_mul", 1.0))
        res_mul = float(knobs.get("res_mul", 1.0))

        cont_scale = 0.0011 * rugged
        detail_scale = 0.0100 * rugged
        macro_scale = 0.00035 * rugged
        macro_amp = 0.55 * rugged
        warp_amp = 140.0 * rugged
        warp_scale = 0.0009
        coast_var_scale = 0.0035
        coast_var_amp = 0.030

        gx = float(wx)
        gy = float(wy)

        wxp = gx + warp_amp * _fbm_perlin(gx * warp_scale, gy * warp_scale, base + 90001, octaves=2)
        wyp = gy + warp_amp * _fbm_perlin((gx + 1337.0) * warp_scale, (gy - 7331.0) * warp_scale, base + 90002, octaves=2)

        h1 = _fbm_perlin(wxp * cont_scale, wyp * cont_scale, base + 11, octaves=5)
        h2 = _fbm_perlin(wxp * detail_scale, wyp * detail_scale, base + 97, octaves=4)
        macro = _fbm_perlin(wxp * macro_scale, wyp * macro_scale, base + 4001, octaves=3)

        height = (0.72 * h1 + 0.28 * h2 + macro * macro_amp) / (1.0 + macro_amp)
        height -= self.sea_level
        height += coast_var_amp * _fbm_perlin(wxp * coast_var_scale, wyp * coast_var_scale, base + 9991, octaves=2)

        # montagnes + micro-relief (meme logique que _generate_chunk)
        ridged = 1.0 - abs(_fbm_perlin(wxp * (0.0045 * rugged), wyp * (0.0045 * rugged), base + 7777, octaves=4))
        ridged = _clamp01(ridged) ** 2
        mount_mask = _clamp01((_clamp01((height + 1.0) * 0.5) - 0.50) / 0.50)
        height += (0.38 * rugged) * ridged * (mount_mask ** 2)
        micro = _fbm_perlin(wxp * 0.025, wyp * 0.025, base + 4242, octaves=3)
        height += 0.05 * micro
        height -= 0.06 * water_bias
        h01 = _clamp01((height + 1.0) * 0.5)

        lake_level = 0.07 + 0.04 * water_bias
        lake_level = max(0.03, min(0.14, lake_level))
        lake_base = _fbm(wxp * 0.0065, wyp * 0.0065, base + 6060, octaves=3)
        lake_noise = 1.0 - abs(lake_base)
        lake_mod = _fbm(wxp * 0.0016, wyp * 0.0016, base + 6061, octaves=2)
        lake_cut_base = 0.62 - 0.10 * water_bias
        lake_cut_base = max(0.45, min(0.85, lake_cut_base))
        lake_cut = max(0.45, min(0.85, lake_cut_base + 0.08 * lake_mod))
        is_lake = (lake_noise > lake_cut) and (height < lake_level) and (height >= 0.0)

        river_noise = abs(_fbm(wxp * 0.008, wyp * 0.008, base + 7070, octaves=3))
        river_th = 0.032 + 0.014 * max(0.0, water_bias)
        is_river = (river_noise < river_th) and (height < 0.55) and (height >= 0.0)
        is_ocean = False

        if is_ocean or is_lake or is_river:
            return None

        lat = (wy / max(1, self.height - 1)) * 2.0 - 1.0
        lat_abs = abs(lat)
        tnoise = _fbm(wxp * 0.003, wyp * 0.003, base + 201, octaves=3)
        t01 = _clamp01((1.0 - lat_abs) + 0.25 * tnoise + temp_bias)
        mnoise = _fbm(wxp * 0.004, wyp * 0.004, base + 333, octaves=4)
        m01 = _clamp01((mnoise + 1.0) * 0.5 - 0.45 * max(0.0, height))

        if t01 < 0.18:
            bid = BIOME_SNOW
        elif t01 < 0.32:
            bid = BIOME_TAIGA if m01 > 0.35 else BIOME_TUNDRA
        else:
            if m01 < 0.22:
                bid = BIOME_DESERT if t01 > 0.45 else BIOME_TUNDRA
            elif m01 < 0.42:
                bid = BIOME_SAVANNA if t01 > 0.45 else BIOME_PLAINS
            elif m01 < 0.58:
                bid = BIOME_PLAINS if t01 < 0.62 else BIOME_FOREST
            else:
                bid = BIOME_RAINFOREST if t01 > 0.62 else BIOME_FOREST

        base_p = 0.02 * biodiv_mul
        if bid in (BIOME_FOREST, BIOME_RAINFOREST, BIOME_TAIGA):
            base_p *= 2.2
        elif bid == BIOME_SAVANNA:
            base_p *= 1.2
        elif bid == BIOME_PLAINS:
            base_p *= 0.9
        elif bid in (BIOME_SNOW, BIOME_TUNDRA):
            base_p *= 0.35
        elif bid == BIOME_DESERT:
            base_p *= 0.25
        ore_p = 0.0045 * res_mul

        tile_seed = _hash_u32(base ^ _hash_u32(wx * 912367) ^ _hash_u32(wy * 972541))
        r0 = _rand01_from_u32(tile_seed)
        if r0 < (ore_p + base_p):
            return None

        score = 0.0
        if bid in (BIOME_PLAINS, BIOME_FOREST):
            score += 3.0
        elif bid == BIOME_SAVANNA:
            score += 1.0
        if bid in (BIOME_DESERT, BIOME_SNOW, BIOME_TUNDRA):
            score -= 4.0
        score -= abs(h01 - 0.62) * 6.0
        return score

    def _find_spawn(self, progress: ProgressCb = None) -> Tuple[int, int]:
        """
        Recherche rapide de spawn sans générer de chunk.
        Évite le gros pic CPU avant l'écran de chargement complet.
        """
        mid_x = self.width // 2
        mid_y = self.height // 2

        best = (mid_x, mid_y)
        best_score = -1e9

        if progress:
            progress(0.0, "Spawn…")

        span_x = min(max(128, self.width // 12), 640)
        span_y = min(max(96, self.height // 12), 480)

        coarse_step = max(10, self.chunk_size // 2)
        x0 = max(0, mid_x - span_x)
        x1 = min(self.width - 1, mid_x + span_x)
        y0 = max(0, mid_y - span_y)
        y1 = min(self.height - 1, mid_y + span_y)

        xs = list(range(x0, x1 + 1, coarse_step))
        ys = list(range(y0, y1 + 1, coarse_step))
        total_samples = max(1, len(xs) * len(ys))
        sample_idx = 0

        for wy in ys:
            for wx in xs:
                score = self._estimate_spawn_score(wx, wy)
                if score is not None and score > best_score:
                    best_score = score
                    best = (wx, wy)
                sample_idx += 1
            if progress:
                progress(
                    0.15 + 0.65 * (sample_idx / total_samples),
                    f"Recherche du point de départ… ({sample_idx}/{total_samples})",
                )

        # passe de raffinement locale autour du meilleur candidat
        bx, by = best
        refine_radius = max(24, coarse_step * 2)
        refine_step = max(3, coarse_step // 4)
        rx0 = max(0, bx - refine_radius)
        rx1 = min(self.width - 1, bx + refine_radius)
        ry0 = max(0, by - refine_radius)
        ry1 = min(self.height - 1, by + refine_radius)

        rxs = list(range(rx0, rx1 + 1, refine_step))
        rys = list(range(ry0, ry1 + 1, refine_step))
        total_refine = max(1, len(rxs) * len(rys))
        refine_idx = 0
        for wy in rys:
            for wx in rxs:
                score = self._estimate_spawn_score(wx, wy)
                if score is None:
                    refine_idx += 1
                    continue
                dist_penalty = 0.002 * (abs(wx - mid_x) + abs(wy - mid_y))
                final_score = score - dist_penalty
                if final_score > best_score:
                    best_score = final_score
                    best = (wx, wy)
                refine_idx += 1
            if progress:
                progress(
                    0.80 + 0.20 * (refine_idx / total_refine),
                    f"Recherche du point de départ… (raffinage {refine_idx}/{total_refine})",
                )

        if progress:
            progress(1.0, "Spawn validé")
        return best


    # ------------------- save helpers (optionnel) -------------------

    def get_world_state_minimal(self) -> Dict[str, Any]:
        """
        Données minimales à sauvegarder :
        - params (ou au moins seed/params)
        - overrides overlay (constructions, props détruits, etc.)
        """
        # On ne sauvegarde PAS les chunks (re-générables).
        # On sauvegarde les modifications seulement.
        ov = []
        for (x, y), v in self._overlay_overrides.items():
            ov.append((int(x), int(y), v))
        gov = []
        for (x, y), v in self._ground_overrides.items():
            gov.append((int(x), int(y), int(v)))
        bov = []
        for (x, y), v in self._biome_overrides.items():
            bov.append((int(x), int(y), int(v)))
        return {
            "seed": self.seed,
            "params": self.params.to_dict(),
            "overlay_overrides": ov,
            "ground_overrides": gov,
            "biome_overrides": bov,
        }

    def apply_world_state_minimal(self, blob: Dict[str, Any]) -> None:
        ov = blob.get("overlay_overrides", []) or []
        self._overlay_overrides.clear()
        for item in ov:
            try:
                x, y, v = item
                self._overlay_overrides[(int(x), int(y))] = v
            except Exception:
                continue
        gov = blob.get("ground_overrides", []) or []
        self._ground_overrides.clear()
        for item in gov:
            try:
                x, y, v = item
                self._ground_overrides[(int(x), int(y))] = int(v)
            except Exception:
                continue
        bov = blob.get("biome_overrides", []) or []
        self._biome_overrides.clear()
        for item in bov:
            try:
                x, y, v = item
                self._biome_overrides[(int(x), int(y))] = int(v)
            except Exception:
                continue


# --------------------------------------------------------------------------------------
# Planet world generator
# --------------------------------------------------------------------------------------

class PlanetWorldGenerator:
    """
    Générateur de planète : ne crée pas toute la carte, il renvoie un ChunkedWorld.
    """
    def __init__(self, tiles_levels: int = 6, chunk_size: int = 64, cache_chunks: int = 2048):
        self.tiles_levels = int(tiles_levels)
        self.chunk_size = int(chunk_size)
        self.cache_chunks = int(cache_chunks)

    def _dims_from_params(self, params: WorldParams) -> Tuple[int, int]:
        """
        Tailles conseillées (assez grandes, mais gérables).
        - Taille symbolique (<= 2048) : Petite/Moyenne/Grande/Gigantesque.
        - Taille \"km\" (ex: 22000/28000/34000) : on mappe grossièrement.
        """
        t = int(getattr(params, "Taille", 384))

        # si ça ressemble à une taille en km
        if t >= 8000:
            # mappage grossier
            if t < 25000:
                label = "Petite"
            elif t < 31000:
                label = "Moyenne"
            elif t < 36000:
                label = "Grande"
            else:
                label = "Gigantesque"
        else:
            # t symbolique
            label = "Petite" if t <= 256 else ("Moyenne" if t <= 384 else ("Grande" if t <= 512 else "Gigantesque"))

        size_map = {
            "Petite": (2048, 1024),
            "Moyenne": (3072, 1536),
            "Grande": (4096, 2048),
            "Gigantesque": (6144, 3072),
        }
        w, h = size_map.get(label, (3072, 1536))

        # gravité : impacte la taille totale à générer (perf + densité de jeu)
        grav = str(getattr(params, "gravity", "Moyenne"))
        if grav == "Forte":
            w = int(w * 0.92)
            h = int(h * 0.92)
        elif grav == "Faible":
            w = int(w * 1.05)
            h = int(h * 1.05)

        # clamp sécurité
        w = max(512, min(16384, w))
        h = max(512, min(8192, h))
        return w, h

    def generate(self, params: WorldParams, rng_seed: Optional[int] = None, progress: ProgressCb = None) -> ChunkedWorld:
        def report(p: float, label: str):
            if progress:
                progress(max(0.0, min(1.0, float(p))), str(label))

        base = _seed_int(rng_seed if rng_seed is not None else params.seed)
        final_seed = make_final_seed(base, params)
        w, h = self._dims_from_params(params)

        # sous-progress entre 5% et 95% pendant le spawn
        def spawn_progress(t: float, label: str):
            # t attendu dans [0,1]
            report(0.05 + 0.90 * max(0.0, min(1.0, float(t))), label)

        world = ChunkedWorld(
            width=w,
            height=h,
            seed=final_seed,
            params=params,
            tiles_levels=self.tiles_levels,
            chunk_size=self.chunk_size,
            cache_chunks=self.cache_chunks,
            progress=spawn_progress,   # <-- nouveau
        )

        report(1.0, "Terminé !")
        return world


# --------------------------------------------------------------------------------------
# Public API (WorldGenerator) : uniquement planète
# --------------------------------------------------------------------------------------

class WorldGenerator:
    """
    Anciennement : WorldGenerator gérait île + monde.
    Maintenant : uniquement planète / chunks.

    ⚠️ Paramètres conservés en **kwargs pour compat (si du code passe encore island_margin_frac, etc.).
    """
    def __init__(self, tiles_levels: int = 6, chunk_size: int = 64, cache_chunks: int = 2048, **_ignored):
        self.tiles_levels = int(tiles_levels)
        self.chunk_size = int(chunk_size)
        self.cache_chunks = int(cache_chunks)

    def generate_planet(self, params: WorldParams, rng_seed: Optional[int] = None, progress: ProgressCb = None) -> ChunkedWorld:
        gen = PlanetWorldGenerator(
            tiles_levels=self.tiles_levels,
            chunk_size=self.chunk_size,
            cache_chunks=self.cache_chunks,
        )
        return gen.generate(params=params, rng_seed=rng_seed, progress=progress)

    def generate_world(self, params: WorldParams, *args, **kwargs) -> ChunkedWorld:
        # compat : ignore mode
        rng_seed = kwargs.get("rng_seed", None)
        progress = kwargs.get("progress", None)
        return self.generate_planet(params=params, rng_seed=rng_seed, progress=progress)
