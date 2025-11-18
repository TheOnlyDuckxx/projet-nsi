# TILES.PY
# Gère les tiles


# --------------- IMPORTATION DES MODULES ---------------
from __future__ import annotations
from typing import Dict, Optional, Tuple

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

# --------------- CATALOGUE ---------------
_DEFAULT_GROUND_SPRITES: Dict[int, str] = {
    OCEAN:      "tile_ocean",
    BEACH:      "tile_beach",
    GRASS:      "tile_grass",
    FOREST:     "tile_forest",
    ROCK:       "tile_rock",
    TAIGA:      "tile_taiga",
    DESERT:     "tile_desert",
    RAINFOREST: "tile_rainforest",
    STEPPE:     "tile_steppe",
}

_DEFAULT_NAME_TO_ID: Dict[str, int] = {
    "ocean": OCEAN,
    "beach": BEACH,
    "grass": GRASS,
    "forest": FOREST,
    "rock": ROCK,
    "taiga": TAIGA,
    "desert": DESERT,
    "rainforest": RAINFOREST,
    "steppe": STEPPE,
}

WATER_SHALLOW = 9
WATER         = 10
WATER_DEEP    = 11

RIVER = 12
LAKE  = 13

_DEFAULT_GROUND_SPRITES.update({
    RIVER: "tile_river",  
    LAKE:  "tile_lake",
})

_DEFAULT_NAME_TO_ID.update({
    "river": RIVER,
    "lake":  LAKE,
})

_DEFAULT_GROUND_SPRITES.update({
    WATER_SHALLOW: "tile_water_shallow",
    WATER:         "tile_water",
    WATER_DEEP:    "tile_water_deep",
})

_DEFAULT_NAME_TO_ID.update({
    "water_shallow": WATER_SHALLOW,
    "water": WATER,
    "water_deep": WATER_DEEP,
})

# --------------- CLASSE PRINCIPALE ---------------
class Tiles:
    """
    Fournit:
      - mapping id <-> clé d'asset pour le sol
      - helpers pour récupérer la Surface depuis Assets
      - sélection d’une variante d’autotile pour falaises/rives
    """

    def __init__(self):
        self._id_to_sprite: Dict[int, str] = dict(_DEFAULT_GROUND_SPRITES)
        self._name_to_id: Dict[str, int]   = dict(_DEFAULT_NAME_TO_ID)
        self._autotile_variants: Dict[str, Dict[str, str]] = {}

    #Enregistrement / modification

    def register_tile(self, tile_id: int, sprite_key: str, logical_name: Optional[str] = None) -> None:
        """Ajoute ou modifie une tuile (id -> sprite_key), et nom logique optionnel (name -> id)."""
        self._id_to_sprite[tile_id] = sprite_key
        if logical_name:
            self._name_to_id[logical_name.lower()] = tile_id

    def register_autotile_variant(self, base_sprite_key: str, variant_code: str, sprite_key: str) -> None:
        """
        Enregistre une variante d’autotile pour un sprite de base.
        variant_code: ex. "edge_n", "edge_e", "corner_ne", "slope_steep", etc.
        """
        self._autotile_variants.setdefault(base_sprite_key, {})[variant_code] = sprite_key

    # ----------------- Query de base -----------------

    def get_tile_id(self, logical_name: str) -> int:
        """Ex: 'grass' -> 2. Lève KeyError si inconnu."""
        ln = logical_name.lower()
        if ln not in self._name_to_id:
            raise KeyError(f"[Tiles] Nom logique inconnu: '{logical_name}'. Clés: {list(self._name_to_id.keys())}")
        return self._name_to_id[ln]

    def get_ground_sprite_name(self, tile_id: int) -> str:
        """Ex: 2 -> 'tile_grass'. Lève KeyError si inconnu."""
        if tile_id not in self._id_to_sprite:
            raise KeyError(f"[Tiles] ID inconnu: {tile_id}. IDs: {list(self._id_to_sprite.keys())}")
        return self._id_to_sprite[tile_id]

    # ----------------- Surfaces via Assets -----------------

    def get_ground_image(self, tile_id: int, assets) -> "pygame.Surface":
        """
        Récupère la Surface du sol via Assets (assets.get_image).
        """
        key = self.get_ground_sprite_name(tile_id)
        return assets.get_image(key)

    def get_autotile_image(self, base_sprite_key: str, variant_code: str, assets) -> Optional["pygame.Surface"]:
        """
        Si une variante d'autotile a été enregistrée, renvoie sa Surface; sinon None.
        """
        var = self._autotile_variants.get(base_sprite_key, {})
        sprite_key = var.get(variant_code)
        if sprite_key:
            return assets.get_image(sprite_key)
        return None

    # ----------------- Autotiling (optionnel, règles simples) -----------------

    @staticmethod
    def cliff_code(dn: int, de: int, ds: int, dw: int) -> str:
        """
        Transforme les deltas de hauteur (tile - voisin) en un code de variante.
        Idée: si >0 => on a une falaise/bord dans la direction du voisin.
        Retourne un code symbolique que tu peux mapper à des sprites si tu en as.
        """
        edges = []
        if dn > 0: edges.append("n")
        if de > 0: edges.append("e")
        if ds > 0: edges.append("s")
        if dw > 0: edges.append("w")
        if not edges:
            return "flat"          # plat / pas de bord apparent
        if len(edges) == 1:
            return f"edge_{edges[0]}"   # edge_n / edge_e / edge_s / edge_w
        # coins ou combinaisons : on normalise pour avoir des codes stables
        edges.sort()
        return "corner_" + "".join(edges)  # ex: corner_en / corner_ns / corner_sw / corner_ens (T)

    def pick_autotile_sprite_key(self, base_tile_id: int, dn: int, de: int, ds: int, dw: int) -> Optional[str]:
        """
        Retourne la sprite key de la variante si enregistrée, sinon None.
        """
        base_key = self.get_ground_sprite_name(base_tile_id)
        code = self.cliff_code(dn, de, ds, dw)
        var = self._autotile_variants.get(base_key, {})
        return var.get(code)

_tiles_singleton = Tiles()

def get_tile_id(logical_name: str) -> int:
    return _tiles_singleton.get_tile_id(logical_name)

def get_ground_sprite_name(tile_id: int) -> str:
    return _tiles_singleton.get_ground_sprite_name(tile_id)