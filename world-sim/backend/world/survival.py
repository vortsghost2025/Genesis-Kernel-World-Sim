"""Survival physics — the body. epistemic.4.

The board audit (scripts/audit_tile_resources.py, Oct 19 2026) shows a
world of abundance: 21,358 berry tiles, 4,278 mushroom, 2,596 root,
1,806 fish. Food scarcity is NOT the pressure — that is the exact rock
the retired pressure model died on (HB701-800: income == consumption
pinned east_adam at zero for 100+ heartbeats, and he correctly reported
it as a bug).

The scarce resources are time, warmth, and safety. So:

  hunger   rises every heartbeat, reset by eating. Raw food satisfies
           modestly; cooked food satisfies far more (fire matters).
  warmth   follows the day/night cycle and the seasons. Nights drain
           it; winter nights dangerously. Fire nearby restores it
           fast; shelter slows the drain.
  vitality fails when hunger or cold is neglected. At zero the agent
           COLLAPSES (down, cannot act, can be rescued by a partner
           who brings food to their tile). Collapse is recoverable —
           the stake is the story, not a permadeath.

Slack is the design invariant: from full hunger, ~70 heartbeats before
weakening. A gather trip (walk + 2-3 gathers) nets multiple meals. The
pressure creates PURPOSE — expeditions, stockpiles, camps — never
famine. The v1 trap (action impossible -> correct refusal misread as
apathy) is the thing this module is built to never do again.

All functions are pure: (state, environment) -> state. The runtime
applies them once per heartbeat; tests own the arithmetic.
"""
from __future__ import annotations

import math

# --- the clock -----------------------------------------------------------
DAY_LENGTH = 72            # heartbeats per day
SEASON_DAYS = 12           # days per season
SEASON_LENGTH = DAY_LENGTH * SEASON_DAYS

DAY_PHASE_START = 0.25     # sunrise fraction of the day cycle
DAY_PHASE_END = 0.75       # sunset fraction

SEASONS = ("spring", "summer", "autumn", "winter")
SEASON_BASE_TEMP = {       # 0 = bitter cold, 100 = scorching
    "spring": 55.0,
    "summer": 72.0,
    "autumn": 46.0,
    "winter": 26.0,
}
DAY_NIGHT_AMPLITUDE = 13.0  # degrees of swing between noon and midnight


def day_phase(heartbeat_number: int) -> float:
    """0.0-1.0 through one day cycle."""
    return (heartbeat_number % DAY_LENGTH) / DAY_LENGTH


def is_night(heartbeat_number: int) -> bool:
    phase = day_phase(heartbeat_number)
    return phase < DAY_PHASE_START or phase >= DAY_PHASE_END


