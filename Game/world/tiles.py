# TILES.PY
# Permet d'obtenir la liste des tiles et leurs id (utile dans la génération du monde et le rendu)

# --------------- ID DU TERRAIN ---------------
OCEAN       = 0
BEACH       = 1
GRASS       = 2
FOREST      = 3
ROCK        = 4
TAIGA       = 5
DESERT      = 6
RAINFOREST  = 7
STEPPE      = 8
WATER_SHALLOW = 9
WATER         = 10
WATER_DEEP    = 11
RIVER = 12
LAKE  = 13
SNOW= 14
SWAMP = 15
MANGROVE = 16
ROCKY = 17
ALPINE = 18
VOLCANIC = 19
MYSTIC = 20

# --------------- CATALOGUE ---------------
_DEFAULT_GROUND_SPRITES = {
    OCEAN:      "tile_ocean",
    BEACH:      "tile_beach",
    GRASS:      "tile_grass",
    FOREST:     "tile_forest",
    ROCK:       "tile_rock",
    TAIGA:      "tile_taiga",
    DESERT:     "tile_desert",
    RAINFOREST: "tile_rainforest",
    STEPPE:     "tile_steppe",
    SNOW:       "tile_snow",
    RIVER: "tile_river",  
    LAKE:  "tile_lake",
    WATER_SHALLOW: "tile_water_shallow",
    WATER:         "tile_water",
    WATER_DEEP:    "tile_water_deep",
    SWAMP:     "tile_swamp",
    MANGROVE:  "tile_mangrove",
    ROCKY:     "tile_rocky",
    ALPINE:    "tile_alpine",
    VOLCANIC:  "tile_volcanic",
    MYSTIC:    "tile_mystic",
}

_DEFAULT_NAME_TO_ID = {
    "ocean": OCEAN,
    "beach": BEACH,
    "grass": GRASS,
    "forest": FOREST,
    "rock": ROCK,
    "taiga": TAIGA,
    "desert": DESERT,
    "rainforest": RAINFOREST,
    "steppe": STEPPE,
    "snow": SNOW,
    "river": RIVER,
    "lake":  LAKE,
    "water_shallow": WATER_SHALLOW,
    "water": WATER,
    "water_deep": WATER_DEEP,
    "swamp": SWAMP,
    "mangrove": MANGROVE,
    "rocky": ROCKY,
    "alpine": ALPINE,
    "volcanic": VOLCANIC,
    "mystic": MYSTIC,
}

# --------------- HELPER ---------------

def get_tile_id(logical_name: str) -> int:
    """Ex: 'grass' -> 2. Lève KeyError si inconnu."""
    ln = logical_name.lower()
    if ln not in _DEFAULT_NAME_TO_ID:
        raise KeyError(f"[Tiles] Nom logique inconnu: '{logical_name}'. Clés: {list(self._name_to_id.keys())}")
    return _DEFAULT_NAME_TO_ID[ln]

def get_ground_sprite_name(tile_id: int) -> str:
    """Ex: 2 -> 'tile_grass'. Lève KeyError si inconnu."""
    if tile_id not in _DEFAULT_GROUND_SPRITES:
        raise KeyError(f"[Tiles] ID inconnu: {tile_id}. IDs: {list(self._id_to_sprite.keys())}")
    return _DEFAULT_GROUND_SPRITES[tile_id]
