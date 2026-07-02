"""Phase 10AG — Observed Slice to World Event Candidate Bridge.
Phase 10AH — Hardened tick/scope/validation for observation bridge.

This module bridges the planet track (fog-of-war + hidden true_map from 10AF)
into the event system (candidate mapper + verifier + ledger from 10K/10L/10T).

The central function ``observation_slice_to_candidate`` takes the
dictionary returned by ``fog_of_war.build_local_observation`` and converts
it into a properly structured ``result`` dict that can be passed to the
existing ``world_event_candidate_mapper.candidate_from_observe_result``.

Pipeline established by this bridge::

    hidden true_map
    → fog-of-war local observation   (build_local_observation)
    → slice_to_event_bridge          (observation_slice_to_candidate)
    → world-event candidate          (candidate_from_observe_result)
    → verifier                        (verify_candidate_event)
    → ledger                          (append_event / validate_event)
    → export                          (export_events)
    → sanitizer                       (sanitize_public_text)

The hidden substrate is never exposed — the bridge extracts only the
observed slice (visible tile IDs, visible landmark IDs, position data)
and builds a safe, summary-only event payload.
"""

from __future__ import annotations

import json
from typing import Any

from backend.world.world_event_candidate_mapper import candidate_from_observe_result

# Observation keys required for a valid bridge call.
_REQUIRED_OBSERVATION_KEYS: frozenset[str] = frozenset({
    "position",
    "visible_tile_ids",
    "visible_tiles",
    "visible_landmarks",
    "agent_id",
})


def observation_slice_to_candidate(
    observation: dict[str, Any],
    actor_id: str | None = None,
    *,
    tick: int,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Convert a ``build_local_observation`` result into a candidate event.

    Parameters
    ----------
    observation:
        The dictionary returned by ``fog_of_war.build_local_observation``.
        Required keys: ``position``, ``visible_tile_ids``, ``visible_tiles``,
        ``visible_landmarks``, ``agent_id``.
        Within ``position``: ``region_id``, ``tile_id``, ``continent_id``,
        ``coordinates`` are expected.
    actor_id:
        Override for the actor performing the observation.  If ``None``,
        the value from ``observation["agent_id"]`` is used.
    tick:
        **Required.** Simulation tick number.  Must be a non-negative integer.
        Used by the verifier for duplicate detection.
    timestamp_utc:
        Optional ISO-8601 timestamp.  Auto-generated if omitted.

    Returns
    -------
    dict
        A candidate event dictionary that satisfies ``validate_event``
        and can be passed to ``verify_candidate_event``.

    Raises
    ------
    ValueError
        If ``tick`` is ``None`` or negative, or if ``observation`` is missing
        required keys.
    """
    # --- Validate tick (required for verifier duplicate detection) ---
    if tick is None or (isinstance(tick, int) and tick < 0):
        raise ValueError(
            f"tick is required and must be a non-negative integer, got {tick!r}"
        )

    # --- Validate observation dict has required keys ---
    missing = _REQUIRED_OBSERVATION_KEYS - observation.keys()
    if missing:
        raise ValueError(
            f"observation missing required keys: {sorted(missing)}"
        )

    # --- Extract position information ---
    position = observation.get("position", {})
    region_id = position.get("region_id", "")
    continent_id = position.get("continent_id", "")
    tile_id = position.get("tile_id", "")
    coordinates = position.get("coordinates", {})

    # --- Resolve actor identity ---
    if actor_id is None:
        actor_id = observation.get("agent_id", "unknown_agent")

    # --- Build a safe summary (region-level metadata only, no hidden data) ---
    visible_tile_ids = list(observation.get("visible_tile_ids", []))
    visible_tiles_raw = observation.get("visible_tiles", [])
    visible_landmarks_raw = observation.get("visible_landmarks", [])

    # Collect resource kinds, terrain types, and biome from visible tiles
    seen_resource_kinds: list[str] = list(
        sorted(
            {
                r
                for tile in visible_tiles_raw
                for r in tile.get("resources", [])
            }
        )
    )
    seen_biomes: list[str] = list(
        sorted(
            {
                tile.get("biome", "")
                for tile in visible_tiles_raw
                if tile.get("biome")
            }
        )
    )

    summary = json.dumps(
        {
            "observed_region": region_id,
            "observed_continent": continent_id,
            "position_tile": tile_id,
            "coordinates": coordinates,
            "visible_tile_count": len(visible_tile_ids),
            "visible_landmark_count": len(visible_landmarks_raw),
            "seen_resource_kinds": seen_resource_kinds,
            "seen_biomes": seen_biomes,
        },
        sort_keys=True,
    )

    # --- Build the ``result`` dict that candidate_from_observe_result expects ---
    # The mapper's result dict needs:
    #   territory_ref: str
    #   evidence_used: list[dict] with at least one having category "observed_world_fact"
    #
    # We construct evidence that reflects only the observed slice.
    # Hidden tile IDs / landmark IDs are never included because they are
    # already absent from the observation output (fog-of-war guarantees this).

    safe_observation_detail = json.dumps(
        {
            "visible_tile_ids": visible_tile_ids,
            "visible_landmark_ids": [
                lm.get("true_landmark_id", lm.get("landmark_id", ""))
                for lm in visible_landmarks_raw
            ],
            "available_actions": observation.get("available_actions", []),
        },
        sort_keys=True,
    )

    result: dict[str, Any] = {
        "territory_ref": region_id,
        "evidence_used": [
            {
                "category": "observed_world_fact",
                "tile_ids": visible_tile_ids,
                "observation_detail": safe_observation_detail,
            }
        ],
        # Explicit claim_scope — bypasses mapper heuristic
        "claim_scope": "observed",
    }

    # --- Delegate to the Phase 10L candidate mapper ---
    return candidate_from_observe_result(
        actor_id=actor_id,
        action_text=summary,
        result=result,
        tick=tick,
        timestamp_utc=timestamp_utc,
    )