"""Phase 10AI — Local Movement Contract.

Pure module that resolves a local movement action inside a hidden true_map
without exposing hidden data.  The result can be passed to the candidate
event mapper to produce a ``move_local`` world event.

This is a pure resolution function — it never writes position state to disk,
never calls runtime or daemon infrastructure, and never mutates the true_map.

Movement scope
--------------
10AI enforces **local adjacency** (Manhattan distance ≤ 1) and the
``blocks_travel`` flag on individual tiles.  The ``travel_edges`` array in the
true_map is **not enforced** by this phase — edge-level travel constraints are
reserved for a future phase.  All tiles sharing a continent and within one
step of the current position are considered reachable unless they carry
``blocks_travel: true``.
"""

from __future__ import annotations

import copy
from typing import Any

# Direction → (dx, dy) using the same coordinate convention as fog_of_war.
DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
}

_REQUIRED_POSITION_FIELDS: frozenset[str] = frozenset({
    "agent_id", "continent_id", "region_id", "tile_id", "coordinates",
    "movement_mode", "travel_capabilities",
})


def _manhattan(a: dict, b: dict) -> int:
    """Manhattan distance between two coordinate dicts."""
    return abs(int(a.get("x", 0)) - int(b.get("x", 0))) + abs(
        int(a.get("y", 0)) - int(b.get("y", 0))
    )


