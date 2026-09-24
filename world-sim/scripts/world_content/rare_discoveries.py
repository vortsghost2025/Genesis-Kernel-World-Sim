"""Rare discoveries - authored wonder content for the planetary world.

Eight unique, hand-written landmarks placed deterministically onto the
generated world far from everything the pair already knows. These are the
long-game payoffs: found weeks or months from now by ordinary walking.

Hard rules:

1. AUTHORED, NOT GENERATED. Names, kinds, and descriptions are written
   here by hand. The generator never invents wonders.
2. PLACEMENT IS DETERMINISTIC. Eligible tiles are filtered by terrain/
   water/continent rules and the pick is a hash over (world seed,
   landmark id). Same inputs -> same placements, every run.
3. NEVER ON KNOWN TILES. Any tile present in either agent's known map is
   ineligible; so is every tile within radius 8 of one (wonders should be
   earned by travel, not stumbled over on the doorstep).
4. NO DUPLICATE TILES. Each discovery occupies its own tile.
5. NO TOUCHING MYSTERIES. The two authored mysteries' tiles stay exactly
   as they are; a wonder may sit near one but never on it.
6. New landmark kinds come from the 10JC section-18 vocabulary additions
   (waterfall, great_lake, crater, canyon, cape, glacier,
   rift_escarpment) - their use here is the content proof for that
   vocabulary decision.

Output is data only: a list of landmark records plus their tile
landmark_ids updates, applied to a candidate map in memory by the caller.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

# ---- The wonders ----------------------------------------------------------

RARE_DISCOVERIES: list[dict[str, Any]] = [
    {
        "landmark_id": "lm_whisper_falls",
        "kind": "waterfall",
        "hidden_name": "Whisper Falls",
        "description": (
            "A thread of white water that falls so far it disappears into "
            "mist before it lands. Standing here, the sound arrives before "
            "the sight. The pool below is the clearest water you have ever "
            "seen."
        ),
        "placement": {"terrain": {"mountain"}, "min_elevation": 0.75,
                      "continent": "cont_a", "quadrant": "N"},
    },
    {
        "landmark_id": "lm_sleeping_fire",
        "kind": "crater",
        "hidden_name": "The Sleeping Fire",
        "description": (
            "A round mountain with its top folded inward like a sleeping "
            "mouth. The stones near the rim are dark and glassy, and the "
            "ground keeps a faint warmth even at night. Nothing here is "
            "burning. Something here once did."
        ),
        "placement": {"terrain": {"mountain"}, "min_elevation": 0.85,
                      "continent": "cont_b"},
    },
    {
        "landmark_id": "lm_deep_mouth",
        "kind": "cave_mouth",
        "hidden_name": "The Deep Mouth",
        "description": (
            "A doorway of stone, taller than any tree, opening into a hush "
            "that swallows footsteps whole. The air coming out of it is "
            "cool and smells of rain that fell before you were born."
        ),
        "placement": {"terrain": {"hill", "mountain"}, "min_elevation": 0.5,
                      "continent": "cont_a", "quadrant": "S"},
    },
    {
        "landmark_id": "lm_mirror_mere",
        "kind": "great_lake",
        "hidden_name": "The Mirror Mere",
        "description": (
            "A lake so still it decides to be the sky. Snow-capped stone "
            "stands at its edge and its reflection stands beneath it. "
            "Which one you are walking beside is briefly unclear."
        ),
        "placement": {"terrain": {"hill", "mountain"}, "brings_water": True,
                      "water": {"type": "lake", "drinkable": True},
                      "min_elevation": 0.6, "continent": "cont_b"},
    },
    {
        "landmark_id": "lm_kneeling_giant",
        "kind": "rock_formation",
        "hidden_name": "The Kneeling Giant",
        "description": (
            "A tower of layered stone bent at its middle as if bowing to "
            "the plain. Wind moves through its hollows and plays it, low "
            "and slow, like a horn heard from very far away."
        ),
        "placement": {"terrain": {"grassland", "hill"}, "continent": "cont_a",
                      "quadrant": "E"},
    },
    {
        "landmark_id": "lm_frozen_stair",
        "kind": "glacier",
        "hidden_name": "The Frozen Stair",
        "description": (
            "A river that stopped moving in one long instant and never "
            "started again. Blue ice in great steps, each one a season the "
            "world decided to keep. It creaks, rarely, like a settling "
            "house."
        ),
        "placement": {"terrain": {"mountain"}, "min_elevation": 0.9,
                      "continent": "cont_b"},
    },
    {
        "landmark_id": "lm_sundered_edge",
        "kind": "rift_escarpment",
        "hidden_name": "The Sundered Edge",
        "description": (
            "The plain simply ends. A wall of red stone falls away for "
            "what feels like forever, and on the far side, smaller than "
            "your thumb, the plain continues. The world broke here once, "
            "and never told anyone why."
        ),
        "placement": {"terrain": {"hill", "grassland"}, "continent": "cont_a",
                      "quadrant": "W"},
    },
    {
        "landmark_id": "lm_lantern_sound",
        "kind": "canyon",
        "hidden_name": "Lantern Sound",
        "description": (
            "A narrow crack between high walls where the last light of "
            "evening lands for a few minutes each day, turning the whole "
            "corridor to poured bronze. The rest of the time it waits in "
            "blue shadow, patient as a temple doorway."
        ),
        "placement": {"terrain": {"hill", "mountain"}, "continent": "cont_b"},
    },
]

# New landmark kinds used here, pending the 10JC section-18.5 confirmation.
NEW_KINDS_USED = {"waterfall", "crater", "cave_mouth", "great_lake",
                  "glacier", "rift_escarpment", "canyon"}

EXCLUSION_RADIUS = 8


def _eligible(tile: dict[str, Any], rule: dict[str, Any], known: set[str],
              center: tuple[float, float] | None, mystery_tiles: set[str]) -> bool:
    p = rule["placement"]
    if tile["tile_id"] in known or tile["tile_id"] in mystery_tiles:
        return False
    if tile.get("blocks_travel"):
        return False
    if p.get("continent") and tile["continent_id"] != p["continent"]:
        return False
    if p.get("terrain") and tile["terrain"] not in p["terrain"]:
        return False
    if p.get("min_elevation") is not None and tile.get("elevation", 0) < p["min_elevation"]:
        return False
    if p.get("needs_water") and not tile.get("water") and not p.get("brings_water"):
        return False
    if p.get("brings_water") and tile.get("water"):
        return False  # the wonder IS the water; it does not displace any
    if tile.get("landmark_ids"):
        return False  # a wonder does not share its tile
    # quadrant filter (relative to continent box center, screen coords)
    q = p.get("quadrant")
    if q and center is not None:
        cx, cy = center
        dx, dy = tile["coordinates"]["x"] - cx, tile["coordinates"]["y"] - cy
        ok = {"N": dy < 0 and abs(dy) >= abs(dx), "S": dy > 0 and abs(dy) >= abs(dx),
              "E": dx > 0 and abs(dx) >= abs(dy), "W": dx < 0 and abs(dx) >= abs(dy)}[q]
        if not ok:
            return False
    return True


def place_discoveries(
    true_map: dict[str, Any],
    known_tile_ids: set[str],
    seed: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the wonder pack to a candidate map copy. Data only.

    Returns (new_map, manifest). Raises ValueError if any wonder cannot be
    placed honestly (no eligible tile).
    """
    out = copy.deepcopy(true_map)
    cont_tiles: dict[str, list[dict]] = {}
    for t in out["tiles"]:
        cont_tiles.setdefault(t["continent_id"], []).append(t)

    mystery_tiles = {m["tile_id"] for m in out.get("mysteries", [])}
    by_id = {t["tile_id"]: t for t in out["tiles"]}

    # expanded known set: known tiles + radius EXCLUSION_RADIUS around them
    known_coords = [by_id[k]["coordinates"] for k in known_tile_ids if k in by_id]

    def far_from_known(t: dict) -> bool:
        x, y = t["coordinates"]["x"], t["coordinates"]["y"]
        return all(abs(x - c["x"]) + abs(y - c["y"]) > EXCLUSION_RADIUS
                   for c in known_coords)

    used: set[str] = set()
    centers: dict[str, tuple[float, float]] = {}
    for cid, cts in cont_tiles.items():
        xs = [t["coordinates"]["x"] for t in cts]
        ys = [t["coordinates"]["y"] for t in cts]
        centers[cid] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    placements = []
    for wonder in RARE_DISCOVERIES:
        cont = wonder["placement"].get("continent")
        pool = [
            t for t in cont_tiles.get(cont, [])
            if t["tile_id"] not in used
            and _eligible(t, wonder, known_tile_ids, centers.get(cont),
                          mystery_tiles)
            and far_from_known(t)
        ]
        if not pool:
            raise ValueError(f"no eligible tile for {wonder['landmark_id']}")
        h = hashlib.sha256(f"{seed}|{wonder['landmark_id']}".encode()).hexdigest()
        pick = pool[int(h[:8], 16) % len(pool)]
        used.add(pick["tile_id"])

        rec = {
            "landmark_id": wonder["landmark_id"],
            "continent_id": pick["continent_id"],
            "tile_id": pick["tile_id"],
            "kind": wonder["kind"],
            "hidden_name": wonder["hidden_name"],
            "description": wonder["description"],
        }
        out["landmarks"].append(rec)
        pick["landmark_ids"] = list(pick.get("landmark_ids", [])) + [wonder["landmark_id"]]
        if wonder["placement"].get("brings_water"):
            pick["water"] = dict(wonder["placement"]["water"])
        placements.append({
            "landmark_id": wonder["landmark_id"],
            "tile_id": pick["tile_id"],
            "coordinates": dict(pick["coordinates"]),
            "continent_id": pick["continent_id"],
            "terrain": pick["terrain"],
        })

    manifest = {
        "pack": "rare_discoveries_v1",
        "seed": seed,
        "count": len(placements),
        "placements": placements,
        "new_kinds_used": sorted(NEW_KINDS_USED),
        "exclusion_radius_around_known": EXCLUSION_RADIUS,
    }
    return out, manifest
