# WORLD_GEN.PY
# Génère le monde procéduralement tout en utilisant les paramètres fournit


# --------------- IMPORTATION DES MODULES ---------------
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import struct
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from Game.world.tiles import get_tile_id

ProgressCb = Optional[Callable[[float, str], None]]


def get_prop_id(name: str) -> int:
    _MAP = {
        "tree_2": 10,
        "tree_dead": 12,
        "rock": 13,
        "palm": 14,
        "cactus": 15,
        "bush": 16,
        "berry_bush": 17,
        "reeds": 18,       # roseaux
        "driftwood": 19,   # bois flotté
        "flower": 20,
        "stump": 21,       # souche
        "log": 22,         # tronc au sol
        "boulder": 23,     # gros rocher
        "flower2": 25,
        "flower3": 26,
        "entrepot": 24,
        "blueberry_bush":28,
    }
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
def load_world_params_from_preset(
    preset_name: str,
    path: str = "Game/data/world_presets.json",
    overrides: Optional[Dict[str, Any]] = None
) -> WorldParams:
    """
    Charge un preset de monde en acceptant :
      - l'ancien format (Taille, Climat, 'Niveau des océans', Ressources, etc.)
      - le nouveau format du menu (world_size, water_coverage, temperature,
        resource_density, atmosphere_density = 'Faible/Normale/Épaisse', etc.)
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Preset file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    preset = doc.get("presets", {}).get(preset_name)
    if preset is None:
        raise KeyError(f"Preset '{preset_name}' not found in {path}")

    # Copie modifiable
    d: Dict[str, Any] = dict(preset)

    # Merge éventuels overrides
    if overrides:
        d.update(overrides)

    # ---------- Taille ----------
    if "Taille" not in d:
        raw_size = d.get("world_size", "Moyenne")
        taille_km: int

        if isinstance(raw_size, (int, float)):
            taille_km = int(raw_size)
        elif isinstance(raw_size, str):
            s = raw_size.lower()
            if "petite" in s:
                taille_km = 22000
            elif "moyen" in s:
                taille_km = 28000
            elif "grand" in s:
                taille_km = 34000
            elif "gigan" in s:
                taille_km = 38000
            else:
                taille_km = 28000
        else:
            taille_km = 28000

        d["Taille"] = taille_km

    # ---------- Climat ----------
    if "Climat" not in d:
        raw_temp = d.get("temperature", "Tempéré")
        climat: str

        if isinstance(raw_temp, str):
            t = raw_temp.lower()
            if "glaciaire" in t:
                climat = "Glaciaire"
            elif "froid" in t:
                climat = "Froid"
            elif "temp" in t:
                climat = "Tempéré"
            elif "chaud" in t:
                climat = "Tropical"
            elif "ardent" in t:
                climat = "Aride"
            else:
                climat = "Tempéré"
        else:
            climat = "Tempéré"

        d["Climat"] = climat

    # ---------- Niveau des océans ----------
    if "Niveau des océans" not in d:
        raw_cov = d.get("water_coverage", "Tempéré")
        niveau: int

        if isinstance(raw_cov, (int, float)):
            niveau = int(raw_cov)
        elif isinstance(raw_cov, str):
            c = raw_cov.lower()
            if "aride" in c:
                niveau = 25
            elif "temp" in c:
                niveau = 50
            elif "océan" in c or "ocean" in c:
                niveau = 75
            else:
                niveau = 50
        else:
            niveau = 50

        d["Niveau des océans"] = niveau

    # ---------- Ressources ----------
    if "Ressources" not in d:
        raw_res = d.get("resource_density", "Moyenne")
        res: str

        if isinstance(raw_res, str):
            r = raw_res.lower()
            if "pauvre" in r:
                res = "Faible"
            elif "moy" in r:
                res = "Normale"
            elif "riche" in r:
                res = "Riche"
            elif "instable" in r:
                # pour l'instant on assimile à Riche (densité forte)
                res = "Riche"
            else:
                res = "Normale"
        else:
            res = "Normale"

        d["Ressources"] = res

    # ---------- Atmosphère (float) ----------
    raw_atmo = d.get("atmosphere_density", 1.0)
    atmo_val: float

    if isinstance(raw_atmo, (int, float)):
        atmo_val = float(raw_atmo)
    elif isinstance(raw_atmo, str):
        s = raw_atmo.lower()
        if "faible" in s:
            atmo_val = 0.7
        elif "norm" in s:
            atmo_val = 1.0
        elif "épais" in s or "epais" in s:
            atmo_val = 1.3
        else:
            try:
                atmo_val = float(raw_atmo.replace(",", "."))
            except Exception:
                atmo_val = 1.0
    else:
        atmo_val = 1.0

    d["atmosphere_density"] = atmo_val

    # ---------- Age par défaut ----------
    if "age" not in d:
        d["age"] = 2000

    # Le reste (seed, world_name, etc.) est déjà géré par WorldParams.from_dict
    return WorldParams.from_dict(d)


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
    def __init__(self,
                 tiles_levels: int = 6,
                 island_margin_frac: float = 0.12,   # marge océan par rapport au plus petit côté (8% par défaut)
                 coast_band_tiles: int = 8,         # largeur de la bande où on "déforme" la côte
                 beach_width_tiles: int = 2,         # épaisseur de la plage (levels==1)
                 coast_noise_amp: float = 0.45):     # amplitude de la rugosité côtière
        self.tiles_levels = tiles_levels
        self.island_margin_frac = max(0.0, min(0.4, island_margin_frac))
        self.coast_band_tiles = max(2, int(coast_band_tiles))
        self.beach_width_tiles = max(1, int(beach_width_tiles))
        self.coast_noise_amp = float(coast_noise_amp)


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

        # [2] Île ronde avec rivage irrégulier (pas d'îlots, pas de terre aux bords)
        cx, cy = (W - 1) * 0.5, (H - 1) * 0.5
        min_dim = min(W, H)

        # marge océan -> garantit un anneau d'eau avant les bords
        margin = max(3, int(self.island_margin_frac * min_dim))
        R0 = (min_dim * 0.5) - margin                 # rayon "cible" du disque
        coast_band = self.coast_band_tiles            # largeur de la bande où on bruit le rivage
        beach_w = self.beach_width_tiles              # plage (levels==1)

        # bruit utilisé seulement pour la bande côtière (fréquence adaptée à la taille)
        coast_scale = 0.06 * (256.0 / max(128.0, min_dim))  # + petit monde => bruit + large
        coast_seed = final_seed + 901

        land_h = [[0.0]*W for _ in range(H)]     # hauteur de la terre (0..1)
        levels  = [[0]*W for _ in range(H)]      # 0: eau, 1: plage, >=2: intérieur

        for y in range(H):
            for x in range(W):
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                rd = d - R0  # négatif = à l'intérieur du cercle, positif = à l'extérieur

                if rd > coast_band:
                    # Au delà de la bande -> eau forcée (océan)
                    levels[y][x] = 0
                    land_h[y][x] = 0.0
                    continue
                if rd < -coast_band:
                    # Profond à l'intérieur du disque -> terre forcée
                    # hauteur douce qui croît vers le centre + un soupçon de bruit
                    core = clamp01(1.0 - (d / max(R0 - coast_band, 1.0))**1.15)
                    n = fbm2d(x*0.02, y*0.02, octaves=3, seed=final_seed+77)  # micro relief
                    h = clamp01(core + 0.12 * n)
                    land_h[y][x] = h
                    # plage si proche du rivage
                    if abs(rd) <= beach_w:
                        levels[y][x] = 1
                    else:
                        inner_levels = max(0, self.tiles_levels - 2)  # réserve 0 et 1
                        levels[y][x] = 2 + int(round(h * inner_levels))
                    continue

                n01 = (fbm2d(x*coast_scale, y*coast_scale, octaves=3, seed=coast_seed) + 1.0) * 0.5  # 0..1
                # amplitude de retrait de côte en tuiles:
                shrink = self.coast_noise_amp * float(coast_band) * n01
                R_eff = R0 - shrink

                if d > R_eff:
                    # Océan (à l'extérieur du rayon rétréci)
                    levels[y][x] = 0
                    land_h[y][x] = 0.0
                else:
                    # Terre (à l'intérieur)
                    # plage si on est dans l'anneau terminal
                    if (R_eff - beach_w) <= d <= R_eff:
                        levels[y][x] = 1  # plage
                        land_h[y][x] = 0.12  # petite hauteur symbolique
                    else:
                        # hauteur douce (monte vers le centre) + micro relief
                        core = clamp01(1.0 - (d / max(R0 - coast_band, 1.0))**1.15)
                        n2 = fbm2d(x*0.02, y*0.02, octaves=3, seed=final_seed+77)
                        h = clamp01(core + 0.12 * n2)
                        land_h[y][x] = h
                        inner_levels = max(0, self.tiles_levels - 2)  # réserve 0 et 1
                        levels[y][x] = 2 + int(round(h * inner_levels))

            report(acc + w_island * ((y+1)/H), "Génération île ronde…")
        acc += w_island

        # (option sécurité) supprimer tout petit morceau de terre isolé:
        self._keep_largest_landmass(levels)
        report(acc + 0.01, "Nettoyage des fragments…")

        # [3] Niveau des océans (stat) — on le CALCULE mais on ne l'utilise plus pour noyer la terre
        # (servira pour lacs/rivières plus tard)
        sea_level = float(params.Niveau_des_océans) / 100.0
        report(acc + w_sea, "Niveau des océans (stat)…")
        acc += w_sea

        # [4] Quantification en étages
        for y in range(H):
            for x in range(W):
                if levels[y][x] == 0:
                    # on laisse l'océan tel quel
                    continue
                if levels[y][x] == 1:
                    # on garde la plage décidée en [2]
                    continue
                # intérieur: étagement 2..N en fonction de land_h
                inner_levels = max(0, self.tiles_levels - 2)
                levels[y][x] = 2 + int(round(clamp01(land_h[y][x]) * inner_levels))
        
        # [4.5] Rivières & lacs internes (eau douce)
        fresh_type = [[0]*W for _ in range(H)]  # 0=aucun, 1=rivière, 2=lac

        # sources en altitude
        sources = self._pick_river_sources(levels, land_h, rng)
        for sx, sy in sources:
            self._carve_river_path(sx, sy, cx, cy, levels, land_h, fresh_type, rng)


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
                if fresh_type[y][x] == 1:
                    biome[y][x] = "river"; ground_id[y][x] = get_tile_id("river")
                elif fresh_type[y][x] == 2:
                    biome[y][x] = "lake";  ground_id[y][x] = get_tile_id("lake")
                elif levels[y][x] <= 0:
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
                    d = self._distance_to_land(x, y, levels)
                    if d < 2:   ground_id[y][x] = get_tile_id("water_shallow")
                    elif d < 5: ground_id[y][x] = get_tile_id("water")
                    else:       ground_id[y][x] = get_tile_id("water_deep")


        # [7] Props (variété + règles par biome + bord d’eau)
        overlay = [[None]*W for _ in range(H)]
        res_map = {"Faible": 0.5, "Normale": 1.0, "Riche": 1.5}
        density_mul = res_map.get(params.Ressources.capitalize(), 1.0) * 1.4

        # étiquette chaud/froid
        temp_map = {"Glaciaire": "cold","Froid":"cold","Tempéré":"temperate","Tropical":"hot","Aride":"hot"}
        temp_label = temp_map.get(params.Climat.capitalize(), "temperate")
        is_hot = (temp_label == "hot")

        rng_cluster_seed = final_seed + 424242
        cluster_scale = 0.07  # plus petit -> taches plus grandes

        def cluster_mask(x, y):
            c = fbm2d(x*cluster_scale, y*cluster_scale, octaves=2, seed=rng_cluster_seed)
            return (c + 1.0) * 0.5  # 0..1

        for y in range(1, H-1):
            for x in range(1, W-1):
                if levels[y][x] <= 0:
                    continue
                b = biome[y][x]
                near_water = (self._distance_to_water(x, y, levels) <= 2)
                cm = cluster_mask(x, y)
                
                near_fresh = (self._distance_to_freshwater(x, y, fresh_type) <= 2)
                if near_fresh and rng.random() < 0.06 * density_mul:
                    overlay[y][x] = get_prop_id("reeds")
                    continue

                if fresh_type[y][x] > 0:   # rivière/lac
                    continue


                # base: petites chances de fleurs/buissons partout hors désert
                if b not in ("desert", "rock") and rng.random() < 0.02 * density_mul * (0.5 + cm):
                    if random.randint(0,2)==0:
                        overlay[y][x] = get_prop_id("flower")
                    elif random.randint(0,2)==1:
                        overlay[y][x] = get_prop_id("flower2")
                    elif random.randint(0,2)==2:
                        overlay[y][x] = get_prop_id("flower3")
                    continue
                if b not in ("desert",) and rng.random() < 0.025 * density_mul * (0.4 + cm):
                    if random.randint(0,3) == 0:
                        overlay[y][x] = get_prop_id("berry_bush")
                    else:
                        overlay[y][x] = get_prop_id("bush")
                    continue

                # forêts/taïga/grassland : arbres & souches/troncs
                if b in ("forest", "rainforest", "taiga", "grassland"):
                    # arbres
                    p_tree = {"forest":0.22,"rainforest":0.28,"taiga":0.18,"grassland":0.08}.get(b,0.0)
                    p_tree *= density_mul * (0.6 + 0.8*cm)
                    if rng.random() < p_tree:
                        if b == "taiga":
                            name = "tree_dead" if rng.random() < 0.6 else "tree_2"
                        elif b == "rainforest":
                            name = "tree_2" if rng.random() < 0.7 else "stump"
                        else:
                            name = "tree_2"
                        overlay[y][x] = get_prop_id(name)
                        continue
                    # souches / troncs au sol (clairsemé)
                    if rng.random() < 0.015 * density_mul * (0.4 + cm):
                        overlay[y][x] = get_prop_id("stump" if rng.random() < 0.5 else "log")
                        continue

                # plage : palmiers (si climat chaud), rochers légers, bois flotté, roseaux près de l’eau
                if b == "beach":
                    if is_hot and rng.random() < 0.06 * density_mul * (0.4 + cm):
                        overlay[y][x] = get_prop_id("palm")
                        continue
                    if near_water and rng.random() < 0.04 * density_mul:
                        overlay[y][x] = get_prop_id("driftwood")
                        continue
                    if near_water and rng.random() < 0.05 * density_mul:
                        overlay[y][x] = get_prop_id("reeds")
                        continue
                    if rng.random() < 0.02 * density_mul:
                        overlay[y][x] = get_prop_id("rock")
                        continue

                # désert : cactus, blocs, quelques rochers
                if b == "desert":
                    if rng.random() < 0.06 * density_mul * (0.4 + cm):
                        overlay[y][x] = get_prop_id("cactus")
                        continue
                    if rng.random() < 0.02 * density_mul:
                        overlay[y][x] = get_prop_id("boulder")
                        continue
                    if rng.random() < 0.015 * density_mul:
                        overlay[y][x] = get_prop_id("rock")
                        continue

                # zones rocheuses/taiga : rochers/boulders
                if b in ("rock", "taiga") and rng.random() < 0.03 * density_mul * (0.3 + cm):
                    overlay[y][x] = get_prop_id("rock" if rng.random() < 0.7 else "boulder")
                    continue

            report(acc + w_props * ((y+1)/H), "Placement des éléments…")

        # éviter la pollution visuelle en bord de côte
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
    
    def _distance_to_water(self, x, y, levels):
        H, W = len(levels), len(levels[0])
        for r in range(1, 6):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H:
                        if levels[ny][nx] == 0:  # eau
                            return r
        return 999
    

    def _keep_largest_landmass(self, levels: List[List[int]]) -> None:
        H = len(levels)
        W = len(levels[0]) if H else 0
        seen = [[False]*W for _ in range(H)]
        comps = []
        from collections import deque

        def bfs(sx, sy):
            q = deque([(sx, sy)])
            seen[sy][sx] = True
            cells = [(sx, sy)]
            while q:
                x, y = q.popleft()
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny][nx]:
                        if levels[ny][nx] > 0:
                            seen[ny][nx] = True
                            q.append((nx, ny))
                            cells.append((nx, ny))
            return cells

        for y in range(H):
            for x in range(W):
                if levels[y][x] > 0 and not seen[y][x]:
                    comps.append(bfs(x, y))

        if not comps:
            return
        main = max(comps, key=len)
        main_set = set(main)
        for y in range(H):
            for x in range(W):
                if levels[y][x] > 0 and (x, y) not in main_set:
                    levels[y][x] = 0  # redevient océan

    def _neighbors8(self, x, y, W, H):
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                if dx==0 and dy==0: continue
                nx, ny = x+dx, y+dy
                if 0 <= nx < W and 0 <= ny < H:
                    yield nx, ny

    def _carve_disc(self, cx, cy, r, levels, land_h, fresh_type):
        H, W = len(levels), len(levels[0])
        rr = r*r
        for y in range(max(0, cy-r), min(H, cy+r+1)):
            for x in range(max(0, cx-r), min(W, cx+r+1)):
                if (x-cx)*(x-cx) + (y-cy)*(y-cy) <= rr:
                    fresh_type[y][x] = 2


    def _carve_river_path(self, sx, sy, cx, cy, levels, land_h, fresh_type, rng):
        H, W = len(levels), len(levels[0])
        x, y = sx, sy
        visited = set()
        steps = 0
        max_steps = (W + H) * 4

        # Bruit spatial fixe pour ce cours d’eau (donc méandres cohérents)
        noise_seed = rng.randint(0, 10**9)
        noise_scale = 0.08      # taille des méandres
        wander_amp = 0.04       # force du "zigzag"
        radial_amp = 0.0006     # biais vers la mer (plus faible qu’avant)
        prev_dx, prev_dy = 0, 0

        while steps < max_steps:
            steps += 1
            visited.add((x, y))

            # marque la rivière
            fresh_type[y][x] = 1  # 1 = rivière

            # atteint la mer ? (voisin eau salée 4-connexe)
            for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if 0 <= nx < W and 0 <= ny < H and levels[ny][nx] == 0 and fresh_type[ny][nx] == 0:
                    return  # on a rejoint l’océan

            # Choix du prochain pas
            dc = math.hypot(x - cx, y - cy)
            candidates = []

            for nx, ny in self._neighbors8(x, y, W, H):
                if (nx, ny) in visited:
                    continue
                # on évite de marcher dans l’océan directement
                if levels[ny][nx] == 0:
                    continue

                base_h = land_h[ny][nx]

                # petit biais vers l’extérieur (mer)
                new_d = math.hypot(nx - cx, ny - cy)
                radial_term = - radial_amp * (new_d - dc)

                # bruit spatial déterministe → méandres
                n = fbm2d(nx * noise_scale, ny * noise_scale, octaves=2, seed=noise_seed)
                wander = wander_amp * n   # dans [-wander_amp, +wander_amp]

                # légère inertie pour ne pas faire des zigzags brutaux
                if prev_dx or prev_dy:
                    dx, dy = nx - x, ny - y
                    dot = dx * prev_dx + dy * prev_dy
                    norm = math.hypot(dx, dy) * math.hypot(prev_dx, prev_dy) or 1.0
                    align = dot / norm   # -1 (demi-tour) → +1 (tout droit)
                    turn_penalty = 0.01 * (1.0 - align)
                else:
                    turn_penalty = 0.0

                cost = base_h + radial_term + wander + turn_penalty
                candidates.append((cost, nx, ny))

            if not candidates:
                break  # coincé

            # On prend au hasard parmi les 2–3 meilleurs candidats
            candidates.sort(key=lambda c: c[0])
            top_k = candidates[:3] if len(candidates) >= 3 else candidates
            _, nx, ny = rng.choice(top_k)

            # Si on monte trop → cul-de-sac : créer un petit lac comme avant
            if land_h[ny][nx] > land_h[y][x] + 0.02:
                self._carve_disc(x, y, rng.randint(2, 3), levels, land_h, fresh_type)
                # repartir du bord le plus bas autour du lac
                cand = []
                for px, py in self._neighbors8(x, y, W, H):
                    cand.append((land_h[py][px], px, py))
                cand.sort()
                if cand:
                    nx, ny = cand[0][1], cand[0][2]
                else:
                    break

            prev_dx, prev_dy = nx - x, ny - y
            x, y = nx, ny


    def _pick_river_sources(self, levels, land_h, rng, count_range=(3,6)):
        H, W = len(levels), len(levels[0])
        cand = []
        # candidats haut perchés, loin des côtes
        for y in range(H):
            for x in range(W):
                if levels[y][x] >= 2 and land_h[y][x] > 0.55 and self._distance_to_water(x,y,levels) > 5:
                    cand.append((land_h[y][x], x, y))
        cand.sort(reverse=True)  # plus hauts d'abord
        sources = []
        want = rng.randint(*count_range)
        min_dist = max(10, min(W,H)//12)
        for h,x,y in cand:
            if len(sources) >= want: break
            if all((abs(x-sx) + abs(y-sy)) >= min_dist for sx,sy in sources):
                sources.append((x,y))
        return sources

    def _distance_to_freshwater(self, x, y, fresh_type):
        H, W = len(fresh_type), len(fresh_type[0])
        for r in range(1, 6):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H:
                        if fresh_type[ny][nx] > 0:
                            return r
        return 999