def resolve_local_move(
    current_position: dict[str, Any],
    direction: str,
    true_map: dict[str, Any],
    *,
    destination_tile_id: str | None = None,
    tick: int = 0,
) -> dict[str, Any]:
    """Resolve a local movement action inside the hidden true_map.

    Parameters
    ----------
    current_position:
        Agent's current position dict (as produced by
        ``fog_of_war.create_active_position`` or a test fixture).
        Must contain ``coordinates`` (with numeric ``x`` and ``y``),
        ``continent_id``, ``tile_id``, ``region_id``, ``agent_id``,
        and ``travel_capabilities``.
    direction:
        One of the keys in :data:`DIRECTIONS` (``"north"``, ``"south"``,
        ``"east"``, ``"west"``, ``"northeast"``, ``"northwest"``,
        ``"southeast"``, ``"southwest"``).
    true_map:
        The full hidden true_map (read-only — never mutated).
    destination_tile_id:
        Optional explicit destination tile ID.  When provided, the function
        looks up the tile by its ID (instead of deriving the target from
        ``direction`` alone).  This enables testing of non-local moves
        (Manhattan distance > 1) and self-target moves.
    tick:
        Current simulation tick.  Must be a non-negative integer.
        Used in the returned ``new_position["last_moved_tick"]``.

    Returns
    -------
    dict
        Result dictionary with keys:

        - ``ok`` (bool) — whether movement was possible.
        - ``error`` (str | None) — human-readable failure reason.
        - ``new_position`` (dict | None) — full new position dict if
          successful.  ``None`` on failure.
        - ``tile_id`` (str | None) — destination tile_id.
        - ``territory_ref`` (str | None) — destination region_id.
        - ``before_ref`` (str | None) — ``"tile:<previous_tile_id>"``.
        - ``after_ref`` (str | None) — ``"tile:<new_tile_id>"``.
        - ``previous_tile_id`` (str | None)
        - ``previous_territory_ref`` (str | None)
        - ``previous_position`` (dict | None) — immutable copy of the
          input position.

    Raises
    ------
    ValueError
        If the position dict is missing required fields, the direction
        is unrecognised, coordinates lack numeric ``x`` or ``y``, or
        ``tick`` is not a non-negative integer.
    """
    # --- Validate inputs ---
    missing = _REQUIRED_POSITION_FIELDS - current_position.keys()
    if missing:
        raise ValueError(
            f"current_position missing required fields: {sorted(missing)}"
        )

    # Validate tick
    if not isinstance(tick, int) or tick < 0:
        raise ValueError(
            f"tick must be a non-negative integer, got {tick!r}"
        )

    direction_lower = direction.strip().lower()
    if direction_lower not in DIRECTIONS:
        raise ValueError(
            f"unrecognised direction {direction!r}; "
            f"expected one of {sorted(DIRECTIONS)}"
        )

    coords = current_position.get("coordinates")
    if not isinstance(coords, dict):
        raise ValueError("current_position.coordinates must be a dict")
    if not isinstance(coords.get("x"), (int, float)):
        raise ValueError("current_position.coordinates.x must be numeric")
    if not isinstance(coords.get("y"), (int, float)):
        raise ValueError("current_position.coordinates.y must be numeric")

    continent_id = current_position.get("continent_id")

    # --- Resolve destination tile ---
    if destination_tile_id is not None:
        # Look up by tile_id directly
        dest_tile: dict[str, Any] | None = None
        for tile in true_map.get("tiles", []):
            if tile.get("tile_id") == destination_tile_id:
                dest_tile = tile
                break
        if dest_tile is None:
            return {
                "ok": False,
                "error": f"no tile with id '{destination_tile_id}'",
                "new_position": None,
                "tile_id": None,
                "territory_ref": None,
                "before_ref": None,
                "after_ref": None,
                "previous_tile_id": current_position.get("tile_id"),
                "previous_territory_ref": current_position.get("region_id"),
                "previous_position": copy.deepcopy(current_position),
            }
        # Check same continent
        if dest_tile.get("continent_id") != continent_id:
            return {
                "ok": False,
                "error": f"cannot change continent to {dest_tile.get('continent_id')}",
                "new_position": None,
                "tile_id": dest_tile["tile_id"],
                "territory_ref": dest_tile.get("region_id"),
                "before_ref": None,
                "after_ref": None,
                "previous_tile_id": current_position.get("tile_id"),
                "previous_territory_ref": current_position.get("region_id"),
                "previous_position": copy.deepcopy(current_position),
            }
        # Check local adjacency
        distance = _manhattan(coords, dest_tile.get("coordinates", {}))
        if distance > 1:
            return {
                "ok": False,
                "error": (
                    f"destination too far (Manhattan distance {distance}); "
                    f"local moves must be adjacent"
                ),
                "new_position": None,
                "tile_id": dest_tile["tile_id"],
                "territory_ref": dest_tile.get("region_id"),
                "before_ref": None,
                "after_ref": None,
                "previous_tile_id": current_position.get("tile_id"),
                "previous_territory_ref": current_position.get("region_id"),
                "previous_position": copy.deepcopy(current_position),
            }
    else:
        # Derive destination from direction
        dx, dy = DIRECTIONS[direction_lower]
        new_x = coords["x"] + dx
        new_y = coords["y"] + dy

        dest_tile = None
        for tile in true_map.get("tiles", []):
            tc = tile.get("coordinates", {})
            if (tile.get("continent_id") == continent_id
                    and tc.get("x") == new_x
                    and tc.get("y") == new_y):
                dest_tile = tile
                break

        if dest_tile is None:
            return {
                "ok": False,
                "error": f"no tile at destination ({new_x}, {new_y})",
                "new_position": None,
                "tile_id": None,
                "territory_ref": None,
                "before_ref": None,
                "after_ref": None,
                "previous_tile_id": current_position.get("tile_id"),
                "previous_territory_ref": current_position.get("region_id"),
                "previous_position": copy.deepcopy(current_position),
            }

    # --- Common checks (apply to both lookup paths) ---

    if dest_tile.get("blocks_travel", False):
        return {
            "ok": False,
            "error": f"travel blocked at tile {dest_tile['tile_id']}",
            "new_position": None,
            "tile_id": dest_tile["tile_id"],
            "territory_ref": dest_tile.get("region_id"),
            "before_ref": None,
            "after_ref": None,
            "previous_tile_id": current_position.get("tile_id"),
            "previous_territory_ref": current_position.get("region_id"),
            "previous_position": copy.deepcopy(current_position),
        }

    if current_position.get("tile_id") == dest_tile["tile_id"]:
        return {
            "ok": False,
            "error": "already at destination tile",
            "new_position": None,
            "tile_id": dest_tile["tile_id"],
            "territory_ref": dest_tile.get("region_id"),
            "before_ref": None,
            "after_ref": None,
            "previous_tile_id": current_position.get("tile_id"),
            "previous_territory_ref": current_position.get("region_id"),
            "previous_position": copy.deepcopy(current_position),
        }

    # --- Build new position ---
    new_position = copy.deepcopy(current_position)
    new_position["tile_id"] = dest_tile["tile_id"]
    new_position["region_id"] = dest_tile["region_id"]
    new_position["coordinates"] = {
        "x": int(dest_tile["coordinates"]["x"]),
        "y": int(dest_tile["coordinates"]["y"]),
    }
    new_position["last_moved_tick"] = tick

    previous_tile_id = current_position.get("tile_id", "")
    new_tile_id = dest_tile["tile_id"]

    return {
        "ok": True,
        "error": None,
        "new_position": new_position,
        "tile_id": new_tile_id,
        "territory_ref": dest_tile.get("region_id", ""),
        "before_ref": f"tile:{previous_tile_id}",
        "after_ref": f"tile:{new_tile_id}",
        "previous_tile_id": previous_tile_id,
        "previous_territory_ref": current_position.get("region_id", ""),
        "previous_position": copy.deepcopy(current_position),
    }