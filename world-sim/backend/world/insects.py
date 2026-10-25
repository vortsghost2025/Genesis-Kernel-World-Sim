"""Insects and Micro-Ecology — bees, stings, and environmental sounds.

Epistemic layer for living environmental details.
Distinction between gather and eat:
  - 'gather' with resource_kind 'honeycomb' transfers 1 honeycomb from the tile into belongings.
    Active bee colonies defend their hive and inflict bee sting damage (2.0 vitality).
    Campfire/hearth smoke (within 1 tile) or cold/night/rain dormancy prevents stings.
  - 'eat' with resource_kind 'honeycomb' consumes 1 honeycomb from belongings, satisfying
    32.0 hunger points (per survival.EAT_SATISFACTION['honeycomb']).
"""
from __future__ import annotations

BEE_STING_DAMAGE = 2.0
BEE_DORMANT_TEMP = 45.0


def bee_colony_state(weather: str, temperature: float, is_night: bool, near_smoke: bool) -> str:
    """Determine the current state of a wild bee colony on a honeycomb tile.

    Returns:
      'calmed': campfire or torch smoke suppresses stinging instincts.
      'dormant': night, winter chill, rain, or storm keeps bees clustered inside.
      'active': warm, exposed daylight; bees actively defend the hive.
    """
    if near_smoke:
        return "calmed"
    if is_night or weather in ("rain", "storm", "blizzard") or temperature < BEE_DORMANT_TEMP:
        return "dormant"
    return "active"


def resolve_bee_gather(colony_state: str, current_vitality: float) -> tuple[float, str]:
    """Calculate sting consequence when gathering honeycomb into inventory.

    Returns:
      (damage, message)
      Stings inflict BEE_STING_DAMAGE (2.0 vitality). Standard vitality and collapse rules
      apply: if vitality drops to or below 0.0, the agent collapses into the downed state.
    """
    if colony_state == "calmed":
        return 0.0, "Harvested honeycomb safely under the cover of campfire smoke."
    if colony_state == "dormant":
        return 0.0, "Harvested honeycomb while the bees were clustered dormant."

    damage = BEE_STING_DAMAGE
    msg = (
        f"Harvested honeycomb, but suffered bee stings (-{damage:.1f} vitality). "
        "Smoke from a nearby fire or cold weather calms the swarm."
    )
    return damage, msg


def ambient_insect_atmosphere(season: str, weather: str, is_night: bool, biome: str = "") -> str | None:
    """Sensory text for environmental observation based on canonical tile biome."""
    b_lower = str(biome).lower()
    if is_night and weather in ("clear", "overcast") and season in ("spring", "summer", "autumn"):
        return "Crickets chorus in the tall grass outside the circle of firelight."
    if any(k in b_lower for k in ("swamp", "wetland", "marsh", "lake", "ravine")):
        if season in ("spring", "summer", "autumn") and weather != "blizzard":
            return "Biting midges and gnats hover in the damp air; smoke or shelter repels them."
    if any(k in b_lower for k in ("forest", "woodland", "thicket", "grove")):
        if not is_night and weather in ("clear", "overcast") and season in ("spring", "summer", "autumn"):
            return "Wild pollinators and bees hum softly among the flowering brush."
    return None
