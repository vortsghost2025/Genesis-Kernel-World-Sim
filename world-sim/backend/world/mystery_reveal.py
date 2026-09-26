"""Mystery reveal mechanic - pure design module (scratch-only, no runtime).

Side-branch content work for the planetary era. The true map carries 2
authored mysteries (reveal_threshold=3 each); the fog engine exposes NO
mystery data and the runtime has NO reveal path. This module defines how
mysteries are discovered, hinted, and revealed - as pure functions only.

Design rules (hard):

1. NO LEAK BEFORE THRESHOLD. An agent that has never occupied the
   mystery's tile receives nothing - no id, no kind, no hint text. The
   only channel open before reveal is first-person experience: standing
   on the tile, again and again.
2. EXPOSURE = OCCUPANCY. Only being *on* the tile accrues evidence
   (consistent with the 10IZ conservative replay rule: "never infer a
   visit merely from visibility"). Seeing the tile from a neighbor tile
   accrues nothing.
3. PROGRESSIVE HINTS ARE VAGUE UNTIL REVEAL. Exposure 1..threshold-1
   produces atmospheric hints that never name the landmark, never carry
   an identifier, and never assert a fact.
4. REVEAL IS A RECORDED CONVERSION. At exposure >= threshold the mystery
   becomes a known landmark (kind + description + name) inside that
   agent's known map. The true map is untouched.
5. PER-AGENT. Adam and Eve each hold their own evidence. One agent's
   reveal gives the other nothing.
6. FAIL CLOSED. Unknown mystery kind -> no hints, no reveal, no crash.

Storage (additive, schema-7B.1 compatible): evidence accrues in
``known_map["myths"]`` - the schema field reserved for unconfirmed lore.
Each mystery owns at most one myth record keyed ``myth_<mystery_id>``.
On reveal the myth flips to ``status="confirmed"`` and the landmark
enters ``known_map["known_landmarks"]``.

Cognition projection: hint text is surfaced under the key
``unsettled_reports`` (implementation words like ``mystery_id`` /
``true_landmark_id`` never appear in agent-facing output).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Authored content library. One ladder + reveal payload per mystery kind.
# Texts are second-person, present tense, and contain NO identifiers.
# ---------------------------------------------------------------------------

MYSTERY_LIBRARY: dict[str, dict[str, Any]] = {
    "repeating_sound": {
        "hints": {
            1: (
                "Sometimes, when the wind drops, you think you hear a tone "
                "beneath the world. It stops when you listen for it."
            ),
            2: (
                "The sound again. Patient. Repeating. Steady as a heartbeat. "
                "It is not wind. It is in the stone."
            ),
        },
        "reveal": {
            "id_suffix": "singing_stone",
            "kind": "singing_rock",
            "name": "The Singing Stone",
            "description": (
                "A slab of summit rock that hums a single repeating note. "
                "Warm to the palm. The tone steadies when you are calm and "
                "wavers when you are afraid - as if the mountain keeps time "
                "for whoever stands here."
            ),
        },
    },
    "distant_light": {
        "hints": {
            1: (
                "Far out where the sea meets the sky, something glimmers "
                "after sunset. It is gone by the time you look twice."
            ),
            2: (
                "The light again, from the same place on the horizon. It does "
                "not drift like a star. It waits."
            ),
        },
        "reveal": {
            "id_suffix": "lantern_west",
            "kind": "watching_light",
            "name": "The Lantern of the West",
            "description": (
                "A steady light on the far cliff edge, visible whenever the "
                "sky is dark enough to hold it. It does not answer. It does "
                "not go out. It has been waiting longer than you have been "
                "walking."
            ),
        },
    },
}

# Sanitized terms that may appear in agent-facing text. Anything not in the
# hint/reveal strings above is internal-only.
FORBIDDEN_PROJECTION_SUBSTRINGS = (
    "mystery", "mystery_id", "true_map", "true_landmark", "known_map",
    "threshold", "mst_",
)


def _myth_id(mystery_id: str) -> str:
    return f"myth_{mystery_id}"


def landmark_id_for(mystery_id: str) -> str:
    """Deterministic landmark id a mystery reveals into."""
    kind = None
    # derive kind from the library by matching the known mystery id pattern
    # caller passes full mystery dict where possible; fallback generic:
    return f"lm_mystery_{mystery_id}"


def get_myth_record(known_map: dict[str, Any], mystery_id: str) -> dict | None:
    for m in known_map.get("myths", []):
        if m.get("id") == _myth_id(mystery_id):
            return m
    return None


def accrue_mystery_evidence(
    known_map: dict[str, Any],
    mystery: dict[str, Any],
    position: dict[str, Any],
    tick: int,
) -> dict[str, Any]:
    """Accrue one unit of evidence if the agent OCCUPIES the mystery tile.

    Pure w.r.t. inputs: returns (new_known_map, accrued) - caller
    persists. Occupancy only; adjacency and visibility accrue nothing.
    At most one accrual per tick per mystery per agent.
    """
    import copy

    if mystery.get("kind") not in MYSTERY_LIBRARY:
        return copy.deepcopy(known_map), False
    tile_id = mystery.get("tile_id")
    if not tile_id or (position or {}).get("tile_id") != tile_id:
        return copy.deepcopy(known_map), False

    km = copy.deepcopy(known_map)
    km.setdefault("myths", [])
    mid = _myth_id(mystery["mystery_id"])
    rec = get_myth_record(km, mystery["mystery_id"])
    if rec is None:
        rec = {
            "id": mid,
            "created_tick": int(tick),
            "claim": MYSTERY_LIBRARY[mystery["kind"]]["hints"][1],
            "basis": f"experience on {tile_id}",
            "confidence": 0.25,
            "status": "gathering",
            "evidence": 0,
            "last_evidence_tick": None,
        }
        km["myths"].append(rec)
    if rec.get("last_evidence_tick") == tick:
        return km, False  # already accrued this tick
    rec["evidence"] = int(rec.get("evidence", 0)) + 1
    rec["last_evidence_tick"] = int(tick)
    # deepen the claim text as evidence grows (still pre-reveal)
    hints = MYSTERY_LIBRARY[mystery["kind"]]["hints"]
    if rec["evidence"] in hints:
        rec["claim"] = hints[rec["evidence"]]
        rec["confidence"] = min(0.9, 0.25 + 0.2 * rec["evidence"])
    return km, True


def mystery_revealed(known_map: dict[str, Any], mystery: dict[str, Any]) -> bool:
    lm_id = landmark_id_for(mystery.get("mystery_id", ""))
    return lm_id in known_map.get("known_landmarks", {})


def check_reveal(known_map: dict[str, Any], mystery: dict[str, Any]) -> bool:
    """True iff accrued evidence meets the mystery's reveal threshold."""
    rec = get_myth_record(known_map, mystery.get("mystery_id", ""))
    if not rec:
        return False
    return int(rec.get("evidence", 0)) >= int(mystery.get("reveal_threshold", 1))


