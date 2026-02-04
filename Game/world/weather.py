# Game/world/weather_system.py
"""
Système de température et d'intempéries dynamiques.
Les probabilités et effets varient selon le biome et le cycle jour/nuit.
"""

import random
import math
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class WeatherCondition:
    """Représente une condition météo avec ses effets"""
    id: str
    name: str
    duration_min: float  # en minutes de jeu
    duration_max: float
    temperature_modifier: float  
    visibility_modifier: float  
    movement_modifier: float 
    morale_per_minute: float  
    sprites: str


# Définitions des conditions météo
WEATHER_CONDITIONS = {
    "clear": WeatherCondition(
        id="clear",
        name="Ciel dégagé",
        duration_min=30.0,
        duration_max=120.0,
        temperature_modifier=0.0,
        visibility_modifier=1.0,
        movement_modifier=1.0,
        morale_per_minute=0.1,
        sprites="placeholder"
    ),
    "cloudy": WeatherCondition(
        id="cloudy",
        name="Nuageux",
        duration_min=20.0,
        duration_max=80.0,
        temperature_modifier=-2.0,
        visibility_modifier=0.95,
        movement_modifier=1.0,
        morale_per_minute=0.0,
        sprites="placeholder"
    ),
    "rain": WeatherCondition(
        id="rain",
        name="Pluie",
        duration_min=10.0,
        duration_max=45.0,
        temperature_modifier=-5.0,
        visibility_modifier=0.75,
        movement_modifier=0.85,
        morale_per_minute=-0.15,
        sprites="rain"
    ),
    "heavy_rain": WeatherCondition(
        id="heavy_rain",
        name="Pluie battante",
        duration_min=5.0,
        duration_max=25.0,
        temperature_modifier=-8.0,
        visibility_modifier=0.55,
        movement_modifier=0.65,
        morale_per_minute=-0.35,
        sprites="placeholder"
    ),
    "storm": WeatherCondition(
        id="storm",
        name="Orage",
        duration_min=5.0,
        duration_max=20.0,
        temperature_modifier=-10.0,
        visibility_modifier=0.50,
        movement_modifier=0.60,
        morale_per_minute=-0.50,
        sprites="placeholder"
    ),
    "snow": WeatherCondition(
        id="snow",
        name="Neige",
        duration_min=15.0,
        duration_max=60.0,
        temperature_modifier=-15.0,
        visibility_modifier=0.70,
        movement_modifier=0.70,
        morale_per_minute=-0.25,
        sprites="placeholder"
    ),
    "blizzard": WeatherCondition(
        id="blizzard",
        name="Blizzard",
        duration_min=5.0,
        duration_max=30.0,
        temperature_modifier=-25.0,
        visibility_modifier=0.40,
        movement_modifier=0.50,
        morale_per_minute=-0.60,
        sprites="placeholder"
    ),
    "fog": WeatherCondition(
        id="fog",
        name="Brouillard",
        duration_min=20.0,
        duration_max=90.0,
        temperature_modifier=-3.0,
        visibility_modifier=0.50,
        movement_modifier=0.90,
        morale_per_minute=-0.10,
        sprites="placeholder"
    ),
    "sandstorm": WeatherCondition(
        id="sandstorm",
        name="Tempête de sable",
        duration_min=10.0,
        duration_max=40.0,
        temperature_modifier=5.0,
        visibility_modifier=0.35,
        movement_modifier=0.55,
        morale_per_minute=-0.45,
        sprites="placeholder"
    ),
    "heatwave": WeatherCondition(
        id="heatwave",
        name="Canicule",
        duration_min=60.0,
        duration_max=240.0,
        temperature_modifier=15.0,
        visibility_modifier=0.90,
        movement_modifier=0.75,
        morale_per_minute=-0.20,
        sprites="placeholder"
    ),
}


