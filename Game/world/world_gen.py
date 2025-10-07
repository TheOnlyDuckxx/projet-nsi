# WORLD_GEN.PY
# Génère le monde procéduralement tout en utilisant les paramètres fournit


"""
NE PAS ESSAYER DE COMPRENDRE CE FICHIER, C'EST 100% FAIT PAR CHAT GPT

Petit récap :

[PARAMÈTRES + SEED]
        ↓
[1] Génére la map avec un "bruit fractal" (cf.wikipédia)
        ↓
[2] Entoure l'ile d'eau
        ↓
[3] Calcul du niveau de la mer (% eau)
        ↓
[4] Normalisation + quantification (étages)
        ↓
[5] Ajout de l'humidité (autre bruit)
        ↓
[6] Choix du biome (règles)
        ↓
[7] Placement des props (arbres, rochers)
        ↓
[8] Recherche du spawn
        ↓
[WORLD DATA prêt pour affichage]

"""


# --------------- IMPORTATION DES MODULES ---------------
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict, Any
import json, os, random, math, hashlib, struct

# --- Optionnel : si tes modules fournissent des helpers d'ID de tuiles/ressources ---
# On les utilise si disponibles, sinon on a un fallback interne.
try:
    from .tiles import get_tile_id  # attendu: get_tile_id("grass") -> int
except Exception:
    def get_tile_id(name: str) -> int:
        # mapping minimal par défaut
        _MAP = {"ocean": 0, "beach": 1, "grass": 2, "forest": 3, "rock": 4, "taiga": 5, "desert": 6, "rainforest": 7, "steppe": 8}
        return _MAP.get(name, 2)

try:
    from .ressource import get_prop_id  # attendu: get_prop_id("tree_small") -> int
except Exception:
    def get_prop_id(name: str) -> int:
        _MAP = {"tree": 10, "rock": 11, "bush": 12}
        return _MAP.get(name, None)


