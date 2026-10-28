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
HUNGER_RATE = 0.6          # rise per heartbeat (human scale: ~147 hb / 2+ days before weakening)
HUNGER_CAP = 100.0
HUNGER_WEAKEN = 88.0       # at/above this: weakening (vitality drains)
EAT_SATISFACTION = {       # raw food: hunger points satisfied (human scale meals)
    "wild_berries": 28.0,
    "mushrooms": 22.0,
    "edible_roots": 34.0,
    "wild_apples": 36.0,
    "nuts": 25.0,
    "honeycomb": 32.0,
    "wild_grain": 22.0,
    "fish": 40.0,
    "meat": 40.0,
    "shellfish": 30.0,
    "cooked_meal": 75.0,   # fire-cooked hearty meal (lasts nearly two full days)
    "milk": 28.0,
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
                in_shelter: bool, wet: float = 0.0) -> float:
    """Warmth drifts toward the ambient comfort level.

    A fire dominates: warmth climbs toward 100 fast regardless of season.
    A shelter insulates: inside, comfort never falls below the floor -
    a structure traps heat and blocks wind, so a winter night inside is
    cool, not lethal, and a cold body warms toward the floor.
    A soaked body (wet >= 50) holds almost no heat: warmth moves at 0.4x
    speed in both directions - you cannot warm up while wet. epistemic.6.
    """
    comfort = max(0.0, min(100.0, ambient_temp))
    if in_shelter:
        comfort = max(comfort, SHELTER_COMFORT_FLOOR)
    if by_fire and wet < 50.0:
        return min(100.0, warmth + FIRE_WARMTH_PER_HB)
    gap = comfort - warmth
    change = gap * WARMTH_APPROACH_RATE
    if wet >= 50.0:
        change *= 0.4
    if change < 0 and in_shelter:
        change *= SHELTER_DECAY_FACTOR
    return max(0.0, min(100.0, warmth + change))


# --- comfort (epistemic.6) ---------------------------------------------------
# A shelter is not just less bad - it is good. The comfort floor means
# inside never feels colder than 45 even in a blizzard; rest inside
# heals vitality twice as fast. Summer days make shelters optional;
# winter nights and storms make them the difference between 13 and 45.
SHELTER_COMFORT_FLOOR = 45.0
REST_REGEN_IN_SHELTER = 1.0      # fed + sheltered: heals 2x
DOWNED_REGEN_IN_SHELTER = 0.4    # downed in shelter: stands ~2.5x sooner


def _pair_seed(pair_name: str) -> int:
    h = 0
    for ch in str(pair_name):
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


def _window_roll(pair_seed: int, window_index: int) -> float:
    """Deterministic 0..1 roll for one weather window."""
    x = (pair_seed * 2654435761 + window_index * 40503) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 1274126177) & 0xFFFFFFFF
    return ((x ^ (x >> 16)) & 0xFFFFFFFF) / 0x100000000


def weather_at(pair_name: str, heartbeat_number: int):
    """Current weather type and the heartbeat the window ends.

    Pure: same (pair, heartbeat) always yields the same sky.
    """
    seed = _pair_seed(pair_name)
    window_index = heartbeat_number // WEATHER_WINDOW
    roll = _window_roll(seed, window_index)
    probs = WEATHER_TABLE[season(heartbeat_number)]
    acc = 0.0
    wtype = "clear"
    for wtype, p in zip(WEATHER_TYPES, probs):
        acc += p
        if roll < acc:
            break
    window_end = (window_index + 1) * WEATHER_WINDOW
    return wtype, window_end


def weather_forecast(pair_name: str, heartbeat_number: int) -> dict:
    """Current weather plus the next window — the sky is legible."""
    wtype, window_end = weather_at(pair_name, heartbeat_number)
    nxt, _ = weather_at(pair_name, window_end)
    return {
        "current": wtype,
        "next": nxt,
        "changes_at_heartbeat": window_end,
    }


def effective_temperature(heartbeat_number: int, weather: str) -> float:
    """Ambient temperature with the sky's modifier."""
    return ambient_temperature(heartbeat_number) + WEATHER_TEMP_MODIFIER.get(
        weather, 0.0)


def wetness_next(wetness: float, weather: str, in_shelter: bool,
                 by_fire: bool) -> float:
    """Wetness rises in rain when exposed; dries in clear weather, fast
    by a fire. Shelter blocks gain entirely."""
    if in_shelter:
        if by_fire:
            return max(0.0, wetness - WETNESS_FIRE_DRY_RATE)
        return max(0.0, wetness - WETNESS_DRY_RATE)
    if weather in ("rain", "storm"):
        return min(100.0, wetness + WETNESS_GAIN_EXPOSED)
    if by_fire:
        return max(0.0, wetness - WETNESS_FIRE_DRY_RATE)
    return max(0.0, wetness - WETNESS_DRY_RATE)


def fire_is_snuffed(weather: str, fire_tile_sheltered: bool) -> bool:
    """THE shelter rule: rain snuffs open fires; a fire under a roof
    keeps burning. This one rule makes roof-building permanently
    valuable."""
    return weather in ("rain", "storm") and not fire_tile_sheltered

