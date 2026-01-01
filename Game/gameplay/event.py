
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from Game.core.utils import resource_path
from Game.ui.hud.notification import add_notification


# ---------- Data classes ----------
@dataclass
class ChoiceDefinition:
    id: str
    label: str
    description: str = ""
    requirements: Optional[dict] = None
    chance: Optional[float] = None
    effects_immediate: List[dict] = field(default_factory=list)
    effects_delayed: List[dict] = field(default_factory=list)
    on_success: List[dict] = field(default_factory=list)
    on_fail: List[dict] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ChoiceDefinition":
        return ChoiceDefinition(
            id=data.get("id") or data.get("label", "choice"),
            label=data.get("label", "Choix"),
            description=data.get("description", ""),
            requirements=data.get("requirements"),
            chance=data.get("chance"),
            effects_immediate=list(data.get("effects_immediate") or []),
            effects_delayed=list(data.get("effects_delayed") or []),
            on_success=list(data.get("on_success") or []),
            on_fail=list(data.get("on_fail") or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventDefinition:
    id: str
    title: str
    short_text: str
    long_text: str
    unique: bool = True
    cooldown: float = 0.0
    already_met: bool = False
    condition: Optional[dict] = None
    choices: List[ChoiceDefinition] = field(default_factory=list)
    effects_immediate: List[dict] = field(default_factory=list)
    effects_delayed: List[dict] = field(default_factory=list)
    python_condition: Optional[Callable[[Any], bool]] = None
    python_effects: Optional[Callable[[Any], None]] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EventDefinition":
        return EventDefinition(
            id=data["id"],
            title=data.get("title", data["id"]),
            short_text=data.get("short_text", ""),
            long_text=data.get("long_text", ""),
            unique=bool(data.get("unique", True)),
            cooldown=float(data.get("cooldown", 0.0) or 0.0),
            already_met=bool(data.get("already_met", False)),
            condition=data.get("condition"),
            choices=[ChoiceDefinition.from_dict(c) for c in data.get("choices", [])],
            effects_immediate=list(data.get("effects_immediate") or []),
            effects_delayed=list(data.get("effects_delayed") or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "short_text": self.short_text,
            "long_text": self.long_text,
            "unique": self.unique,
            "cooldown": self.cooldown,
            "already_met": self.already_met,
            "condition": self.condition,
            "effects_immediate": self.effects_immediate,
            "effects_delayed": self.effects_delayed,
            "choices": [c.to_dict() for c in self.choices],
        }


@dataclass
class EventInstance:
    definition_id: str
    state: str = "new"  # new | active | resolved | archived
    is_new: bool = True
    selected_choice: Optional[str] = None
    last_trigger_time: float = 0.0  # minutes de jeu (accumulées)
    delayed_effects: List[Dict[str, Any]] = field(default_factory=list)
    delay_timers: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "state": self.state,
            "is_new": self.is_new,
            "selected_choice": self.selected_choice,
            "last_trigger_time": self.last_trigger_time,
            "delayed_effects": self.delayed_effects,
            "delay_timers": self.delay_timers,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EventInstance":
        inst = EventInstance(definition_id=data["definition_id"])
        inst.state = data.get("state", "new")
        inst.is_new = data.get("is_new", False)
        inst.selected_choice = data.get("selected_choice")
        inst.last_trigger_time = data.get("last_trigger_time", 0.0)
        inst.delayed_effects = data.get("delayed_effects", [])
        inst.delay_timers = data.get("delay_timers", [])
        return inst


# ---------- Event Manager ----------
class EventManager:
    def __init__(self, data_path: str = "Game/data/events.json"):
        self.data_path = data_path
        self.definitions: Dict[str, EventDefinition] = {}
        self.instances: Dict[str, EventInstance] = {}
        self.last_time_hits: Dict[str, tuple] = {}  # event_id -> (day, hour, minute)
        self.runtime_flags: Dict[str, Any] = {}
        self.python_events: Dict[str, EventDefinition] = {}
        self._load_definitions()
        self._register_builtin_events()

    # ---------- Loading ----------
    def _load_definitions(self):
        try:
            with open(resource_path(self.data_path), "r", encoding="utf-8") as f:
                doc = json.load(f)
            for ev in doc.get("events", []):
                ed = EventDefinition.from_dict(ev)
                self.definitions[ed.id] = ed
        except FileNotFoundError:
            print(f"[Events] Aucun fichier {self.data_path}, aucun évènement data-driven chargé.")
        except Exception as e:
            print(f"[Events] Erreur de chargement des événements: {e}")

    def _register_builtin_events(self):
        protect_egg = EventDefinition(
            id="protect_first_egg",
            title="Protéger l'œuf",
            short_text="Un œuf est apparu ! Protégez-le jusqu'à l'éclosion.",
            long_text="Votre espèce vient de pondre son premier œuf. Assurez-vous qu'il ne soit pas détruit avant l'éclosion.",
            unique=True,
            already_met=False,
            cooldown=0.0,
        )
        self.register_python_event(protect_egg)

    def register_python_event(self, definition: EventDefinition):
        """Permet d'ajouter un évènement défini en Python (condition/effets complexes)."""
        self.python_events[definition.id] = definition
        self.definitions[definition.id] = definition

    # ---------- Persistence ----------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instances": {eid: inst.to_dict() for eid, inst in self.instances.items()},
            "last_time_hits": self.last_time_hits,
            "runtime_flags": self.runtime_flags,
        }

    def load_state(self, data: Dict[str, Any]):
        if not data:
            return
        self.instances = {
            k: EventInstance.from_dict(v) for k, v in (data.get("instances") or {}).items()
        }
        self.last_time_hits = data.get("last_time_hits", {})
        self.runtime_flags = data.get("runtime_flags", {})

    # ---------- Helpers ----------
    def _get_game_time(self, phase) -> tuple[int, int, float]:
        """
        Retourne (jour, heure, minute_float) depuis le cycle jour/nuit.
        minute_float peut contenir la fraction.
        """
        dn = getattr(phase, "day_night", None)
        if dn is None:
            return 0, 0, 0.0
        ratio = dn.get_time_ratio()
        hours_float = ratio * 24.0
        hours = int(hours_float)
        minutes_float = (hours_float - hours) * 60.0
        minutes = int(minutes_float)
        return getattr(dn, "jour", 0), hours, minutes + (minutes_float - minutes)

    def _game_minutes_absolute(self, phase) -> float:
        jour, hour, minute = self._get_game_time(phase)
        return jour * 24 * 60 + hour * 60 + minute

    def _evaluate_condition(self, cond: Any, phase, event_id: Optional[str] = None) -> bool:
        """Évalue récursivement une condition data-driven ou un callable Python."""
        if cond is None:
            return True
        if isinstance(cond, bool):
            return cond
        if callable(cond):
            try:
                return bool(cond(phase))
            except Exception as e:
                print(f"[Events] Condition callable échouée pour {event_id}: {e}")
                return False
        if isinstance(cond, list):
            return all(self._evaluate_condition(c, phase, event_id) for c in cond)
        if not isinstance(cond, dict):
            return False

        if "and" in cond:
            return all(self._evaluate_condition(c, phase, event_id) for c in cond["and"])
        if "or" in cond:
            return any(self._evaluate_condition(c, phase, event_id) for c in cond["or"])

        ctype = cond.get("type")
        if ctype == "time":
            target_h = cond.get("hour", 0)
            target_m = cond.get("minute", 0)
            once_per_day = cond.get("once_per_day", True)
            jour, hour, minute = self._get_game_time(phase)
            if hour != target_h or int(minute) != int(target_m):
                return False
            if once_per_day and event_id:
                last = self.last_time_hits.get(event_id)
                if last and last == (jour, target_h, target_m):
                    return False
            return True
        if ctype == "random":
            chance = float(cond.get("chance", 0.0))
            return random.random() < chance
        if ctype == "flag_equals":
            key = cond.get("key")
            value = cond.get("value")
            return self.runtime_flags.get(key) == value
        if ctype == "player_has_xp":
            min_xp = float(cond.get("min", 0.0))
            espece = getattr(phase, "espece", None)
            return bool(espece and getattr(espece, "xp", 0) >= min_xp)
        if ctype == "phase_attr_true":
            attr = cond.get("attr")
            return bool(attr and getattr(phase, attr, False))

        return False

    def _apply_effects(self, effects: List[dict], phase):
        for eff in effects or []:
            if not isinstance(eff, dict):
                continue
            etype = eff.get("type")
            if etype == "notification":
                msg = eff.get("message") or eff.get("text") or ""
                if msg:
                    add_notification(msg)
            elif etype == "add_xp":
                amount = float(eff.get("amount", 0))
                if amount and getattr(phase, "espece", None):
                    try:
                        phase.espece.add_xp(amount)
                    except Exception as e:
                        print(f"[Events] add_xp échec: {e}")
            elif etype == "set_flag":
                key = eff.get("key")
                if key:
                    self.runtime_flags[key] = eff.get("value", True)
            elif etype == "callback" and callable(eff.get("fn")):
                try:
                    eff["fn"](phase)
                except Exception as e:
                    print(f"[Events] Effet callback échoué: {e}")
            elif etype == "modify_happiness":
                amount = eff.get("amount", 0)
                if amount and hasattr(phase, "change_happiness"):
                    reason = eff.get("reason")
                    phase.change_happiness(amount, reason)
            elif etype == "add_mutation":
                mut_id = eff.get("id")
                espece = getattr(phase, "espece", None)
                if mut_id and espece and getattr(espece, "mutations", None):
                    try:
                        espece.mutations.appliquer(mut_id)
                    except Exception as e:
                        print(f"[Events] Impossible d'ajouter la mutation {mut_id}: {e}")
            elif etype == "add_resource":
                res_id = eff.get("id")
                qty = int(eff.get("amount", 0))
                if res_id and qty and getattr(phase, "warehouse", None) is not None:
                    phase.warehouse[res_id] = phase.warehouse.get(res_id, 0) + qty
            elif etype == "unlock_craft":
                craft_id = eff.get("craft_id")
                if craft_id and hasattr(phase, "unlock_craft"):
                    phase.unlock_craft(craft_id)
            elif etype == "set_death_policy":
                mode = eff.get("mode")
                if hasattr(phase, "set_death_policy"):
                    phase.set_death_policy(mode)
            else:
                # Effet inconnu : pour extension future
                print(f"[Events] Effet inconnu ignoré: {eff}")

    # ---------- Lifecycle ----------
    def update(self, dt: float, phase):
        # 1) appliquer effets différés
        self._update_delayed(dt, phase)
        if getattr(phase, "ui_menu_open", False):
            return

        # 2) tenter de déclencher de nouveaux events
        for ev_id, definition in self.definitions.items():
            inst = self.instances.get(ev_id)
            if inst and inst.state in {"active", "resolved", "archived"}:
                # cooldown pour non-uniques
                if definition.unique:
                    continue
                cooldown = float(definition.cooldown or 0.0)
                if cooldown > 0 and inst.last_trigger_time:
                    if self._game_minutes_absolute(phase) - inst.last_trigger_time < cooldown:
                        continue
            if definition.unique and (definition.already_met or (inst and inst.state != "new")):
                continue

            if definition.python_condition and not self._evaluate_condition(definition.python_condition, phase, ev_id):
                continue
            if not self._evaluate_condition(definition.condition, phase, ev_id):
                continue

            self._trigger_event(definition, phase)

    def _trigger_event(self, definition: EventDefinition, phase):
        inst = self.instances.get(definition.id) or EventInstance(definition_id=definition.id)
        inst.state = "active"
        inst.is_new = True
        inst.last_trigger_time = self._game_minutes_absolute(phase)
        inst.delayed_effects = []
        inst.delay_timers = []

        self.instances[definition.id] = inst
        jour, h, m = self._get_game_time(phase)
        self.last_time_hits[definition.id] = (jour, int(h), int(m))
        if definition.id == "La mort" and hasattr(phase, "death_event_ready"):
            phase.death_event_ready = False

        # Effets immédiats de la définition
        if definition.python_effects:
            try:
                definition.python_effects(phase)
            except Exception as e:
                print(f"[Events] Effets Python échoués pour {definition.id}: {e}")
        self._apply_effects(definition.effects_immediate, phase)

        # Effets différés de la définition
        for eff in definition.effects_delayed:
            delay = float(eff.get("delay", 0))
            inst.delayed_effects.append(eff)
            inst.delay_timers.append(delay)

        add_notification(definition.short_text or definition.title)

    def _update_delayed(self, dt: float, phase):
        for inst in self.instances.values():
            if not inst.delayed_effects:
                continue
            for idx in range(len(inst.delayed_effects) - 1, -1, -1):
                inst.delay_timers[idx] -= dt
                if inst.delay_timers[idx] <= 0:
                    eff = inst.delayed_effects.pop(idx)
                    inst.delay_timers.pop(idx)
                    self._apply_effects([eff], phase)

    # ---------- Choices ----------
    def resolve_event(self, event_id: str, choice_id: str, phase):
        definition = self.definitions.get(event_id)
        inst = self.instances.get(event_id)
        if not definition or not inst:
            return
        choice = next((c for c in definition.choices if c.id == choice_id), None)
        if not choice:
            return
        if inst.state not in {"active", "new"}:
            return

        # Vérifier requirements
        if choice.requirements and not self._evaluate_condition(choice.requirements, phase, event_id):
            return

        # Gestion chance
        roll_success = True
        if choice.chance is not None:
            roll_success = random.random() <= float(choice.chance)

        effects_to_apply = list(choice.effects_immediate)
        delayed_to_schedule = list(choice.effects_delayed)

        if roll_success:
            effects_to_apply += list(choice.on_success)
        else:
            effects_to_apply += list(choice.on_fail)

        self._apply_effects(effects_to_apply, phase)

        # Planifier effets différés
        for eff in delayed_to_schedule:
            delay = float(eff.get("delay", 0))
            inst.delayed_effects.append(eff)
            inst.delay_timers.append(delay)

        inst.selected_choice = choice.id
        inst.state = "resolved"
        inst.is_new = False
        if definition.unique:
            definition.already_met = True

    # ---------- Query helpers ----------
    def get_sorted_events(self) -> List[EventInstance]:
        unresolved = []
        resolved = []
        for ev_id, inst in self.instances.items():
            if inst.state in {"new", "active"}:
                unresolved.append(inst)
            else:
                resolved.append(inst)
        unresolved.sort(key=lambda i: i.last_trigger_time, reverse=True)
        resolved.sort(key=lambda i: i.last_trigger_time, reverse=True)
        return unresolved + resolved

    def get_definition(self, event_id: str) -> Optional[EventDefinition]:
        return self.definitions.get(event_id)
