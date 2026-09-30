"""Phase 10JB-1 — Pure fog adapter for the first-pair runtime.

Bridges the living first-pair civilization to the Phase-7 true-map /
fog-of-war geography without rewriting history. This module is pure:
it reads its inputs and returns in-memory results; it never writes
canonical state and never calls a provider or model.

Contamination-safety contract (10IZ §5.7):
- cognition-facing output never contains the strings ``true_map`` or
  ``known_map``;
- ``true_landmark_id`` is projected as ``landmark_id``;
- only radius-visible tiles appear in observations;
- hidden mysteries never enter cognition output.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from backend.world.fog_of_war import (
    build_local_observation,
    create_empty_known_map,
    get_visible_tile_ids,
    merge_observation_into_known_map,
    validate_known_map,
    validate_true_map,
)

_FORBIDDEN_PROMPT_STRINGS = ("true_map", "known_map", "true_landmark_id")
_HISTORICAL_HABITAT_TILES = (
    "public-start-adam",
    "public-shared-center",
    "public-start-eve",
)
_HISTORICAL_ADJACENCY: dict[str, list[str]] = {
    "public-start-adam": ["public-shared-center"],
    "public-shared-center": ["public-start-adam", "public-start-eve"],
    "public-start-eve": ["public-shared-center"],
}


class FogAdapterError(Exception):
    """Raised when fog state is invalid; callers must fail closed."""


def load_true_map(data_root: Path | str) -> dict[str, Any]:
    """Load and validate the canonical true map. Read-only."""
    path = Path(data_root) / "world" / "true_map.json"
    if not path.is_file():
        raise FogAdapterError(f"true map not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FogAdapterError(f"true map unreadable: {type(exc).__name__}") from exc
    result = validate_true_map(raw)
    if not result["ok"]:
        raise FogAdapterError(f"true map invalid: {result['errors'][:3]}")
    return raw


def build_world_position_from_tile(
    true_map: dict[str, Any], tile_id: str
) -> dict[str, Any]:
    """Convert a living tile_id to a fog world-position dict."""
    tiles = {t["tile_id"]: t for t in true_map.get("tiles", [])}
    tile = tiles.get(tile_id)
    if tile is None:
        raise FogAdapterError(f"tile not in true map: {tile_id}")
    return {
        "schema_version": true_map.get("schema_version", "7B.1"),
        "agent_id": "",
        "active": True,
        "continent_id": tile["continent_id"],
        "region_id": tile["region_id"],
        "tile_id": tile_id,
        "coordinates": dict(tile["coordinates"]),
        "facing": "north",
        "movement_mode": "walk",
        "travel_capabilities": ["walk_local"],
        "last_moved_tick": 0,
    }


def seed_known_map_from_history(
    heartbeat_records: list[dict[str, Any]],
    agent_ref: str,
    starting_tile_id: str,
    agent_id: str = "",
) -> dict[str, Any]:
    """Deterministically seed a known map from actual heartbeat history.

    Replay rule (10IZ §5.3): for each historical heartbeat,
    1. read the recorded position for the agent;
    2. mark the occupied tile as observed and visited;
    3. mark adjacent historically visible tiles as observed;
    4. increment visit count only for the occupied tile;
    5. retain the earliest observed tick;
    6. never infer a visit merely from visibility.

    ``agent_id`` is the full canonical agent ID (e.g. ``genesis-agent-…``)
    used to match ``acting_agent_id`` in mutation records. When empty,
    mutations are matched by the action_taken key instead.
    """
    known = create_empty_known_map(agent_ref)
    position = starting_tile_id

    for hb in heartbeat_records:
        hb_num = hb.get("heartbeat_number", 0)

        # Update position: match by agent_id in mutations, or by
        # action_taken[agent_ref] as a fallback
        for mut in hb.get("world_mutations", []):
            if agent_id and mut.get("acting_agent_id", "") == agent_id:
                if mut.get("action_type") == "move":
                    outcome = mut.get("outcome", {})
                    if outcome.get("status") == "success":
                        position = outcome.get("to", position)
            elif not agent_id:
                # Fallback: check action_taken for this agent_ref
                action = hb.get("action_taken", {}).get(agent_ref, {})
                if action.get("action_type") == "move":
                    # Find the matching mutation for position update
                    target = action.get("target_tile", "")
                    if target and target != position:
                        # Check if there's a matching mutation
                        for m2 in hb.get("world_mutations", []):
                            if (
                                m2.get("action_type") == "move"
                                and m2.get("outcome", {}).get("to") == target
                                and m2.get("outcome", {}).get("status") == "success"
                            ):
                                position = target
                                break

        # Mark occupied tile as visited and observed
        _seed_visit_tile(known, position, hb_num)
        # Mark adjacent tiles as observed (not visited)
        for adj in _HISTORICAL_ADJACENCY.get(position, []):
            _seed_observe_tile(known, adj, hb_num)

        known["last_observation_tick"] = max(
            known.get("last_observation_tick", 0), hb_num
        )

    # Seed the meeting stone as a known landmark if history proves it
    for hb in heartbeat_records:
        for mut in hb.get("world_mutations", []):
            if mut.get("action_type") == "create_public_object":
                obj_input = mut.get("input", {})
                if obj_input.get("object_id") == "meeting-stone-center":
                    hb_num = hb.get("heartbeat_number", 0)
                    stone_tile = obj_input.get("tile_id", "public-shared-center")
                    if stone_tile in known["known_tiles"]:
                        known["known_landmarks"]["lm_meeting_stone_center"] = {
                            "true_landmark_id": "lm_meeting_stone_center",
                            "first_observed_tick": hb_num,
                            "last_observed_tick": hb_num,
                            "kind": "meeting_stone",
                            "confidence": 1.0,
                            "description": obj_input.get("description", ""),
                        }
                    break

    result = validate_known_map(known)
    if not result["ok"]:
        raise FogAdapterError(f"seeded known map invalid: {result['errors'][:3]}")
    return known


def _seed_visit_tile(
    known: dict[str, Any], tile_id: str, tick: int
) -> None:
    entry = known["known_tiles"].get(tile_id)
    if entry is None:
        known["known_tiles"][tile_id] = {
            "tile_id": tile_id,
            "first_observed_tick": tick,
            "last_observed_tick": tick,
            "visit_count": 1,
            "confidence": 1.0,
            "observed_terrain": "unknown",
            "observed_biome": "unknown",
            "observed_resources": [],
            "observed_hazards": [],
            "agent_given_name": None,
            "notes": [],
        }
    else:
        entry["visit_count"] += 1
        entry["last_observed_tick"] = tick


def _seed_observe_tile(
    known: dict[str, Any], tile_id: str, tick: int
) -> None:
    if tile_id not in known["known_tiles"]:
        known["known_tiles"][tile_id] = {
            "tile_id": tile_id,
            "first_observed_tick": tick,
            "last_observed_tick": tick,
            "visit_count": 0,
            "confidence": 1.0,
            "observed_terrain": "unknown",
            "observed_biome": "unknown",
            "observed_resources": [],
            "observed_hazards": [],
            "agent_given_name": None,
            "notes": [],
        }


def cognition_safe_observation(
    true_map: dict[str, Any],
    tile_id: str,
    known_map: dict[str, Any],
    conditions: dict[str, Any] | None,
    objects_here: list[dict[str, Any]],
    agent_ref: str = "",
) -> dict[str, Any]:
    """Build a cognition-safe observation from fog data.

    Returns the living observation contract:
    {tile_id, visible_tiles, objects_here, visible_tile_details}

    The projection scrubs implementation terms and includes only
    radius-visible tiles with safe terrain/biome/landmark details.
    """
    position = build_world_position_from_tile(true_map, tile_id)
    position["agent_id"] = agent_ref

    raw = build_local_observation(true_map, position, known_map, conditions)
    visible_ids = raw.get("visible_tile_ids", [])
    visible_tiles_raw = raw.get("visible_tiles", [])
    visible_landmarks_raw = raw.get("visible_landmarks", [])

    # Project landmarks: rename true_landmark_id → landmark_id,
    # filter to only landmarks on visible tiles
    landmark_by_tile: dict[str, list[dict[str, Any]]] = {}
    for lm in visible_landmarks_raw:
        lm_tile = lm.get("tile_id", "")
        safe_lm = {
            "landmark_id": lm.get("true_landmark_id", ""),
            "tile_id": lm_tile,
            "kind": lm.get("kind", ""),
            "description": lm.get("description", ""),
        }
        landmark_by_tile.setdefault(lm_tile, []).append(safe_lm)

    # Project tiles: keep safe fields, attach landmarks and resources
    # Build a resource lookup from the true map's resource entries
    resource_by_tile: dict[str, list[str]] = {}
    for res in true_map.get("resources", []):
        res_tile = res.get("tile_id", "")
        if res.get("amount", 0) > 0:
            resource_by_tile.setdefault(res_tile, []).append(res["kind"])
    # Deduplicate
    for k in resource_by_tile:
        resource_by_tile[k] = sorted(set(resource_by_tile[k]))

    # Conditions are REPORTED ONLY. The radius dial is deliberately not
    # turned on here: wiring conditions into the radius is a pressure change
    # and is deferred to its own phase (spec §4.1). Reporting must not alter
    # visible_tiles.
    safe_conditions = {}
    if conditions:
        for key in ("visibility", "time_of_day", "radius"):
            if key in conditions:
                safe_conditions[key] = conditions[key]

    tile_details: list[dict[str, Any]] = []
    for t in visible_tiles_raw:
        tid = t.get("tile_id", "")
        detail = {
            "tile_id": tid,
            "terrain": t.get("terrain", "unknown"),
            "biome": t.get("biome", "unknown"),
            "landmarks": landmark_by_tile.get(tid, []),
            "resources": resource_by_tile.get(tid, []),
            # Transmitted per visible tile. The world carries exactly one
            # drinkable fresh_water tile in 80,000 and the agents have been
            # asking about water since the first live loop; the fact was
            # present in the true map and dropped here. Generic projection -
            # no tile id or resource name is special-cased, so the singular
            # tile stays a discovery (spec §6).
            "water": copy.deepcopy(t.get("water")) or {},
            "hazards": list(t.get("hazards", [])),
        }
        tile_details.append(detail)

    observation = {
        "tile_id": tile_id,
        "visible_tiles": visible_ids,
        "objects_here": objects_here,
        "visible_tile_details": tile_details,
    }
    if safe_conditions:
        observation["conditions"] = safe_conditions

    # Contamination safety check
    obs_text = json.dumps(observation)
    for forbidden in _FORBIDDEN_PROMPT_STRINGS:
        if forbidden in obs_text:
            raise FogAdapterError(
                f"contamination safety violation: '{forbidden}' in observation"
            )

    return observation


# --- World walls (docs/world_walls_spec.md) -----------------------------
# One rule, three keys: a public object whose object_type or object_id names
# a key and which stands adjacent to a barrier tile of the matching biome
# opens travel to that barrier tile — for everyone, because a raft standing
# in the world is a public fact. The wall itself is made of MISSING EDGES
# (blocks_travel alone does not gate derive_topology), so the unlock works
# by synthesizing the edges the wall removed.
BARRIER_UNLOCK_KEYS = {
    # barrier biome        -> object key (object_type or object_id)
    "deep_lake": "raft",
    "dark_thicket": "campfire",
    "deep_ravine": "bridge",
}


def _barrier_tiles_by_biome(true_map: dict[str, Any]) -> dict[str, dict]:
    """Barrier tiles by tile_id: biome-locked, blocks_travel true."""
    out: dict[str, dict] = {}
    for t in true_map.get("tiles", []):
        if not isinstance(t, dict):
            continue
        biome = t.get("biome")
        if biome in BARRIER_UNLOCK_KEYS and t.get("blocks_travel"):
            out[t.get("tile_id", "")] = t
    return out


def _geo_neighbors(tile: dict, coord_index: dict) -> list[str]:
    """4-connected neighbor tile ids via coordinate lookup — not id-string
    arithmetic, which breaks on named tiles (public-shared-center, origin
    tiles) and any future naming. The true map stores travel edges
    4-connected and bidirectional; the unlock synthesizes edges in the same
    shape."""
    coords = tile.get("coordinates") or {}
    x, y = coords.get("x"), coords.get("y")
    if x is None or y is None:
        return []
    return [coord_index[(x + dx, y + dy)]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (x + dx, y + dy) in coord_index]


def _synthesized_unlock_edges(true_map: dict[str, Any],
                              public_objects: list[dict]) -> list[dict]:
    """Edges a standing key object adds: object's tile -> adjacent barrier
    of the matching biome -> that barrier's non-barrier neighbors.

    The barrier never links sideways to other barriers (locked or not):
    each wall tile answers only to a key standing next to IT. Fog still
    governs downstream — both endpoints must be known for an edge to act.
    """
    if not public_objects:
        return []
    barriers = _barrier_tiles_by_biome(true_map)
    if not barriers:
        return []
    tiles_by_id = {t.get("tile_id"): t
                   for t in true_map.get("tiles", []) if isinstance(t, dict)}
    coord_index = {}
    for t in true_map.get("tiles", []):
        if not isinstance(t, dict):
            continue
        c = t.get("coordinates") or {}
        if c.get("x") is not None and c.get("y") is not None:
            coord_index[(c["x"], c["y"])] = t.get("tile_id")
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(a: str, b: str) -> None:
        for pair in ((a, b), (b, a)):
            if pair not in seen:
                seen.add(pair)
                edges.append({"from_tile_id": pair[0],
                              "to_tile_id": pair[1]})

    for obj in public_objects:
        if not isinstance(obj, dict):
            continue
        key_claim = " ".join([
            str(obj.get("object_type") or ""),
            str(obj.get("object_id") or ""),
        ]).casefold()
        stand_tile = obj.get("tile_id")
        if not stand_tile or stand_tile not in tiles_by_id:
            continue
        for biome, key in BARRIER_UNLOCK_KEYS.items():
            if key not in key_claim:
                continue
            for nb_id in _geo_neighbors(tiles_by_id[stand_tile],
                                        coord_index):
                barrier = barriers.get(nb_id)
                if not barrier or barrier.get("biome") != biome:
                    continue
                # The key stands adjacent: barrier opens to its non-barrier
                # neighbors (both shores). Sideways barrier links stay gone.
                for open_id in _geo_neighbors(barrier, coord_index):
                    neighbor = tiles_by_id.get(open_id)
                    if neighbor is None or open_id in barriers:
                        continue
                    if neighbor.get("blocks_travel"):
                        continue  # never bridge onto unrelated blocked land
                    _add(stand_tile, nb_id)
                    _add(nb_id, open_id)
                break
    return edges


def derive_topology(
    true_map: dict[str, Any],
    known_maps: list[dict[str, Any]],
    public_objects: list[dict] | None = None,
) -> dict[str, Any]:
    """Derive a runtime policy topology from known tiles ∩ travel edges.

    Returns {allowed_tile_ids, tiles (with adjacency), movement_allowed,
    one_edge_per_heartbeat} matching the living policy topology shape.

    `public_objects` (flat records from world state) synthesize unlock edges
    per BARRIER_UNLOCK_KEYS: a raft by deep water opens the water, a
    campfire by a dark thicket opens the thicket, a bridge by a ravine
    opens the ravine — for every agent, because objects are public.
    """
    known_union: set[str] = set()
    for km in known_maps:
        known_union.update(km.get("known_tiles", {}).keys())

    # Always include historical habitat tiles
    known_union.update(_HISTORICAL_HABITAT_TILES)

    # Filter travel edges: both endpoints must be known
    all_edges = list(true_map.get("travel_edges", []))
    all_edges.extend(_synthesized_unlock_edges(true_map, public_objects or []))
    active_edges: list[tuple[str, str]] = []
    for edge in all_edges:
        from_id = edge.get("from_tile_id", "")
        to_id = edge.get("to_tile_id", "")
        if from_id in known_union and to_id in known_union:
            active_edges.append((from_id, to_id))

    # Build adjacency from active edges
    adjacency: dict[str, set[str]] = {}
    for from_id, to_id in active_edges:
        adjacency.setdefault(from_id, set()).add(to_id)

    # Also include historical habitat adjacency (always valid)
    for tile_id, adj_list in _HISTORICAL_ADJACENCY.items():
        if tile_id in known_union:
            existing = adjacency.setdefault(tile_id, set())
            for adj in adj_list:
                if adj in known_union:
                    existing.add(adj)

    # Derive allowed tiles: known tiles reachable from any known tile
    reachable: set[str] = set()
    for tile_id in known_union:
        if tile_id in adjacency or any(
            tile_id in targets for targets in adjacency.values()
        ):
            reachable.add(tile_id)

    # Ensure all habitat tiles are always reachable
    reachable.update(t for t in _HISTORICAL_HABITAT_TILES if t in known_union)

    tiles_list = []
    for tile_id in sorted(reachable):
        adj_sorted = sorted(adjacency.get(tile_id, set()))
        tiles_list.append({"tile_id": tile_id, "adjacent": adj_sorted})

    return {
        "allowed_tile_ids": sorted(reachable),
        "movement_allowed": True,
        "one_edge_per_heartbeat": True,
        "tiles": tiles_list,
    }


def merge_observation(
    known_map: dict[str, Any],
    observation: dict[str, Any],
    tick: int,
) -> dict[str, Any]:
    """Merge a cognition-safe observation's tile data into a known map.

    This is a wrapper that reconstructs the fog observation format
    from the cognition-safe projection so the existing pure merge
    function can be reused without modification.
    """
    tile_details = observation.get("visible_tile_details", [])
    landmarks_by_tile: dict[str, list[dict[str, Any]]] = {}
    for td in tile_details:
        for lm in td.get("landmarks", []):
            landmarks_by_tile.setdefault(td["tile_id"], []).append(lm)

    fog_tiles = []
    for td in tile_details:
        fog_tiles.append({
            "tile_id": td["tile_id"],
            "terrain": td.get("terrain", "unknown"),
            "biome": td.get("biome", "unknown"),
            "resources": [],
            "hazards": [],
        })

    fog_observation = {
        "visible_tiles": fog_tiles,
        "visible_landmarks": [
            {
                "true_landmark_id": lm["landmark_id"],
                "tile_id": tile_id,
                "kind": lm.get("kind", ""),
                "description": lm.get("description", ""),
            }
            for tile_id, lms in landmarks_by_tile.items()
            for lm in lms
        ],
    }

    updated = merge_observation_into_known_map(known_map, fog_observation, tick)
    result = validate_known_map(updated)
    if not result["ok"]:
        raise FogAdapterError(f"merged known map invalid: {result['errors'][:3]}")
    return updated


def fog_gate_active(store_root: Path | str, pair_id: str = "east") -> bool:
    """Check whether known-map files exist in the living store (the gate)."""
    root = Path(store_root)
    adam = root / f"known_map_{pair_id}_adam.json"
    eve = root / f"known_map_{pair_id}_eve.json"
    return adam.is_file() and eve.is_file()


def load_known_map(store_root: Path | str, agent_ref: str) -> dict[str, Any]:
    """Load a per-agent known map from the living store."""
    path = Path(store_root) / f"known_map_{agent_ref}.json"
    if not path.is_file():
        raise FogAdapterError(f"known map not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FogAdapterError(f"known map unreadable: {type(exc).__name__}") from exc
    result = validate_known_map(raw)
    if not result["ok"]:
        raise FogAdapterError(f"known map invalid: {result['errors'][:3]}")
    return raw


def persist_known_map(
    store_root: Path | str, agent_ref: str, known_map: dict[str, Any]
) -> None:
    """Persist a per-agent known map to the living store."""
    path = Path(store_root) / f"known_map_{agent_ref}.json"
    path.write_text(
        json.dumps(known_map, indent=2, sort_keys=True), newline="\n"
    )


def get_known_tile_ids(known_map: dict[str, Any]) -> set[str]:
    """Return the set of tile IDs known to an agent."""
    return set(known_map.get("known_tiles", {}).keys())


def get_known_union(known_maps: list[dict[str, Any]]) -> set[str]:
    """Return the union of tile IDs known across all agents."""
    union: set[str] = set()
    for km in known_maps:
        union.update(get_known_tile_ids(km))
    return union
