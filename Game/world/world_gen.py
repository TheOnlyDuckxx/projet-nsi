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
import os
import time
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

def get_prop_id(name: str) -> int:
    _MAP = {
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
        "entrepot": 102,
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
    }
    return _MAP.get(name, _MAP["tree_2"])

ATMOSPHERE_MAP = {
    "Basse": 0.7,
    "Faible": 0.7,
    "Normale": 1.0,
    "Moyenne": 1.0,
    "Haute": 1.3,
    "Épaisse": 1.3,
}

# --------------------------------------------------------------------------------------
# World parameters
# --------------------------------------------------------------------------------------

@dataclass
class WorldParams:
    seed: Optional[int]

    # Historique / compat : vous aviez ces clés dans vos presets.
    # On les garde pour ne pas casser les loaders.
    Taille: int  # peut être : 256/384/512/... (symbolique) OU une taille en km (ex: 28000)
    Climat: str
    Niveau_des_océans: int  # 0..100
    Ressources: str
    age: int

    # Nouveau / menu
    world_name: str = "Nouveau Monde"
    atmosphere_density: float = 1.0

    biodiversity: str = "Moyenne"
    tectonic_activity: str = "Stable"
    weather: str = "Variable"
    gravity: str = "Moyenne"
    cosmic_radiation: str = "Faible"
    mystic_influence: str = "Nulle"
    dimensional_stability: str = "Stable"

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "WorldParams":
        raw = d.get("atmosphere_density", 1.0)
        if isinstance(raw, str):
            atmosphere_density = ATMOSPHERE_MAP.get(raw, 1.0)
        else:
            atmosphere_density = float(raw)
        return WorldParams(
            seed=d.get("seed", None),
            Taille=int(d.get("Taille", 256)),
            Climat=str(d.get("Climat", "Tempéré")),
            Niveau_des_océans=int(d.get("Niveau des océans", d.get("Niveau_des_océans", 50))),
            Ressources=str(d.get("Ressources", "Moyenne")),
            age=int(d.get("age", 2000)),
            world_name=str(d.get("world_name", "Nouveau Monde")),
            atmosphere_density=atmosphere_density,
            biodiversity=str(d.get("biodiversity", "Moyenne")),
            tectonic_activity=str(d.get("tectonic_activity", "Stable")),
            weather=str(d.get("weather", "Variable")),
            gravity=str(d.get("gravity", "Moyenne")),
            cosmic_radiation=str(d.get("cosmic_radiation", "Faible")),
            mystic_influence=str(d.get("mystic_influence", "Nulle")),
            dimensional_stability=str(d.get("dimensional_stability", "Stable")),
        )


    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_world_params_from_preset(
    preset_name: str,
    path: str = "Game/data/world_presets.json",
    overrides: Optional[Dict[str, Any]] = None,
) -> WorldParams:
    """
    Charge un preset en acceptant :
      - ancien format : Taille, Climat, 'Niveau des océans', Ressources...
      - format menu : world_size, temperature, water_coverage, resource_density, etc.
    """
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

    # --- World name
    if "world_name" not in d:
        d["world_name"] = d.get("world_name", preset_name)

    # --- Taille
    # Si world_size est un label, on le transforme en symbolique (256/384/512/768).
    if "Taille" not in d:
        raw_size = d.get("world_size", "Moyenne")
        if isinstance(raw_size, (int, float)):
            d["Taille"] = int(raw_size)
        else:
            s = str(raw_size).lower()
            if "petit" in s:
                d["Taille"] = 256
            elif "moyen" in s:
                d["Taille"] = 384
            elif "grand" in s:
                d["Taille"] = 512
            elif "gigan" in s:
                d["Taille"] = 768
            else:
                d["Taille"] = 384

    # --- Climat
    if "Climat" not in d:
        raw_temp = d.get("temperature", "Tempéré")
        t = str(raw_temp).lower()
        if "glacia" in t:
            d["Climat"] = "Glaciaire"
        elif "froid" in t:
            d["Climat"] = "Froid"
        elif "arid" in t:
            d["Climat"] = "Aride"
        elif "trop" in t or "chaud" in t:
            d["Climat"] = "Tropical"
        else:
            d["Climat"] = "Tempéré"

    # --- Niveau des océans
    if "Niveau des océans" not in d and "Niveau_des_océans" not in d:
        raw_cov = d.get("water_coverage", "Tempéré")
        if isinstance(raw_cov, (int, float)):
            d["Niveau_des_océans"] = int(raw_cov)
        else:
            c = str(raw_cov).lower()
            if "aride" in c or "sec" in c:
                d["Niveau_des_océans"] = 25
            elif "océan" in c or "ocean" in c or "beaucoup" in c:
                d["Niveau_des_océans"] = 75
            else:
                d["Niveau_des_océans"] = 50

    # --- Ressources
    if "Ressources" not in d:
        d["Ressources"] = str(d.get("resource_density", "Moyenne"))

    # --- age
    if "age" not in d:
        d["age"] = int(d.get("age", 2000))

    # --- atmosphere_density (menu -> float)
    if "atmosphere_density" not in d:
        raw = d.get("atmosphere_density", "Normale")
        if isinstance(raw, (int, float)):
            d["atmosphere_density"] = float(raw)
        else:
            s = str(raw).lower()
            if "faible" in s or "thin" in s:
                d["atmosphere_density"] = 0.8
            elif "épais" in s or "dense" in s or "thick" in s:
                d["atmosphere_density"] = 1.2
            else:
                d["atmosphere_density"] = 1.0

    # autres champs menu (si absents)
    d.setdefault("biodiversity", d.get("biodiversity", "Moyenne"))
    d.setdefault("tectonic_activity", d.get("tectonic_activity", "Stable"))
    d.setdefault("weather", d.get("weather", "Variable"))
    d.setdefault("gravity", d.get("gravity", "Moyenne"))
    d.setdefault("cosmic_radiation", d.get("cosmic_radiation", "Faible"))
    d.setdefault("mystic_influence", d.get("mystic_influence", "Nulle"))
    d.setdefault("dimensional_stability", d.get("dimensional_stability", "Stable"))

    return WorldParams.from_dict(d)