# Probabilités par biome 
BIOME_WEATHER_PROBABILITIES = {
    # Biomes aquatiques
    "ocean": {
        "clear": 0.35,
        "cloudy": 0.25,
        "rain": 0.20,
        "heavy_rain": 0.10,
        "storm": 0.08,
        "fog": 0.02,
    },
    "coast": {
        "clear": 0.40,
        "cloudy": 0.25,
        "rain": 0.15,
        "heavy_rain": 0.08,
        "storm": 0.05,
        "fog": 0.07,
    },
    "lake": {
        "clear": 0.45,
        "cloudy": 0.25,
        "rain": 0.15,
        "heavy_rain": 0.08,
        "fog": 0.07,
    },
    "river": {
        "clear": 0.45,
        "cloudy": 0.25,
        "rain": 0.15,
        "heavy_rain": 0.05,
        "fog": 0.10,
    },
    
    # Biomes tempérés
    "plains": {
        "clear": 0.50,
        "cloudy": 0.25,
        "rain": 0.15,
        "heavy_rain": 0.05,
        "storm": 0.03,
        "fog": 0.02,
    },
    "forest": {
        "clear": 0.40,
        "cloudy": 0.30,
        "rain": 0.20,
        "heavy_rain": 0.07,
        "fog": 0.03,
    },
    "rainforest": {
        "clear": 0.25,
        "cloudy": 0.20,
        "rain": 0.35,
        "heavy_rain": 0.15,
        "storm": 0.05,
    },
    "savanna": {
        "clear": 0.60,
        "cloudy": 0.20,
        "rain": 0.10,
        "heavy_rain": 0.05,
        "storm": 0.05,
    },
    
    # Biomes arides
    "desert": {
        "clear": 0.75,
        "cloudy": 0.10,
        "sandstorm": 0.10,
        "heatwave": 0.05,
    },
    
    # Biomes froids
    "taiga": {
        "clear": 0.40,
        "cloudy": 0.25,
        "fog": 0.05,
        "snow": 0.25,
        "blizzard": 0.05,
    },
    "tundra": {
        "clear": 0.35,
        "cloudy": 0.25,
        "snow": 0.30,
        "blizzard": 0.10,
    },
    "snow": {
        "clear": 0.30,
        "cloudy": 0.20,
        "snow": 0.35,
        "blizzard": 0.15,
    },
    
    # Biomes spéciaux
    "swamp": {
        "cloudy": 0.35,
        "fog": 0.35,
        "rain": 0.20,
        "clear": 0.10,
    },
    "mangrove": {
        "cloudy": 0.30,
        "rain": 0.30,
        "heavy_rain": 0.15,
        "fog": 0.15,
        "clear": 0.10,
    },
    "rocky": {
        "clear": 0.50,
        "cloudy": 0.25,
        "rain": 0.10,
        "heavy_rain": 0.08,
        "storm": 0.07,
    },
    "alpine": {
        "clear": 0.35,
        "cloudy": 0.25,
        "snow": 0.25,
        "blizzard": 0.10,
        "fog": 0.05,
    },
    "volcanic": {
        "clear": 0.40,
        "cloudy": 0.30,
        "storm": 0.15,
        "rain": 0.10,
        "fog": 0.05,
    },
    "mystic": {
        "fog": 0.40,
        "cloudy": 0.30,
        "clear": 0.20,
        "storm": 0.10,
    },
}


class TemperatureSystem:
    """
    Gère la température ambiante basée sur :
    - Le biome
    - L'heure (jour/nuit)
    - La saison (via le cycle annuel)
    - Les conditions météo actuelles
    """
    
    # Températures de base par biome 
    BASE_TEMPERATURES = {
        "ocean": 15.0,
        "coast": 18.0,
        "lake": 16.0,
        "river": 17.0,
        "plains": 20.0,
        "forest": 18.0,
        "rainforest": 28.0,
        "savanna": 30.0,
        "desert": 35.0,
        "taiga": 5.0,
        "tundra": -5.0,
        "snow": -15.0,
        "swamp": 22.0,
        "mangrove": 26.0,
        "rocky": 18.0,
        "alpine": -2.0,
        "volcanic": 25.0,
        "mystic": 15.0,
    }
    
    def __init__(self):
        self.day_night_amplitude = 8.0  # variation jour/nuit en °C
        self.seasonal_amplitude = 15.0  # variation saisonnière en °C
    
    def get_temperature(
        self,
        biome: str,
        time_of_day: float,  
        day_of_year: int,    
        weather_modifier: float = 0.0
    ) -> float:
        """
        Calcule la température actuelle.
        
        Args:
            biome: Nom du biome
            time_of_day: Position dans la journée (0.0 à 1.0)
            day_of_year: Jour de l'année pour la saison
            weather_modifier: Modificateur de la météo
            
        Returns:
            Température 
        """
        base = self.BASE_TEMPERATURES.get(biome, 20.0)
        
        # Variation jour/nuit 
        day_night_factor = math.sin((time_of_day - 0.25) * 2 * math.pi)
        day_night_delta = day_night_factor * self.day_night_amplitude
        
        # Variation saisonnière (pic jour 172 ~= mi-été, creux jour 355 ~= mi-hiver)
        seasonal_factor = math.sin((day_of_year / 365.0 - 0.22) * 2 * math.pi)
        seasonal_delta = seasonal_factor * self.seasonal_amplitude
        
        # Réduction de l'amplitude saisonnière pour les biomes tropicaux
        if biome in ("rainforest", "desert", "savanna"):
            seasonal_delta *= 0.3
        
        temperature = base + day_night_delta + seasonal_delta + weather_modifier
        
        return round(temperature, 1)


