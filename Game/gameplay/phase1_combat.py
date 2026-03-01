from __future__ import annotations

import math
import random

import pygame

from Game.ui.hud.notification import add_notification


def clear_entity_combat_refs(phase, ent):
    phase._ensure_move_runtime(ent)
    ent._combat_target = None
    ent._combat_attack_cd = 0.0
    ent._combat_repath_cd = 0.0
    ent._combat_anchor = None


def stop_entity_combat(phase, ent, stop_motion: bool = True):
    clear_entity_combat_refs(phase, ent)
    if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
        return
    if ent.ia.get("etat") == "combat":
        ent.ia["etat"] = "idle"
        ent.ia["objectif"] = None
        ent.ia["order_action"] = None
        ent.ia["target_craft_id"] = None
    if stop_motion:
        ent.move_path = []
        ent._move_from = (float(ent.x), float(ent.y))
        ent._move_to = None
        ent._move_t = 0.0


def start_entity_combat(phase, attacker, target) -> bool:
    if not attacker or not target:
        return False
    if attacker is target:
        return False
    if attacker not in phase.entities or target not in phase.entities:
        return False
    if getattr(attacker, "is_egg", False):
        return False
    if getattr(target, "is_egg", False):
        return False
    if not hasattr(attacker, "ia") or not isinstance(attacker.ia, dict):
        return False
    if getattr(target, "_dead_processed", False) or target.jauges.get("sante", 0) <= 0:
        return False

    attacker_is_fauna = bool(getattr(attacker, "is_fauna", False))
    attacker_is_aggressive = bool(getattr(attacker, "is_aggressive", False))
    target_is_fauna = bool(getattr(target, "is_fauna", False))

    if attacker_is_fauna and not attacker_is_aggressive:
        return False
    if attacker_is_aggressive:
        if target_is_fauna:
            return False
    else:
        if not target_is_fauna:
            return False

    phase._ensure_move_runtime(attacker)
    if hasattr(attacker, "comportement"):
        attacker.comportement.cancel_work("combat_start")
    attacker.ia["etat"] = "combat"
    attacker.ia["objectif"] = ("combat", (int(target.x), int(target.y)))
    attacker.ia["order_action"] = None
    attacker.ia["target_craft_id"] = None
    attacker._combat_target = target
    attacker._combat_attack_cd = 0.0
    attacker._combat_repath_cd = 0.0
    attacker._combat_anchor = (float(attacker.x), float(attacker.y))
    return True


def combat_attack_interval(attacker) -> float:
    speed = float(getattr(attacker, "physique", {}).get("vitesse", 3) or 3)
    agilite = float(getattr(attacker, "combat", {}).get("agilite", 0) or 0)
    base = max(0.35, 1.2 - speed * 0.05 - agilite * 0.01)
    combat = getattr(attacker, "combat", {}) or {}
    atk_speed = combat.get("attaque_speed", combat.get("attack_speed", None))
    try:
        atk_speed = float(atk_speed) if atk_speed is not None else None
    except Exception:
        atk_speed = None
    if atk_speed is not None and atk_speed > 0:
        return max(0.2, base / atk_speed)
    return base


def combat_attack_range(attacker) -> float:
    taille = float(getattr(attacker, "physique", {}).get("taille", 3) or 3)
    return max(0.85, 0.75 + taille * 0.06)


def combat_damage(attacker, target) -> float:
    physique = getattr(attacker, "physique", {}) or {}
    force = float(physique.get("force", 1) or 1)
    speed = float(physique.get("vitesse", 1) or 1)
    taille = float(physique.get("taille", 1) or 1)
    combat = getattr(attacker, "combat", {}) or {}
    melee = float(combat.get("attaque_melee", 0) or 0)
    attack_bonus = float(combat.get("attaque", combat.get("attack", 0)) or 0)
    defense = float(getattr(target, "combat", {}).get("defense", 0) or 0)

    raw = 1.0 + force * 1.4 + speed * 0.55 + taille * 0.2 + melee * 0.05 + attack_bonus
    reduced = raw - defense * 0.2
    dmg = max(1.0, reduced)
    return dmg * random.uniform(0.9, 1.1)