def season(heartbeat_number: int) -> str:
    idx = (heartbeat_number // SEASON_LENGTH) % len(SEASONS)
    return SEASONS[idx]


def ambient_temperature(heartbeat_number: int) -> float:
    """Temperature at this heartbeat: seasonal base + day/night swing.

    Warmest at mid-day, coldest at mid-night — a sine on the day phase,
    so dusk cools gradually instead of snapping.
    """
    base = SEASON_BASE_TEMP[season(heartbeat_number)]
    phase = day_phase(heartbeat_number)
    swing = math.sin(2 * math.pi * (phase - DAY_PHASE_START)) * DAY_NIGHT_AMPLITUDE
    return base + swing


# --- hunger ----------------------------------------------------------------
HUNGER_RATE = 1.4          # rise per heartbeat (slack invariant: ~70 hb)
HUNGER_CAP = 100.0
HUNGER_WEAKEN = 88.0       # at/above this: weakening (vitality drains)
EAT_SATISFACTION = {       # raw food: hunger points satisfied
    "wild_berries": 18.0,
    "mushrooms": 14.0,
    "edible_roots": 22.0,
    "fish": 26.0,
    "shellfish": 20.0,
    "cooked_meal": 55.0,   # exists only through fire (phase 2 craft)
}
COOKED_MULTIPLIER = 2.5    # any raw food cooked satisfies this much more


def hunger_next(hunger: float, heartbeat_number: int) -> float:
    """Hunger rises unconditionally. Time is the pressure."""
    return min(HUNGER_CAP, max(0.0, hunger + HUNGER_RATE))


def eat_satisfaction(resource_kind: str, cooked: bool = False) -> float:
    base = EAT_SATISFACTION.get(resource_kind, 10.0)
    return base * (COOKED_MULTIPLIER if cooked else 1.0)


# --- warmth ------------------------------------------------------------------
WARMTH_APPROACH_RATE = 0.10   # fraction of the gap closed per heartbeat
FIRE_RADIUS = 3               # tiles: lit fire restores warmth here
FIRE_WARMTH_PER_HB = 9.0      # standing by a fire, warmth climbs fast
SHELTER_DECAY_FACTOR = 0.45   # inside shelter: cold drains < half as fast
FREEZE_THRESHOLD = 20.0       # at/below this warmth: vitality drains


def warmth_next(warmth: float, ambient_temp: float, by_fire: bool,
                in_shelter: bool) -> float:
    """Warmth drifts toward the ambient comfort level.

    A fire dominates: warmth climbs toward 100 fast regardless of season.
    Shelter does not heat — it slows the drain (you hold what you have).
    """
    comfort = max(0.0, min(100.0, ambient_temp))
    if by_fire:
        return min(100.0, warmth + FIRE_WARMTH_PER_HB)
    gap = comfort - warmth
    change = gap * WARMTH_APPROACH_RATE
    if change < 0 and in_shelter:
        change *= SHELTER_DECAY_FACTOR
    return max(0.0, min(100.0, warmth + change))


# --- vitality ------------------------------------------------------------------
VITALITY_CAP = 100.0
STARVING_DRAIN = 0.6        # per heartbeat at hunger >= HUNGER_WEAKEN
FREEZING_DRAIN = 0.8        # per heartbeat at warmth <= FREEZE_THRESHOLD
REGEN_RATE = 0.5            # fed and warm: slow recovery
COLLAPSE_THRESHOLD = 0.0    # vitality at/below: down
RECOVERY_STAND_AT = 12.0    # vitality needed to stand again after collapse
DOWNED_PASSIVE_REGEN = 0.15  # slow self-recovery while down (rescue is better)


def vitality_next(vitality: float, hunger: float, warmth: float,
                  downed: bool) -> float:
    """Vitality drains under neglect, regenerates under care."""
    if downed:
        return min(RECOVERY_STAND_AT, vitality + DOWNED_PASSIVE_REGEN)
    v = vitality
    if hunger >= HUNGER_WEAKEN:
        v -= STARVING_DRAIN
    if warmth <= FREEZE_THRESHOLD:
        v -= FREEZING_DRAIN
    if hunger <= 45.0 and warmth >= 50.0:
        v += REGEN_RATE
    return max(0.0, min(VITALITY_CAP, v))


# --- the vitals block -------------------------------------------------------
def initial_vitals() -> dict:
    """Healthy start. No retroactive famine for existing agents."""
    return {"hunger": 18.0, "warmth": 82.0, "vitality": 100.0,
            "downed": False}


def apply_heartbeat(vitals: dict, heartbeat_number: int, by_fire: bool,
                    in_shelter: bool, ate_satisfaction: float = 0.0) -> dict:
    """One heartbeat of embodiment. Returns a NEW vitals dict.

    `ate_satisfaction` is the hunger points satisfied by food eaten this
    heartbeat (0 = nothing eaten). Everything else follows the physics.
    """
    hunger = hunger_next(vitals.get("hunger", 0.0), heartbeat_number)
    hunger = max(0.0, hunger - ate_satisfaction)
    warmth = warmth_next(vitals.get("warmth", 50.0),
                         ambient_temperature(heartbeat_number),
                         by_fire, in_shelter)
    downed = bool(vitals.get("downed", False))
    vitality = vitality_next(vitals.get("vitality", 100.0), hunger,
                             warmth, downed)
    if downed and vitality >= RECOVERY_STAND_AT:
        downed = False
    if not downed and vitality <= COLLAPSE_THRESHOLD:
        downed = True
    return {
        "hunger": round(hunger, 2),
        "warmth": round(warmth, 2),
        "vitality": round(vitality, 2),
        "downed": downed,
    }


def vitals_state_label(vitals: dict) -> str:
    """One word for the observation: what the body is doing."""
    if vitals.get("downed"):
        return "collapsed"
    if vitals.get("vitality", 100.0) <= 25.0:
        return "failing"
    if vitals.get("hunger", 0.0) >= HUNGER_WEAKEN:
        return "starving"
    if vitals.get("warmth", 100.0) <= FREEZE_THRESHOLD:
        return "freezing"
    if vitals.get("hunger", 0.0) >= 60.0:
        return "hungry"
    if vitals.get("warmth", 100.0) <= 40.0:
        return "cold"
    return "well"