def load_world_params_from_menu_dict(menu_dict: Dict[str, Any]) -> WorldParams:
    """
    Construit un WorldParams à partir du JSON du menu (format 'Custom' que tu as donné).
    """
    raw_seed = menu_dict.get("seed", None)
    if raw_seed in (None, "", "Aléatoire", "Aleatoire", "Random", "random"):
        seed = None
    else:
        try:
            seed = int(raw_seed)
        except Exception:
            seed = None

    size_label = str(menu_dict.get("world_size", "Moyenne"))
    s = size_label.lower()
    if "petit" in s:
        taille = 256
    elif "grand" in s:
        taille = 512
    elif "gigan" in s:
        taille = 768
    else:
        taille = 384

    # water_coverage, temperature etc restent en label mais on les mappe sur votre ancien format
    water_label = str(menu_dict.get("water_coverage", "Tempéré")).lower()
    if "aride" in water_label:
        oceans = 25
    elif "océan" in water_label or "ocean" in water_label:
        oceans = 75
    else:
        oceans = 50

    temp_label = str(menu_dict.get("temperature", "Tempéré")).lower()
    if "glacia" in temp_label:
        climat = "Glaciaire"
    elif "froid" in temp_label:
        climat = "Froid"
    elif "arid" in temp_label:
        climat = "Aride"
    elif "chaud" in temp_label or "trop" in temp_label:
        climat = "Tropical"
    else:
        climat = "Tempéré"

    raw = menu_dict.get("atmosphere_density", "Normale")
    if isinstance(raw, str):
        atmo = ATMOSPHERE_MAP.get(raw, 1.0)
    else:
        atmo = float(raw)


    return WorldParams(
        seed=seed,
        Taille=taille,
        Climat=climat,
        Niveau_des_océans=oceans,
        Ressources=str(menu_dict.get("resource_density", "Moyenne")),
        age=int(menu_dict.get("age", 2000)),
        world_name=str(menu_dict.get("world_name", "Nouveau Monde")),
        atmosphere_density=float(atmo),
        biodiversity=str(menu_dict.get("biodiversity", "Moyenne")),
        tectonic_activity=str(menu_dict.get("tectonic_activity", "Stable")),
        weather=str(menu_dict.get("weather", "Variable")),
        gravity=str(menu_dict.get("gravity", "Moyenne")),
        cosmic_radiation=str(menu_dict.get("cosmic_radiation", "Faible")),
        mystic_influence=str(menu_dict.get("mystic_influence", "Nulle")),
        dimensional_stability=str(menu_dict.get("dimensional_stability", "Stable")),
    )