def grant_fauna_combat_rewards(phase, attacker, target):
    if not attacker or not target:
        return
    if getattr(target, "_combat_loot_granted", False):
        return
    target._combat_loot_granted = True
    if getattr(target, "is_fauna", False) and phase._is_player_species_entity(attacker):
        phase._run_stats["animals_killed"] = int(phase._run_stats.get("animals_killed", 0) or 0) + 1
        phase._stats_current_day["animals_killed"] = int(phase._stats_current_day.get("animals_killed", 0) or 0) + 1

    physique = getattr(target, "physique", {}) or {}
    taille = float(physique.get("taille", 2) or 2)
    endurance = float(physique.get("endurance", 3) or 3)
    xp_gain = max(8, int(round(endurance * 5 + taille * 2)))
    attacker.add_xp(xp_gain)

    meat_qty = max(1, int(round(taille * 0.7 + endurance * 0.35 + random.uniform(0.2, 1.2))))
    leather_qty = int(taille // 3)
    if random.random() < 0.55:
        leather_qty += 1

    drops = [("meat", meat_qty)]
    if leather_qty > 0:
        drops.append(("leather", leather_qty))

    gained: list[str] = []
    for item_id, qty in drops:
        taken = 0
        if hasattr(attacker, "comportement") and hasattr(attacker.comportement, "_add_to_inventory"):
            try:
                taken = int(attacker.comportement._add_to_inventory(item_id, int(qty)))
            except Exception:
                taken = 0
        if taken > 0:
            gained.append(f"{item_id} x{taken}")

    add_notification(f"{attacker.nom} a vaincu {target.nom} (+{xp_gain} XP espèce).")
    if gained:
        add_notification("Butin récupéré : " + ", ".join(gained))


def update_entity_combat(phase, ent, dt: float):
    if not hasattr(ent, "ia") or not isinstance(ent.ia, dict):
        return
    phase._ensure_move_runtime(ent)

    if ent.ia.get("etat") != "combat":
        if ent._combat_target is not None:
            clear_entity_combat_refs(phase, ent)
        return

    if getattr(ent, "is_fauna", False) and not getattr(ent, "is_aggressive", False):
        stop_entity_combat(phase, ent)
        return

    target = ent._combat_target
    if target is None or target is ent or target not in phase.entities:
        stop_entity_combat(phase, ent)
        return
    if getattr(ent, "is_aggressive", False):
        if getattr(target, "is_fauna", False) or getattr(target, "is_egg", False):
            stop_entity_combat(phase, ent)
            return
    else:
        if not getattr(target, "is_fauna", False):
            stop_entity_combat(phase, ent)
            return
    if getattr(target, "_dead_processed", False) or target.jauges.get("sante", 0) <= 0:
        stop_entity_combat(phase, ent)
        return

    chase_limit = float(getattr(ent, "chase_distance", 0.0) or 0.0)
    if chase_limit > 0.0 and getattr(ent, "is_aggressive", False):
        anchor = getattr(ent, "_combat_anchor", None)
        if anchor is None:
            ent._combat_anchor = (float(ent.x), float(ent.y))
            anchor = ent._combat_anchor
        ax, ay = float(anchor[0]), float(anchor[1])
        dx_e = float(ent.x) - ax
        dy_e = float(ent.y) - ay
        dx_t = float(target.x) - ax
        dy_t = float(target.y) - ay
        limit2 = chase_limit * chase_limit
        if (dx_e * dx_e + dy_e * dy_e) > limit2 or (dx_t * dx_t + dy_t * dy_t) > limit2:
            stop_entity_combat(phase, ent)
            return

    dist = math.hypot(float(target.x) - float(ent.x), float(target.y) - float(ent.y))
    attack_range = combat_attack_range(ent)

    ent._combat_attack_cd = max(0.0, float(ent._combat_attack_cd) - dt)

    if dist <= attack_range:
        ent.move_path = []
        ent._move_from = (float(ent.x), float(ent.y))
        ent._move_to = None
        ent._move_t = 0.0

        if ent._combat_attack_cd > 0.0:
            return

        damage = combat_damage(ent, target)
        target.jauges["sante"] = max(0.0, float(target.jauges.get("sante", 0)) - damage)
        target._last_attacker = ent
        ent._combat_attack_cd = combat_attack_interval(ent)
        if hasattr(ent, "attack_anim_ms"):
            ent._attack_anim_until_ms = pygame.time.get_ticks() + int(ent.attack_anim_ms)

        if target.jauges.get("sante", 0) <= 0:
            if not getattr(ent, "is_fauna", False) and getattr(target, "is_fauna", False):
                grant_fauna_combat_rewards(phase, ent, target)
            stop_entity_combat(phase, ent)
        return

    ent._combat_repath_cd = max(0.0, float(ent._combat_repath_cd) - dt)
    if ent._combat_repath_cd > 0.0:
        return

    chase_tile = phase._find_nearest_walkable(
        (int(target.x), int(target.y)),
        max_radius=2,
        forbidden=phase._occupied_tiles(exclude=[ent, target]),
        ent=ent,
    )
    if chase_tile is None:
        chase_tile = (int(target.x), int(target.y))

    phase._apply_entity_order(
        ent,
        target=chase_tile,
        etat="combat",
        objectif=("combat", (int(target.x), int(target.y))),
        action_mode=None,
        craft_id=None,
    )
    ent._combat_repath_cd = 0.25


def draw_fauna_health_bar(phase, screen, ent):
    if not getattr(ent, "is_fauna", False):
        return
    if ent.jauges.get("sante", 0) <= 0:
        return
    poly = phase.view.tile_surface_poly(int(ent.x), int(ent.y))
    if not poly:
        return

    max_hp = float(getattr(ent, "max_sante", 100) or 100)
    hp = float(ent.jauges.get("sante", 0) or 0)
    ratio = max(0.0, min(1.0, hp / max(1.0, max_hp)))

    cx = sum(p[0] for p in poly) / len(poly)
    top = min(p[1] for p in poly) - 18
    bar_w, bar_h = 46, 7
    bg = pygame.Rect(int(cx - bar_w / 2), int(top - bar_h), bar_w, bar_h)
    fg = bg.inflate(-2, -2)
    fg.width = int(max(1, fg.width) * ratio)

    surface = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 175))
    screen.blit(surface, (bg.x, bg.y))

    if fg.width > 0:
        color = (220, 60, 60) if ratio < 0.35 else (235, 170, 60) if ratio < 0.7 else (90, 205, 105)
        pygame.draw.rect(screen, color, fg, border_radius=2)


def draw_species_health_bar(phase, screen, ent):
    if getattr(ent, "is_fauna", False) or getattr(ent, "is_egg", False):
        return
    if getattr(ent, "espece", None) != phase.espece:
        return
    max_hp = float(getattr(ent, "max_sante", 100) or 100)
    hp = float(ent.jauges.get("sante", 0) or 0)
    if hp <= 0 or hp >= max_hp:
        return
    poly = phase.view.tile_surface_poly(int(ent.x), int(ent.y))
    if not poly:
        return

    ratio = max(0.0, min(1.0, hp / max(1.0, max_hp)))
    cx = sum(p[0] for p in poly) / len(poly)
    top = min(p[1] for p in poly) - 22
    bar_w, bar_h = 48, 6
    bg = pygame.Rect(int(cx - bar_w / 2), int(top - bar_h), bar_w, bar_h)
    fg = bg.inflate(-2, -2)
    fg.width = int(max(1, fg.width) * ratio)

    surface = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 165))
    screen.blit(surface, (bg.x, bg.y))

    if fg.width > 0:
        color = (220, 80, 80) if ratio < 0.35 else (235, 170, 60) if ratio < 0.7 else (90, 205, 105)
        pygame.draw.rect(screen, color, fg, border_radius=2)
