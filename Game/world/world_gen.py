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
from typing import Callable

# Type du callback: progress(fraction: float, label: str)
ProgressCb = Optional[Callable[[float, str], None]]
# --- Optionnel : si tes modules fournissent des helpers d'ID de tuiles/ressources ---
# On les utilise si disponibles, sinon on a un fallback interne.
from Game.world.tiles import get_tile_id

def get_prop_id(name: str) -> int:
    _MAP = {
        "tree_2": 10,
        "tree_base": 11,
        "tree_dead": 12,
        "rock": 13,
    }
    # Si le nom n’est pas reconnu → renvoie une variante générique “tree”
    return _MAP.get(name, _MAP["tree_2"])


# --------- Données & paramètres ---------
@dataclass
class WorldParams:
    seed: Optional[int]
    Taille: int                 # ancien planet_width
    Climat: str                 # ancien temperature
    Niveau_des_océans: int      # ancien water_pct
    Ressources: str             # ancien resource_density (valeur symbolique)
    age: int
    atmosphere_density: float = 1.0
    world_name: str = "Nouveau Monde"

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "WorldParams":
        return WorldParams(
            seed=d.get("seed", None),
            Taille=int(d.get("Taille", 256)),
            Climat=str(d.get("Climat", "Tempéré")),
            Niveau_des_océans=int(d.get("Niveau des océans", 50)),
            Ressources=str(d.get("Ressources", "Normale")),
            age=int(d.get("age", 2000)),
            atmosphere_density=float(d.get("atmosphere_density", 1.0)),
            world_name=str(d.get("world_name", "Nouveau Monde")),
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


def km_to_blocks(km: int) -> int:
        km = max(20000, min(40000, km))
        t = (km - 20000) / 20000
        return int(256 + (256 * (t ** 1.3)))

# --------- Seed finale (seed + signature params) ---------
def _normalize_params_for_seed(params: WorldParams) -> str:
    """Crée une signature stable des paramètres du monde (pour la graine)."""
    res_map = {"Faible": 0.5, "Normale": 1.0, "Riche": 1.5}
    ressources_val = res_map.get(str(params.Ressources).capitalize(), 1.0)
    taille_blocs = km_to_blocks(params.Taille)

    # Ordre stable + arrondis raisonnables
    return "|".join([
        f"taille_km={params.Taille}",
        f"taille_blocs={taille_blocs}",
        f"age={params.age}",
        f"climat={params.Climat}",
        f"eau={params.Niveau_des_océans}",
        f"atmo={round(params.atmosphere_density, 4)}",
        f"ressources={round(ressources_val, 4)}",
        f"nom={params.world_name}",
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
        self.tiles_levels = tiles_levels

    def generate_island(self, params: WorldParams, rng_seed: Optional[int]=None,
                        progress: ProgressCb=None) -> WorldData:
        def report(p, label):
            if progress:
                progress(max(0.0, min(1.0, p)), label)
        if params.seed in (None, "Aléatoire", "random", ""):
            params.seed = random.randint(0, 10**9)
        final_seed = rng_seed if rng_seed is not None else make_final_seed(params.seed, params)
        rng = random.Random(final_seed)

        W= H = km_to_blocks(params.Taille)

        # Petites pondérations de temps par phase (à la louche)
        w_height  = 0.30
        w_island  = 0.10
        w_sea     = 0.05
        w_quant   = 0.10
        w_moist   = 0.15
        w_biome   = 0.20
        w_props   = 0.08
        w_spawn   = 0.02

        acc = 0.0
        report(acc, "Initialisation…")

        # [1] Heightmap brute
        base_scale = 0.012 if max(W, H) >= 300 else 0.02
        height_raw = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                n = fbm2d(x*base_scale, y*base_scale, octaves=4, seed=final_seed)
                height_raw[y][x] = (n + 1.0) * 0.5
            report(acc + w_height * ((y+1)/H), "Génération du terrain…")
        acc += w_height

        # [2] Masque île
        cx, cy = (W - 1) * 0.5, (H - 1) * 0.5
        maxd = math.hypot(cx, cy) or 1.0
        atmo = params.atmosphere_density
        falloff_strength = 0.85 + (1.2 - atmo) * 0.25
        height_island = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                d = math.hypot(x - cx, y - cy) / maxd
                f = smoothstep(d ** falloff_strength)
                h = clamp01(height_raw[y][x] - f*0.65)
                height_island[y][x] = h
            report(acc + w_island * ((y+1)/H), "Découpage de l’île…")
        acc += w_island

        # [3] Niveau de la mer + renormalisation
        sea_level = self._sea_level_from_percent(height_island, params.Niveau_des_océans)
        report(acc + w_sea*0.5, "Calcul du niveau de la mer…")
        land_h = [[0.0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                land_h[y][x] = max(0.0, height_island[y][x] - sea_level)
        maxh = max((v for row in land_h for v in row), default=1e-6)
        if maxh < 1e-6: maxh = 1e-6
        for y in range(H):
            for x in range(W):
                land_h[y][x] /= maxh
        report(acc + w_sea, "Niveau de la mer…")
        acc += w_sea

        # [4] Quantification en étages
        levels = [[0]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                levels[y][x] = self._quantize(land_h[y][x], self.tiles_levels)
            report(acc + w_quant * ((y+1)/H), "Étagement du relief…")
        acc += w_quant

        # [5] Humidité
        moist = [[0.0]*W for _ in range(H)]
        mscale = 0.03
        for y in range(H):
            for x in range(W):
                m = fbm2d(x*mscale, y*mscale, octaves=3, seed=final_seed+1337)
                moist[y][x] = (m + 1.0) * 0.5
            report(acc + w_moist * ((y+1)/H), "Ajout de vie…")
        acc += w_moist

        # [6] Biomes + ground_id
        temp_map = {
            "Glaciaire": "cold",
            "Froid": "cold",
            "Tempéré": "temperate",
            "Tropical": "hot",
            "Aride": "hot"
        }
        temp_label = temp_map.get(params.Climat.capitalize(), "temperate")
        temp_bias = {"cold": -0.25, "temperate": 0.0, "hot": +0.25}[temp_label]
        temp_global = clamp01(0.5 + temp_bias)
        biome = [["ocean"]*W for _ in range(H)]
        ground_id = [[get_tile_id("ocean")]*W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                if levels[y][x] <= 0:
                    biome[y][x] = "ocean"; ground_id[y][x] = get_tile_id("ocean")
                elif levels[y][x] == 1:
                    biome[y][x] = "beach"; ground_id[y][x] = get_tile_id("beach")
                else:
                    b = self._choose_biome(land_h[y][x], moist[y][x], temp_global)
                    biome[y][x] = b
                    ground_id[y][x] = get_tile_id(self._biome_to_ground(b))
            report(acc + w_biome * ((y+1)/H), "Attribution des biomes…")
        acc += w_biome

        for y in range(H):
            for x in range(W):
                if biome[y][x] == "ocean":
                    # distance à la côte
                    d = self._distance_to_land(x, y, levels)
                    if d < 2:
                        ground_id[y][x] = get_tile_id("water_shallow")
                    elif d < 5:
                        ground_id[y][x] = get_tile_id("water")
                    else:
                        ground_id[y][x] = get_tile_id("water_deep")

        # [7] Props
        overlay = [[None]*W for _ in range(H)]
        res_map = {"Faible": 0.5, "Normale": 1.0, "Riche": 1.5}
        density_mul = res_map.get(params.Ressources.capitalize(), 1.0) * 1.4

        # Définition des variantes pondérées
        tree_variants = {
            "forest": [("tree_2", 0.6), ("tree_dead", 0.2), ("tree_base", 0.2)],
            "rainforest": [("tree_2", 0.5), ("tree_dead", 0.3),("tree_base", 0.2)],
            "taiga": [("tree_2", 0.3), ("tree_dead", 0.7)],
            "grassland": [("tree_2", 0.8), ("tree_base", 0.2)],
        }

        rock_variants = {
            "rock": [("rock", 1.0)],
            "beach": [("rock", 0.6)],
            "desert": [("rock", 0.4)],
        }

        prob_tree = {"forest":0.22,"rainforest":0.28,"taiga":0.18,"grassland":0.08,"steppe":0.04}
        prob_rock = {"rock":0.12,"beach":0.02,"desert":0.03,"taiga":0.03}

        for y in range(1, H-1):
            for x in range(1, W-1):
                if levels[y][x] <= 0: 
                    continue
                b = biome[y][x]
                tprob = prob_tree.get(b, 0.0) * density_mul
                rprob = prob_rock.get(b, 0.0) * density_mul

                # Arbres
                if rng.random() < tprob and b in tree_variants:
                    name = self._weighted_choice(tree_variants[b], rng)
                    overlay[y][x] = get_prop_id(name)
                    continue
                # Rochers
                if rng.random() < rprob and b in rock_variants:
                    name = self._weighted_choice(rock_variants[b], rng)
                    overlay[y][x] = get_prop_id(name)
            report(acc + w_props * ((y+1)/H), "Placement des éléments…")
        self._sparsify_coast(overlay, levels)
        acc += w_props


        # [8] Spawn
        report(acc + w_spawn*0.5, "Recherche d’un bon spawn…")
        spawn = self._find_spawn(levels, biome, overlay)
        acc += w_spawn
        report(1.0, "Terminé !")

        return WorldData(
            width=W, height=H, sea_level=sea_level, heightmap=land_h,
            levels=levels, ground_id=ground_id, moisture=moist,
            biome=biome, overlay=overlay, spawn=spawn
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
            return "desert"
        if b in ("rock",):
            return "rock"
        if b == "beach":
            return "beach"
        return "grass"

    def _sparsify_coast(self, overlay: List[List[Optional[int]]], levels: List[List[int]]):
        H = len(levels)
        W = len(levels[0]) if H > 0 else 0
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
        H = len(levels)
        W = len(levels[0]) if H > 0 else 0
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
    
    def _weighted_choice(self, items, rng):
        total = sum(w for _, w in items)
        r = rng.random() * total
        for name, w in items:
            if r < w:
                return name
            r -= w
        return items[-1][0]
    
    def _distance_to_land(self, x, y, levels):
        H, W = len(levels), len(levels[0])
        for r in range(1, 8):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H:
                        if levels[ny][nx] > 0:
                            return r
        return 999
 