# --------------------------------------------------------------------------------------
# Deterministic seed helpers
# --------------------------------------------------------------------------------------

def _seed_int(v: Any) -> int:
    if v is None:
        return random.getrandbits(63)

    if isinstance(v, str):
        s = v.strip()
        if s in ("", "Aléatoire", "Aleatoire", "Random", "random"):
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
    """
    Seed final = hash(base_seed + paramètres).
    Important : on n'interprète pas Taille comme km ici, on garde la valeur brute.
    """
    raw_atmo = getattr(params, "atmosphere_density", 1.0)
    if isinstance(raw_atmo, str):
        atmo_val = ATMOSPHERE_MAP.get(raw_atmo, 1.0)
    else:
        try:
            atmo_val = float(raw_atmo)
        except Exception:
            atmo_val = 1.0

    sig = (
        f"{int(base_seed)}|{params.world_name}|{params.Taille}|{params.Climat}|"
        f"{int(params.Niveau_des_océans)}|{params.Ressources}|{int(params.age)}|"
        f"{atmo_val:.3f}|{getattr(params,'biodiversity','Moyenne')}|"
        f"{getattr(params,'tectonic_activity','Stable')}|{getattr(params,'weather','Variable')}|{getattr(params,'gravity','Moyenne')}|"
        f"{getattr(params,'cosmic_radiation','Faible')}|{getattr(params,'mystic_influence','Nulle')}|{getattr(params,'dimensional_stability','Stable')}"
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
# Biomes (IDs + names)
# --------------------------------------------------------------------------------------

BIOME_OCEAN = 1
BIOME_COAST = 2
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
BIOME_ROCKY = 20
BIOME_ALPINE = 21
BIOME_VOLCANIC = 22
BIOME_MYSTIC = 23

BIOME_ID_TO_NAME: Dict[int, str] = {
    BIOME_OCEAN: "ocean",
    BIOME_COAST: "coast",
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
    BIOME_ROCKY: "rocky",
    BIOME_ALPINE: "alpine",
    BIOME_VOLCANIC: "volcanic",
    BIOME_MYSTIC: "mystic",
}


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
        cache_chunks: int = 256,
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

        # Proxies pour compat (world.ground_id[y][x], etc.)
        self.heightmap = _GridProxy(self.width, self.height, self.get_height01)
        self.moisture = _GridProxy(self.width, self.height, self.get_moisture01)
        self.levels = _GridProxy(self.width, self.height, self.get_level)
        self.ground_id = _GridProxy(self.width, self.height, self.get_ground_id)
        self.biome = _GridProxy(self.width, self.height, self.get_biome_name)
        self.overlay = _GridProxy(self.width, self.height, self.get_overlay, self.set_overlay)
        self.max_levels = tiles_levels

        # Spawn (déterminé rapidement)
        self.spawn = self._find_spawn(progress=progress)


    # ------------------- tile ids safe -------------------

    def _safe_tile_id(self, name: str) -> int:
        try:
            return int(get_tile_id(name))
        except Exception:
            try:
                return int(get_tile_id("grass"))
            except Exception:
                return 0

    # ------------------- parameters -> knobs -------------------

    def _sea_level_from_params(self, params: WorldParams) -> float:
        v = float(getattr(params, "Niveau_des_océans", 50))
        v = max(0.0, min(100.0, v))
        # 0% -> mer basse (0.42), 100% -> mer haute (0.58)
        return 0.42 + (v / 100.0) * 0.16

    def _knobs(self):
        p = self.params
        # temp bias
        temp_label = str(getattr(p, "Climat", "Tempéré"))
        temp_bias = {
            "Glaciaire": -0.38,
            "Froid": -0.22,
            "Tempéré": 0.0,
            "Chaud": 0.20,
            "Aride": 0.28,
            "Tropical": 0.18,
        }.get(temp_label, 0.0)

        water_v = float(getattr(p, "Niveau_des_océans", 50))
        water_bias = (water_v - 50.0) / 100.0  # -0.5..+0.5

        biodiv = str(getattr(p, "biodiversity", "Moyenne"))
        biodiv_mul = {"Faible": 0.65, "Moyenne": 1.0, "Élevée": 1.25, "Haute": 1.25}.get(biodiv, 1.0)

        tect = str(getattr(p, "tectonic_activity", "Stable"))
        rugged = {"Stable": 0.9, "Modérée": 1.0, "Instable": 1.25, "Violente": 1.45}.get(tect, 1.0)

        res_label = str(getattr(p, "Ressources", "Moyenne"))
        res_mul = {"Faible": 0.75, "Moyenne": 1.0, "Normale": 1.0, "Élevée": 1.2, "Haute": 1.2, "Riche": 1.35}.get(res_label, 1.0)

        atmo = float(getattr(p, "atmosphere_density", 1.0))
        atmo = max(0.6, min(1.6, atmo))

        weather = str(getattr(p, "weather", "Variable"))
        # plus variable = plus d'écarts d'humidité
        weather_var = {"Calme": 0.85, "Stable": 0.9, "Variable": 1.0, "Extrême": 1.25}.get(weather, 1.0)

        grav = str(getattr(p, "gravity", "Moyenne"))
        grav_relief = {"Faible": 1.12, "Basse": 1.12, "Moyenne": 1.0, "Forte": 0.92, "Élevée": 0.92}.get(grav, 1.0)

        rad = str(getattr(p, "cosmic_radiation", "Faible"))
        rad_mul = {"Nulle": 1.05, "Faible": 1.0, "Moyenne": 0.92, "Forte": 0.82}.get(rad, 1.0)

        myst = str(getattr(p, "mystic_influence", "Nulle"))
        myst_mul = {"Nulle": 0.0, "Faible": 0.35, "Moyenne": 0.65, "Forte": 1.0}.get(myst, 0.0)

        return {
            "temp_bias": temp_bias,
            "water_bias": water_bias,
            "biodiv_mul": biodiv_mul * rad_mul,
            "rugged": rugged * grav_relief * (0.85 + 0.25 * atmo),
            "res_mul": res_mul,
            "atmo": atmo,
            "weather_var": weather_var,
            "myst_mul": myst_mul,
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
        ch, lx, ly = self._get_chunk_xy(x, y)
        return int(ch.ground_u16[ch.idx(lx, ly)])

    def get_biome_id(self, x: int, y: int) -> int:
        ch, lx, ly = self._get_chunk_xy(x, y)
        return int(ch.biome_u8[ch.idx(lx, ly)])

    def get_biome_name(self, x: int, y: int) -> str:
        return BIOME_ID_TO_NAME.get(self.get_biome_id(x, y), "unknown")

    def get_is_water(self, x: int, y: int) -> bool:
        bid = self.get_biome_id(x, y)
        return bid in (BIOME_OCEAN, BIOME_COAST, BIOME_LAKE, BIOME_RIVER)

    # ------------------- chunk management -------------------

    def _get_chunk_xy(self, x: int, y: int):
        x = _wrap_lon_x(int(x), self.width)
        y = _clamp_lat_y(int(y), self.height)
        return self._get_chunk(x, y)

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

        # -------- paramètres -> multiplicateurs (comme avant) --------
        temp_label = str(getattr(self.params, "Climat", "Tempéré"))
        temp_bias = {"Glaciaire": -0.35, "Froid": -0.20, "Tempéré": 0.0, "Chaud": 0.20, "Aride": 0.25, "Tropical": 0.18}.get(temp_label, 0.0)

        water_v = float(getattr(self.params, "Niveau_des_océans", 50))
        water_bias = (water_v - 50.0) / 100.0  # -0.5..+0.5

        biodiv = str(getattr(self.params, "biodiversity", "Moyenne"))
        biodiv_mul = {"Faible": 0.65, "Moyenne": 1.0, "Élevée": 1.25, "Haute": 1.25}.get(biodiv, 1.0)

        tect = str(getattr(self.params, "tectonic_activity", "Stable"))
        rugged = {"Stable": 0.9, "Modérée": 1.0, "Instable": 1.2, "Violente": 1.35}.get(tect, 1.0)

        res_label = str(getattr(self.params, "Ressources", "Moyenne"))
        res_mul = {"Faible": 0.75, "Moyenne": 1.0, "Normale": 1.0, "Élevée": 1.2, "Haute": 1.2}.get(res_label, 1.0)

        base = int(self.seed)

        # -------- helpers bruit (continus) --------
        def ridged(x: float, y: float, seed: int, octaves: int = 4) -> float:
            # _fbm -> [-1,1], ridged -> [0,1]
            n = _fbm(x, y, seed, octaves=octaves)
            r = 1.0 - abs(n)
            return _clamp01(r)

        def domain_warp(gx: float, gy: float, amp: float, scale: float, seed: int) -> tuple[float, float]:
            wx = gx + amp * _fbm(gx * scale, gy * scale, seed + 1, octaves=3)
            wy = gy + amp * _fbm((gx + 1337.0) * scale, (gy - 7331.0) * scale, seed + 2, octaves=3)
            return wx, wy

        # échelles (IMPORTANT : ne plus dépendre de cx/cy)
        cont_scale   = 0.0011 * rugged
        detail_scale = 0.0100 * rugged

        warp_amp   = 140.0 * rugged     # en tuiles
        warp_scale = 0.0009             # fréquence du warp

        peak_scale = 0.0045 * rugged    # fréquence montagnes
        micro_scale = 0.025             # micro-relief

        # petite variation de côte (continue) pour casser les rivages trop lisses
        coast_var_scale = 0.0035
        coast_var_amp   = 0.020  # +/- 0.02 sur le niveau mer

        # boucle chunk
        for ly in range(cs):
            gy = cy * cs + ly
            if gy >= self.height:
                break

            lat = (gy / max(1, self.height - 1)) * 2.0 - 1.0  # -1..+1
            lat_abs = abs(lat)

            for lx in range(cs):
                gx = cx * cs + lx
                if gx >= self.width:
                    break

                # --- domain warp (rend formes + naturelles, casse l’alignement chunk/grid) ---
                wx, wy = domain_warp(float(gx), float(gy), amp=warp_amp, scale=warp_scale, seed=base + 90000)

                # --- élévation (CONTINUE) ---
                h1 = _fbm(wx * cont_scale,   wy * cont_scale,   base + 11,  octaves=5)
                h2 = _fbm(wx * detail_scale, wy * detail_scale, base + 97,  octaves=4)
                h = 0.70 * h1 + 0.30 * h2
                h01 = _clamp01((h + 1.0) * 0.5)

                # accentue un peu le contraste (évite les continents “tout pareil”)
                h01 = _clamp01(h01 ** 1.12)

                # montagnes (ridged) seulement si altitude déjà un peu haute
                r = ridged(wx * peak_scale, wy * peak_scale, base + 7777, octaves=4)
                r = r * r  # sharpen
                mount_mask = _clamp01((h01 - 0.52) / 0.48)
                h01 = _clamp01(h01 + (0.33 * rugged) * r * (mount_mask ** 2))

                # micro-relief (plaines moins plates)
                micro = _fbm(wx * micro_scale, wy * micro_scale, base + 4242, octaves=3)  # [-1,1]
                h01 = _clamp01(h01 + 0.045 * micro)

                # plus d'eau => baisse terre
                h01 = _clamp01(h01 - 0.06 * water_bias)

                # variation locale du niveau de mer (continue) pour côtes + naturelles
                sea_here = self.sea_level + coast_var_amp * _fbm(wx * coast_var_scale, wy * coast_var_scale, base + 9991, octaves=2)

                # --- température (CONTINUE) ---
                tnoise = _fbm(wx * 0.003, wy * 0.003, base + 201, octaves=3)
                t01 = 1.0 - lat_abs
                t01 = _clamp01(t01 + 0.25 * tnoise + temp_bias)

                # --- humidité (CONTINUE) ---
                mnoise = _fbm(wx * 0.004, wy * 0.004, base + 333, octaves=4)
                m01 = _clamp01((mnoise + 1.0) * 0.5)
                # plus haut => plus sec
                m01 = _clamp01(m01 - 0.38 * max(0.0, h01 - sea_here))

                # --- eau douce (pas d'océans/mer) ---
                lake_level = sea_here - 0.06 + 0.05 * water_bias
                lake_level = max(0.30, min(0.70, lake_level))
                lake_noise = _fbm(wx * 0.0022, wy * 0.0022, base + 6060, octaves=3)
                lake_cut = 0.58 - 0.10 * water_bias
                is_lake = (lake_noise > lake_cut) and (h01 < lake_level)

                river_noise = abs(_fbm(wx * 0.008, wy * 0.008, base + 7070, octaves=3))
                river_th = 0.03 + 0.012 * max(0.0, water_bias)
                is_river = (river_noise < river_th) and (h01 < 0.78)

                is_water = is_lake or is_river
                coast = (not is_water) and (
                    (lake_noise > lake_cut - 0.06 and h01 < lake_level + 0.03)
                    or (river_noise < river_th * 1.8 and h01 < 0.80)
                )

                # --- biome (inchangé dans l’idée) ---
                if is_lake:
                    bid = BIOME_LAKE
                elif is_river:
                    bid = BIOME_RIVER
                elif coast:
                    bid = BIOME_COAST
                else:
                    if t01 < 0.18:
                        bid = BIOME_SNOW
                    elif t01 < 0.30:
                        bid = BIOME_TAIGA if m01 > 0.35 else BIOME_TUNDRA
                    else:
                        if m01 < 0.18:
                            bid = BIOME_DESERT if t01 > 0.45 else BIOME_TUNDRA
                        elif m01 < 0.35:
                            bid = BIOME_SAVANNA if t01 > 0.45 else BIOME_PLAINS
                        elif m01 < 0.60:
                            bid = BIOME_PLAINS if t01 < 0.55 else BIOME_FOREST
                        else:
                            bid = BIOME_RAINFOREST if t01 > 0.55 else BIOME_FOREST

                # --- niveau (anti-plateau : dithering + meilleure normalisation) ---
                if bid == BIOME_LAKE:
                    level = 0
                    gname = "lake"
                elif bid == BIOME_RIVER:
                    level = 0
                    gname = "river"
                elif bid == BIOME_COAST:
                    level = 1
                    gname = "beach"
                else:
                    # normalise hauteur de terre au-dessus côte
                    base0 = sea_here + 0.040
                    land01 = (h01 - base0) / max(1e-6, (1.0 - base0))
                    land01 = _clamp01(land01)

                    # jitter déterministe (casse les grands aplats)
                    jit = _rand01_from_u32(_hash_u32(base ^ _hash_u32(gx * 92837111) ^ _hash_u32(gy * 689287499))) - 0.5
                    land01 = _clamp01(land01 + 0.11 * jit)

                    inner = max(1, self.tiles_levels - 2)
                    level = 2 + int(round(land01 * inner))

                    # boost pics montagneux
                    if r > 0.78 and level < self.tiles_levels:
                        level += 1

                    level = max(2, min(self.tiles_levels, level))

                    # ground par biome
                    if bid in (BIOME_SNOW, BIOME_TUNDRA):
                        gname = "snow" if bid == BIOME_SNOW else "tundra"
                    elif bid == BIOME_DESERT:
                        gname = "desert"
                    elif bid == BIOME_SAVANNA:
                        gname = "savanna"
                    else:
                        gname = "grass"

                gid = self._safe_tile_id(gname)

                # --- props (IMPORTANT : seed par TUILE, pas par chunk) ---
                prop = 0
                if bid not in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER) and not coast:
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

                    tile_seed = _hash_u32(base ^ _hash_u32(gx * 912367) ^ _hash_u32(gy * 972541))
                    r0 = _rand01_from_u32(tile_seed)
                    r1 = _rand01_from_u32(_hash_u32(tile_seed ^ 0xA5A5A5A5))

                    if r0 < ore_p:
                        if level >= 5 and r1 < 0.18:
                            prop = get_prop_id("ore_gold")
                        elif r1 < 0.55:
                            prop = get_prop_id("ore_iron")
                        else:
                            prop = get_prop_id("ore_copper")
                    elif r0 < ore_p + base_p:
                        if bid == BIOME_DESERT:
                            prop = get_prop_id("cactus") if r1 < 0.7 else get_prop_id("rock")
                        elif bid in (BIOME_TUNDRA, BIOME_SNOW):
                            prop = get_prop_id("rock") if r1 < 0.65 else get_prop_id("stump")
                        elif bid in (BIOME_FOREST, BIOME_RAINFOREST, BIOME_TAIGA):
                            prop = get_prop_id("tree_1") if r1 < 0.33 else (get_prop_id("tree_2") if r1 < 0.66 else get_prop_id("tree_3"))
                        elif bid == BIOME_SAVANNA:
                            prop = get_prop_id("tree_dead") if r1 < 0.35 else get_prop_id("bush")
                        else:
                            prop = get_prop_id("bush") if r1 < 0.6 else get_prop_id("flower")

                # écrit chunk
                k = ch.idx(lx, ly)
                ch.height_u8[k] = int(_clamp01(h01) * 255.0)
                ch.temp_u8[k]   = int(_clamp01(t01) * 255.0)
                ch.moist_u8[k]  = int(_clamp01(m01) * 255.0)
                ch.levels_u8[k] = int(level)
                ch.ground_u16[k]= int(gid)
                ch.overlay_obj[k] = int(prop)
                ch.biome_u8[k]  = int(bid)

        return ch

    # ------------------- spawn -------------------

    def _find_spawn(self, progress: ProgressCb = None) -> Tuple[int, int]:
        """
        Spawn rapide :
        - recherche locale autour du centre/équateur (évite générer des chunks partout)
        - peu d’essais
        - yield du GIL pour laisser l’UI respirer (sinon "ne répond plus")
        """
        rng = random.Random(self.seed ^ 0xC0FFEE)

        mid_x = self.width // 2
        mid_y = self.height // 2

        # zone de recherche locale (tweakables)
        x_span = max(64, self.width // 16)      # ~6% de la largeur
        y_span = max(64, self.height // 10)     # ~10% de la hauteur
        tries = 60                               # au lieu de 1200

        best = None
        best_score = -1e9

        for i in range(tries):
            # IMPORTANT : local, pas un x uniforme sur toute la planète
            x = _wrap_lon_x(mid_x + rng.randrange(-x_span, x_span + 1), self.width)
            y = _clamp_lat_y(mid_y + rng.randrange(-y_span, y_span + 1), self.height)

            # 1 seul appel biome (au lieu de get_is_water + get_biome_id)
            bid = self.get_biome_id(x, y)
            if bid in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER):
                continue

            # éviter props / obstacles
            if self.get_overlay(x, y):
                continue

            # score : plains/forest favorisés
            score = 0.0
            if bid in (BIOME_PLAINS, BIOME_FOREST):
                score += 3.0
            elif bid == BIOME_SAVANNA:
                score += 1.0

            # pénalise désert/neige
            if bid in (BIOME_DESERT, BIOME_SNOW, BIOME_TUNDRA):
                score -= 4.0

            # altitude modérée
            h = self.get_height01(x, y)
            score -= abs(h - (self.sea_level + 0.12)) * 6.0

            if score > best_score:
                best_score = score
                best = (x, y)

            # Progress + yield GIL (sinon thread UI bloqué)
            if progress and (i % 5 == 0 or i == tries - 1):
                progress(i / max(1, tries - 1), f"Recherche du point de départ… ({i+1}/{tries})")
            if i % 2 == 0:
                time.sleep(0)  # yield GIL

        if best:
            return best

        # fallback : spiral courte autour du centre (toujours locale)
        if progress:
            progress(1.0, "Fallback spawn…")
        for r in range(1, 256):
            # périmètre du carré de rayon r
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    x = _wrap_lon_x(mid_x + dx, self.width)
                    y = _clamp_lat_y(mid_y + dy, self.height)
                    bid = self.get_biome_id(x, y)
                    if bid not in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER) and not self.get_overlay(x, y):
                        return (x, y)
            for dy in range(-r + 1, r):
                for dx in (-r, r):
                    x = _wrap_lon_x(mid_x + dx, self.width)
                    y = _clamp_lat_y(mid_y + dy, self.height)
                    bid = self.get_biome_id(x, y)
                    if bid not in (BIOME_OCEAN, BIOME_LAKE, BIOME_RIVER) and not self.get_overlay(x, y):
                        return (x, y)

            if r % 16 == 0:
                time.sleep(0)

        return (mid_x, mid_y)


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
        return {
            "seed": self.seed,
            "params": self.params.to_dict(),
            "overlay_overrides": ov,
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


# --------------------------------------------------------------------------------------
# Planet world generator
# --------------------------------------------------------------------------------------

class PlanetWorldGenerator:
    """
    Générateur de planète : ne crée pas toute la carte, il renvoie un ChunkedWorld.
    """
    def __init__(self, tiles_levels: int = 6, chunk_size: int = 64, cache_chunks: int = 256):
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

        # gravity influence dimensions (perf)
        grav = str(getattr(params, "gravity", "Moyenne"))
        if grav in ("Forte", "Élevée", "Haute"):
            w = int(w * 0.92)
            h = int(h * 0.92)
        elif grav in ("Faible", "Basse"):
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
    def __init__(self, tiles_levels: int = 6, chunk_size: int = 64, cache_chunks: int = 256, **_ignored):
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