# --------- Données & paramètres ---------
@dataclass
class WorldParams:
    seed: Optional[int]
    planet_width: int
    planet_height: int
    water_pct: int                     # 0..100
    temperature: str                   # "cold" | "temperate" | "hot"
    atmosphere_density: float          # ~ 0.6..1.4
    resource_density: float            # ~ 0.5..2.0
    world_name: str = "New World"

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "WorldParams":
        return WorldParams(
            seed=d.get("seed", None),
            planet_width=int(d["planet_width"]),
            planet_height=int(d["planet_height"]),
            water_pct=int(d["water_pct"]),
            temperature=str(d["temperature"]),
            atmosphere_density=float(d["atmosphere_density"]),
            resource_density=float(d["resource_density"]),
            world_name=str(d.get("world_name", "New World")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorldData:
    width: int
    height: int
    sea_level: float
    heightmap: List[List[float]]       # 0..1 (après normalisation et mer retirée)
    levels:   List[List[int]]          # étages / cubes (0..N)
    ground_id: List[List[int]]         # id tuile sol (herbe, sable…)
    moisture: List[List[float]]        # 0..1
    biome:    List[List[str]]          # nom de biome par case
    overlay:  List[List[Optional[int]]]# props (arbres, rochers…)
    spawn:    Tuple[int, int]          # (x, y)


# --------- Presets ---------
def load_world_params_from_preset(preset_name: str, path: str="Game/data/world_presets.json",
                                  overrides: Optional[Dict[str, Any]]=None) -> WorldParams:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Preset file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    preset = doc.get("presets", {}).get(preset_name)
    if preset is None:
        raise KeyError(f"Preset '{preset_name}' not found in {path}")
    if overrides:
        preset = {**preset, **overrides}
    return WorldParams.from_dict(preset)


# --------- Seed finale (seed + signature params) ---------
def _normalize_params_for_seed(params: WorldParams) -> str:
    # Ordre stable + arrondis raisonnables
    return "|".join([
        f"w={params.planet_width}",
        f"h={params.planet_height}",
        f"water={params.water_pct}",
        f"temp={params.temperature}",
        f"atmo={round(params.atmosphere_density, 4)}",
        f"res={round(params.resource_density, 4)}",
        f"name={params.world_name}",
    ])

def make_final_seed(user_seed: Optional[int], params: WorldParams) -> int:
    base = user_seed if user_seed is not None else 0
    sig  = _normalize_params_for_seed(params)
    data = f"{base}::{sig}".encode("utf-8")
    h = hashlib.blake2b(data, digest_size=8).digest()  # 64-bit
    return struct.unpack("<Q", h)[0]


# --------- Petits helpers math/noise ---------
def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def smoothstep(t: float) -> float:
    t = clamp01(t)
    return t * t * (3 - 2 * t)

def value_noise2d(ix: int, iy: int, seed: int) -> float:
    # Value-noise cheap mais suffisant pour un MVP (déterministe)
    rnd = random.Random((ix * 73856093) ^ (iy * 19349663) ^ seed)
    return rnd.uniform(-1.0, 1.0)

def fbm2d(x: float, y: float, octaves: int, seed: int) -> float:
    amp, freq = 1.0, 1.0
    val, norm = 0.0, 0.0
    for i in range(octaves):
        xi, yi = math.floor(x * freq), math.floor(y * freq)
        xf, yf = (x * freq) - xi, (y * freq) - yi

        n00 = value_noise2d(xi,     yi,     seed + i)
        n10 = value_noise2d(xi + 1, yi,     seed + i)
        n01 = value_noise2d(xi,     yi + 1, seed + i)
        n11 = value_noise2d(xi + 1, yi + 1, seed + i)

        ux, uy = smoothstep(xf), smoothstep(yf)
        nx0 = lerp(n00, n10, ux)
        nx1 = lerp(n01, n11, ux)
        nxy = lerp(nx0, nx1, uy)

        val += nxy * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return val / max(norm, 1e-9)


# --------- Générateur principal (île) ---------
class WorldGenerator:
    def __init__(self, tiles_levels: int = 6):
        """
        tiles_levels = nombre de niveaux (étages de cubes) max après quantification.
        """
        self.tiles_levels = tiles_levels

    def generate_island(self, params: WorldParams, rng_seed: Optional[int]=None) -> WorldData:
        """
        Génère une île isométrique cohérente à partir de params.
        - rng_seed : si fourni, override la seed finale (utile pour tests A/B)
        """
        final_seed = rng_seed if rng_seed is not None else make_final_seed(params.seed, params)
        rng = random.Random(final_seed)

        W, H = params.planet_width, params.planet_height

        # --- 1) Heightmap brute (fBM) ---
        # Échelle des features: planètes + grandes => features plus larges
        base_scale = 0.012 if max(W, H) >= 300 else 0.02
        height_raw = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                n = fbm2d(x*base_scale, y*base_scale, octaves=4, seed=final_seed)
                height_raw[y][x] = (n + 1.0) * 0.5  # 0..1

        # --- 2) Masque Île (radial falloff) ---
        cx, cy = (W - 1) * 0.5, (H - 1) * 0.5
        maxd = math.hypot(cx, cy) or 1.0
        # Atmosphere_density adoucit/renforce le falloff
        atmo = params.atmosphere_density
        falloff_strength = 0.85 + (1.2 - atmo) * 0.25   # tweakable
        height_island = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                d = math.hypot(x - cx, y - cy) / maxd  # 0..1
                # courbe en S, paramétrée par falloff_strength
                f = smoothstep(d ** falloff_strength)
                h = clamp01(height_raw[y][x] - f*0.65)  # 0.65 règle la taille de l'île
                height_island[y][x] = h

        # --- 3) Niveau de la mer par quantile (water_pct) ---
        sea_level = self._sea_level_from_percent(height_island, params.water_pct)
        land_h = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                land_h[y][x] = max(0.0, height_island[y][x] - sea_level)

        # Renormalisation 0..1 (au-dessus de la mer)
        maxh = max((v for row in land_h for v in row), default=1e-6)
        if maxh < 1e-6:
            maxh = 1e-6
        for y in range(H):
            for x in range(W):
                land_h[y][x] /= maxh

        # --- 4) Quantification en étages ---
        levels = [[self._quantize(land_h[y][x], self.tiles_levels) for x in range(W)] for y in range(H)]

        # --- 5) Moisture + Temp (biomes) ---
        moist = [[0.0]*W for _ in range(H)]
        mscale = 0.03
        for y in range(H):
            for x in range(W):
                m = fbm2d(x*mscale, y*mscale, octaves=3, seed=final_seed+1337)
                moist[y][x] = (m + 1.0) * 0.5  # 0..1

        temp_bias = {"cold": -0.25, "temperate": 0.0, "hot": +0.25}.get(params.temperature, 0.0)
        temp_global = clamp01(0.5 + temp_bias)

        biome = [["ocean"]*W for _ in range(H)]
        ground_id = [[get_tile_id("ocean")]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                if levels[y][x] <= 0:
                    biome[y][x] = "ocean"
                    ground_id[y][x] = get_tile_id("ocean")
                elif levels[y][x] == 1:
                    biome[y][x] = "beach"
                    ground_id[y][x] = get_tile_id("beach")
                else:
                    b = self._choose_biome(land_h[y][x], moist[y][x], temp_global)
                    biome[y][x] = b
                    # mapping biome -> sol
                    ground_id[y][x] = get_tile_id(self._biome_to_ground(b))

        # --- 6) Props (arbres/rochers) selon biome + densité ---
        overlay = [[None]*W for _ in range(H)]
        base_tree = {
            "forest": 0.22,
            "rainforest": 0.28,
            "taiga": 0.18,
            "grassland": 0.08,
            "steppe": 0.04,
        }
        base_rock = {
            "rock": 0.12,
            "beach": 0.02,
            "desert": 0.03,
            "taiga": 0.03,
        }
        density_mul = clamp01(params.resource_density) * 1.4  # boost léger

        for y in range(1, H-1):
            for x in range(1, W-1):
                if levels[y][x] <= 0:
                    continue  # mer
                b = biome[y][x]
                # arbres
                tprob = base_tree.get(b, 0.0) * density_mul
                if rng.random() < tprob:
                    overlay[y][x] = get_prop_id("tree")
                    continue
                # rochers
                rprob = base_rock.get(b, 0.0) * density_mul
                if rng.random() < rprob:
                    overlay[y][x] = get_prop_id("rock")

        # Évite d’en mettre trop près du bord de l’eau immédiat
        self._sparsify_coast(overlay, levels)

        # --- 7) Spawn (zone “saine”) ---
        spawn = self._find_spawn(levels, biome, overlay)

        return WorldData(
            width=W,
            height=H,
            sea_level=sea_level,
            heightmap=land_h,
            levels=levels,
            ground_id=ground_id,
            moisture=moist,
            biome=biome,
            overlay=overlay,
            spawn=spawn,
        )

    # --------- Helpers privés ---------
    def _sea_level_from_percent(self, heightmap: List[List[float]], water_pct: int) -> float:
        flat = sorted(v for row in heightmap for v in row)
        if not flat:
            return 0.0
        k = int(len(flat) * (water_pct / 100.0))
        if k < 0: k = 0
        if k >= len(flat): k = len(flat) - 1
        return flat[k]

    def _quantize(self, h01: float, levels: int) -> int:
        # h in [0..1] → 0..levels (entier)
        q = int(round(h01 * levels))
        if q < 0: q = 0
        if q > levels: q = levels
        return q

    def _choose_biome(self, land_h: float, moist: float, temp_global: float) -> str:
        # land_h > 0 assuré
        # règles simples pour MVP
        if land_h < 0.08:
            return "beach"
        # matrice humidité/temp
        if moist < 0.28:
            return "desert" if temp_global > 0.6 else "steppe"
        elif moist < 0.6:
            return "grassland" if temp_global >= 0.4 else "taiga"
        else:
            return "rainforest" if temp_global > 0.6 else "forest"

    def _biome_to_ground(self, b: str) -> str:
        if b in ("forest", "rainforest", "grassland", "steppe", "taiga"):
            return "grass"
        if b in ("desert",):
            return "sand" if hasattr(self, "_sand_exists") and self._sand_exists else "desert"
        if b in ("rock",):
            return "rock"
        if b == "beach":
            return "beach"
        return "grass"

    def _sparsify_coast(self, overlay: List[List[Optional[int]]], levels: List[List[int]]):
        H, W = len(levels), len(levels[0]) if levels else (0, 0)
        for y in range(1, H-1):
            for x in range(1, W-1):
                if overlay[y][x] is None:
                    continue
                # si près d’une case d’eau (niveau 0), chance de retirer
                if (levels[y-1][x] == 0 or levels[y+1][x] == 0 or
                    levels[y][x-1] == 0 or levels[y][x+1] == 0):
                    if random.random() < 0.6:
                        overlay[y][x] = None

    def _find_spawn(self, levels: List[List[int]], biome: List[List[str]], overlay: List[List[Optional[int]]]) -> Tuple[int, int]:
        H, W = len(levels), len(levels[0]) if levels else (0, 0)
        best = None
        best_score = -1e9
        for y in range(2, H-2):
            for x in range(2, W-2):
                if levels[y][x] <= 0:  # pas dans l’eau
                    continue
                if overlay[y][x] is not None:  # éviter spawn sur un prop
                    continue
                # plat = variation faible autour
                flatness = 0.0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0: 
                            continue
                        flatness -= abs(levels[y][x] - levels[y+dy][x+dx])
                # pénalise proximité de l’eau immédiate
                water_near = 0
                for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                    if levels[y+dy][x+dx] == 0: water_near += 1
                score = flatness - 2.5*water_near
                # bonus biomes “faciles”
                if biome[y][x] in ("grassland","forest","beach"):
                    score += 2.0
                if score > best_score:
                    best_score = score
                    best = (x, y)
        return best if best else (W//2, H//2)
