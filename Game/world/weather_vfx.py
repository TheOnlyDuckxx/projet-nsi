from __future__ import annotations

import math
import random

import pygame


class WeatherVFXController:
    """Gère l'état et le rendu des effets visuels météo."""

    def __init__(self):
        self.particles: dict[str, list[dict]] = {
            "rain": [],
            "snow": [],
            "sand": [],
        }
        self.time = 0.0
        self.flash_timer = 0.0
        self.flash_alpha = 0
        self.last_condition_id: str | None = None

    def reset(self):
        self.particles["rain"].clear()
        self.particles["snow"].clear()
        self.particles["sand"].clear()
        self.time = 0.0
        self.flash_timer = 0.0
        self.flash_alpha = 0
        self.last_condition_id = None

    def _reset_if_weather_changed(self, condition_id: str | None):
        if condition_id == self.last_condition_id:
            return
        self.last_condition_id = condition_id
        self.particles["rain"].clear()
        self.particles["snow"].clear()
        self.particles["sand"].clear()
        self.flash_timer = 0.0
        self.flash_alpha = 0

    def update(self, dt: float, weather_system, screen_size: tuple[int, int]):
        if not weather_system:
            return

        weather_info = weather_system.get_weather_info()
        condition_id = weather_info.get("id")
        self._reset_if_weather_changed(condition_id)
        self.time += max(0.0, dt)

        w, h = screen_size
        area_scale = max(0.55, min(2.0, (w * h) / (1280 * 720)))

        rain_target = 0
        snow_target = 0
        sand_target = 0

        if condition_id == "rain":
            rain_target = int(150 * area_scale)
        elif condition_id == "heavy_rain":
            rain_target = int(250 * area_scale)
        elif condition_id == "storm":
            rain_target = int(320 * area_scale)
        elif condition_id == "snow":
            snow_target = int(120 * area_scale)
        elif condition_id == "blizzard":
            snow_target = int(230 * area_scale)
        elif condition_id == "sandstorm":
            sand_target = int(220 * area_scale)

        rain_particles = self.particles["rain"]
        while len(rain_particles) < rain_target:
            rain_particles.append(
                {
                    "x": random.uniform(-w * 0.2, w * 1.2),
                    "y": random.uniform(-h, 0),
                    "vx": random.uniform(-140.0, -40.0),
                    "vy": random.uniform(620.0, 980.0),
                    "length": random.uniform(8.0, 20.0),
                    "width": random.choice((1, 1, 1, 2)),
                }
            )
        del rain_particles[rain_target:]

        for p in rain_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["y"] > h + 24 or p["x"] < -w * 0.3:
                p["x"] = random.uniform(-w * 0.2, w * 1.2)
                p["y"] = random.uniform(-h * 0.35, -8.0)

        snow_particles = self.particles["snow"]
        while len(snow_particles) < snow_target:
            snow_particles.append(
                {
                    "x": random.uniform(0, w),
                    "y": random.uniform(-h, 0),
                    "vx": random.uniform(-30.0, 30.0),
                    "vy": random.uniform(30.0, 80.0),
                    "radius": random.uniform(1.5, 3.8),
                    "phase": random.uniform(0.0, math.tau),
                }
            )
        del snow_particles[snow_target:]

        for p in snow_particles:
            p["x"] += (p["vx"] + math.sin(self.time * 1.6 + p["phase"]) * 18.0) * dt
            p["y"] += p["vy"] * dt
            if p["y"] > h + 8:
                p["y"] = random.uniform(-h * 0.3, -6.0)
                p["x"] = random.uniform(0, w)
            elif p["x"] < -12:
                p["x"] = w + 12
            elif p["x"] > w + 12:
                p["x"] = -12

        sand_particles = self.particles["sand"]
        while len(sand_particles) < sand_target:
            sand_particles.append(
                {
                    "x": random.uniform(-w, 0),
                    "y": random.uniform(0, h),
                    "vx": random.uniform(260.0, 440.0),
                    "vy": random.uniform(-20.0, 20.0),
                    "length": random.uniform(10.0, 18.0),
                }
            )
        del sand_particles[sand_target:]

        for p in sand_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["x"] > w + 20:
                p["x"] = random.uniform(-w * 0.35, -8.0)
                p["y"] = random.uniform(0, h)
            elif p["y"] < -8 or p["y"] > h + 8:
                p["y"] = random.uniform(0, h)

        if condition_id == "storm":
            if self.flash_timer > 0.0:
                self.flash_timer -= dt
                self.flash_alpha = max(0, int(self.flash_alpha * 0.88))
            elif random.random() < min(0.35 * max(dt, 0.0), 0.2):
                self.flash_timer = random.uniform(0.05, 0.18)
                self.flash_alpha = random.randint(120, 185)
        else:
            self.flash_timer = 0.0
            self.flash_alpha = 0

    def draw(self, screen: pygame.Surface, weather_system):
        if not weather_system:
            return

        condition_id = weather_system.get_weather_info().get("id")
        if not condition_id:
            return

        w, h = screen.get_size()
        fx = pygame.Surface((w, h), pygame.SRCALPHA)

        if condition_id in ("rain", "heavy_rain", "storm"):
            rain_color = (160, 185, 220, 150 if condition_id == "rain" else 180)
            for p in self.particles["rain"]:
                x0 = int(p["x"])
                y0 = int(p["y"])
                x1 = int(p["x"] + (p["vx"] / max(p["vy"], 1.0)) * p["length"])
                y1 = int(p["y"] + p["length"])
                pygame.draw.line(fx, rain_color, (x0, y0), (x1, y1), int(p["width"]))
            if condition_id in ("heavy_rain", "storm"):
                fx.fill((16, 24, 36, 28), special_flags=pygame.BLEND_RGBA_ADD)

        if condition_id in ("snow", "blizzard"):
            for p in self.particles["snow"]:
                pygame.draw.circle(
                    fx,
                    (245, 248, 255, 190 if condition_id == "blizzard" else 160),
                    (int(p["x"]), int(p["y"])),
                    max(1, int(p["radius"])),
                )
            if condition_id == "blizzard":
                fx.fill((210, 220, 235, 40))

        if condition_id == "sandstorm":
            fx.fill((165, 120, 65, 58))
            for p in self.particles["sand"]:
                x0 = int(p["x"])
                y0 = int(p["y"])
                x1 = int(p["x"] + p["length"])
                y1 = int(p["y"] + p["length"] * 0.06)
                pygame.draw.line(fx, (225, 185, 120, 140), (x0, y0), (x1, y1), 2)

        if condition_id == "fog":
            fx.fill((208, 220, 228, 74))
            for i in range(4):
                y = int((i + 0.2) * (h / 4) + math.sin(self.time * 0.35 + i * 0.9) * 24)
                band_h = int(h * 0.22)
                pygame.draw.ellipse(
                    fx,
                    (228, 236, 242, 36),
                    (-int(w * 0.12), y, int(w * 1.25), band_h),
                )

        if condition_id == "heatwave":
            fx.fill((255, 188, 118, 22))
            for y in range(0, h, 7):
                shift = int(math.sin(self.time * 4.0 + y * 0.028) * 4)
                pygame.draw.line(fx, (255, 218, 165, 18), (0 + shift, y), (w + shift, y), 1)

        if condition_id == "cloudy":
            fx.fill((86, 96, 112, 18))

        if condition_id == "storm":
            fx.fill((10, 14, 24, 44))

        screen.blit(fx, (0, 0))

        if self.flash_alpha > 0:
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((236, 244, 255, self.flash_alpha))
            screen.blit(flash, (0, 0))