def apply_reveal(
    known_map: dict[str, Any],
    mystery: dict[str, Any],
    tick: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """If the threshold is met, convert the mystery into a known landmark.

    Returns (new_known_map, revealed_landmark_or_None). Idempotent: a
    second call changes nothing and returns None.
    """
    import copy

    kind = mystery.get("kind")
    lib = MYSTERY_LIBRARY.get(kind)
    if lib is None:
        return copy.deepcopy(known_map), None
    km = copy.deepcopy(known_map)
    if mystery_revealed(km, mystery):
        return km, None
    if not check_reveal(km, mystery):
        return km, None

    rv = lib["reveal"]
    lm_id = landmark_id_for(mystery["mystery_id"])
    km.setdefault("known_landmarks", {})[lm_id] = {
        "true_landmark_id": lm_id,
        "first_observed_tick": int(tick),
        "last_observed_tick": int(tick),
        "kind": rv["kind"],
        "confidence": 1.0,
        "description": f"{rv['name']}. {rv['description']}",
    }
    rec = get_myth_record(km, mystery["mystery_id"])
    if rec is not None:
        rec["status"] = "confirmed"
        rec["confidence"] = 1.0
    return km, km["known_landmarks"][lm_id]


def project_unsettled_reports(known_map: dict[str, Any]) -> list[dict[str, Any]]:
    """Agent-facing projection: vague, identifier-free, gathered-only.

    Returns a list of {"report": str, "certainty": float}. Confirmed
    myths are no longer 'unsettled' - they are landmarks, carried by the
    landmark projection instead. Nothing here leaks the mystery system.
    """
    out = []
    for m in known_map.get("myths", []):
        if m.get("status") != "gathering":
            continue
        claim = str(m.get("claim", ""))
        lowered = claim.lower()
        if any(bad in lowered or bad in claim for bad in FORBIDDEN_PROJECTION_SUBSTRINGS):
            continue  # fail closed: a contaminated claim is dropped, not shown
        out.append({"report": claim, "certainty": float(m.get("confidence", 0.25))})
    return out


def project_discoveries(known_map: dict[str, Any]) -> list[dict[str, Any]]:
    """Agent-facing projection of REVEALED mystery landmarks.

    Emits only landmarks the agent earned by reaching threshold
    (id prefix ``lm_mystery_``): ``{kind, name_and_description}``.
    Ordinary observed landmarks are excluded - they are carried by the
    normal landmark projection. Contaminated records are dropped, never
    shown.
    """
    out = []
    for lm_id, lm in (known_map.get("known_landmarks") or {}).items():
        if not str(lm_id).startswith("lm_mystery_"):
            continue
        if not isinstance(lm, dict):
            continue
        desc = str(lm.get("description", ""))
        lowered = desc.lower()
        if any(bad in lowered or bad in desc for bad in FORBIDDEN_PROJECTION_SUBSTRINGS):
            continue  # fail closed
        out.append({
            "kind": str(lm.get("kind", "")),
            "name_and_description": desc,
        })
    return out