# --- vitality ------------------------------------------------------------------
VITALITY_CAP = 100.0
STARVING_DRAIN = 0.6        # per heartbeat at hunger >= HUNGER_WEAKEN
FREEZING_DRAIN = 0.8        # per heartbeat at warmth <= FREEZE_THRESHOLD
REGEN_RATE = 0.5            # fed and warm: slow recovery
COLLAPSE_THRESHOLD = 0.0    # vitality at/below: down
RECOVERY_STAND_AT = 12.0    # vitality needed to stand again after collapse
DOWNED_PASSIVE_REGEN = 0.15  # slow self-recovery while down (rescue is better)


# --- weather: the sky (epistemic.5) -----------------------------------------
# Weather is a PURE function of (pair seed, heartbeat): no state file, no
# drift, no split-brain â€” the sky is part of the physics, not a process.
# Stable windows give agents something to plan around, and the forecast
# (the next window) is visible in every observation: weather is planning
# material, not dice.
WEATHER_WINDOW = 36            # heartbeats per weather window (half a day)
WEATHER_TYPES = ("clear", "overcast", "rain", "storm")
# per-season probabilities (clear, overcast, rain, storm); a winter storm
# reads as a blizzard in the observation, but the math is one thing
WEATHER_TABLE = {
    "spring": (0.55, 0.20, 0.20, 0.05),
    "summer": (0.78, 0.12, 0.08, 0.02),
    "autumn": (0.50, 0.22, 0.21, 0.07),
    "winter": (0.52, 0.20, 0.18, 0.10),
}
WEATHER_TEMP_MODIFIER = {"clear": 0.0, "overcast": -3.0,
                         "rain": -6.0, "storm": -11.0}
WETNESS_GAIN_EXPOSED = 9.0     # per heartbeat in rain, unsheltered
WETNESS_DRY_RATE = 4.0         # per heartbeat in clear/overcast
WETNESS_FIRE_DRY_RATE = 14.0   # drying by a fire
WET_THRESHOLD = 50.0           # soaked: cannot warm up (see warmth_next)
STORM_EXPOSURE_DRAIN = 0.3     # vitality per heartbeat, exposed in a storm


def vitality_next(vitality: float, hunger: float, warmth: float,
                  downed: bool, in_shelter: bool = False) -> float:
    """Vitality drains under neglect, regenerates under care.
    Rest inside a shelter heals twice as fast - comfort is medicine."""
    if downed:
        rate = DOWNED_REGEN_IN_SHELTER if in_shelter else DOWNED_PASSIVE_REGEN
        return min(RECOVERY_STAND_AT, vitality + rate)
    v = vitality
    if hunger >= HUNGER_WEAKEN:
        v -= STARVING_DRAIN
    if warmth <= FREEZE_THRESHOLD:
        v -= FREEZING_DRAIN
    if hunger <= 45.0 and warmth >= 50.0:
        v += REST_REGEN_IN_SHELTER if in_shelter else REGEN_RATE
    return max(0.0, min(VITALITY_CAP, v))
# --- the vitals block -------------------------------------------------------
def initial_vitals() -> dict:
    """Healthy start. No retroactive famine for existing agents."""
    return {"hunger": 18.0, "warmth": 82.0, "vitality": 100.0,
            "wetness": 0.0, "downed": False}


def apply_heartbeat(vitals: dict, heartbeat_number: int, by_fire: bool,
                    in_shelter: bool, ate_satisfaction: float = 0.0,
                    weather: str = "clear") -> dict:
    """One heartbeat of embodiment. Returns a NEW vitals dict.

    `ate_satisfaction` is the hunger points satisfied by food eaten this
    heartbeat (0 = nothing eaten). `weather` is the current sky (the
    caller resolves the forecast); it drives wetness, the temperature
    modifier, and storm exposure. Everything else follows the physics.
    """
    hunger = hunger_next(vitals.get("hunger", 0.0), heartbeat_number)
    hunger = max(0.0, hunger - ate_satisfaction)
    wetness = wetness_next(vitals.get("wetness", 0.0), weather,
                           in_shelter, by_fire)
    temp = effective_temperature(heartbeat_number, weather)
    warmth = warmth_next(vitals.get("warmth", 50.0), temp,
                         by_fire, in_shelter, wetness)
    downed = bool(vitals.get("downed", False))
    vitality = vitality_next(vitals.get("vitality", 100.0), hunger,
                             warmth, downed, in_shelter)
    if weather == "storm" and not in_shelter and not downed:
        vitality = max(0.0, vitality - STORM_EXPOSURE_DRAIN)
    if downed and vitality >= RECOVERY_STAND_AT:
        downed = False
    if not downed and vitality <= COLLAPSE_THRESHOLD:
        downed = True
    return {
        "hunger": round(hunger, 2),
        "warmth": round(warmth, 2),
        "vitality": round(vitality, 2),
        "wetness": round(wetness, 2),
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
