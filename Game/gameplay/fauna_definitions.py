from __future__ import annotations

from typing import Optional

from Game.species.fauna import AggressiveFaunaDefinition, PassiveFaunaDefinition


def rabbit_definition() -> PassiveFaunaDefinition:
    return PassiveFaunaDefinition(
        species_name="Lapin",
        entity_name="Lapin",
        move_speed=2.1,
        hp=100,
        vision_range=10.0,
        flee_distance=6.0,
        sprite_sheet_idle="rabbit_idle",
        sprite_sheet_run="rabbit_run",
        sprite_sheet_frame_size=(32, 32),
        sprite_base_scale=0.75,
    )


def capybara_definition() -> PassiveFaunaDefinition:
    return PassiveFaunaDefinition(
        species_name="Capybara",
        entity_name="Capybara",
        move_speed=1.1,
        hp=100,
        vision_range=4.0,
        flee_distance=1.0,
        sprite_sheet_idle="capybara_idle",
        sprite_sheet_frame_size=(32, 32),
        sprite_base_scale=0.75,
    )


def scorpion_definition() -> AggressiveFaunaDefinition:
    return AggressiveFaunaDefinition(
        species_name="Scorpion",
        entity_name="Scorpion",
        move_speed=3.6,
        hp=70,
        vision_range=10.0,
        flee_distance=0.0,
        attack=3.0,
        attack_speed=1.7,
        sprite_sheet_idle="scorpion_idle",
        sprite_sheet_frame_size=(32, 32),
        sprite_base_scale=0.8,
    )


def champi_definition() -> AggressiveFaunaDefinition:
    return AggressiveFaunaDefinition(
        species_name="Scorpion",
        entity_name="Scorpion",
        move_speed=1.6,
        hp=200,
        vision_range=6.0,
        flee_distance=0.0,
        attack=10.0,
        attack_speed=0.6,
        sprite_sheet_idle="champi_idle",
        sprite_sheet_frame_size=(32, 32),
        sprite_base_scale=0.8,
    )


def flamme_definition() -> AggressiveFaunaDefinition:
    return AggressiveFaunaDefinition(
        species_name="Flamme",
        entity_name="Flamme",
        move_speed=2.4,
        hp=30,
        vision_range=6.0,
        flee_distance=0.0,
        attack=20.0,
        attack_speed=0.1,
        sprite_sheet_idle="flame_idle",
        sprite_sheet_frame_size=(32, 32),
        sprite_base_scale=0.8,
    )


def forest_boss_definition() -> AggressiveFaunaDefinition:
    return AggressiveFaunaDefinition(
        species_name="Slime Tower",
        entity_name="Slime Tower",
        move_speed=1.4,
        hp=300,
        vision_range=6.0,
        flee_distance=0.0,
        attack=15.0,
        attack_speed=1.2,
        sprite_sheet_idle="forest_boss_idle",
        sprite_sheet_frame_size=(48, 48),
        sprite_base_scale=1,
    )


def fauna_definition_catalog() -> dict[str, PassiveFaunaDefinition]:
    return {
        "lapin": rabbit_definition(),
        "capybara": capybara_definition(),
        "scorpion": scorpion_definition(),
        "champi": champi_definition(),
        "flamme": flamme_definition(),
        "forest_boss": forest_boss_definition(),
    }


def get_fauna_definition(species_id: str | None) -> Optional[PassiveFaunaDefinition]:
    if not species_id:
        return None
    key = str(species_id).strip().lower()
    return fauna_definition_catalog().get(key)