class WeatherSystem:
    """
    Système principal de météo dynamique.
    Gère les transitions de conditions météo et leurs effets.
    """
    
    def __init__(self, world, day_night_cycle, seed: int = 0):
        self.world = world
        self.day_night = day_night_cycle
        self.temperature_system = TemperatureSystem()
        
        # État actuel
        self.current_condition: Optional[WeatherCondition] = WEATHER_CONDITIONS["clear"]
        self.condition_timer: float = 0.0  # temps restant en minutes
        self.next_change_in: float = 5.0  # prochaine évaluation en minutes
        
        # RNG déterministe
        self.rng = random.Random(seed)
        
        # Cache biome du joueur (pour optimisation)
        self._cached_biome: Optional[str] = None
        self._cache_position: Optional[Tuple[int, int]] = None
    
    def _get_player_biome(self, player_x: int, player_y: int) -> str:
        """Récupère le biome à la position du joueur avec cache"""
        pos = (int(player_x), int(player_y))
        
        if self._cache_position == pos and self._cached_biome:
            return self._cached_biome
        
        try:
            biome = self.world.get_biome_name(player_x, player_y)
            self._cached_biome = biome
            self._cache_position = pos
            return biome
        except Exception:
            return "plains"  # fallback
    
    def _select_weather_for_biome(self, biome: str) -> str:
        """Sélectionne une nouvelle condition météo basée sur le biome"""
        probs = BIOME_WEATHER_PROBABILITIES.get(biome)
        
        if not probs:
            # Biome inconnu, utilise plains par défaut
            probs = BIOME_WEATHER_PROBABILITIES["plains"]
        
        # Sélection pondérée
        conditions = list(probs.keys())
        weights = list(probs.values())
        
        chosen = self.rng.choices(conditions, weights=weights, k=1)[0]
        return chosen
    
    def update(self, dt: float, player_x: int, player_y: int):
        """
        Met à jour le système météo.
        
        Args:
            dt: Delta temps en secondes
            player_x, player_y: Position du joueur pour déterminer le biome
        """
        # Conversion dt (secondes) -> minutes de jeu
        dt_minutes = dt / 60.0
        
        self.condition_timer -= dt_minutes
        
        if self.condition_timer <= 0.0:
            # Changement de météo
            biome = self._get_player_biome(player_x, player_y)
            new_condition_id = self._select_weather_for_biome(biome)
            self.current_condition = WEATHER_CONDITIONS[new_condition_id]
            
            # Durée aléatoire dans l'intervalle défini
            duration = self.rng.uniform(
                self.current_condition.duration_min,
                self.current_condition.duration_max
            )
            self.condition_timer = duration
    
    def get_current_temperature(self, player_x: int, player_y: int) -> float:
        """Calcule la température actuelle à la position du joueur"""
        biome = self._get_player_biome(player_x, player_y)
        
        # Récupère l'heure actuelle (0.0 à 1.0)
        time_ratio = self.day_night.get_time_ratio()
        
        # Calcule le jour de l'année (0 à 364)
        day_of_year = int((self.day_night.jour % 365))
        
        # Modificateur météo
        weather_mod = self.current_condition.temperature_modifier if self.current_condition else 0.0
        
        return self.temperature_system.get_temperature(
            biome=biome,
            time_of_day=time_ratio,
            day_of_year=day_of_year,
            weather_modifier=weather_mod
        )
    
    def get_visibility_multiplier(self) -> float:
        """Retourne le multiplicateur de visibilité actuel"""
        if self.current_condition:
            return self.current_condition.visibility_modifier
        return 1.0
    
    def get_movement_multiplier(self) -> float:
        """Retourne le multiplicateur de vitesse de déplacement"""
        if self.current_condition:
            return self.current_condition.movement_modifier
        return 1.0
    
    def get_morale_impact(self, dt: float) -> float:
        """
        Calcule l'impact sur le moral pour ce frame.
        
        Args:
            dt: Delta temps en secondes
            
        Returns:
            Changement de moral à appliquer
        """
        if not self.current_condition:
            return 0.0
        
        dt_minutes = dt / 60.0
        return self.current_condition.morale_per_minute * dt_minutes
    
    def get_weather_info(self) -> Dict:
        """Retourne les informations météo actuelles pour l'UI"""
        if not self.current_condition:
            return {
                "name": "Inconnu",
                "icon": "❓",
                "time_remaining": 0.0
            }
        
        return {
            "id": self.current_condition.id,
            "name": self.current_condition.name,
            "icon": self.current_condition.sprites,
            "time_remaining": self.condition_timer,
            "temperature_mod": self.current_condition.temperature_modifier,
            "visibility": self.current_condition.visibility_modifier,
            "movement": self.current_condition.movement_modifier,
        }
    
    def force_weather(self, condition_id: str, duration_minutes: float = 30.0):
        """Force une condition météo spécifique (pour events/debug)"""
        if condition_id in WEATHER_CONDITIONS:
            self.current_condition = WEATHER_CONDITIONS[condition_id]
            self.condition_timer = duration_minutes
    
    # ---- Sauvegarde / Chargement ----
    
    def to_dict(self) -> Dict:
        """Sérialise l'état du système météo"""
        return {
            "current_condition_id": self.current_condition.id if self.current_condition else None,
            "condition_timer": self.condition_timer,
            "rng_state": self.rng.getstate(),
        }
    
    def from_dict(self, data: Dict):
        """Restaure l'état du système météo"""
        cid = data.get("current_condition_id")
        if cid and cid in WEATHER_CONDITIONS:
            self.current_condition = WEATHER_CONDITIONS[cid]
        
        self.condition_timer = float(data.get("condition_timer", 60.0))
        
        rng_state = data.get("rng_state")
        if rng_state:
            try:
                self.rng.setstate(rng_state)
            except Exception:
                pass
