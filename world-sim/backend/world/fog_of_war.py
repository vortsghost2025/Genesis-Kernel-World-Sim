"""Pure fog-of-war helpers for Phase 7 world expansion.

All functions operate on dictionaries and return in-memory data only. They do
not read or write canonical runtime data, call providers, run daemons, advance
ticks, or mutate Docker/VPS state.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from backend.world.fog_of_war_schema import SCHEMA_VERSION


ValidationResult = dict[str, Any]


def _validation(ok: bool, errors: list[str] | None = None) -> ValidationResult:
    return {"ok": ok, "errors": errors or []}


def _required(data: dict[str, Any], fields: list[str], label: str, errors: list[str]) -> None:
    for field in fields:
        if field not in data:
            errors.append(f"{label} missing required field: {field}")


def _is_coordinates(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("x"), (int, float))
        and isinstance(value.get("y"), (int, float))
    )


def create_empty_known_map(agent_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_id": agent_id,
        "known_tiles": {},
        "known_landmarks": {},
        "named_places": {},
        "routes": [],
        "hypotheses": [],
        "myths": [],
        "contact_evidence": [],
        "last_observation_tick": 0,
    }


def create_active_position(
    agent_id: str,
    continent_id: str,
    region_id: str,
    tile_id: str,
    coordinates: dict[str, int | float],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_id": agent_id,
        "active": True,
        "continent_id": continent_id,
        "region_id": region_id,
        "tile_id": tile_id,
        "coordinates": dict(coordinates),
        "facing": "north",
        "movement_mode": "walk",
        "travel_capabilities": ["walk_local"],
        "last_moved_tick": 0,
    }


def create_dormant_position(agent_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_id": agent_id,
        "active": False,
        "continent_id": None,
        "region_id": None,
        "tile_id": None,
        "coordinates": None,
        "facing": None,
        "movement_mode": "inactive",
        "travel_capabilities": [],
        "last_moved_tick": None,
    }


def validate_true_map(true_map: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    _required(
        true_map,
        [
            "schema_version",
            "world_id",
            "seed",
            "continents",
            "regions",
            "tiles",
            "landmarks",
            "resources",
            "hazards",
            "mysteries",
            "travel_edges",
        ],
        "true_map",
        errors,
    )
    if errors:
        return _validation(False, errors)

    continents = true_map.get("continents", [])
    regions = true_map.get("regions", [])
    tiles = true_map.get("tiles", [])
    landmarks = true_map.get("landmarks", [])
    if not isinstance(continents, list) or not continents:
        errors.append("true_map.continents must be a non-empty list")
    if not isinstance(regions, list) or not regions:
        errors.append("true_map.regions must be a non-empty list")
    if not isinstance(tiles, list) or not tiles:
        errors.append("true_map.tiles must be a non-empty list")

    continent_ids = {c.get("continent_id") for c in continents if isinstance(c, dict)}
    region_ids = {r.get("region_id") for r in regions if isinstance(r, dict)}
    tile_ids = {t.get("tile_id") for t in tiles if isinstance(t, dict)}

    for continent in continents:
        if not isinstance(continent, dict):
            errors.append("continent entries must be objects")
            continue
        _required(continent, ["continent_id", "name"], "continent", errors)

    for region in regions:
        if not isinstance(region, dict):
            errors.append("region entries must be objects")
            continue
        _required(region, ["region_id", "continent_id", "name"], "region", errors)
        if region.get("continent_id") not in continent_ids:
            errors.append(f"region references unknown continent: {region.get('region_id')}")

    for tile in tiles:
        if not isinstance(tile, dict):
            errors.append("tile entries must be objects")
            continue
        _required(
            tile,
            [
                "tile_id",
                "continent_id",
                "region_id",
                "coordinates",
                "terrain",
                "biome",
                "resources",
                "hazards",
                "landmark_ids",
                "blocks_travel",
            ],
            "tile",
            errors,
        )
        if tile.get("continent_id") not in continent_ids:
            errors.append(f"tile references unknown continent: {tile.get('tile_id')}")
        if tile.get("region_id") not in region_ids:
            errors.append(f"tile references unknown region: {tile.get('tile_id')}")
        if not _is_coordinates(tile.get("coordinates")):
            errors.append(f"tile has invalid coordinates: {tile.get('tile_id')}")

    for landmark in landmarks:
        if not isinstance(landmark, dict):
            errors.append("landmark entries must be objects")
            continue
        _required(landmark, ["landmark_id", "continent_id", "tile_id", "kind"], "landmark", errors)
        if landmark.get("continent_id") not in continent_ids:
            errors.append(f"landmark references unknown continent: {landmark.get('landmark_id')}")
        if landmark.get("tile_id") not in tile_ids:
            errors.append(f"landmark references unknown tile: {landmark.get('landmark_id')}")

    return _validation(not errors, errors)


def validate_known_map(known_map: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    _required(
        known_map,
        [
            "schema_version",
            "agent_id",
            "known_tiles",
            "known_landmarks",
            "named_places",
            "routes",
            "hypotheses",
            "myths",
            "contact_evidence",
            "last_observation_tick",
        ],
        "known_map",
        errors,
    )
    if errors:
        return _validation(False, errors)
    if not isinstance(known_map.get("known_tiles"), dict):
        errors.append("known_map.known_tiles must be an object")
    if not isinstance(known_map.get("known_landmarks"), dict):
        errors.append("known_map.known_landmarks must be an object")
    if not isinstance(known_map.get("named_places"), dict):
        errors.append("known_map.named_places must be an object")
    for field in ["routes", "hypotheses", "myths", "contact_evidence"]:
        if not isinstance(known_map.get(field), list):
            errors.append(f"known_map.{field} must be a list")
    return _validation(not errors, errors)


def validate_world_position(position: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    _required(
        position,
        [
            "schema_version",
            "agent_id",
            "active",
            "continent_id",
            "region_id",
            "tile_id",
            "coordinates",
            "facing",
            "movement_mode",
            "travel_capabilities",
            "last_moved_tick",
        ],
        "world_position",
        errors,
    )
    if errors:
        return _validation(False, errors)
    if not isinstance(position.get("active"), bool):
        errors.append("world_position.active must be boolean")
    if position.get("active"):
        for field in ["continent_id", "region_id", "tile_id", "coordinates"]:
            if position.get(field) in (None, ""):
                errors.append(f"active position requires {field}")
        if not _is_coordinates(position.get("coordinates")):
            errors.append("active position requires numeric coordinates")
    else:
        if position.get("movement_mode") != "inactive":
            errors.append("dormant position must use movement_mode=inactive")
    if not isinstance(position.get("travel_capabilities"), list):
        errors.append("world_position.travel_capabilities must be a list")
    return _validation(not errors, errors)


def _condition_radius(radius: int, conditions: dict[str, Any] | None) -> int:
    effective = int((conditions or {}).get("radius", radius))
    visibility = (conditions or {}).get("visibility")
    time_of_day = (conditions or {}).get("time_of_day")
    terrain = (conditions or {}).get("terrain")
    if visibility in {"low", "storm", "fog"} or time_of_day == "night" or terrain in {"cave", "dense_forest"}:
        effective -= 1
    if visibility == "high" or terrain in {"hill", "open_plain", "coast"}:
        effective += 1
    return max(0, effective)


def get_visible_tile_ids(
    true_map: dict[str, Any],
    position: dict[str, Any],
    radius: int,
    conditions: dict[str, Any] | None = None,
) -> list[str]:
    if not position.get("active") or not _is_coordinates(position.get("coordinates")):
        return []
    effective_radius = _condition_radius(radius, conditions)
    origin = position["coordinates"]
    continent_id = position.get("continent_id")
    visible: list[tuple[int | float, str]] = []
    for tile in true_map.get("tiles", []):
        if tile.get("continent_id") != continent_id:
            continue
        coords = tile.get("coordinates")
        if not _is_coordinates(coords):
            continue
        distance = abs(coords["x"] - origin["x"]) + abs(coords["y"] - origin["y"])
        if distance <= effective_radius:
            visible.append((distance, tile["tile_id"]))
    return [tile_id for _, tile_id in sorted(visible, key=lambda item: (item[0], item[1]))]


def build_local_observation(
    true_map: dict[str, Any],
    position: dict[str, Any],
    known_map: dict[str, Any],
    conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    radius = int((conditions or {}).get("radius", 1))
    visible_tile_ids = get_visible_tile_ids(true_map, position, radius, conditions)
    tiles_by_id = {tile.get("tile_id"): tile for tile in true_map.get("tiles", [])}
    landmarks_by_id = {landmark.get("landmark_id"): landmark for landmark in true_map.get("landmarks", [])}

    visible_tiles = []
    visible_landmarks = []
    for tile_id in visible_tile_ids:
        tile = tiles_by_id[tile_id]
        visible_tiles.append({
            "tile_id": tile["tile_id"],
            "continent_id": tile["continent_id"],
            "region_id": tile["region_id"],
            "coordinates": dict(tile["coordinates"]),
            "terrain": tile["terrain"],
            "biome": tile["biome"],
            "water": copy.deepcopy(tile.get("water")),
            "resources": list(tile.get("resources", [])),
            "hazards": list(tile.get("hazards", [])),
            "landmark_ids": list(tile.get("landmark_ids", [])),
        })
        for landmark_id in tile.get("landmark_ids", []):
            landmark = landmarks_by_id.get(landmark_id)
            if landmark:
                visible_landmarks.append({
                    "true_landmark_id": landmark["landmark_id"],
                    "tile_id": landmark["tile_id"],
                    "continent_id": landmark["continent_id"],
                    "kind": landmark["kind"],
                    "description": landmark.get("description", ""),
                })

    return {
        "schema_version": SCHEMA_VERSION,
        "agent_id": known_map.get("agent_id") or position.get("agent_id"),
        "position": {
            "continent_id": position.get("continent_id"),
            "region_id": position.get("region_id"),
            "tile_id": position.get("tile_id"),
            "coordinates": copy.deepcopy(position.get("coordinates")),
        },
        "visible_tile_ids": visible_tile_ids,
        "visible_tiles": visible_tiles,
        "visible_landmarks": visible_landmarks,
        "available_actions": ["observe", "rest", "gather", "move_local"],
        "hypotheses": [],
    }


def merge_observation_into_known_map(
    known_map: dict[str, Any],
    observation: dict[str, Any],
    tick: int,
) -> dict[str, Any]:
    for tile in observation.get("visible_tiles", []):
        tile_id = tile["tile_id"]
        existing = known_map["known_tiles"].get(tile_id)
        if existing:
            if existing["last_observed_tick"] != tick:
                existing["last_observed_tick"] = tick
                existing["visit_count"] += 1
                existing["observed_resources"] = sorted(set(existing.get("observed_resources", [])) | set(tile.get("resources", [])))
                existing["observed_hazards"] = sorted(set(existing.get("observed_hazards", [])) | set(tile.get("hazards", [])))
        else:
            known_map["known_tiles"][tile_id] = {
                "tile_id": tile_id,
                "first_observed_tick": tick,
                "last_observed_tick": tick,
                "visit_count": 1,
                "confidence": 1.0,
                "observed_terrain": tile.get("terrain", "unknown"),
                "observed_biome": tile.get("biome", "unknown"),
                "observed_resources": list(tile.get("resources", [])),
                "observed_hazards": list(tile.get("hazards", [])),
                "agent_given_name": None,
                "notes": [],
            }
    for landmark in observation.get("visible_landmarks", []):
        landmark_id = landmark["true_landmark_id"]
        existing = known_map["known_landmarks"].get(landmark_id)
        if existing:
            if existing["last_observed_tick"] != tick:
                existing["last_observed_tick"] = tick
        else:
            known_map["known_landmarks"][landmark_id] = {
                "true_landmark_id": landmark_id,
                "first_observed_tick": tick,
                "last_observed_tick": tick,
                "kind": landmark.get("kind", "unknown"),
                "confidence": 1.0,
                "description": landmark.get("description", ""),
            }
    if known_map.get("last_observation_tick", 0) != tick:
        known_map["last_observation_tick"] = tick
    return known_map


def add_agent_place_name(
    known_map: dict[str, Any],
    true_landmark_id: str,
    agent_given_name: str,
    tick: int,
    reason: str,
) -> dict[str, Any]:
    existing = known_map["named_places"].get(true_landmark_id)
    previous_names = []
    if existing:
        previous_names = list(existing.get("previous_names", [])) + [existing.get("agent_given_name", "")]
    known_map["named_places"][true_landmark_id] = {
        "true_landmark_id": true_landmark_id,
        "agent_given_name": agent_given_name,
        "first_named_tick": tick,
        "name_reason": reason,
        "previous_names": [name for name in previous_names if name],
    }
    return known_map


def add_hypothesis(
    known_map: dict[str, Any],
    claim: str,
    basis: str,
    confidence: float,
    tick: int,
) -> dict[str, Any]:
    hypothesis = {
        "id": f"hyp_{known_map.get('agent_id', 'agent')}_{len(known_map['hypotheses']) + 1:03d}",
        "created_tick": tick,
        "claim": claim,
        "basis": basis,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "status": "unverified",
    }
    known_map["hypotheses"].append(hypothesis)
    return known_map


def add_contact_evidence(known_map: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(evidence)
    normalized.setdefault("evidence_id", f"contact_{len(known_map['contact_evidence']) + 1:03d}")
    normalized.setdefault("agent_id", known_map.get("agent_id", ""))
    normalized.setdefault("tick", known_map.get("last_observation_tick", 0))
    normalized.setdefault("confidence", 0.0)
    normalized.setdefault("interpretation", "")
    normalized.setdefault("reveals_agent", False)
    normalized["level"] = max(0, min(4, int(normalized.get("level", 0))))
    known_map["contact_evidence"].append(normalized)
    return known_map


def contact_level(known_map: dict[str, Any], explicit_investigation: bool = False) -> dict[str, Any]:
    level = 0
    for evidence in known_map.get("contact_evidence", []):
        evidence_level = int(evidence.get("level", 4 if evidence.get("reveals_agent") else 0))
        level = max(level, max(0, min(4, evidence_level)))
    unlocked = level >= 4 or (level >= 3 and explicit_investigation)
    if unlocked and level >= 4:
        reason = "direct_contact_evidence"
    elif unlocked:
        reason = "strong_evidence_with_investigation"
    else:
        reason = "insufficient_evidence"
    return {"level": level, "unlocked": unlocked, "reason": reason}


def project_legacy_map_state(
    true_map: dict[str, Any],
    known_maps: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    known_maps = known_maps or {}
    known_landmark_ids = set()
    if known_maps:
        for known_map in known_maps.values():
            known_landmark_ids.update(known_map.get("known_landmarks", {}).keys())
            known_landmark_ids.update(known_map.get("named_places", {}).keys())

    entities = []
    for landmark in true_map.get("landmarks", []):
        tile = next((t for t in true_map.get("tiles", []) if t.get("tile_id") == landmark.get("tile_id")), None)
        if not tile:
            continue
        discovered = not known_maps or landmark["landmark_id"] in known_landmark_ids
        entities.append({
            "id": landmark["landmark_id"],
            "name": landmark.get("kind", "landmark").replace("_", " ").title(),
            "type": "landmark",
            "region": landmark.get("continent_id", "unknown"),
            "x": tile.get("coordinates", {}).get("x", 0),
            "y": tile.get("coordinates", {}).get("y", 0),
            "discovered": discovered,
            "description": landmark.get("description", ""),
            "first_seen_tick": None,
        })
    return {
        "entities": entities,
        "regions": {
            continent.get("continent_id"): {
                "name": continent.get("name", continent.get("continent_id")),
                "discovered": False,
                "exploration_level": 0,
            }
            for continent in true_map.get("continents", [])
        },
        "disclaimer": "Legacy projection generated from fog-of-war schema; not canonical runtime data.",
    }


def build_canonical_observation(
    agent_id: str,
    data_root: Path | str,
    conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only local observation from canonical fog-of-war files.

    Loads the canonical fog-of-war runtime files and builds an observation
    using the agent's current position and known map. Does not mutate any files.

    Args:
        agent_id: The canonical agent ID (e.g., "east_adam", "east_eve").
        data_root: Root directory containing world/ and agents/ subdirs.
        conditions: Optional conditions dict (e.g., {"radius": 1}).

    Returns:
        Observation dict from build_local_observation().

    Raises:
        FileNotFoundError: If any required canonical file is missing.
        json.JSONDecodeError: If any file contains invalid JSON.
    """
    root = Path(data_root) if not isinstance(data_root, Path) else data_root
    true_map_path = root / "world" / "true_map.json"
    position_path = root / "agents" / agent_id / "world_position.json"
    known_map_path = root / "agents" / agent_id / "known_map.json"

    if not true_map_path.exists():
        raise FileNotFoundError(f"Canonical true_map not found: {true_map_path}")
    if not position_path.exists():
        raise FileNotFoundError(f"Canonical position not found: {position_path}")
    if not known_map_path.exists():
        raise FileNotFoundError(f"Canonical known_map not found: {known_map_path}")

    true_map = json.loads(true_map_path.read_text(encoding="utf-8"))
    position = json.loads(position_path.read_text(encoding="utf-8"))
    known_map = json.loads(known_map_path.read_text(encoding="utf-8"))

    return build_local_observation(true_map, position, known_map, conditions)
