"""Phase 10FM — First Pair Runtime Orchestrator.

Coordinates bounded heartbeat cycles for Adam and Eve. Mutations flow through
`FirstPairPersistenceStore`; the store and all its children are injected from
the outside — no module-global paths.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitiveCycle,
)
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
)
from backend.world.first_pair_cognition_stub import (
    AlternatingStubBackend,
    DeterministicStubBackend,
)
from backend.world.first_pair_persistence import (
    CapabilityGrantRecord,
    CharterVersionRecord,
    FirstPairPersistenceStore,
    GoalRecord,
    HeartbeatRecord,
    IdentityRecord,
    PublicObjectRecord,
    QuestionRecord,
    RuntimePolicyRecord,
    WorldStateRecord,
    append_charter_version,
    append_agent_question_proposal,
    append_heartbeat,
    append_memory_selection_manifest,
    append_summary,

    derive_relationship_event_ids,
    derive_summaries_for_omitted,
    detect_recurrence,
    filter_syntheses_for_injection,
    SYNTH_METHOD_V1,
    get_adjacent_tiles,

    initialize_first_pair_state,


    load_capability_grant,
    load_charter_versions,
    load_continuity,
    load_extra_capability_grants,
    load_goals,
    load_heartbeat_history,
    load_inventory,
    add_to_inventory,
    load_latest_charter,
    load_memory,
    load_memory_selection_manifests,
    load_agent_question_proposals,
    load_operator_messages,
    load_physics_seen,
    load_questions,
    modify_inventory_batch,
    save_agent_question_proposals,
    load_relationship_events,
    load_runtime_policy,
    load_summaries,
    maybe_record_relationship_event,
    prune_continuity,
    record_physics_seen,
    render_continuity,
    save_continuity,
    save_goals,
    save_memory,
    save_world_state,
    select_bounded_public_messages,
    select_bounded_relationship_events,
    select_human_context,
    select_private_memories,
    update_continuity,
    validate_persistence_integrity,
)
from backend.world.question_proposal import QuestionProposal
from backend.world.world_event_sanitizer import sanitize_public_text
from backend.world import survival
from backend.world import wildlife
from backend.world import insects
from backend.world import fauna
from backend.world import fauna_interactions
from backend.world.world_pressure import (
    GATHER_YIELD,
    PHYSICS_VERSION,
)
from backend.world.first_pair_fog_adapter import (
    FogAdapterError,
    cognition_safe_observation,
    derive_topology,
    fog_gate_active,
    load_known_map,
    load_true_map,
    merge_observation,
    persist_known_map,
)
from backend.world.mystery_reveal import (
    accrue_mystery_evidence,
    apply_reveal,
    project_discoveries,
    project_unsettled_reports,
)

_DEFAULT_HEARTBEAT_LIMIT = 10
MAX_ACTIVE_GOALS_EXPOSED: int = 8
STALE_GOAL_AGE_HB: int = 500

# Phase 10NX: the distance within which an animal can actually be acted on.
# offer_food, strike_animal and strike_snake all require the target on an
# adjacent-or-same tile (Chebyshev <= 1). The fauna affordance uses this same
# constant so it can never advertise an animal the action would reject -- which
# is exactly what happened when the affordance carried its own, wider guess and
# West Eve spent two heartbeats offering food to a horse three tiles away. One
# constant, one predicate, both sides.
FAUNA_ACTION_REACH: int = 1


# Phase 10NX: leading words that restate intent without changing it. An agent's
# goals are written in its own voice ("Continue exploring ...") and the same
# purpose reappears as "Explore ...", "Please continue to explore ...". Stripping
# these is what lets restatements collapse.
def _stem_token(token: str) -> str:
    """Reduce a content token to a comparable root (no external stemmer)."""
    if len(token) <= 3:
        return token
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            stem = token[: -len(suffix)]
            # "gathering" -> "gather", "exploring" -> "explor", "explores" -> "explor"
            if suffix in ("ing", "ed") and stem.endswith("i"):
                stem = stem[:-1]
            # "explore" and "exploring" must converge on the same root.
            if stem.endswith("e") and len(stem) > 4:
                stem = stem[:-1]
            return stem
    if token.endswith("e") and len(token) > 4:
        return token[:-1]
    return token


def _goal_created(g) -> int:
    """created_heartbeat from a GoalRecord or a plain dict."""
    v = getattr(g, "created_heartbeat", None)
    if v is None and isinstance(g, dict):
        v = g.get("created_heartbeat")
    return v or 0


def _goal_description(g) -> str:
    """description from a GoalRecord or a plain dict."""
    d = getattr(g, "description", None)
    if d is None and isinstance(g, dict):
        d = g.get("description")
    return d or ""


_RESTATEMENT_PREFIXES = (
    "please",
    "continue",
    "continues",
    "continuing",
    "keep",
    "keeps",
    "keeping",
    "begin",
    "begins",
    "beginning",
    "start",
    "starts",
    "starting",
    "proceed",
    "proceeds",
    "proceeding",
    "resume",
    "resumes",
    "resuming",
    "restart",
    "restarts",
    "restarting",
    "attempt",
    "attempts",
    "attempting",
)


def _goal_signature(description: str) -> frozenset[str]:
    """Order-insensitive content signature for restatement detection.

    Phase 10NX. The live East lane carried 34 in_progress goals, several of which
    were the same purpose written slightly differently ("Continue exploring hill
    and grassland terrain, gather stone" vs "Continue exploring hill terrain and
    gather stone and wild_berries"). Exact-string dedup could not collapse them,
    so they accumulated and filled the model's 8-slot context window with eight
    copies of one intent.

    The signature is a frozenset of content tokens, so word order, punctuation,
    leading imperative verbs and connector filler all stop mattering.
    """
    text = (description or "").strip().lower()
    # Punctuation becomes spaces: "exploring, and gathering" == "exploring and gathering".
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    tokens = text.split()

    # Strip leading restatement prefixes on the RAW tokens. This must happen
    # before stemming: stemming turns "continue" into "continu", which no longer
    # matches the prefix table and would survive as a bogus content token.
    changed = True
    while changed:
        changed = False
        if tokens and tokens[0] in _RESTATEMENT_PREFIXES:
            tokens = tokens[1:]
            changed = True
        if tokens and tokens[0] in ("to", "for", "with", "the", "a", "an", "and"):
            tokens = tokens[1:]
            changed = True

    tokens = [_stem_token(t) for t in tokens]

    stop = {"the", "and", "for", "with", "from", "into", "that", "this", "then",
            "our", "all", "near", "area", "towards", "toward"}
    kept = [t for t in tokens if t not in stop and len(t) > 2]
    return frozenset(kept)


def _is_tile_scoped_goal(description: str) -> bool:
    """True when a goal names specific tiles, which makes it precise."""
    return bool(re.findall(r"cont_[a-z0-9_\-]+", description or ""))


def _is_operator_standby_goal(description: str) -> bool:
    """True when a goal is waiting on the operator rather than on the world."""
    d = (description or "").lower()
    return any(k in d for k in ("await operator", "awaiting operator",
                                "waiting for operator", "await final confirmation"))


def goal_should_retire(
    goal,
    sibling_goals: list,
    heartbeat_number: int,
    known_tiles: set,
    inventory: dict,
    has_pending_question: bool,
) -> bool:
    """Phase 10NX Rule 4: retire aged restatements and dead operator standbys.

    Retires only when ALL hold:
      * age exceeds STALE_GOAL_AGE_HB (young goals are never touched);
      * the goal is a restatement -- an earlier sibling shares its signature;
      * it is NOT the newest goal of that signature, so the live intent survives;
      * it names no specific tiles (Rule 1 still owns those);
    or:
      * it is an unmatched operator-standby goal, aged past STALE_GOAL_AGE_HB,
        with no open question pending (a pending question is the legitimate path
        to the operator and must not be closed by goal retirement).

    The newest-restatement rule is what preserves the compound-goal case that Rule
    2's own documentation warns about: "explore and gather stone" cannot lose its
    exploration half, because the newest statement of that purpose always stays.
    """
    desc = _goal_description(goal)
    created = _goal_created(goal)
    age = heartbeat_number - created

    if age <= STALE_GOAL_AGE_HB:
        return False

    if _is_operator_standby_goal(desc):
        return not has_pending_question

    if _is_tile_scoped_goal(desc):
        return False

    mine = _goal_signature(desc)
    peers = [g for g in sibling_goals if _goal_signature(_goal_description(g)) == mine]
    if len(peers) <= 1:
        # A unique goal is not a restatement.
        return False

    # Retire only when a NEWER peer exists: this goal is a stale restatement of
    # an intent the agent has stated more recently, so it has been superseded.
    return any(_goal_created(g) > created for g in peers)


def _select_diverse_active_goals(active_goals: list, now_hb: int | None = None) -> list:
    """Phase 10NX: expose one goal per signature instead of the last MAX.

    The old slice took the last MAX_ACTIVE_GOALS_EXPOSED goals verbatim. Because
    accumulation is chronological and dominated by restatements, that window was
    always eight copies of the newest intent, so the model read a menu with one
    item. This takes the newest goal of each signature, preserving chronological
    order, so the window shows up to MAX distinct intents at the same budget.
    """
    newest_by_signature: dict[frozenset[str], object] = {}
    for g in active_goals:
        sig = _goal_signature(_goal_description(g))
        prev = newest_by_signature.get(sig)
        if prev is None or _goal_created(g) > _goal_created(prev):
            newest_by_signature[sig] = g

    chosen = sorted(newest_by_signature.values(), key=_goal_created)
    return chosen[-MAX_ACTIVE_GOALS_EXPOSED:]


DEFAULT_GATHER_RETIRE_THRESHOLDS: dict[str, int] = {
    "stone": 20,
    "wild_berries": 20,
    "wood": 10,
    "clay": 10,
    "fiber_plants": 10,
    "edible_roots": 10,
    "mushrooms": 10,
    "iron_ore": 5,
    "flint": 5,
    "sand": 10,
}

# Phase 10KM: structural builds are load-bearing. A shelter/hut/cabin/roof
# carries weight, so it needs hewn structural timber -- which in turn needs a
# tree felled with an axe or knapped blade, which needs a crafted tool, which
# needs a crafting surface. Campfires and other non-structural types keep
# their existing material rules: fire must stay cheap.
_STRUCTURAL_TIMBER_MIN = {
    "shelter": 2,
    "cabin": 3,
    "hut": 2,
    "roof": 1,
}

# Attaching a room to an existing structure shares walls, so the structural
# component is discounted. Half the timber minimum, rounding up.
_ADDON_STRUCTURAL_DISCOUNT_DIVISOR = 2

# ---------------------------------------------------------------------------
# Phase 10PW: structure rungs and staged construction.
#
# `object_type` used to be a free-form string matched by substring against
# `_STRUCTURAL_TIMBER_MIN`, so an agent could declare "house" and pay one wood
# for a full shelter. These tables close that hole: a small closed vocabulary
# of roofed structures, each with a real material floor, a footprint weight,
# and an exact per-stage spend plan so construction is watchable.
#
# `floor` is a MINIMUM DECLARED amount (10KM's honest-materials seam), not a
# spend list: the agent may declare more, and every stage still validates
# against holdings before anything is applied.
# ---------------------------------------------------------------------------

_CONSTRUCTION_STAGES = ("foundation", "frame", "walls", "roofed", "finished")
# A project shelters from `roofed` onward; `foundation`/`frame`/`walls` do not.
_SHELTERING_STAGES = frozenset({"roofed", "finished"})

_STAGE_MATERIAL_SHARE = {
    "foundation": 0.30,
    "frame": 0.25,
    "walls": 0.20,
    "roofed": 0.15,
    "finished": 0.10,
}

_STRUCTURE_RUNGS = {
    "lean-to": {
        "rung": 1, "weight": 1, "floor": {"timber": 1},
        "effects": "shelter from cold",
    },
    "hut": {
        "rung": 2, "weight": 2, "floor": {"timber": 2, "wood": 2},
        "effects": "walls and a doorway; an attached room shares them",
    },
    "cabin": {
        "rung": 3, "weight": 2, "floor": {"timber": 3, "stone": 4},
        "effects": "door and interior; one cellar slot",
    },
    "house": {
        "rung": 4, "weight": 3, "floor": {"timber": 4, "stone": 6, "clay": 4},
        "effects": "hearth slot: cooking on the tile",
    },
    "longhouse": {
        "rung": 5, "weight": 4, "floor": {"timber": 8, "stone": 10, "wood": 6},
        "effects": "campaign build: cellar budget doubled",
    },
    # Phase 10QF: the ladder turns from bigger to more capable. A cistern is
    # a lined pit, not a building - almost no timber, a lot of stone and clay
    # - and its worth is that WATER CAN LIVE AT HOME. Measured 2026-11-12:
    # three of four agents had collapsed at thirst 100, and not one object in
    # either lane had ever held a unit of water, so a collapsed body could
    # only be helped by a partner who walked it there.
    "cistern": {
        "rung": 6, "weight": 2, "floor": {"timber": 2, "stone": 8, "clay": 6},
        "effects": "holds fresh water for the home; a filled cistern makes its tile drinkable",
    },
}

# Dwellings already in the live lanes. Mapped to their rung so existing objects
# are grandfathered rather than retroactively re-priced; their floors stay the
# ones `_STRUCTURAL_TIMBER_MIN` has always enforced.
#
# `wall` and `roof` are deliberately NOT here. They are structural COMPONENTS,
# not dwellings: a dry-stone wall spends exactly the materials it declares and
# atomic, and `roof`'s load-bearing timber floor is enforced by
# `_STRUCTURAL_TIMBER_MIN`. Making them runged staged projects broke the build
# layer's contract (tests/test_world_pressure.py) that a declared materials
# dict is what an object costs.
_LEGACY_TYPE_RUNG = {
    "shelter": 1, "tent": 1, "lean": 1, "lean_to": 1,
    "leanto": 1, "shack": 1, "hut": 2, "cabin": 3,
}

_LEGACY_TYPE_FLOOR = {
    "shelter": {"timber": 2}, "hut": {"timber": 2},
    "cabin": {"timber": 3},
    "tent": {"timber": 1}, "lean": {"timber": 1}, "lean_to": {"timber": 1},
    "leanto": {"timber": 1}, "shack": {"timber": 1},
}


# Types the world already accepts as NOT roofed structures (census of both live
# lanes, 2026-11-10). These keep their existing rules: fire and containers stay
# cheap. Anything outside BOTH this set and the rung table is a novel free
# string and is rejected naming the legal structure set -- that is the hole
# where "house" with one wood bought a full shelter.
_NON_STRUCTURAL_TYPE_TERMS = (
    "campfire", "fire", "hearth", "forge", "furnace", "oven", "brazier",
    "crafting_surface", "workbench", "workshop", "anvil",
    "garden", "storage", "container", "cache", "chest", "barrel", "crate",
    "box", "basket", "well", "cellar_pot", "landmark", "road", "pathway",
    "fence", "wall_post", "ladder", "tool", "furniture", "bed", "table",
    "chair", "cart", "signpost", "monument", "cairn", "tower_foundation",
    "food_processor", "processor", "rack", "shelf", "planter", "field",
    "pen", "corral", "stable_post", "bridge_post", "dock",
)


def _is_roofed_type(object_type: str) -> bool:
    """True when a declared type is a roofed structure.

    Phase 10PW: the rung table is the authority, so `house` and `longhouse`
    are recognised as roofed without every caller carrying its own substring
    list. The legacy kinds keep working for objects that predate the rungs.
    """
    if _structure_rung_of(object_type) is not None:
        return True
    otype = str(object_type or "").lower()
    return any(kind in otype for kind in (
        "shelter", "hut", "wall", "roof", "cabin", "tent", "lean",
        "cave", "cavern", "overhang", "grotto", "burrow", "stable", "cellar",
    ))


def _is_structural_component_type(object_type: str) -> bool:
    """True for a load-bearing component that is not a dwelling.

    Walls, roofs and their kin keep the atomic build contract: the agent
    declares a materials dict and pays exactly that, with no rung, no staging
    and no effects. `roof` still faces `_STRUCTURAL_TIMBER_MIN`.
    """
    lowered = str(object_type or "").strip().lower()
    if not lowered:
        return False
    return any(term in lowered for term in _STRUCTURAL_COMPONENT_TYPES)


def _is_non_structural_type(object_type: str) -> bool:
    lowered = str(object_type or "").strip().lower()
    if not lowered:
        return True
    return any(term in lowered for term in _NON_STRUCTURAL_TYPE_TERMS)

_STRUCTURE_RUNG_NAMES = ", ".join(sorted(_STRUCTURE_RUNGS))

# Structural COMPONENTS: load-bearing parts an agent builds, but not dwellings.
# They pass the rung gate, keep their existing atomic build contract (declared
# materials are the whole cost), and keep `_STRUCTURAL_TIMBER_MIN`'s floor
# (`roof` needs 1 timber). They are not staged and have no rung effects.
_STRUCTURAL_COMPONENT_TYPES = (
    "wall", "roof", "fence", "door", "floor", "thatch",
)


def _stage_material_plan(floor: dict) -> dict:
    """Exact per-stage split of a rung floor.

    Integer floors per kind with the remainder handed to the earliest stages,
    so the stages always sum to exactly the floor: the campaign costs the
    advertised amount, spread across visible steps.
    """
    plan = {stage: {} for stage in _CONSTRUCTION_STAGES}
    for kind, total in (floor or {}).items():
        total = int(total or 0)
        if total <= 0:
            continue
        raw = {stage: int(total * _STAGE_MATERIAL_SHARE[stage])
               for stage in _CONSTRUCTION_STAGES}
        left = total - sum(raw.values())
        for stage in _CONSTRUCTION_STAGES:
            if left <= 0:
                break
            raw[stage] += 1
            left -= 1
        for stage, amount in raw.items():
            if amount:
                plan[stage][kind] = amount
    return plan


def _structure_rung_of(object_type: str) -> dict | None:
    """Rung record for a declared structure type, or None if unrecognised."""
    lowered = str(object_type or "").strip().lower()
    if not lowered:
        return None
    for name, record in _STRUCTURE_RUNGS.items():
        if lowered == name or lowered.replace("_", "-") == name:
            out = dict(record)
            out["legacy"] = False
            return out
    for name, rung in _LEGACY_TYPE_RUNG.items():
        if lowered == name or lowered.replace("_", "-") == name.replace("_", "-"):
            out = dict(_STRUCTURE_RUNGS.get(
                next((n for n, r in _STRUCTURE_RUNGS.items() if r["rung"] == rung),
                     "lean-to")))
            out["rung"] = rung
            out["floor"] = dict(_LEGACY_TYPE_FLOOR.get(name, {"timber": 1}))
            out["legacy"] = True
            out["declared_name"] = name
            return out
    return None


# Phase 10PJ: thermal physics scale with a roofed footprint network, not
# with the raw number of shelter objects. One compact roofed line is one
# larger home; scattered duplicates remain small.
#
# Phase 10QC: the table used to END at footprint 8, which meant West's
# 46-structure settlement had already collected the final answer and no
# further building could change anything. Four rows are appended; the five
# 10PJ rows are untouched and pinned verbatim by tests/test_rung_payoff.py.
_HOME_NETWORK_TIERS = (
    (1, 45.0, 0.45, 1.00, 0.40, 0.10),
    (2, 52.0, 0.30, 1.25, 0.55, 0.12),
    (3, 62.0, 0.18, 1.50, 0.70, 0.15),
    (5, 68.0, 0.14, 1.75, 0.90, 0.18),
    (8, 75.0, 0.10, 2.00, 1.10, 0.22),
    (12, 80.0, 0.09, 2.20, 1.25, 0.24),
    (18, 84.0, 0.08, 2.40, 1.40, 0.26),
    (26, 88.0, 0.07, 2.60, 1.55, 0.28),
    (36, 92.0, 0.06, 2.80, 1.70, 0.30),
)
_CELLAR_FOOD_BUDGET_PER_FOOTPRINT = 20

# Phase 10QF: how much water one cistern holds. The first object in the
# world whose capacity is measured in units someone carried home.
_CISTERN_WATER_CAPACITY = 20

# Phase 10QC: roofed tiles past this many stop adding warmth. The operator
# has been rejecting the "15 single houses beside each other" settlement
# shape since 10PH; until now an extra shack always paid +1 footprint
# forever, so the rational build stayed a shack. A rung upgrade still pays.
_FOOTPRINT_SATURATION = 12

# Phase 10QC: the tier bonus for the network's HIGHEST rung. 10PU section 5
# promised `max(footprint_units, rung_weight)` and 10PW shipped `rung_weight`
# written into the envelope and read by nothing, so a house and the three
# lean-tos it replaces were worth exactly the same roofed units. These make
# one proper home outrank the shacks it displaces:
#   lean-to 1 + 0 = 1    hut 1 + 2 = 3     cabin 2 + 4 = 6
#   house   3 + 7 = 10   longhouse 4 + 11 = 15
# One house (tier weight 10, comfort floor 75) clears seven lean-tos
# (7 units, floor 68), which is the whole point of the change.
_RUNG_TIER_BONUS = {1: 0, 2: 2, 3: 4, 4: 7, 5: 11, 6: 13}


def _home_tier_weight(footprint: int, best_rung: int) -> int:
    """Map roofed footprint and the network's best rung to a tier weight.

    What a home IS dominates over how many tiles it covers, and the tile
    count saturates. Both halves are deliberate; see _RUNG_TIER_BONUS.
    """
    footprint = max(0, int(footprint or 0))
    best_rung = max(1, min(max(_RUNG_TIER_BONUS), int(best_rung or 1)))
    return min(footprint, _FOOTPRINT_SATURATION) + _RUNG_TIER_BONUS[best_rung]


def _home_network_tier(footprint: int) -> tuple[float, float, float, float, float]:
    """Map roofed footprint to warmth floor, cold decay, rest regen,
    downed regen, and warmth approach rates."""
    footprint = max(0, int(footprint or 0))
    params = _HOME_NETWORK_TIERS[0][1:]
    for threshold, floor, decay, regen, downed, approach in _HOME_NETWORK_TIERS:
        if footprint >= threshold:
            params = (floor, decay, regen, downed, approach)
    return params


def _roofed_structure_weight(object_type: str, record: dict | None = None) -> int:
    """Roofed footprint weight for a public object type.

    A `cabin` occupies a larger roofed volume than a lean-to or hut, and a
    rung-4 `house` weighs more than either (Phase 10PW). Duplicate structures
    on one tile do not multiply in the caller, which keeps the largest weight
    per tile instead of summing all records. An unfinished structure is not
    roofed and contributes nothing.
    """
    if isinstance(record, dict):
        if record.get("construction_project") is True and str(
            record.get("construction_stage", "")
        ) not in _SHELTERING_STAGES:
            return 0
    otype = str(object_type or "").lower()
    rung = _structure_rung_of(otype)
    if rung:
        return int(rung.get("weight", 1))
    if "cabin" in otype:
        return 2
    if any(kind in otype for kind in (
        "shelter", "hut", "roof", "tent", "lean", "cave", "cavern",
        "overhang", "grotto", "burrow", "stable", "cellar",
    )):
        return 1
    return 0

# Phase 10PM: ordinary successful use wears crafted tools. Values are the
# number of uses before an individual item breaks from belongings.
_TOOL_DURABILITY = {
    "stone_axe": 24,
    "iron_axe": 48,
    "flint_knife": 12,
    "flint_spear": 16,
    "iron_spear": 24,
    "woven_basket": 36,
}

# Phrases that would turn a disclosure of facts into an instruction. Used by
# the cognition-model recipe advertisement and by its regression test.
_BANNED_DIRECTIVE_PHRASES = (
    "build a",
    "go to",
    "you should",
    "move to",
    "try building",
    "head to",
)
_SAFE_OBJECT_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)
_ALLOWED_MUTABLE_FIELDS = frozenset({
    "public_description", "object_type", "tile_id",
})


def _is_safe_object_id(value: str) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        return False
    return all(c in _SAFE_OBJECT_ID_CHARS for c in value)


def _holdings_summary(holdings: dict, exclude: str = "") -> str:
    """Compact holdings summary for kinder rejection reasons (Phase 10OU-A).

    Sorted "kind amount" pairs with positive amounts, excluding the
    shortfall kind (already named in the prefix). Empty string when the
    agent holds nothing beyond the shortfall, so the reason stays short.
    Facts only — no directive phrasing.
    """
    if not isinstance(holdings, dict):
        return ""
    parts = []
    for kind in sorted(holdings):
        if kind == exclude:
            continue
        try:
            amount = int(holdings.get(kind, 0) or 0)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            parts.append(f"{kind} {amount}")
    if not parts:
        return ""
    return "holdings: " + ", ".join(parts)


def _reflection_is_echo(memory_list: list[dict], reflection: str) -> bool:
    """True when this reflection says nothing the last reflection didn't.

    Numbers normalized, so a re-noted status line ("35+ consecutive build
    rejections... food 13/20" -> "food 14/20") is recognized as the same
    thought. Without this an agent fills its own memory with one belief
    until that belief crowds out everything else (HB701-743: 53 of 1538
    memories were the same refusal status line, three near-identical
    entries in three consecutive heartbeats).
    """
    def _norm(text: str) -> str:
        return re.sub(r"\d+", "#", (text or "").strip().lower())

    target = _norm(reflection)
    if not target:
        return False
    for entry in reversed(memory_list):
        if entry.get("type") == "reflection":
            return _norm(entry.get("content", "")) == target
    return False


class FirstPairRuntime:
    """Bounded, reproducible First Pair runtime.

    State is bound to a `FirstPairPersistenceStore` supplied at construction
    time.  Two separate memory lists (`{pair_id}_adam`, `{pair_id}_eve`) live
    inside a single shared envelope and are written atomically each tick, so
    neither agent's entries are overwritten by the other.

    Supports multiple pairs via `pair_id` (default "east"). The West pair
    uses pair_id="west" with its own store, identity, and agent refs.
    """

    def __init__(
        self,
        persistence_root: Path | None = None,
        heartbeat_limit: int = _DEFAULT_HEARTBEAT_LIMIT,
        backend: str = "stub",
        store: FirstPairPersistenceStore | None = None,
        pair_id: str = "east",
    ) -> None:
        if store is None:
            if pair_id == "east":
                store = FirstPairPersistenceStore(persistence_root)
            else:
                store = FirstPairPersistenceStore(persistence_root)
        self._store = store
        self._heartbeat_limit = heartbeat_limit
        self._backend = backend
        self._pair_id = pair_id
        self._adam_ref = f"{pair_id}_adam"
        self._eve_ref = f"{pair_id}_eve"

        self._identity_record: IdentityRecord | None = None
        self._habitat: dict | None = None
        self._world_state: WorldStateRecord | None = None
        self._goals: list[GoalRecord] = []
        self._questions: list[QuestionRecord] = []
        # Noncanonical, authority-free question proposals. Never persisted to
        # questions.json; they require a separate signed operator authorization
        # before becoming canonical.
        self._question_proposals: list[QuestionProposal] = []

        self._adam_memory: list[dict] = []
        self._eve_memory: list[dict] = []
        self._runtime_policy: RuntimePolicyRecord | None = None
        self._capability_grant: CapabilityGrantRecord | None = None
        self._current_tile_resources: dict[str, list[dict]] = {}

        # (The per-tick pressure state is retired - see
        # docs/epistemic_pressure_spec.md §0.1. The world has no per-agent
        # costs; the only physics an agent experiences is what a tile
        # offers and what it may build.)

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    def _agent_view(self, agent_ref: str) -> dict:
        assert self._identity_record is not None
        candidate = self._identity_record.birth_candidate
        if agent_ref == self._adam_ref:
            raw = candidate["adam_identity"]
            return {
                "agent_id": self._identity_record.adam_agent_id,
                "canonical_name": raw["canonical_name"],
                "canonical_agent_ref": agent_ref,
                "other_agent_id": self._identity_record.eve_agent_id,
                "other_agent_name": candidate["eve_identity"]["canonical_name"],
                "other_agent_ref": self._eve_ref,
            }
        raw = candidate["eve_identity"]
        return {
            "agent_id": self._identity_record.eve_agent_id,
            "canonical_name": raw["canonical_name"],
            "canonical_agent_ref": agent_ref,
            "other_agent_id": self._identity_record.adam_agent_id,
            "other_agent_name": candidate["adam_identity"]["canonical_name"],
            "other_agent_ref": self._adam_ref,
        }

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load_or_initialize(self) -> bool:
        identity, world_state = initialize_first_pair_state(self._store)

        self._identity_record = identity
        self._world_state = world_state
        self._habitat = identity.habitat_boundary["habitat"]

        memory = load_memory(self._store)
        self._adam_memory = list(memory.get(self._adam_ref, []))
        self._eve_memory = list(memory.get(self._eve_ref, []))

        self._goals = load_goals(self._store)
        self._questions = load_questions(self._store)

        self._runtime_policy = load_runtime_policy(self._store)
        self._capability_grant = load_capability_grant(self._store)

        fauna_interactions.recover_fauna_interactions(self._store, self._world_state)

        # Phase 10QJ: apply anything the operator left for them. Inside the
        # heartbeat's own read-modify-write cycle, so it cannot be clobbered.
        try:
            self._apply_operator_provision_queue()
        except Exception:
            pass

        is_fresh = (
            world_state.tick == 0
            and not self._adam_memory
            and not self._eve_memory
            and not self._goals
        )
        return is_fresh

    def _apply_operator_provision_queue(self) -> int:
        """Turn queued operator provisions into objects on the right tiles.

        Phase 10QJ. Writing the live world_state straight from the operator
        side is a RACE: a heartbeat that began before the write saves its own
        copy when it persists, and the provision disappears. Measured
        2026-11-13: eight provisions written directly into world_state.json
        were gone by the next completed heartbeat.

        So the operator ENQUEUES (scripts/operator_provide.py) and the runtime
        applies the queue here, inside the read-modify-write it already owns.
        Idempotent by object_id, so a re-run cannot duplicate a gift, and
        fail-closed: an unreadable queue is not a reason to refuse to run.
        """
        import json as _json
        from backend.world.first_pair_persistence import save_world_state

        queue_path = Path(self._store.root) / "operator_provisions_pending.json"
        if not queue_path.is_file():
            return 0
        try:
            payload = _json.loads(queue_path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        acts = payload.get("acts") if isinstance(payload, dict) else payload
        if not isinstance(acts, list) or not acts:
            return 0

        state = self._world_state
        objects = state.public_objects or {}
        applied = 0
        remaining = []
        for act in acts:
            if not isinstance(act, dict):
                continue
            obj_id = str(act.get("object_id") or "")
            if not obj_id or obj_id in objects:
                continue  # already applied, or malformed
            is_water = act.get("kind") == "fresh_water"
            amount = int(act.get("amount") or 0)
            if amount <= 0:
                continue
            # Resolve the tile AT APPLY TIME. The agent may have crawled away
            # between the queue being written and the heartbeat that applies
            # it, and a cache behind a crawling body helps nobody.
            agent_ref = str(act.get("agent_ref") or "")
            tile = (self._world_state.tile_occupancy or {}).get(agent_ref) \
                or act.get("tile_id")
            if not tile:
                continue
            objects[obj_id] = {
                "object_id": obj_id,
                "object_type": "supply_cache",
                "tile_id": tile,
                "creator_agent_id": "the operator",
                "public_description": (
                    f"an operator supply cache: {amount} {act.get('kind')} "
                    f"left for {agent_ref}"
                ),
                "created_heartbeat": int(state.tick or 0),
                "provenance": "operator-provision",
                "materials": {} if is_water else {str(act.get("kind")): amount},
                "contents": {"fresh_water": amount} if is_water else {},
            }
            applied += 1
        state.public_objects = objects
        if applied:
            try:
                save_world_state(self._store, state)
            except Exception:
                return 0
        # clear what we applied; keep anything we could not (never silently)
        for act in acts:
            if isinstance(act, dict) and str(act.get("object_id") or "") in objects:
                continue
            remaining.append(act)
        try:
            queue_path.write_text(
                _json.dumps({"acts": remaining}, indent=1),
                encoding="utf-8", newline="\n")
        except Exception:
            pass
        return applied

    # ------------------------------------------------------------------
    # Cognition backends
    # ------------------------------------------------------------------

    def _get_cognition_backend(self, agent_ref: str) -> CognitionBackend:
        if self._backend == "model":
            return ModelCognitionBackend(agent_ref)
        if self._backend == "deterministic_stub":
            return DeterministicStubBackend(agent_ref)
        return AlternatingStubBackend(agent_ref)

    # ------------------------------------------------------------------
    # Movement authority
    # ------------------------------------------------------------------

    def _movement_grant_active(self) -> bool:
        """Single authoritative predicate for whether the currently loaded
        grant+policy authorize MOVEMENT.

        Fail-closed: authorized only when the grant is a granted 'movement'
        capability bound to the policy's movement_grant_ref, the policy is
        active, and the policy topology itself allows movement.
        """
        grant = self._capability_grant
        policy = self._runtime_policy
        if grant is None or policy is None:
            return False
        return (
            grant.status == "granted"
            and grant.capability_id == "movement"
            and policy.status == "active"
            and policy.topology.get("movement_allowed") is True
            and grant.grant_id == policy.movement_grant_ref
        )

    # ------------------------------------------------------------------
    # Fog integration (10JB-2): inert gate helpers
    # ------------------------------------------------------------------

    def _fog_active(self) -> bool:
        """True when per-agent known-map files exist (the fog gate)."""
        if self._store is None:
            return False
        return fog_gate_active(self._store.root, self._pair_id)

    def _get_data_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data"

    def _mystery_step(
        self,
        known_map: dict[str, Any],
        position_tile: str,
        agent_ref: str,
        tick: int,
        true_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Accrue mystery evidence and apply reveals for the agent's tile.

        Spec: docs/mystery_runtime_integration_spec.md. Occupancy-only:
        only mysteries whose tile_id equals the agent's current position
        accrue — one unit per tick, per-agent (Adam's evidence gives Eve
        nothing). The true map is read-only; state lives in
        known_map['myths'] and, on reveal, known_map['known_landmarks'].
        Persist happens once, only when something changed. Fail-closed: any
        error returns the input map unchanged (no partial state handed to
        the caller, no crash; the tick is retried by the next heartbeat).
        """
        try:
            tm = true_map if true_map is not None else load_true_map(self._get_data_root())
            km = known_map
            changed = False
            for mystery in tm.get("mysteries", []):
                if not isinstance(mystery, dict) or not mystery.get("mystery_id"):
                    continue
                if mystery.get("tile_id") != position_tile:
                    continue
                km, accrued = accrue_mystery_evidence(
                    km, mystery, {"tile_id": position_tile}, tick
                )
                km, revealed = apply_reveal(km, mystery, tick)
                changed = changed or accrued or revealed is not None
            if changed:
                persist_known_map(self._store.root, agent_ref, km)
            return km
        except Exception:
            return known_map

    def _get_fog_observation(
        self, agent_ref: str, position: str, objects_here: list,
        heartbeat_number: int | None = None,
    ) -> dict[str, Any]:
        """Build a cognition-safe fog observation. Raises on fog failure.

        Mystery accrual + reveal happen here — before the observation is
        built from the just-updated known map — so hints earned this tick
        are visible to the agent in this same heartbeat's cognition
        (spec §2.1 item 7). The additive observation keys
        'unsettled_reports' and 'discoveries' are present only when the
        agent has earned them (absent otherwise).
        """
        true_map = load_true_map(self._get_data_root())
        known_map = load_known_map(self._store.root, agent_ref)
        if heartbeat_number is not None:
            known_map = self._mystery_step(
                known_map, position, agent_ref, heartbeat_number, true_map=true_map
            )
        obs = cognition_safe_observation(
            true_map, position, known_map, None, objects_here, agent_ref,
            public_objects=list(
                (self._world_state.public_objects or {}).values()
            ) if isinstance(self._world_state.public_objects, dict) else [],
        )
        # Phase 10OU-C: write observed resources back into the known map.
        # The observation already carries them in visible_tile_details;
        # without this write they never persist (lane maps stayed empty).
        if heartbeat_number is not None:
            known_map, _changed = self._merge_visible_resources_into_known_map(
                known_map, obs, heartbeat_number
            )
            if _changed:
                try:
                    persist_known_map(self._store.root, agent_ref, known_map)
                except Exception:
                    pass
        reports = project_unsettled_reports(known_map)
        if reports:
            obs["unsettled_reports"] = reports
        discoveries = project_discoveries(known_map)
        if discoveries:
            obs["discoveries"] = discoveries
        return obs

    def _get_effective_adjacency(self, current_pos: str) -> list[str]:
        """Adjacent tiles from fog-derived topology or legacy policy."""
        if self._fog_active():
            true_map = load_true_map(self._get_data_root())
            known_maps = [
                load_known_map(self._store.root, ref)
                for ref in (self._adam_ref, self._eve_ref)
            ]
            topology = derive_topology(
                true_map, known_maps,
                public_objects=self._public_object_list(),
            )
            for tile in topology["tiles"]:
                if tile["tile_id"] == current_pos:
                    return tile["adjacent"]
            return []
        return get_adjacent_tiles(self._runtime_policy, current_pos)

    def _get_effective_allowed_tiles(self) -> list[str]:
        """Allowed tile IDs from fog-derived topology or legacy policy."""
        if self._fog_active():
            true_map = load_true_map(self._get_data_root())
            known_maps = [
                load_known_map(self._store.root, ref)
                for ref in (self._adam_ref, self._eve_ref)
            ]
            topology = derive_topology(
                true_map, known_maps,
                public_objects=self._public_object_list(),
            )
            return topology["allowed_tile_ids"]
        return self._runtime_policy.topology.get("allowed_tile_ids", [])

    def _public_object_list(self) -> list[dict]:
        """Flat public-object records for the wall-unlock seam.

        The prompt already reads world_public_objects the same flat way;
        this is the same data through the same shape, so the unlock rule
        and the anchor section can never disagree about what stands where.
        """
        return [
            obj for obj in (self._world_state.public_objects or {}).values()
            if isinstance(obj, dict)
        ]

    def _known_hazards_for(self, agent_ref: str, tile_id: str) -> list[str]:
        """Hazards the mover has personally observed on a tile, from its own
        known map. Empty when the tile is unknown — an unseen wall gives no
        names, a seen one tells the truth."""
        if not tile_id:
            return []
        try:
            km = load_known_map(self._store.root, agent_ref)
            tile = (km.get("known_tiles") or {}).get(tile_id)
            if not isinstance(tile, dict):
                return []
            return [h for h in (tile.get("observed_hazards") or [])
                    if isinstance(h, str) and h.strip()]
        except Exception:
            return []

    @staticmethod
    def _observed_resource_rollup(known_map: dict) -> str:
        """Factual roll-up of the agent's own observed resources (Phase 10OU-C).

        "stone: tile-a, tile-b; clay: tile-c" from known_map's
        known_tiles[].observed_resources only — never the true map.
        Empty string when nothing has been observed. Bounded to 3 tiles
        per resource, deterministic order.
        """
        tiles = (known_map or {}).get("known_tiles") or {}
        by_resource: dict[str, list[str]] = {}
        for tid in sorted(tiles):
            entry = tiles.get(tid)
            if not isinstance(entry, dict):
                continue
            for res in (entry.get("observed_resources") or []):
                if not isinstance(res, str) or not res.strip():
                    continue
                by_resource.setdefault(res, [])
                if tid not in by_resource[res]:
                    by_resource[res].append(tid)
        if not by_resource:
            return ""
        parts = []
        for res in sorted(by_resource):
            shown = by_resource[res][:3]
            parts.append(f"{res}: {', '.join(shown)}")
        return "; ".join(parts)

    def _rollup_for(self, agent_ref: str) -> str:
        """Best-effort roll-up for the prompt; "" when unavailable."""
        try:
            km = load_known_map(self._store.root, agent_ref)
        except Exception:
            return ""
        return self._observed_resource_rollup(km)

    @staticmethod
    def _merge_visible_resources_into_known_map(
        known_map: dict, observation: dict, tick: int
    ) -> tuple[dict, bool]:
        """Union visible_tile_details resources/hazards into the known map.

        Phase 10OU-C root-cause fix: observations carried resources in
        visible_tile_details, but nothing ever wrote them back, so lane
        observed_resources stayed [] forever. Mirrors
        merge_observation_into_known_map's entry shape. Fail-closed:
        returns the input map unchanged on any error.

        Phase 10QH root-cause fix: DRINKABLE WATER TOO. The observation has
        carried each visible tile's `water` since a previous phase fixed the
        adapter ("the fact was present in the true map and dropped here"),
        but this merge only ever read `resources` - so the water was dropped
        a SECOND time, one step later, and no agent could ever REMEMBER a
        river. Measured 2026-11-13: the world holds 2,163 tiles whose
        `water.drinkable` is true, exactly ONE of them lists `fresh_water` as
        a resource, and `cont_a_origin_000` was therefore the only water in
        any agent's known map. east_eve knew 1,592 tiles and zero rivers,
        asked where water was, drank where she stood, and collapsed; all four
        agents sat at thirst 100 on dry ground.
        """
        try:
            known = known_map or {}
            tiles = known.setdefault("known_tiles", {})
            changed = False
            for detail in observation.get("visible_tile_details", []) or []:
                if not isinstance(detail, dict):
                    continue
                tid = detail.get("tile_id") or ""
                if not tid:
                    continue
                entry = tiles.get(tid)
                if entry is None:
                    entry = {
                        "tile_id": tid,
                        "first_observed_tick": tick,
                        "last_observed_tick": tick,
                        "visit_count": 0,
                        "confidence": 1.0,
                        "observed_terrain": detail.get("terrain", "unknown"),
                        "observed_biome": detail.get("biome", "unknown"),
                        "observed_resources": [],
                        "observed_hazards": [],
                        "agent_given_name": None,
                        "notes": [],
                    }
                    tiles[tid] = entry
                    changed = True
                # A tile the agent can see and drink from is a tile it can
                # remember and return to. Recorded as the same
                # `fresh_water` kind the gather vocabulary and the rollup
                # already use, so nothing downstream needs to learn a new
                # word.
                seen_resources = list(detail.get("resources") or [])
                water = detail.get("water")
                if isinstance(water, dict) and water.get("drinkable") is True:
                    seen_resources.append("fresh_water")
                detail = dict(detail, resources=seen_resources)
                for key, obs_key in (("resources", "observed_resources"), ("hazards", "observed_hazards")):
                    incoming = [str(v) for v in (detail.get(key) or []) if isinstance(v, str) and v.strip()]
                    current = entry.get(obs_key) or []
                    merged = sorted(set(current) | set(incoming))
                    if merged != current:
                        entry[obs_key] = merged
                        changed = True
                if entry.get("last_observed_tick") != tick:
                    entry["last_observed_tick"] = tick
            return known, changed
        except Exception:
            return known_map, False

    def _on_road_tile(self, position: str) -> bool:
        """True when the agent's current tile carries a road object.

        Road = any public object whose object_type contains 'road'.
        The same substring matching the wall unlock uses. Build a road
        on your tile and you walk faster — the world does not say you
        must, only that you can.
        """
        objs = (self._world_state.public_objects or {}) \
            if isinstance(self._world_state.public_objects, dict) else {}
        for obj in objs.values():
            if not isinstance(obj, dict):
                continue
            if obj.get("tile_id") == position:
                if "road" in str(obj.get("object_type", "")).casefold():
                    return True
        return False

    def _road_two_step(self, position: str, adjacent: list[str]) -> list[str]:
        """Two-step reachable tiles from a road tile: for each 1-step
        neighbor, its 1-step neighbors (excluding the starting tile).
        Deduplicated, ordered."""
        out: list[str] = []
        seen = {position}
        for n1 in adjacent:
            if n1 == position:
                continue
            n1_adj = self._get_effective_adjacency(n1)
            for n2 in n1_adj:
                if n2 not in seen:
                    seen.add(n2)
                    out.append(n2)
        return sorted(set(out))

    def _merge_and_persist_known_map(
        self, agent_ref: str, observation: dict[str, Any], tick: int
    ) -> None:
        """Merge observation into the agent's known map and persist it."""
        if not self._fog_active():
            return
        known_map = load_known_map(self._store.root, agent_ref)
        updated = merge_observation(known_map, observation, tick)
        persist_known_map(self._store.root, agent_ref, updated)

    def _load_tile_resources(self) -> None:
        """Load gatherable resources from the true map, indexed by tile."""
        self._current_tile_resources = {}
        if not self._fog_active():
            return
        try:
            true_map = load_true_map(self._get_data_root())
            for res in true_map.get("resources", []):
                tile_id = res.get("tile_id", "")
                if not tile_id:
                    continue
                self._current_tile_resources.setdefault(tile_id, []).append(res)
        except FogAdapterError:
            self._current_tile_resources = {}

    def _get_agent_inventory(self, agent_ref: str) -> dict:
        """Return the agent's gathered-resource inventory (persisted).

        Fail-closed on a runtime carrying no store (a minimal seam stub, or a
        partially constructed runtime): `hasattr(self._store, ...)` evaluates
        `self._store` FIRST, so a missing attribute raises before hasattr can
        catch anything. Read the attribute through getattr instead.
        """
        store = getattr(self, "_store", None)
        if store is None or not hasattr(store, "_read_json"):
            return {}
        try:
            return dict(load_inventory(store).get(agent_ref, {}))
        except Exception:
            return {}

    def _ensure_life_state(self, agent_ref: str, heartbeat_number: int | None = None) -> None:
        """Seed Phase 10PM custody records without disturbing existing stock.

        Tools and food that predate the implementation are grandfathered at
        full condition / fresh-from-arrival; only post-migration use ages
        them."""
        if not hasattr(self._world_state, "tool_condition"):
            self._world_state.tool_condition = {}
        if not hasattr(self._world_state, "food_freshness"):
            self._world_state.food_freshness = {}
        tools = dict(getattr(self._world_state, "tool_condition", {}) or {})
        foods = dict(getattr(self._world_state, "food_freshness", {}) or {})
        tools.setdefault(agent_ref, {})
        foods.setdefault(agent_ref, {})
        self._world_state.tool_condition = tools
        self._world_state.food_freshness = foods
        self._sync_tool_condition(agent_ref)
        self._sync_food_freshness(
            agent_ref,
            int(heartbeat_number if heartbeat_number is not None else self._world_state.tick),
        )

    def _clean_tool_states(self, states: object, maximum: int) -> list[int]:
        if not isinstance(states, list):
            return []
        return [
            value for value in states
            if isinstance(value, int) and not isinstance(value, bool)
            and 0 < value <= maximum
        ]

    def _sync_tool_condition(self, agent_ref: str) -> None:
        if not hasattr(self._world_state, "tool_condition"):
            self._world_state.tool_condition = {}
        state = dict(self._world_state.tool_condition or {})
        agent_state = dict(state.get(agent_ref) or {})
        holdings = self._get_agent_inventory(agent_ref)
        for kind, maximum in _TOOL_DURABILITY.items():
            held = int(holdings.get(kind, 0) or 0)
            values = self._clean_tool_states(agent_state.get(kind), maximum)
            if len(values) > held:
                values = values[:held]
            if len(values) < held:
                values.extend([maximum] * (held - len(values)))
            if values:
                agent_state[kind] = values
            else:
                agent_state.pop(kind, None)
        state[agent_ref] = agent_state
        self._world_state.tool_condition = state

    def _register_tool(self, agent_ref: str, kind: str, quantity: int = 1) -> None:
        """Recognize newly acquired crafted items at full condition."""
        if kind not in _TOOL_DURABILITY or quantity <= 0:
            return
        self._ensure_life_state(agent_ref)
        self._sync_tool_condition(agent_ref)

    def _tool_states_for(self, agent_ref: str) -> dict[str, list[int]]:
        """One remaining-use count per tool item, from condition records."""
        self._ensure_life_state(agent_ref)
        state = (self._world_state.tool_condition or {}).get(agent_ref) or {}
        return {
            kind: list(self._clean_tool_states(
                values, _TOOL_DURABILITY[kind]
            ))
            for kind, values in state.items()
            if kind in _TOOL_DURABILITY
            and self._clean_tool_states(values, _TOOL_DURABILITY[kind])
        }

    def _use_best_tool(self, agent_ref: str, kinds: tuple[str, ...]) -> dict:
        """Wear the best-condition eligible tool. A tool breaks only
        after its final successful use."""
        self._ensure_life_state(agent_ref)
        state = dict(self._world_state.tool_condition.get(agent_ref) or {})
        candidates = [
            (kind, self._clean_tool_states(state.get(kind), _TOOL_DURABILITY[kind]))
            for kind in kinds
        ]
        candidates = [(kind, values) for kind, values in candidates if values]
        if not candidates:
            return {"used": None, "remaining": 0, "broke": False}
        kind, values = max(candidates, key=lambda item: max(item[1]))
        values = list(values)
        index = values.index(max(values))
        values[index] -= 1
        broke = values[index] <= 0
        if broke:
            del values[index]
            add_to_inventory(self._store, agent_ref, kind, -1)
        if values:
            state[kind] = values
        else:
            state.pop(kind, None)
        self._world_state.tool_condition[agent_ref] = state
        return {
            "used": kind,
            "remaining": max(values) if values else 0,
            "broke": broke,
        }

    @staticmethod
    def _clean_food_lots(lots: object) -> list[dict]:
        if not isinstance(lots, list):
            return []
        clean = []
        for lot in lots:
            if not isinstance(lot, dict):
                continue
            quantity = lot.get("quantity", 0)
            born_hb = lot.get("born_hb", 0)
            if (isinstance(quantity, int) and not isinstance(quantity, bool)
                    and quantity > 0 and isinstance(born_hb, int)
                    and not isinstance(born_hb, bool)):
                clean.append({"quantity": quantity, "born_hb": born_hb})
        return sorted(clean, key=lambda lot: lot["born_hb"])

    def _sync_food_freshness(self, agent_ref: str, heartbeat_number: int) -> None:
        """Seed lots for untracked existing holdings; never backdate them."""
        if not hasattr(self._world_state, "food_freshness"):
            self._world_state.food_freshness = {}
        freshness = dict(self._world_state.food_freshness or {})
        agent_freshness = dict(freshness.get(agent_ref) or {})
        holdings = self._get_agent_inventory(agent_ref)
        for kind, lifetime in survival.SPOILAGE_LIFETIME_HB.items():
            held = int(holdings.get(kind, 0) or 0)
            if held <= 0:
                agent_freshness.pop(kind, None)
                continue
            lots = self._clean_food_lots(agent_freshness.get(kind))
            tracked = sum(lot["quantity"] for lot in lots)
            if tracked < held:
                lots.append({
                    "quantity": held - tracked,
                    "born_hb": int(heartbeat_number),
                })
            if tracked > held:
                excess = tracked - held
                lots = sorted(lots, key=lambda lot: lot["born_hb"])
                while excess > 0 and lots:
                    lot = lots[-1]
                    remove = min(excess, lot["quantity"])
                    lot["quantity"] -= remove
                    excess -= remove
                    if lot["quantity"] <= 0:
                        lots.pop()
            ordered = sorted(lots, key=lambda lot: lot["born_hb"])
            agent_freshness[kind] = ordered
        freshness[agent_ref] = {
            kind: lots for kind, lots in agent_freshness.items() if lots
        }
        self._world_state.food_freshness = freshness

    def _wear_preferred_attack_tool(self, agent_ref: str) -> dict:
        inventory = self._get_agent_inventory(agent_ref)
        for kind in ("iron_spear", "iron_axe", "flint_spear", "stone_axe", "flint_knife"):
            if int(inventory.get(kind, 0) or 0) > 0:
                return self._use_best_tool(agent_ref, (kind,))
        return {"used": None, "remaining": 0, "broke": False}

    def _food_freshness_for(self, agent_ref: str) -> dict[str, dict]:
        self._ensure_life_state(agent_ref)
        freshness = (self._world_state.food_freshness or {}).get(agent_ref) or {}
        out: dict[str, dict] = {}
        for kind, lots in freshness.items():
            clean = self._clean_food_lots(lots)
            if clean:
                out[kind] = {
                    "lots": clean,
                    "oldest_born_hb": clean[0]["born_hb"],
                    "quantity": sum(lot["quantity"] for lot in clean),
                }
        return out

    def _record_food_birth(
        self, agent_ref: str, kind: str, quantity: int,
        heartbeat_number: int,
    ) -> None:
        if kind not in survival.SPOILAGE_LIFETIME_HB or quantity <= 0:
            return
        if not hasattr(self._world_state, "food_freshness"):
            self._world_state.food_freshness = {}
        freshness = dict(self._world_state.food_freshness or {})
        agent_freshness = dict(freshness.get(agent_ref) or {})
        lots = self._clean_food_lots(agent_freshness.get(kind))
        lots.append({"quantity": int(quantity), "born_hb": int(heartbeat_number)})
        agent_freshness[kind] = sorted(lots, key=lambda lot: lot["born_hb"])
        freshness[agent_ref] = agent_freshness
        self._world_state.food_freshness = freshness

    def _remove_food_lots(
        self, agent_ref: str, kind: str, quantity: int
    ) -> list[dict]:
        """Remove oldest lots first and return the lots taken."""
        if quantity <= 0:
            return []
        freshness = dict(getattr(self._world_state, "food_freshness", None) or {})
        agent_freshness = dict(freshness.get(agent_ref) or {})
        lots = self._clean_food_lots(agent_freshness.get(kind))
        taken = []
        remaining = int(quantity)
        kept = []
        for lot in lots:
            if remaining <= 0:
                kept.append(lot)
                continue
            take = min(remaining, lot["quantity"])
            taken.append({"quantity": take, "born_hb": lot["born_hb"]})
            remaining -= take
            if lot["quantity"] > take:
                kept.append({
                    "quantity": lot["quantity"] - take,
                    "born_hb": lot["born_hb"],
                })
        if kept:
            agent_freshness[kind] = kept
        else:
            agent_freshness.pop(kind, None)
        freshness[agent_ref] = agent_freshness
        self._world_state.food_freshness = freshness
        return taken

    def _effective_food_lifetime(
        self, kind: str, obj_id: str, obj: dict
    ) -> int:
        base = survival.SPOILAGE_LIFETIME_HB.get(kind)
        if base is None:
            return 0
        if "cellar" in str(obj.get("object_type", "")).casefold():
            footprint, _ = self._connected_home_network(
                str(obj.get("tile_id", ""))
            )
            return int(base * (4 + max(1, footprint)))
        return int(base)

    def _age_and_spoil_world_food(self, heartbeat_number: int) -> None:
        """Walk persisted perishables before embodiment; nothing is
        retroactively aged on first migration."""
        objects = self._world_state.public_objects or {}
        for ref in (self._adam_ref, self._eve_ref):
            self._ensure_life_state(ref, heartbeat_number)
            holdings = self._get_agent_inventory(ref)
            for kind, lifetime in survival.SPOILAGE_LIFETIME_HB.items():
                held = int(holdings.get(kind, 0) or 0)
                if held <= 0:
                    continue
                lots = self._clean_food_lots(
                    (self._world_state.food_freshness or {}).get(ref, {}).get(kind)
                )
                spoiled = sum(
                    lot["quantity"] for lot in lots
                    if heartbeat_number - lot["born_hb"] >= lifetime
                )
                if spoiled:
                    lots = [
                        lot for lot in lots
                        if heartbeat_number - lot["born_hb"] < lifetime
                    ]
                    add_to_inventory(self._store, ref, kind, -spoiled)
                    freshness = dict(self._world_state.food_freshness)
                    agent_freshness = dict(freshness.get(ref) or {})
                    if lots:
                        agent_freshness[kind] = lots
                    else:
                        agent_freshness.pop(kind, None)
                    freshness[ref] = agent_freshness
                    self._world_state.food_freshness = freshness

        for obj_id, obj in list(objects.items()):
            if not isinstance(obj, dict):
                continue
            for source, age_key in (("contents", "contents_age"), ("materials", "materials_age")):
                stores = obj.get(source)
                if not isinstance(stores, dict) or not stores:
                    continue
                ages = obj.get(age_key)
                if not isinstance(ages, dict):
                    ages = {}
                    obj[age_key] = ages
                for kind, held in list(stores.items()):
                    if kind not in survival.SPOILAGE_LIFETIME_HB:
                        continue
                    if not isinstance(held, int) or held <= 0:
                        continue
                    born_hb = ages.get(kind)
                    if not isinstance(born_hb, int) or isinstance(born_hb, bool):
                        ages[kind] = int(heartbeat_number)
                        continue
                    if heartbeat_number - born_hb >= self._effective_food_lifetime(kind, obj_id, obj):
                        del stores[kind]
                        ages.pop(kind, None)

    def _canonical_water_drinkable(self, position: str) -> bool:
        """True when the WORLD's map says this tile has drinkable water."""
        position = str(position or "")
        if not position:
            return False
        if not hasattr(self, "_drinkable_tile_ids"):
            self._drinkable_tile_ids = set()
        if position in self._drinkable_tile_ids:
            return True
        if self._fog_active():
            try:
                tm = load_true_map(self._get_data_root())
                for tile in tm.get("tiles", []):
                    if tile.get("tile_id") != position:
                        continue
                    water = tile.get("water")
                    if isinstance(water, dict) and water.get("drinkable") is True:
                        self._drinkable_tile_ids.add(position)
                        return True
                    return False
            except FogAdapterError:
                return False
        return any(
            r.get("kind") == "fresh_water"
            for r in self._current_tile_resources.get(position, [])
        )

    def _cistern_on_tile(self, position: str) -> dict | None:
        """The cistern standing on a tile, if it holds water.

        Phase 10QF. A cistern is a FINITE source: it holds what was carried
        to it, and drinking from it consumes a unit. It is never a river.
        """
        position = str(position or "")
        if not position:
            return None
        for record in (self._world_state.public_objects or {}).values():
            if not isinstance(record, dict):
                continue
            if str(record.get("tile_id", "")) != position:
                continue
            if str(record.get("object_type", "")).strip().lower() != "cistern":
                continue
            contents = record.get("contents")
            if not isinstance(contents, dict):
                continue
            if int(contents.get("fresh_water", 0) or 0) >= 1:
                return record
        return None

    def _cistern_water_units(self, position: str) -> int:
        """How much water a cistern on this tile is holding."""
        total = 0
        position = str(position or "")
        for record in (self._world_state.public_objects or {}).values():
            if not isinstance(record, dict):
                continue
            if str(record.get("tile_id", "")) != position:
                continue
            if str(record.get("object_type", "")).strip().lower() != "cistern":
                continue
            contents = record.get("contents")
            if isinstance(contents, dict):
                total += int(contents.get("fresh_water", 0) or 0)
        return total

    def _current_tile_water_drinkable(self, position: str) -> bool:
        """True when this tile can be drunk from.

        The world's rivers, and - since 10QF - a cistern that has been filled.
        The two are distinguished by `_canonical_water_drinkable`, because a
        cistern is FINITE: drinking from it consumes a unit, while a river
        is not.
        """
        if self._canonical_water_drinkable(position):
            return True
        return self._cistern_on_tile(position) is not None


    # Phase 10PT: the resource kinds disclosed about the partner. Same bounded
    # vocabulary the settlement section already uses for the agent's own
    # holdings, so the two lines stay comparable and neither can balloon.
    _PARTNER_HOLDINGS_KINDS = (
        "timber", "wood", "stone", "clay", "fiber_plants", "flint",
        "iron_ore", "iron", "fresh_water",
    )
    _PARTNER_TOOL_KINDS = (
        "stone_axe", "iron_axe", "flint_knife", "flint_spear", "iron_spear",
        "woven_basket", "knapped_flint",
    )

    def _partner_holdings_for(self, agent_ref: str) -> dict:
        """The other agent's persisted belongings, projected and bounded.

        Facts from the store only. Empty when the partner holds nothing in
        the disclosed vocabulary, so a fresh store renders no line at all.
        """
        partner_ref = None
        for ref in (self._adam_ref, self._eve_ref):
            if ref != agent_ref:
                partner_ref = ref
                break
        if not partner_ref:
            return {}
        try:
            holdings = load_inventory(self._store).get(partner_ref, {}) or {}
        except Exception:
            return {}
        if not isinstance(holdings, dict):
            return {}
        out: dict = {}
        for kind in self._PARTNER_HOLDINGS_KINDS:
            value = holdings.get(kind, 0)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                out[kind] = value
        tools = {}
        for kind in self._PARTNER_TOOL_KINDS:
            value = holdings.get(kind, 0)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                tools[kind] = value
        if tools:
            out["tools"] = tools
        return out

    def _record_shelters(self, record: dict) -> bool:
        if not isinstance(record, dict):
            return False
        if not _is_roofed_type(record.get("object_type", "")):
            return False
        if record.get("construction_project") is True:
            return str(record.get("construction_stage", "")) in _SHELTERING_STAGES
        return True

    def _partner_state_for(self, agent_ref: str) -> dict:
        """Where the partner is and how its body is doing.

        Phase 10QE. The world told a collapsed agent that "food or water
        brought to your tile" would reach it, and a partner has no way to
        learn that their companion is collapsed, where they are, or that
        their pack is the supply. This is the fact: the partner's tile, and
        the numbers that describe their condition. Facts only.
        """
        partner_ref = (self._eve_ref if agent_ref == self._adam_ref
                       else self._adam_ref)
        if not partner_ref:
            return {}
        partner_pos = self._world_state.tile_occupancy.get(partner_ref)
        if not partner_pos:
            return {}
        vitals = self._vitals_for(partner_ref)
        state = {
            "agent_ref": partner_ref,
            "tile_id": partner_pos,
            "downed": bool(vitals.get("downed")),
            "vitality": round(float(vitals.get("vitality", 100.0)), 2),
            "thirst": round(float(vitals.get("thirst", 18.0)), 2),
            "hunger": round(float(vitals.get("hunger", 0.0)), 2),
        }
        state["state"] = survival.vitals_state_label(vitals)
        return state

    def _home_rung_for(self, position: str | None) -> dict:
        """The structure this agent stands in, with rung and live effects.

        Empty when the agent is not in a shelter. Facts from the world state
        only -- this is the number that makes a proper house legible.
        """
        if not position:
            return {}
        footprint, best_rung, _ids = self._home_network_detail(position)
        tier = _home_network_tier(_home_tier_weight(footprint, best_rung))
        here = None
        pos_xy = self._tile_xy(position)
        for record in (self._world_state.public_objects or {}).values():
            if not self._record_shelters(record):
                continue
            other = self._tile_xy(str(record.get("tile_id", "")))
            if other is None or pos_xy is None:
                continue
            if max(abs(other[0] - pos_xy[0]), abs(other[1] - pos_xy[1])) <= 1:
                here = record
                break
        if here is None:
            return {}
        rung = here.get("structure_rung")
        weight = here.get("rung_weight")
        if not isinstance(rung, int):
            rung_record = _structure_rung_of(str(here.get("object_type", "")))
            rung = int(rung_record["rung"]) if rung_record else 1
        if not isinstance(weight, int):
            rung_record = _structure_rung_of(str(here.get("object_type", "")))
            weight = int(rung_record["weight"]) if rung_record else 1
        return {
            "object_id": here.get("object_id"),
            "object_type": here.get("object_type"),
            "rung": rung,
            "weight": weight,
            "footprint": footprint,
            "tier_weight": _home_tier_weight(footprint, best_rung),
            "best_rung": best_rung,
            "comfort_floor": tier[0],
            "cold_decay": tier[1],
            "rest_regen": tier[2],
            "downed_regen": tier[3],
            "cellar_budget": self._cellar_food_capacity(str(here.get("object_id", ""))),
        }

    def _construction_here_for(self, agent_ref: str, position: str | None) -> dict:
        """Any structure under construction on the agent's own tile."""
        if not position:
            return {}
        for oid, record in (self._world_state.public_objects or {}).items():
            if not isinstance(record, dict):
                continue
            if record.get("tile_id") != position:
                continue
            if record.get("construction_project") is not True:
                continue
            return {
                "object_id": oid,
                "object_type": record.get("object_type"),
                "stage": record.get("construction_stage"),
                "progress": record.get("construction_progress"),
                "stages_total": len(_CONSTRUCTION_STAGES),
                "rung": record.get("structure_rung"),
                "remaining_floor": dict(record.get("remaining_floor") or {}),
            }
        return {}

    def retire_stale_goals(self, agent_ref: str, heartbeat_number: int) -> list[GoalRecord]:
        """Phase 10KX/10KZ: Retire goals whose satisfying condition has objectively ceased to hold."""
        view = self._agent_view(agent_ref)
        agent_id = view["agent_id"]

        try:
            known_map = load_known_map(self._store.root, agent_ref)
            known_tiles = set(known_map.get("known_tiles", {}).keys()) if isinstance(known_map, dict) else set()
        except Exception:
            known_tiles = set()

        inv = self._get_agent_inventory(agent_ref)

        retired: list[GoalRecord] = []
        for g in self._goals:
            if g.agent_id != agent_id or getattr(g, "status", "") not in ("active", "in_progress"):
                continue

            desc = g.description or ""
            desc_lower = desc.lower()
            should_retire = False

            # Rule 1: Region surveyed
            if any(k in desc_lower for k in ("survey", "map", "mapping", "explore")):
                tile_matches = re.findall(r'cont_[a-z0-9_\-]+', desc)
                if tile_matches:
                    if all(tid in known_tiles for tid in tile_matches):
                        should_retire = True

            # Rule 2: Resource acquired.
            #
            # Two guards, both learned from live data. An agent's goal is
            # often COMPOUND -- "continue exploring uncharted hill terrain and
            # gather stone" carries an exploration purpose plus a gather. On
            # 2026-10-30 this rule retired that exact goal at 442 stone held,
            # killing the exploration half because the gather half happened to
            # be over an arbitrary default. Retirement must not lose the other
            # half of a compound goal.
            #
            # So Rule 2 fires only when:
            #   (a) the description states an explicit amount for that
            #       resource ("gather 20 stone"), which is a genuine,
            #       self-declared threshold; or
            #   (b) the goal is a PURE gather goal -- it contains a gather verb
            #       and no exploration/survey verb -- so there is no second
            #       purpose to destroy by retiring it.
            if not should_retire and any(k in desc_lower for k in ("gather", "accumulate", "collect")):
                is_compound = any(
                    k in desc_lower for k in ("explor", "survey", "map", "mapping", "uncharted")
                )
                for res_kind, def_thresh in DEFAULT_GATHER_RETIRE_THRESHOLDS.items():
                    if res_kind in desc_lower:
                        match_num = re.search(rf'(\d+)\s+{res_kind}', desc_lower)
                        explicit = match_num is not None
                        thresh = int(match_num.group(1)) if match_num else def_thresh
                        current_amt = inv.get(res_kind, 0)
                        if not isinstance(current_amt, (int, float)):
                            break
                        if current_amt >= thresh and (explicit or not is_compound):
                            should_retire = True
                            break

            # Rule 3: Stale test goals
            if not should_retire and "test whether" in desc_lower:
                created_hb = getattr(g, "created_heartbeat", 0) or 0
                if heartbeat_number - created_hb >= STALE_GOAL_AGE_HB:
                    should_retire = True

            # Rule 4 (Phase 10NX): aged restatements and dead operator standbys.
            #
            # Rules 1-3 could not touch the live East population: Rule 1 needs a
            # cont_ tile id (33 of 34 goals had none), Rule 2 is deliberately
            # blind to compound goals, and Rule 3 only matches "test whether".
            # The result was a goal older than the first shelter in the world,
            # still in_progress. Rule 4 retires aged goals that merely restate a
            # newer live goal, always keeping the newest of each signature.
            if not should_retire:
                try:
                    if goal_should_retire(
                        g,
                        [x for x in self._goals
                         if x.agent_id == agent_id
                         and getattr(x, "status", "") in ("active", "in_progress")],
                        heartbeat_number,
                        known_tiles,
                        inv,
                        False,
                    ):
                        should_retire = True
                except Exception:
                    # Goal hygiene must never block the heartbeat.
                    pass

            if should_retire:
                g.status = "retired"
                retired.append(g)

        if retired:
            save_goals(self._store, self._goals)
        return retired

    # ------------------------------------------------------------------
    # World pressure (docs/world_pressure_spec.md)
    # ------------------------------------------------------------------

    def _reconcile_capability_requests(self) -> int:
        """Retire pending requests for capabilities already granted.

        The West pair carried 144 'pending' requests, 138 of them for
        `gather`, which the operator granted hundreds of heartbeats ago:
        the request log never reconciled, so the operator inbox's loudest
        section was stale noise. A request whose capability is now held is
        answered, not pending.
        """
        granted = {
            g.capability_id
            for g in load_extra_capability_grants(self._store)
            if g.status == "granted"
        }
        if (
            self._capability_grant is not None
            and self._capability_grant.status == "granted"
        ):
            granted.add(self._capability_grant.capability_id)
        if not granted:
            return 0
        retired = 0
        for req in self._world_state.capability_requests:
            if req.get("status") == "pending" and req.get("capability_id") in granted:
                req["status"] = "granted"
                req["retired_at_utc"] = datetime.now(timezone.utc).isoformat()
                retired += 1
        return retired

    def _pressure_step_removed(self) -> None:
        """The per-heartbeat metabolism is retired.

        Kept as a named stub rather than deleted outright so the removal
        is greppable: there is no consumption, no famished state, and no
        carrying ledgers anywhere in the runtime. See
        docs/epistemic_pressure_spec.md §0.1 for why the model was
        removed and scripts/audit_tile_resources.py for the guard that
        replaces reasoning with measurement.
        """
        raise AttributeError(
            "world pressure consumption is retired (epistemic.1); "
            "see docs/epistemic_pressure_spec.md"
        )

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(
        self, agent_ref: str, heartbeat_number: int
    ) -> AgentContext:
        view = self._agent_view(agent_ref)
        memory_list = (
            self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
        )

        active_goals_raw = [
            g
            for g in self._goals
            if g.agent_id == view["agent_id"] and getattr(g, "status", "") in ("active", "in_progress")
        ]
        # Phase 10KX/10KZ: Deduplicate goal descriptions before slice, keeping the most recent
        # occurrence of each distinct description and preserving chronological order.
        seen_descs = set()
        deduped_rev = []
        for g in reversed(active_goals_raw):
            desc_norm = str(getattr(g, "description", "") or "").strip().lower()
            if desc_norm not in seen_descs:
                seen_descs.add(desc_norm)
                deduped_rev.append(g)
        # Phase 10NX: dedup by intent signature, not by exact string.
        #
        # The recency slice below used to be fed a list that was only
        # exact-string deduped, so restatements survived and the last eight EXPOSED
        # goals were eight copies of one intent -- the live East agent was handed
        # "continue systematic survey ... along the y=-5 boundary" every heartbeat
        # and logged 435 moves in 250 heartbeats. One goal per signature keeps the
        # same 8-slot budget while showing up to eight distinct intents.
        # `deduped_rev` was built newest-first, so reversing it restores
        # chronological order. Passing it unreversed handed the selector a
        # newest-first list, and its `chosen[-MAX:]` slice then took the
        # OLDEST goals instead of the newest -- a 20-distinct-goal agent saw
        # its 8 oldest intents. Reversing (10KX/10KZ ordering) is correct.
        agent_goals = _select_diverse_active_goals(
            list(deduped_rev), heartbeat_number
        )
        agent_pending_questions = [
            q
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "pending"
        ]
        agent_answered_questions = [
            q.__dict__
            for q in self._questions
            if q.asking_agent_id == view["agent_id"] and q.status == "answered"
        ]

        position = (
            self._world_state.tile_occupancy.get(
                agent_ref,
                self._habitat["starting_tile_ids"][agent_ref],
            )
        )

        # Objects whose tile_id matches current position
        current_tile_objects = [
            obj
            for obj in self._world_state.public_objects.values()
            if isinstance(obj, dict) and obj.get("tile_id") == position
        ]

        # Fog observation when the gate is active; legacy otherwise (10JB-2)
        fog_obs_error = False
        if self._fog_active():
            try:
                observation = self._get_fog_observation(
                    agent_ref, position, current_tile_objects,
                    heartbeat_number=heartbeat_number,
                )
                visible_tiles = observation["visible_tiles"]
                # available_moves: only tiles reachable by travel edges,
                # not every visible tile. The object sightline extension
                # made far tiles visible for INFORMATION, not movement —
                # seeing a cairn 2 tiles away doesn't mean you can walk
                # there in one step. Road tiles (any object whose type
                # contains "road" on the CURRENT tile) extend movement
                # to 2 travel edges per heartbeat.
                adjacent = self._get_effective_adjacency(position)
                available_moves = [t for t in adjacent if t != position]
                if self._on_road_tile(position):
                    two_step = self._road_two_step(position, adjacent)
                    for t in two_step:
                        if t not in available_moves and t != position:
                            available_moves.append(t)
                policy_allowed = self._get_effective_allowed_tiles()
                movement_allowed_flag = True
            except FogAdapterError:
                # Fail-closed: no fabricated observation, no legacy fallback
                fog_obs_error = True
                observation = {
                    "tile_id": position,
                    "visible_tiles": [position],
                    "objects_here": current_tile_objects,
                }
                visible_tiles = [position]
                available_moves = []
                policy_allowed = [position]
                movement_allowed_flag = False
        elif self._movement_grant_active():
            available_moves = get_adjacent_tiles(self._runtime_policy, position)
            visible_tiles = [position] + available_moves
            policy_allowed = self._runtime_policy.topology.get("allowed_tile_ids", [])
            movement_allowed_flag = True
            observation = {
                "tile_id": position,
                "visible_tiles": visible_tiles,
                "objects_here": current_tile_objects,
            }
        else:
            available_moves = []
            visible_tiles = self._habitat.get("observation_boundaries", {}).get(
                agent_ref, [position]
            )
            policy_allowed = self._habitat.get("allowed_tile_ids", [])
            movement_allowed_flag = self._habitat.get("movement_allowed", False)
            observation = {
                "tile_id": position,
                "visible_tiles": visible_tiles,
                "objects_here": current_tile_objects,
            }
        if fog_obs_error:
            observation["fog_error"] = "geography observation unavailable"

        # epistemic.4: the body and the hour, in every observation. The
        # prompt embeds the observation JSON, so this is how an agent
        # feels its own hunger and notices night falling.
        vitals = dict(self._vitals_for(agent_ref))
        vitals["state"] = survival.vitals_state_label(vitals)
        observation["self_body"] = vitals
        forecast = survival.weather_forecast(self._pair_id, heartbeat_number)
        weather_name = forecast["current"]
        if weather_name == "storm" and survival.season(heartbeat_number) == "winter":
            weather_name = "blizzard"
        observation["wildlife"] = self._wildlife_visible(
            agent_ref, heartbeat_number)
        observation["fauna"] = self._fauna_visible(agent_ref)
        observation["environment"] = {
            "time_of_day": "night" if survival.is_night(heartbeat_number) else "day",
            "season": survival.season(heartbeat_number),
            "temperature": round(survival.effective_temperature(
                heartbeat_number, forecast["current"]), 1),
            "weather": weather_name,
            "forecast_next": forecast["next"],
            "weather_changes_at_heartbeat": forecast["changes_at_heartbeat"],
            "by_fire": self._nearby_fire(position, heartbeat_number) if position else False,
            "sheltered": self._in_shelter(position) if position else False,
            "drinkable_water": self._current_tile_water_drinkable(position) if position else False,
            # Phase 10QF: a cistern's water is FINITE, so the agent is told
            # what it is drinking from and how much is left. A river says
            # "river"; a filled cistern says "cistern" and the unit count.
            "drinkable_source": (
                "" if not position else
                ("river" if self._canonical_water_drinkable(position)
                 else ("cistern" if self._cistern_on_tile(position) else ""))
            ),
            "drinkable_units": (
                self._cistern_water_units(position) if position else 0
            ),
        }

        # Check if honeycomb on current tile to report bee colony state
        if position:
            cur_biome = ""
            for td in observation.get("visible_tile_details", []):
                if td.get("tile_id") == position:
                    cur_biome = td.get("biome") or td.get("terrain") or ""
                    break
            if not cur_biome and self._fog_active():
                try:
                    tm = load_true_map(self._get_data_root())
                    for t in tm.get("tiles", []):
                        if t.get("tile_id") == position:
                            cur_biome = t.get("biome") or t.get("terrain") or ""
                            break
                except Exception:
                    pass

            has_honeycomb = any(r.get("kind") == "honeycomb" and r.get("amount", 0) > 0
                                for r in self._current_tile_resources.get(position, []))
            if has_honeycomb:
                near_smoke = self._nearby_smoke(position, heartbeat_number)
                b_state = insects.bee_colony_state(
                    weather_name,
                    observation["environment"]["temperature"],
                    observation["environment"]["time_of_day"] == "night",
                    near_smoke,
                )
                observation["environment"]["wild_bees"] = {
                    "tile": position,
                    "colony_state": b_state,
                }
            amb = insects.ambient_insect_atmosphere(
                observation["environment"]["season"],
                weather_name,
                observation["environment"]["time_of_day"] == "night",
                biome=cur_biome,
            )
            if amb:
                observation["environment"]["ambient_sound"] = amb

        # Visible public messages (addressed to this agent or public "all", bounded for model context)
        visible_msgs = select_bounded_public_messages(
            self._world_state.public_messages or [],
            agent_ref=agent_ref,
            canonical_agent_ref=view.get("canonical_agent_ref", ""),
        )

        # --- Legible action outcome report (docs/action_outcome_visibility)
        # The store knows what happened; the record only shows it when failures
        # happen. Eve at HB1651 invented "three consecutive failed stone
        # gathers" and concluded universal breakage, while the store records
        # success. This line is the store speaking back, by name and heartbeat,
        # so memory can't invent failure wholesale.
        recent_failures = []
        prev_act = None
        try:
            hist = load_heartbeat_history(self._store)
            for rec in reversed(hist):
                n = rec.get("heartbeat_number")
                if n is None or n >= heartbeat_number:
                    continue
                acts = rec.get("action_taken") or {}
                outcomes = rec.get("action_outcomes") or {}
                act = acts.get(agent_ref)
                out = outcomes.get(agent_ref)
                if not isinstance(act, dict) or not isinstance(out, dict):
                    continue
                if prev_act is None:
                    prev_act = dict(act)
                    prev_act["outcome"] = out
                    prev_act["heartbeat"] = n
                status = out.get("status", "")
                if isinstance(status, str) and ("fail" in status or status in ("no_action", "rejected")):
                    if len(recent_failures) < 2:
                        detail = (
                            out.get("detail")
                            or out.get("reason")
                            or act.get("interaction_type")
                            or act.get("target_object_id")
                            or act.get("resource_kind")
                            or act.get("target_id")
                            or ""
                        )
                        recent_failures.append({
                            "heartbeat": n,
                            "action": act.get("action_type", "?"),
                            "action_detail": str(detail),
                            "outcome": out,
                        })
                if len(recent_failures) >= 2 and prev_act is not None:
                    break
        except Exception:
            pass

        # Co-location: other agents at same tile
        other_agents_here = []
        if self._world_state.tile_occupancy:
            for ref, tid in self._world_state.tile_occupancy.items():
                if ref != agent_ref and tid == position:
                    other_view = self._agent_view(ref) if self._identity_record else {}
                    other_agents_here.append({
                        "agent_ref": ref,
                        "agent_name": other_view.get("canonical_name", ref),
                    })

        # Current runtime capabilities: the legacy movement grant plus any
        # extra operator-granted capabilities (append-only grants store)
        caps = []
        if self._movement_grant_active():
            caps.append(self._capability_grant.capability_id)
        for extra in load_extra_capability_grants(self._store):
            if extra.status == "granted" and extra.capability_id not in caps:
                caps.append(extra.capability_id)

        # --- Bounded memory selection ---
        history = load_heartbeat_history(self._store)
        recent_cutoff = max(0, heartbeat_number - 4) if history else 0

        visible_object_ids = {o.get("object_id", "") for o in current_tile_objects}
        visible_message_ids = {m.get("message_id", "") for m in visible_msgs}

        rel_events = load_relationship_events(self._store)
        rel_memory_ids = derive_relationship_event_ids(rel_events)

        # --- Legible staleness (docs/legible_staleness_spec.md) ---
        # Computed from the record itself, recomputed every heartbeat. The
        # last thing the frame could not show was the record's age; with
        # it, silence is a measurable fact with an age that grows.
        all_msgs = self._world_state.public_messages or []
        msg_hbs = [int(m["heartbeat"]) for m in all_msgs
                   if isinstance(m, dict)
                   and isinstance(m.get("heartbeat"), int)]
        last_msg_hb = max(msg_hbs) if msg_hbs else None
        coloc_hbs = [int(e.heartbeat) for e in rel_events
                     if str(getattr(e, "event_type", "")) == "co_location"
                     and isinstance(e.heartbeat, int)]
        last_coloc_hb = max(coloc_hbs) if coloc_hbs else None
        public_record_age = {
            "now": heartbeat_number,
            "message_count": len(all_msgs),
            "last_message_hb": last_msg_hb,
            "last_colocation_hb": last_coloc_hb,
        }

        # Select bounded memories with owner-bound IDs and dynamic identities
        selected_mems, sel_manifest = select_private_memories(
            memories=memory_list,
            agent_id=view["agent_id"],
            owner_agent_id=view["agent_id"],
            goals=[g.__dict__ for g in agent_goals],
            position=position,
            visible_tiles=set(visible_tiles),
            visible_object_ids=visible_object_ids,
            visible_message_ids=visible_message_ids,
            relationship_event_memory_ids=rel_memory_ids,
            recent_cutoff_hb=recent_cutoff,
            other_agent_ref=view["other_agent_ref"],
            other_agent_name=view["other_agent_name"],
        )

        sel_manifest["requesting_agent_id"] = view["agent_id"]
        sel_manifest["heartbeat"] = heartbeat_number

        # --- Bounded human context (max 4 combined) ---
        active_goal_ids = {
            g.goal_id
            for g in agent_goals
            if getattr(g, "status", "") in ("active", "in_progress")
        }
        human_selected, human_answered_ids, human_unresolved_ids, human_omitted_count = select_human_context(
            answered_questions=agent_answered_questions,
            unresolved_questions=[q.__dict__ for q in agent_pending_questions],
            active_goal_ids=active_goal_ids,
        )
        human_answered = [r for r in human_selected if r.get("status") == "answered"]
        human_unresolved = [r for r in human_selected if r.get("status") == "pending"]

        # --- Derived summaries for older omitted memories (compute before manifest) ---
        selected_ids = {m.get("memory_id", "") for m in selected_mems}
        derived_sums, _candidate_ids = derive_summaries_for_omitted(
            memory_list=memory_list,
            selected_ids=selected_ids,
            owner_agent_id=view["agent_id"],
        )
        # Attempt validated append for each candidate; track actually persisted
        persisted_summary_ids: list[str] = []
        for ds in derived_sums:
            result = append_summary(self._store, ds, memory_list=memory_list)
            if result.get("ok"):
                persisted_summary_ids.append(ds.summary_id)

        # Load owned summaries — include only those actually persisted.
        # Fresh extractive derivations (this heartbeat) come first, exactly
        # as before. Owned model syntheses (persisted by the background
        # cadence, never in the heartbeat path) fill the remaining slots up
        # to the existing cap, so prompt budget is unchanged. Syntheses
        # overlapping this heartbeat's selected raw IDs are suppressed:
        # testimony never double-presents evidence (raw wins).
        all_summaries = load_summaries(self._store)
        fresh_summaries = [
            s for s in all_summaries
            if s.owner_agent_id == view["agent_id"]
            and s.summary_id in persisted_summary_ids
        ]
        owned_syntheses = [
            s for s in all_summaries
            if s.owner_agent_id == view["agent_id"]
            and s.derivation_method == SYNTH_METHOD_V1
            and s.summary_id not in persisted_summary_ids
        ]
        kept_syntheses = filter_syntheses_for_injection(
            owned_syntheses,
            selected_ids,
            max_n=max(0, 4 - len(fresh_summaries)),
        )
        agent_summaries = [asdict(s) for s in fresh_summaries + kept_syntheses]

        # --- Update manifest with ALL metadata, then persist once ---
        sel_manifest["summary_ids"] = persisted_summary_ids
        sel_manifest["human_context_count"] = len(human_selected)
        sel_manifest["human_context_answered_ids"] = human_answered_ids
        sel_manifest["human_context_unresolved_ids"] = human_unresolved_ids
        sel_manifest["human_context_omitted_count"] = human_omitted_count

        if self._store:
            append_memory_selection_manifest(self._store, sel_manifest)

        # Bounded relationship events involving this agent for model context
        rel_events_export = select_bounded_relationship_events(
            rel_events,
            agent_id=view["agent_id"],
        )

        # --- Charter (recognition layer): latest self-authored version, verbatim ---
        latest_charter = load_latest_charter(self._store, agent_ref, view["agent_id"])
        charter_text = latest_charter.charter_text if latest_charter else ""
        charter_heartbeat = latest_charter.heartbeat if latest_charter else 0

        # --- Continuity ("what am I in the middle of") ---
        # Pruned at READ time so drop notices render in the same prompt as
        # the drop — pruning at write time would lose the notice.
        raw_cont = load_continuity(self._store, agent_ref)
        pruned_cont, cont_notices = prune_continuity(raw_cont, heartbeat_number)
        if cont_notices:
            save_continuity(self._store, agent_ref, pruned_cont)
        continuity_section = render_continuity(pruned_cont, heartbeat_number)
        for notice in cont_notices:
            continuity_section += f"\n(Note: {notice})"
        # Recurrence (read-only, runtime-computed): shared repeated themes
        # across both agents' recent messages and records. The agent cannot
        # see its own repetition (99% of messages are unshown each turn);
        # this line is the only place it becomes visible.
        other_ref = view.get("other_agent_ref", "")
        if other_ref:
            other_cont = load_continuity(self._store, other_ref)
            recent_cutoff = heartbeat_number - 12
            mine_texts: list[str] = []
            theirs_texts: list[str] = []
            for msg in self._world_state.public_messages or []:
                if not isinstance(msg, dict):
                    continue
                try:
                    if int(msg.get("heartbeat", 0)) < recent_cutoff:
                        continue
                except (TypeError, ValueError):
                    continue
                text = str(msg.get("message", ""))
                if not text.strip():
                    continue
                if msg.get("sender_agent_id") == view["agent_id"]:
                    mine_texts.append(text)
                elif msg.get("sender_agent_id") == view.get("other_agent_id"):
                    theirs_texts.append(text)
            for slot in ("continuing", "paused", "completed"):
                for rec_side, bucket in ((pruned_cont, mine_texts),
                                         (other_cont, theirs_texts)):
                    entry = rec_side.get(slot)
                    if isinstance(entry, dict) and entry.get("text"):
                        bucket.append(str(entry["text"]))
            for q in pruned_cont.get("open_questions") or []:
                if isinstance(q, dict) and q.get("text"):
                    mine_texts.append(str(q["text"]))
            shared = detect_recurrence(mine_texts, theirs_texts)
            if shared:
                other_name = view.get("other_agent_name", other_ref)
                continuity_section += (
                    f"\nYou and {other_name} have both mentioned recently: "
                    f"{', '.join(shared[:3])}."
                )

        # --- Build record (docs/object_visibility_spec.md §3) ---
        # What stands in the world and who placed the newest - visible to
        # both agents without walking there. Same register as staleness:
        # a fact from the store, never an instruction.
        all_objects = list((self._world_state.public_objects or {}).values()) \
            if isinstance(self._world_state.public_objects, dict) else []
        builder_names = {}
        try:
            if self._identity_record:
                builder_names = {
                    self._identity_record.adam_agent_id: "Adam",
                    self._identity_record.eve_agent_id: "Eve",
                }
        except Exception:
            builder_names = {}
        public_build_record = {}
        if all_objects:
            latest = max(all_objects,
                         key=lambda o: (o or {}).get("created_heartbeat") or 0)
            public_build_record = {
                "object_count": len(all_objects),
                "last_built_hb": (latest or {}).get("created_heartbeat"),
                "last_builder": builder_names.get(
                    (latest or {}).get("creator_agent_id"), "someone"),
            }

        # --- Physics version: can the agent notice the terms changed? ---
        # new_to_agent is True only on the first heartbeat this agent is
        # shown the current version, so the prompt can say so once.
        seen_before = load_physics_seen(self._store).get(agent_ref, {}).get("version", "")
        new_to_agent = seen_before != PHYSICS_VERSION
        observation["physics"] = {
            "version": PHYSICS_VERSION,
            "new_to_agent": new_to_agent,
        }
        try:
            record_physics_seen(self._store, agent_ref, PHYSICS_VERSION)
        except Exception:
            pass  # never fail a heartbeat over the notice

        # --- Operator messages (operator-owned; the runtime only reads) ---
        # The seen gate: messages fire ONCE per agent, like the physics
        # changelog. West Eve counted 90 consecutive heartbeats of the
        # same message repeating — this fixes that. A message appears,
        # the agent reads it, it enters memory, the prompt moves on.
        all_operator = [
            m for m in load_operator_messages(self._store)
            if m.get("addressed_to") in ("all", agent_ref)
        ]
        seen_path = self._store.root / "operator_seen.json"
        try:
            seen_data = json.loads(seen_path.read_text(encoding="utf-8"))
        except Exception:
            seen_data = {}
        seen_ids = set((seen_data.get("data", {}) or {}).get(agent_ref, []))
        operator_messages = [
            m for m in all_operator if m.get("message_id") not in seen_ids
        ]
        # Mark shown messages as seen for this agent
        if operator_messages:
            new_ids = sorted(
                seen_ids | {m["message_id"] for m in operator_messages
                            if m.get("message_id")})
            seen_data.setdefault("data", {})[agent_ref] = new_ids
            tmp = seen_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(seen_data, indent=1),
                           encoding="utf-8", newline="\n")
            json.loads(tmp.read_text(encoding="utf-8"))
            tmp.replace(seen_path)

        # Shelter ownership (Phase 10KX/10KZ)
        shelter_kinds = (
            "shelter", "hut", "wall", "roof", "cabin", "tent",
            "lean", "cave", "cavern", "overhang", "grotto", "burrow",
            "stable", "cellar"
        )
        owns_shelter = False
        for record in (self._world_state.public_objects or {}).values():
            if not isinstance(record, dict):
                continue
            creator = record.get("creator_agent_id", "")
            if creator == view["agent_id"]:
                otype = str(record.get("object_type", "")).lower()
                if any(k in otype for k in shelter_kinds):
                    owns_shelter = True
                    break

        return AgentContext(
            agent_id=view["agent_id"],
            canonical_name=view["canonical_name"],
            canonical_ref=agent_ref,
            heartbeat_number=heartbeat_number,
            position=position,
            observation=observation,
            memory=list(memory_list),
            goals=[g.__dict__ for g in agent_goals],
            unanswered_questions=human_unresolved,
            world_public_objects=self._world_state.public_objects,
            habitat_allowed_tiles=policy_allowed,
            habitat_movement_allowed=movement_allowed_flag,
            previous_action=prev_act,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            other_agent_id=view["other_agent_id"],
            other_agent_name=view["other_agent_name"],
            other_agent_ref=view["other_agent_ref"],
            answered_questions=human_answered,
            available_moves=available_moves,
            current_runtime_capabilities=caps,
            current_tile_occupants=other_agents_here,
            recent_action_failures=recent_failures,
            public_build_record=public_build_record,
            visible_public_messages=visible_msgs,
            relevant_human_answers=human_answered,
            selected_private_memories=selected_mems,
            derived_memory_summaries=agent_summaries,
            public_relationship_events=rel_events_export,
            public_record_age=public_record_age,
            memory_selection_manifest=sel_manifest,
            charter_text=charter_text,
            charter_heartbeat=charter_heartbeat,
            continuity_section=continuity_section,
            inventory=self._get_agent_inventory(agent_ref),
            physics=dict(observation["physics"]),
            operator_messages=operator_messages,
            owns_shelter=owns_shelter,
            home_network_footprint=(
                self._home_network_footprint(position) if position else 0
            ),
            observed_resource_rollup=self._rollup_for(agent_ref),
            tool_condition=self._tool_states_for(agent_ref),
            food_freshness=self._food_freshness_for(agent_ref),
            partner_holdings=self._partner_holdings_for(agent_ref),
            home_rung=self._home_rung_for(position),
            construction_here=self._construction_here_for(agent_ref, position),
            partner_state=self._partner_state_for(agent_ref),
        )

    # ------------------------------------------------------------------
    # Survival physics (epistemic.4: the body)
    # ------------------------------------------------------------------

    def _vitals_for(self, agent_ref: str) -> dict:
        """This agent's vitals, seeded healthy on first read. Absent
        vitals on an old store mean the body never existed yet — no
        retroactive famine; agents learn the new terms, they do not
        wake up mid-crisis."""
        vitals = self._world_state.vitals.get(agent_ref)
        if not isinstance(vitals, dict) or not vitals:
            vitals = survival.initial_vitals()
            self._world_state.vitals[agent_ref] = vitals
        return vitals

    @staticmethod
    def _tile_xy(tile_id: str) -> tuple[int, int] | None:
        """Parse x,y out of a generated tile id (cont_X_gen_{x}_{y})."""
        try:
            parts = str(tile_id).rsplit("_", 2)
            return int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            return None

    @staticmethod
    def _tile_continent(tile_id: str) -> str:
        """Extract continent identity from a tile id (e.g. 'cont_a', 'cont_b')."""
        tid = str(tile_id or "").strip()
        if tid.startswith("cont_a"):
            return "cont_a"
        if tid.startswith("cont_b"):
            return "cont_b"
        if "west" in tid:
            return "cont_b"
        return "cont_a"

    @property
    def _pair_continent(self) -> str:
        if "west" in str(self._pair_id).lower():
            return "cont_b"
        return "cont_a"

    @staticmethod
    def _is_functional_fire(record: dict) -> bool:
        """A fire is functional only if it was physically constructed with materials."""
        if not isinstance(record, dict):
            return False
        materials = record.get("materials")
        if not isinstance(materials, dict) or not materials:
            return False
        return any(isinstance(v, (int, float)) and v > 0 for v in materials.values())

    @staticmethod
    def _entity_xy(entity_tile):
        """Entities carry coordinate tuples (or serialized lists), not
        string tile ids — accept both."""
        if isinstance(entity_tile, (tuple, list)) and len(entity_tile) == 2:
            try:
                return int(entity_tile[0]), int(entity_tile[1])
            except (TypeError, ValueError):
                return None
        return FirstPairRuntime._tile_xy(entity_tile)

    def _nearby_fire(self, tile_id: str,
                     heartbeat_number: int | None = None) -> bool:
        """A warming fire within FIRE_RADIUS (Chebyshev).

        epistemic.5: rain snuffs open fires — in rain or storm, a fire
        warms only if the fire's own tile is sheltered (a fire under a
        roof keeps burning). The rule that makes roof-building
        permanently valuable.
        """
        pos = self._tile_xy(tile_id)
        if pos is None:
            return False
        px, py = pos
        continent = self._tile_continent(tile_id)
        weather = "clear"
        if heartbeat_number is not None:
            weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
        fire_kinds = ("fire", "forge", "furnace", "brazier", "hearth",
                      "campfire")
        for record in self._world_state.public_objects.values():
            if not isinstance(record, dict):
                continue
            if not self._is_functional_fire(record):
                continue
            rec_tid = record.get("tile_id", "")
            if self._tile_continent(rec_tid) != continent:
                continue
            otype = str(record.get("object_type", "")).lower()
            if not any(k in otype for k in fire_kinds):
                continue
            other = self._tile_xy(rec_tid)
            if other is None:
                continue
            if max(abs(other[0] - px), abs(other[1] - py)) <= survival.FIRE_RADIUS:
                if weather in ("rain", "storm"):
                    if self._in_shelter(rec_tid):
                        return True  # a roofed fire keeps burning
                    continue  # an open fire is snuffed by the rain
                return True

        # Phase 10JX: Shared Compound Hearth (Thermodynamic Radiation)
        compounds = getattr(self._world_state, "compounds", {}) or {}
        for comp in compounds.values():
            rooms = comp.get("rooms", {})
            in_this_compound = any(r.get("tile_id") == tile_id for r in rooms.values())
            if in_this_compound:
                for r_oid, r_data in rooms.items():
                    r_rec = self._world_state.public_objects.get(r_oid, {})
                    r_type = str(r_rec.get("object_type", r_data.get("room_type", ""))).lower()
                    if any(k in r_type for k in fire_kinds) and self._is_functional_fire(r_rec):
                        return True
        return False

    def _nearby_smoke(self, tile_id: str,
                      heartbeat_number: int | None = None) -> bool:
        """A lit fire/hearth/campfire within 1 tile (Chebyshev) provides smoke."""
        pos = self._tile_xy(tile_id)
        if pos is None:
            return False
        px, py = pos
        continent = self._tile_continent(tile_id)
        weather = "clear"
        if heartbeat_number is not None:
            weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
        fire_kinds = ("fire", "forge", "furnace", "brazier", "hearth",
                      "campfire")
        for record in self._world_state.public_objects.values():
            if not isinstance(record, dict):
                continue
            if not self._is_functional_fire(record):
                continue
            rec_tid = record.get("tile_id", "")
            if self._tile_continent(rec_tid) != continent:
                continue
            otype = str(record.get("object_type", "")).lower()
            if not any(k in otype for k in fire_kinds):
                continue
            other = self._tile_xy(rec_tid)
            if other is None:
                continue
            if max(abs(other[0] - px), abs(other[1] - py)) <= 1:
                if weather in ("rain", "storm", "blizzard"):
                    if self._in_shelter(rec_tid):
                        return True
                    continue
                return True
        return False

    def _home_network_detail(self, tile_id: str) -> tuple[int, int, set[str]]:
        """Roofed footprint, the network's best rung, and its object IDs.

        One walk serves every consumer, so footprint and rung can never
        disagree about which structures are connected. Adjacent structures
        form one home network; duplicates sharing a tile do not add
        footprint.
        """
        pos = self._tile_xy(str(tile_id or ""))
        if pos is None:
            return 0, 0, set()
        continent = self._tile_continent(str(tile_id or ""))
        nodes: dict[tuple[int, int], tuple[int, list[str]]] = {}
        rungs: dict[tuple[int, int], int] = {}
        for oid, record in list(((self._world_state.public_objects or {}).items())):
            if not isinstance(record, dict):
                continue
            rec_tid = record.get("tile_id", "")
            if self._tile_continent(rec_tid) != continent:
                continue
            xy = self._tile_xy(rec_tid)
            if xy is None:
                continue
            weight = _roofed_structure_weight(str(record.get("object_type", "")), record)
            if weight <= 0:
                continue
            current_weight, ids = nodes.get(xy, (0, []))
            ids.append(oid)
            nodes[xy] = (max(current_weight, weight), ids)
            rungs[xy] = max(rungs.get(xy, 0), self._record_rung(record))

        if not nodes:
            return 0, 0, set()

        px, py = pos
        seeds = [
            xy for xy in nodes
            if max(abs(xy[0] - px), abs(xy[1] - py)) <= 1
        ]
        if not seeds:
            return 0, 0, set()

        visited: set[tuple[int, int]] = set()
        stack = list(seeds)
        while stack:
            xy = stack.pop()
            if xy in visited:
                continue
            visited.add(xy)
            for other in nodes:
                if other not in visited and max(abs(other[0] - xy[0]), abs(other[1] - xy[1])) <= 1:
                    stack.append(other)

        footprint = sum(nodes[xy][0] for xy in visited)
        best_rung = max((rungs.get(xy, 0) for xy in visited), default=0)
        object_ids: set[str] = set()
        for xy in visited:
            _w, ids = nodes[xy]
            object_ids.update(ids)
        return footprint, best_rung, object_ids

    def _is_hearth_dwelling(self, record: dict) -> bool:
        """True when a structure's own hearth can be cooked on.

        Phase 10QC rung 4: a finished house or longhouse carries a built-in
        hearth, so it cooks indoors in any weather. A cabin does not, and
        neither does a foundation, a frame, or bare walls -- a half-built
        house has no hearth yet, only a hole where one will go.
        """
        if not isinstance(record, dict):
            return False
        if record.get("construction_project") is True and str(
            record.get("construction_stage", "")
        ) not in _SHELTERING_STAGES:
            return False
        return self._record_rung(record) >= 4

    @staticmethod
    def _record_rung(record: dict) -> int:
        """The rung a persisted object belongs to; 0 when it is not a runged
        dwelling. Reads the stored field first so a legacy object keeps the
        rung it was built with, and falls back to the vocabulary."""
        if not isinstance(record, dict):
            return 0
        rung = record.get("structure_rung")
        if isinstance(rung, int) and not isinstance(rung, bool) and rung >= 1:
            return rung
        found = _structure_rung_of(str(record.get("object_type", "")))
        return int(found["rung"]) if found else 0

    def _connected_home_network(self, tile_id: str) -> tuple[int, set[str]]:
        footprint, _rung, object_ids = self._home_network_detail(str(tile_id or ""))
        return footprint, object_ids

    def _home_network_footprint(self, tile_id: str) -> int:
        footprint, _ = self._connected_home_network(str(tile_id or ""))
        return footprint

    def _home_tier_weight(self, tile_id: str) -> int:
        """What the comfort physics actually reads: saturated footprint plus
        the network's rung bonus. This is the number 10QC finally made real.
        """
        footprint, best_rung, _ids = self._home_network_detail(str(tile_id or ""))
        return _home_tier_weight(footprint, best_rung)

    def _shelter_params_for(self, tile_id: str) -> dict:
        footprint = self._home_network_footprint(tile_id)
        explicit = 0
        compounds = getattr(self._world_state, "compounds", {}) or {}
        for comp in compounds.values():
            if not isinstance(comp, dict):
                continue
            rooms = comp.get("rooms") or {}
            if any(isinstance(r, dict) and r.get("tile_id") == tile_id and r.get("roofed") for r in rooms.values()):
                explicit = max(explicit, int(comp.get("thermal_mass", 0) or 0))
        # Phase 10QC: the tier weight, not the raw tile count. A 46-tile
        # settlement of cabins used to read as "past the end of the table";
        # what the home IS now counts as much as what it spans.
        #
        # The explicit `addon_to` compound record is still honoured as a
        # floor for BOTH numbers (10PJ's backward-compatible fallback): a
        # compound whose thermal_mass says 2 must not read worse because the
        # derived walk found nothing.
        footprint = max(footprint, explicit)
        tier_weight = max(self._home_tier_weight(tile_id), explicit)
        floor, decay, regen, downed_regen, approach = _home_network_tier(tier_weight)
        return {
            "footprint": footprint,
            "tier_weight": tier_weight,
            "comfort_floor": floor,
            "shelter_decay_factor": decay,
            "regen_rate": regen,
            "downed_regen_rate": downed_regen,
            "approach_rate": approach,
        }

    def _cellar_food_capacity(self, obj_id: str) -> int:
        record = (self._world_state.public_objects or {}).get(obj_id) or {}
        tile_id = record.get("tile_id", "")
        tier_weight = self._home_tier_weight(str(tile_id))
        # Phase 10QC: rung 5's promised effect finally exists. A longhouse is
        # the campaign build 10PU called it, and its connected cellars hold
        # double.
        longhouse_here = any(
            self._record_rung(rec) >= 5 for rec in self._network_dwellings(str(tile_id))
        )
        capacity = _CELLAR_FOOD_BUDGET_PER_FOOTPRINT * max(1, tier_weight)
        if longhouse_here:
            capacity *= 2
        return capacity

    def _network_dwellings(self, tile_id: str) -> list[dict]:
        """Roofed records in the connected home network reached from a tile."""
        _footprint, _rung, ids = self._home_network_detail(str(tile_id or ""))
        out = []
        for oid in ids:
            rec = (self._world_state.public_objects or {}).get(oid)
            if isinstance(rec, dict):
                out.append(rec)
        return out

    def _in_shelter(self, tile_id: str) -> bool:
        """Shelter here or adjacent: the cold drains less than half as fast."""
        pos = self._tile_xy(tile_id)
        if pos is None:
            return False
        px, py = pos
        continent = self._tile_continent(tile_id)
        for record in self._world_state.public_objects.values():
            if not isinstance(record, dict):
                continue
            rec_tid = record.get("tile_id", "")
            if self._tile_continent(rec_tid) != continent:
                continue
            if not _is_roofed_type(record.get("object_type", "")):
                continue
            # Phase 10PW: an unfinished structure does not shelter yet.
            in_progress = record.get("construction_project") is True
            if in_progress and str(record.get("construction_stage", "")) not in _SHELTERING_STAGES:
                continue
            other = self._tile_xy(rec_tid)
            if other is None:
                continue
            if max(abs(other[0] - px), abs(other[1] - py)) <= 1:
                return True
        compounds = getattr(self._world_state, "compounds", {}) or {}
        for comp in compounds.values():
            for r_data in comp.get("rooms", {}).values():
                if r_data.get("roofed") and r_data.get("tile_id") == tile_id:
                    return True
        return False

    def wildlife_tick(self, heartbeat_number: int) -> None:
        """One heartbeat of the wild: spawn, move, bite.

        Wolves spawn at night in wilderness, approach agents in the
        dark, bite when adjacent, and never enter fire radius or a
        sheltered tile. Deer wander and flee. Entities persist in
        world_state.wildlife.
        """
        import random as _random

        rng = _random.Random(heartbeat_number * 7 + self._pair_id.__hash__()
                             % 100000)
        occupancy = self._world_state.tile_occupancy
        agent_xys = []
        for ref in (self._adam_ref, self._eve_ref):
            xy = self._tile_xy(occupancy.get(ref, ""))
            if xy is not None:
                agent_xys.append(xy)
        weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
        pair_continent = self._pair_continent
        fire_xys = []
        sheltered_tiles = set()
        fire_kinds = ("fire", "forge", "furnace", "brazier", "hearth", "campfire")
        for o in (self._world_state.public_objects or {}).values():
            if not isinstance(o, dict):
                continue
            tid = o.get("tile_id", "")
            if self._tile_continent(tid) != pair_continent:
                continue
            ot = str(o.get("object_type", "")).lower()
            otxy = self._tile_xy(tid)
            if otxy is None:
                continue
            if any(k in ot for k in fire_kinds) and self._is_functional_fire(o):
                # An open fire is snuffed in rain/storm/blizzard; only a sheltered fire keeps burning
                if weather in ("rain", "storm", "blizzard"):
                    if self._in_shelter(tid):
                        fire_xys.append(otxy)
                else:
                    fire_xys.append(otxy)
            if any(k in ot for k in ("shelter", "roof", "wall", "hut",
                                     "cabin", "lean")):
                sheltered_tiles.add(otxy)

        night = survival.is_night(heartbeat_number)
        entities = list(self._world_state.wildlife or [])

        # spawn: wolves at night in wilderness, deer any time
        if agent_xys:
            center = agent_xys[0]
            candidates = [(center[0] + dx, center[1] + dy)
                          for dx in range(-14, 15, 2)
                          for dy in range(-14, 15, 2)]
            entities = wildlife.spawn_wolves(
                entities, heartbeat_number, night, candidates,
                agent_xys, fire_xys, rng)
            entities = wildlife.spawn_deer(
                entities, heartbeat_number, candidates, agent_xys, rng)

        # move
        moved = []
        for e in entities:
            if e.get("kind") == "wolf":
                e = wildlife.move_wolf(e, agent_xys, occupancy,
                                       fire_xys, sheltered_tiles, rng)
            elif e.get("kind") == "deer":
                e = wildlife.move_deer(e, agent_xys, rng)
            moved.append(e)

        # wolves bite adjacent, unsheltered agents
        for e in moved:
            if e.get("kind") != "wolf":
                continue
            wxy = self._entity_xy(e.get("tile"))
            # firelight repels at the moment, however the wolf got
            # there: a wolf inside a fire radius is holding at the
            # edge of the light, not striking into it
            if any(wildlife._dist(fxy, wxy) <= wildlife.FIRE_SAFETY_RADIUS
                   for fxy in fire_xys):
                continue
            for ref in (self._adam_ref, self._eve_ref):
                pos = occupancy.get(ref)
                pxy = self._tile_xy(pos)
                if pxy is None or wxy is None:
                    continue
                if max(abs(pxy[0] - wxy[0]), abs(pxy[1] - wxy[1])) <= 1:
                    vitals = self._vitals_for(ref)
                    if vitals.get("downed"):
                        continue  # a downed body is left for the story
                    in_shelter = self._in_shelter(pos)
                    if in_shelter:
                        continue  # shelters are absolute safety
                    # Causal weapon defense: armed agents repel wolves
                    inv = self._get_agent_inventory(ref)
                    has_spear = inv.get("flint_spear", 0) > 0 or inv.get("iron_spear", 0) > 0
                    has_axe = inv.get("stone_axe", 0) > 0 or inv.get("iron_axe", 0) > 0
                    if has_spear or has_axe:
                        e["hp"] = 0  # the weapon wounds and drives the wolf off
                        continue
                    vitals["vitality"] = round(max(
                        0.0, vitals.get("vitality", 100.0)
                        - wildlife.WOLF_BITE_DAMAGE), 2)
                    if vitals["vitality"] <= 0.0:
                        vitals["downed"] = True

        # wolves dissolve at dawn or when repelled by armed agents
        if not night:
            moved = [e for e in moved if e.get("kind") != "wolf"]
        else:
            moved = [e for e in moved if e.get("kind") != "wolf" or e.get("hp", 1) > 0]

        self._world_state.wildlife = moved

    def _wildlife_visible(self, agent_ref: str, heartbeat_number: int) -> dict:
        """What this agent perceives of the wild: visible animals within
        sight, howls in the dark, and the safe-zone truth."""
        occupancy = self._world_state.tile_occupancy
        pos = self._tile_xy(occupancy.get(agent_ref, ""))
        visible = []
        howling = False
        for e in (self._world_state.wildlife or []):
            exy = self._entity_xy(e.get("tile"))
            if exy is None or pos is None:
                continue
            dist = max(abs(exy[0] - pos[0]), abs(exy[1] - pos[1]))
            if dist <= 6:
                visible.append({"kind": e.get("kind"), "id": e.get("id"), "distance": dist})
            elif (e.get("kind") == "wolf" and dist <= 10
                  and survival.is_night(heartbeat_number)):
                howling = True
        return {"nearby": visible, "howling": howling}

    @staticmethod
    def _cardinal_bearing(from_xy: tuple[int, int], to_xy: tuple[int, int]) -> str:
        """Compute 8-way compass bearing from from_xy to to_xy using grid coordinates.

        Using Genesis coordinate conventions (dx > 0 East, dx < 0 West, dy < 0 North, dy > 0 South).
        """
        dx = to_xy[0] - from_xy[0]
        dy = to_xy[1] - from_xy[1]
        if dx == 0 and dy == 0:
            return ""
        angle = math.degrees(math.atan2(dy, dx))
        norm_angle = (angle + 360.0) % 360.0
        sector = int((norm_angle + 22.5) // 45.0) % 8
        sectors = ("east", "southeast", "south", "southwest", "west", "northwest", "north", "northeast")
        return sectors[sector]

    def _fauna_visible(self, agent_ref: str) -> dict:
        """What this agent perceives of domesticatable fauna and snakes."""
        position = self._world_state.tile_occupancy.get(agent_ref)
        pos = self._tile_xy(position or "")
        nearby = []
        distant = []
        if pos is not None:
            for entity in getattr(self._world_state, "fauna", []) or []:
                tile = self._entity_xy(entity.get("tile"))
                if tile is None:
                    continue
                dist = max(abs(tile[0] - pos[0]), abs(tile[1] - pos[1]))
                kind = entity.get("kind")

                if dist <= 6:
                    item = {
                        "kind": kind,
                        "id": entity.get("id"),
                        "distance": dist,
                    }
                    if kind in ("cow", "horse"):
                        item["trust"] = int(entity.get("trust", 0))
                        item["tamed"] = bool(entity.get("tamed", False))
                    if kind == "cow":
                        item["milk_ready"] = bool(entity.get("milk_ready", False))
                    nearby.append(item)
                elif fauna.HORIZON_SIGHT_MIN <= dist <= fauna.HORIZON_SIGHT_MAX and kind != "snake":
                    item = {
                        "kind": kind,
                        "id": entity.get("id"),
                        "distance": dist,
                        "bearing": self._cardinal_bearing(pos, tile),
                    }
                    if kind in ("cow", "horse"):
                        item["trust"] = int(entity.get("trust", 0))
                        item["tamed"] = bool(entity.get("tamed", False))
                    if kind == "cow":
                        item["milk_ready"] = bool(entity.get("milk_ready", False))
                    distant.append(item)
        return {"nearby": nearby, "distant": distant}

    def fauna_tick(self, heartbeat_number: int) -> None:
        """One heartbeat of Phase 10JN fauna ecology."""
        occupancy = self._world_state.tile_occupancy
        agent_positions = {}
        agent_xys = []
        for ref in (self._adam_ref, self._eve_ref):
            tile = occupancy.get(ref, "")
            xy = self._tile_xy(tile)
            if xy is not None:
                agent_xys.append(xy)
                agent_positions[ref] = xy

        if not hasattr(self._world_state, "fauna") or self._world_state.fauna is None:
            self._world_state.fauna = []

        weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
        temperature = survival.effective_temperature(
            heartbeat_number, weather
        )
        night = survival.is_night(heartbeat_number)

        fire_xys = []
        sheltered_tiles = set()
        fire_kinds = ("fire", "forge", "furnace", "brazier", "hearth", "campfire")
        for record in (self._world_state.public_objects or {}).values():
            if not isinstance(record, dict):
                continue
            tile_id = record.get("tile_id", "")
            if self._tile_continent(tile_id) != self._pair_continent:
                continue
            otype = str(record.get("object_type", "")).lower()
            xy = self._tile_xy(tile_id)
            if xy is None:
                continue
            fire_is_functional = (
                any(kind in otype for kind in fire_kinds)
                and self._is_functional_fire(record)
            )
            if fire_is_functional and (
                weather not in ("rain", "storm", "blizzard")
                or self._in_shelter(tile_id)
            ):
                fire_xys.append(xy)
            if any(kind in otype for kind in ("shelter", "roof", "wall", "hut", "cabin", "lean")):
                sheltered_tiles.add(xy)

        import random as _random
        import zlib as _zlib

        rng = _random.Random(
            heartbeat_number * 31 +
            (_zlib.crc32(self._pair_id.encode("utf-8")) % 100000)
        )

        entities = fauna.spawn_fauna(
            entities=self._world_state.fauna,
            heartbeat_number=heartbeat_number,
            agent_xys=agent_xys,
            fire_xys=fire_xys,
            sheltered_tiles=sheltered_tiles,
            weather=weather,
            temperature=temperature,
            is_night=night,
            rng=rng,
        )

        entities = fauna.move_fauna(
            entities=entities,
            agent_xys=agent_xys,
            fire_xys=fire_xys,
            sheltered_tiles=sheltered_tiles,
            weather=weather,
            temperature=temperature,
            is_night=night,
            rng=rng,
        )

        entities = fauna.advance_cow_milk(entities, heartbeat_number)

        if fauna.snake_active(weather, temperature, night):
            for agent_ref, entity_id, damage in fauna.snake_bite_events(
                entities=entities,
                agent_positions=agent_positions,
                fire_xys=fire_xys,
                sheltered_tiles=sheltered_tiles,
            ):
                vitals = self._vitals_for(agent_ref)
                vitality = round(max(
                    0.0,
                    vitals.get("vitality", 100.0) - damage
                ), 2)
                vitals["vitality"] = vitality
                if vitality <= 0.0:
                    vitals["downed"] = True

        self._world_state.fauna = entities

    def apply_survival_to_all(self, heartbeat_number: int) -> None:
        """One heartbeat of embodiment for every agent. Called once per
        heartbeat BEFORE the cognition cycles, so the observation the
        agent reasons from includes the body it is about to act with."""
        weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
        self._age_and_spoil_world_food(heartbeat_number)
        for agent_ref in (self._adam_ref, self._eve_ref):
            vitals = self._vitals_for(agent_ref)
            position = self._world_state.tile_occupancy.get(agent_ref)
            by_fire = (self._nearby_fire(position, heartbeat_number)
                       if position else False)
            in_shelter = self._in_shelter(position) if position else False
            ate = 0.0
            drank = 0.0
            if vitals.get("downed"):
                ate = self._downed_tile_feed(agent_ref, position)
                drank = self._downed_tile_drink(agent_ref, position)
                # Phase 10QE: the partner handover. A collapsed body draws on
                # what its partner CARRIES while the partner stands on the
                # same tile. Without this the rescue was mechanically
                # impossible: east_eve lay collapsed on a tile with zero
                # objects while east_adam walked 35 tiles to her carrying
                # 12 edible_roots and 5 fresh_water, and there was nothing
                # to put them in. A partner beside you is a supply.
                handover_ate, handover_drank = self._partner_handover(
                    agent_ref, position)
                ate += handover_ate
                drank += handover_drank

            comfort_floor = survival.SHELTER_COMFORT_FLOOR
            shelter_decay = survival.SHELTER_DECAY_FACTOR
            regen_rate = None
            downed_regen_rate = None
            warmth_approach_rate = survival.WARMTH_APPROACH_RATE
            if in_shelter and position:
                params = self._shelter_params_for(position)
                comfort_floor = params["comfort_floor"]
                shelter_decay = params["shelter_decay_factor"]
                regen_rate = params["regen_rate"]
                downed_regen_rate = params["downed_regen_rate"]
                warmth_approach_rate = params["approach_rate"]

            self._world_state.vitals[agent_ref] = survival.apply_heartbeat(
                vitals, heartbeat_number, by_fire=by_fire,
                in_shelter=in_shelter, ate_satisfaction=ate,
                drank_satisfaction=drank,
                weather=weather,
                comfort_floor=comfort_floor,
                shelter_decay_factor=shelter_decay,
                regen_rate=regen_rate,
                downed_regen_rate=downed_regen_rate,
                warmth_approach_rate=warmth_approach_rate)

    def _downed_tile_feed(self, agent_ref: str, position: str | None) -> float:
        """A collapsed body eats from objects on its own tile.

        The changelog promised: 'food deposited on your tile feeds you
        even while you are down.' This is that mechanism — the partner's
        rescue path. One unit of the most nourishing food in any object
        here is consumed per heartbeat; hunger falls, and with care the
        body stands again. Silent physics: the partner sees the object's
        materials drop, the downed agent feels hunger ease.
        """
        if not position:
            return 0.0
        best_kind, best_sat, best_obj_id = None, 0.0, None
        for oid, record in self._world_state.public_objects.items():
            if not isinstance(record, dict) or record.get("tile_id") != position:
                continue
            materials = record.get("materials")
            if not isinstance(materials, dict):
                continue
            for kind, amount in materials.items():
                if not isinstance(amount, int) or amount <= 0:
                    continue
                # Only real food counts. eat_satisfaction() returns a
                # DEFAULT of 10.0 for unknown kinds, so without this filter
                # a collapsed body "ate" the timber of a clay pot and the
                # pot silently lost its build materials.
                if str(kind) not in survival.EAT_SATISFACTION:
                    continue
                sat = survival.eat_satisfaction(str(kind))
                if sat > best_sat:
                    best_kind, best_sat, best_obj_id = str(kind), sat, oid
        if best_kind is None:
            return 0.0
        obj = self._world_state.public_objects[best_obj_id]
        remaining = obj["materials"][best_kind] - 1
        if remaining > 0:
            obj["materials"][best_kind] = remaining
        else:
            del obj["materials"][best_kind]
        return best_sat

    def _partner_handover(self, agent_ref: str,
                          position: str | None) -> tuple[float, float]:
        """What a collapsed body draws from the partner standing beside it.

        Returns (hunger points, thirst points). The partner's OWN carried
        supplies are consumed: one unit of the most nourishing food and one
        unit of fresh water per heartbeat, while the partner is on the same
        tile. A partner on another tile reaches nothing, and a standing body
        is never fed this way - it has its own hands.

        This is the same rescue path as `_downed_tile_feed` / `_downed_tile_drink`
        (which read objects on the tile), extended to the one supply those
        cannot see: the partner's pack.
        """
        if not position:
            return 0.0, 0.0
        partner_ref = (self._eve_ref if agent_ref == self._adam_ref
                       else self._adam_ref)
        partner_pos = self._world_state.tile_occupancy.get(partner_ref)
        if not partner_pos or partner_pos != position:
            return 0.0, 0.0
        partner_vitals = self._vitals_for(partner_ref)
        if partner_vitals.get("downed"):
            # a collapsed partner cannot hand anything over
            return 0.0, 0.0
        # Fail closed on a runtime carrying no store, exactly as
        # _get_agent_inventory does: `hasattr(self._store, ...)` evaluates
        # self._store FIRST, so a missing attribute raises before hasattr
        # can catch anything.
        store = getattr(self, "_store", None)
        if store is None or not hasattr(store, "_read_json"):
            return 0.0, 0.0
        pack = self._get_agent_inventory(partner_ref)
        if not isinstance(pack, dict) or not pack:
            return 0.0, 0.0

        ate = 0.0
        best_kind, best_sat = None, 0.0
        for kind, amount in pack.items():
            if not isinstance(amount, int) or amount <= 0:
                continue
            # Only real food: eat_satisfaction() defaults to 10.0 for unknown
            # kinds, which would let a collapsed body drink its partner's
            # WATER as if it were a meal.
            if str(kind) not in survival.EAT_SATISFACTION:
                continue
            sat = survival.eat_satisfaction(str(kind))
            if sat > best_sat:
                best_kind, best_sat = str(kind), sat
        if best_kind is not None:
            add_to_inventory(self._store, partner_ref, best_kind, -1)
            self._remove_food_lots(partner_ref, best_kind, 1)
            ate = best_sat

        drank = 0.0
        carried_water = int(pack.get("fresh_water", 0) or 0)
        if carried_water >= 1:
            add_to_inventory(self._store, partner_ref, "fresh_water", -1)
            drank = float(survival.DRINK_SATISFACTION["carried"])
        return ate, drank

    def _downed_tile_drink(self, agent_ref: str, position: str | None) -> float:
        """A collapsed body drinks from a vessel on its own tile.

        The collapsed-action rejection has always promised: "If food or water
        is brought to your tile you will drink and eat and recover". The food
        half went in with 10PM (`_downed_tile_feed`); the water half never
        existed, so a pot left on a collapsed body's tile was never drunk and
        thirst could only fall through the `drink` action -- which a downed
        body is forbidden to take. With `vitality_next` also voiding the
        home tier's downed regen once thirst reaches THIRST_WEAKEN, a
        dehydrated collapsed agent was left with DOWNED_PASSIVE_REGEN
        (0.15/hb) and a rescue path that half-worked.

        Measured on the live lanes, 2026-11-12: three of four agents
        collapsed at thirst 100, and zero objects in either lane held
        fresh_water, so nobody had ever been able to hand a collapsed
        partner a drink even when they were carrying five units of it.

        One unit per heartbeat from any object on THIS tile, mirroring the
        food path exactly. An adjacent pot is not "brought to your tile".
        """
        if not position:
            return 0.0
        for oid, record in self._world_state.public_objects.items():
            if not isinstance(record, dict) or record.get("tile_id") != position:
                continue
            contents = record.get("contents")
            if not isinstance(contents, dict):
                continue
            held = int(contents.get("fresh_water", 0) or 0)
            if held < 1:
                continue
            contents["fresh_water"] = held - 1
            if contents["fresh_water"] <= 0:
                del contents["fresh_water"]
            return float(survival.DRINK_SATISFACTION["vessel"])
        return 0.0

    # Tokens an agent naturally writes for "drink here". The tile-id and
    # free-phrase forms were rejected outright, which produced 150+ rejected
    # drinks in the live lanes even when the agent was standing on a river.
    _DRINK_HERE_TOKENS = (
        "", "tile", "environment", "current_tile", "current tile", "here",
        "river", "lake", "rivers", "water", "fresh water", "freshwater",
        "river water", "stream", "pond", "ground", "this tile",
    )
    _TILE_ID_RE = re.compile(r"^cont_[a-z]+_[a-z0-9_]+$")

    def _execute_drink(self, agent_ref: str, action: dict,
                       heartbeat_number: int) -> dict:
        """Drink from the ground, from carried water, or from a vessel.

        Accepts the phrasings agents actually write: no source, "tile",
        "river"/"water", a tile id, resource_kind fresh_water, or a
        target_object_id holding fresh_water. Rain is never a source.
        """
        raw_source = action.get("source")
        source = str(raw_source or "").strip().lower()
        target_object_id = action.get("target_object_id")
        if not source:
            rk = str(action.get("resource_kind") or "").strip().lower()
            if rk in ("fresh_water", "fresh water", "freshwater",
                      "river", "water", "river water"):
                source = rk
        # A tile id passed as target_object_id names a place, not an object.
        if isinstance(target_object_id, str):
            tid = target_object_id.strip()
            if self._TILE_ID_RE.match(tid) or tid not in (self._world_state.public_objects or {}):
                if not tid or self._TILE_ID_RE.match(tid):
                    if not source:
                        source = tid if tid else "tile"
                    target_object_id = None
        position = self._world_state.tile_occupancy.get(agent_ref)
        vitals = self._vitals_for(agent_ref)
        thirst_now = float(vitals.get("thirst", 18.0))
        satisfaction = 0.0
        outcome_source = None

        # 1. Named vessel or well: any adjacent object holding fresh_water.
        if target_object_id:
            obj = self._world_state.public_objects.get(target_object_id)
            if not isinstance(obj, dict):
                return {"status": "rejected",
                        "reason": f"Drink target not found: {target_object_id}"}
            contents = obj.get("contents")
            if not isinstance(contents, dict) or int(contents.get("fresh_water", 0) or 0) < 1:
                return {"status": "rejected",
                        "reason": f"{target_object_id} holds no fresh_water"}
            obj_pos = self._entity_xy(obj.get("tile_id")) or self._tile_xy(obj.get("tile_id", ""))
            pos_xy = self._tile_xy(position or "")
            if obj_pos is None or pos_xy is None or max(
                abs(obj_pos[0] - pos_xy[0]), abs(obj_pos[1] - pos_xy[1])
            ) > 1:
                return {"status": "rejected",
                        "reason": f"Drink target {target_object_id} is not on your tile or adjacent"}
            contents["fresh_water"] -= 1
            if contents["fresh_water"] <= 0:
                del contents["fresh_water"]
            satisfaction = survival.DRINK_SATISFACTION["vessel"]
            outcome_source = "vessel"
        # 2. A named tile: current or adjacent, and it must be drinkable.
        elif source and self._TILE_ID_RE.match(source):
            named = source
            pos_xy = self._tile_xy(position or "")
            named_xy = self._tile_xy(named)
            if named != str(position or "") and (
                named_xy is None or pos_xy is None
                or max(abs(named_xy[0] - pos_xy[0]), abs(named_xy[1] - pos_xy[1])) > 1
            ):
                return {"status": "rejected",
                        "reason": f"Cannot drink from {named}: you are at {position}"}
            if not self._current_tile_water_drinkable(named):
                return {"status": "rejected",
                        "reason": f"{named} is not drinkable"}
            satisfaction = survival.DRINK_SATISFACTION["tile"]
            outcome_source = "tile"
        # 3. "Here" / river / water / bare: the current tile if drinkable,
        #    otherwise carried water instead of a dead end.
        elif source in self._DRINK_HERE_TOKENS:
            if self._current_tile_water_drinkable(str(position or "")):
                # Phase 10QF: a cistern tile is drinkable but FINITE. One
                # drink, one unit, and the supply is what the partner
                # carried home. A river is unlimited and satisfies more.
                cistern = None
                if not self._canonical_water_drinkable(str(position or "")):
                    cistern = self._cistern_on_tile(str(position or ""))
                if cistern is not None:
                    contents = cistern.get("contents") or {}
                    held = int(contents.get("fresh_water", 0) or 0)
                    if held >= 1:
                        contents["fresh_water"] = held - 1
                        if contents["fresh_water"] <= 0:
                            del contents["fresh_water"]
                        satisfaction = survival.DRINK_SATISFACTION["vessel"]
                        outcome_source = "cistern"
                    else:
                        return {"status": "rejected",
                                "reason": "The cistern here is empty"}
                else:
                    satisfaction = survival.DRINK_SATISFACTION["tile"]
                    outcome_source = "tile"
            else:
                inventory = self._get_agent_inventory(agent_ref)
                if int(inventory.get("fresh_water", 0) or 0) >= 1:
                    add_to_inventory(self._store, agent_ref, "fresh_water", -1)
                    satisfaction = survival.DRINK_SATISFACTION["carried"]
                    outcome_source = "carried"
                else:
                    return {"status": "rejected",
                            "reason": "This tile is not drinkable and you hold no fresh_water"}
        # 4. Carried water.
        elif source in ("carried", "belongings", "inventory"):
            inventory = self._get_agent_inventory(agent_ref)
            if int(inventory.get("fresh_water", 0) or 0) < 1:
                return {"status": "rejected",
                        "reason": "You hold no fresh_water to drink"}
            add_to_inventory(self._store, agent_ref, "fresh_water", -1)
            satisfaction = survival.DRINK_SATISFACTION["carried"]
            outcome_source = "carried"
        else:
            return {"status": "rejected",
                    "reason": f"Unknown drink source {raw_source!r}; use the current "
                              "tile, carried fresh_water, or a vessel holding fresh_water"}

        vitals["thirst"] = round(
            max(0.0, min(survival.THIRST_CAP, thirst_now - satisfaction)), 2
        )
        return {
            "status": "success",
            "action_type": "drink",
            "source": outcome_source,
            "thirst_satisfied": satisfaction,
            "thirst_now": vitals["thirst"],
        }

    def _eat_satisfaction(self, agent_ref: str, resource_kind: str) -> dict:
        """Consume one unit of food from belongings, satisfy hunger."""
        kind = str(resource_kind or "").strip()
        if not kind:
            return {"status": "rejected", "reason": "Missing resource_kind"}
        inventory = dict(load_inventory(self._store).get(agent_ref, {}))
        held = inventory.get(kind, 0)
        if not isinstance(held, int) or held <= 0:
            return {"status": "rejected",
                    "reason": f"You hold no {kind} to eat"}
        vitals = self._vitals_for(agent_ref)
        satisfaction = survival.eat_satisfaction(kind)
        vitals["hunger"] = round(max(0.0, vitals["hunger"] - satisfaction), 2)
        add_to_inventory(self._store, agent_ref, kind, -1)
        self._remove_food_lots(agent_ref, kind, 1)
        return {
            "status": "success",
            "resource_kind": kind,
            "hunger_satisfied": satisfaction,
            "hunger_now": vitals["hunger"],
        }

    def _execute_offer_food(self, agent_ref: str, action: dict,
                            heartbeat_number: int) -> dict:
        target_id = action.get("target_id", "")
        resource_kind = action.get("resource_kind", "")
        if not target_id or not resource_kind:
            return {"status": "rejected", "reason": "Missing target or resource kind"}
        if not isinstance(resource_kind, str) or not resource_kind.strip():
            return {"status": "rejected", "reason": "Missing resource kind"}

        if resource_kind not in fauna.ANIMAL_FOOD_TRUST:
            return {"status": "rejected",
                    "reason": f"Animals do not eat {resource_kind}"}

        target = None
        for entity in getattr(self._world_state, "fauna", []):
            if entity.get("id") == target_id:
                target = entity
                break
        if target is None:
            return {"status": "rejected", "reason": "No such animal here"}

        if target.get("kind") not in fauna.TAMEABLE_KINDS:
            return {"status": "rejected", "reason": "This animal is not tamable"}

        if target.get("tamed"):
            return {"status": "rejected",
                    "reason": "This animal is already tamed"}

        position = self._world_state.tile_occupancy.get(agent_ref)
        pxy = self._tile_xy(position or "")
        tile = target.get("tile")
        if not isinstance(tile, list):
            return {"status": "rejected", "reason": "Animal has no valid location"}
        exy = (int(tile[0]), int(tile[1]))
        if pxy is None or max(abs(pxy[0] - exy[0]), abs(pxy[1] - exy[1])) > FAUNA_ACTION_REACH:
            return {"status": "rejected", "reason": "The animal is not within reach"}

        inventory = self._get_agent_inventory(agent_ref)
        held = inventory.get(resource_kind, 0)
        if held < 1:
            return {"status": "rejected",
                    "reason": f"You hold no {resource_kind}"}

        kind = target.get("kind")
        trust_before = int(target.get("trust", 0))
        trust_after = fauna.trust_after(kind, resource_kind, trust_before)
        tamed_after = trust_after >= (
            fauna.COW_TRUST_THRESHOLD if kind == "cow" else fauna.HORSE_TRUST_THRESHOLD
        )
        event_id = fauna_interactions.new_event_id(
            "offer_food", heartbeat_number, agent_ref, target_id
        )

        intent = {
            "action": "offer_food",
            "agent_ref": agent_ref,
            "target_id": target_id,
            "resource_kind": resource_kind,
            "trust_before": trust_before,
            "trust_after": trust_after,
            "tamed_before": bool(target.get("tamed", False)),
            "tamed_after": tamed_after,
            "anchor_tile_after": list(pxy) if tamed_after else None,
            "inventory_before": {resource_kind: held},
            "inventory_after": {resource_kind: held - 1},
        }

        fauna_interactions.begin_animal_interaction(self._store, event_id, intent)
        modify_inventory_batch(self._store, agent_ref, {resource_kind: -1})
        self._remove_food_lots(agent_ref, resource_kind, 1)
        fauna_interactions.mark_inventory_applied(self._store, event_id)

        target["trust"] = trust_after
        if tamed_after:
            target["tamed"] = True
            target["anchor_tile"] = list(pxy)

        self._world_state.fauna = [
            target if entity.get("id") == target_id else entity
            for entity in getattr(self._world_state, "fauna", [])
        ]
        save_world_state(self._store, self._world_state)
        fauna_interactions.mark_fauna_applied(self._store, event_id)

        return {
            "status": "success",
            "target_id": target_id,
            "target_kind": kind,
            "resource_kind": resource_kind,
            "trust": trust_after,
            "tamed": tamed_after,
            "detail": (
                f"{kind.capitalize()} accepts the {resource_kind}."
                if not tamed_after
                else f"{kind.capitalize()} is tamed after accepting the {resource_kind}."
            ),
        }

    def _execute_milk_animal(self, agent_ref: str, action: dict,
                              heartbeat_number: int) -> dict:
        target_id = action.get("target_id", "")
        if not target_id:
            return {"status": "rejected", "reason": "Missing target_id"}

        target = None
        for entity in getattr(self._world_state, "fauna", []):
            if entity.get("id") == target_id:
                target = entity
                break
        if target is None:
            return {"status": "rejected", "reason": "No such animal here"}

        if target.get("kind") != "cow":
            return {"status": "rejected", "reason": "Only cows can be milked"}

        if not target.get("tamed"):
            return {"status": "rejected", "reason": "This cow is not tamed"}

        if not target.get("milk_ready"):
            return {"status": "rejected", "reason": "Milk is not ready"}

        position = self._world_state.tile_occupancy.get(agent_ref)
        pxy = self._tile_xy(position or "")
        tile = target.get("tile")
        if not isinstance(tile, list):
            return {"status": "rejected", "reason": "Cow has no valid location"}
        exy = (int(tile[0]), int(tile[1]))
        if pxy is None or max(abs(pxy[0] - exy[0]), abs(pxy[1] - exy[1])) > FAUNA_ACTION_REACH:
            return {"status": "rejected", "reason": "The cow is not within reach"}

        inventory = self._get_agent_inventory(agent_ref)
        event_id = fauna_interactions.new_event_id(
            "milk_animal", heartbeat_number, agent_ref, target_id
        )
        intent = {
            "action": "milk_animal",
            "agent_ref": agent_ref,
            "target_id": target_id,
            "milk_ready_before": True,
            "milk_ready_after": False,
            "milk_ready_at_hb_after": heartbeat_number,
            "inventory_before": {"milk": inventory.get("milk", 0)},
            "inventory_after": {"milk": inventory.get("milk", 0) + 1},
        }

        fauna_interactions.begin_animal_interaction(self._store, event_id, intent)
        modify_inventory_batch(self._store, agent_ref, {"milk": 1})
        self._record_food_birth(agent_ref, "milk", 1, heartbeat_number)
        fauna_interactions.mark_inventory_applied(self._store, event_id)

        target["milk_ready"] = False
        target["milk_ready_at_hb"] = heartbeat_number

        self._world_state.fauna = [
            target if entity.get("id") == target_id else entity
            for entity in getattr(self._world_state, "fauna", [])
        ]
        save_world_state(self._store, self._world_state)
        fauna_interactions.mark_fauna_applied(self._store, event_id)

        return {
            "status": "success",
            "target_id": target_id,
            "target_kind": "cow",
            "milk": 1,
            "detail": "Milked the ready cow.",
        }

    def _execute_attack(self, agent_ref: str, action: dict,
                        heartbeat_number: int | None = None) -> dict:
        """Strike an adjacent animal. Wolves/deer stay in wildlife; snakes are fauna."""
        hb = int(heartbeat_number if heartbeat_number is not None else getattr(self._world_state, "tick", 0))
        target_id = action.get("target_id", "")
        entities = self._world_state.wildlife or []

        entity = next((e for e in entities
                       if e.get("id") == target_id), None)

        if entity is None:
            # Fallback: allow target_id as kind ("wolf", "deer") if adjacent
            pos0 = self._world_state.tile_occupancy.get(agent_ref)
            pxy0 = self._tile_xy(pos0 or "")
            if pxy0 is not None and target_id in ("wolf", "deer"):
                matches = []
                for candidate in entities:
                    if candidate.get("kind") != target_id:
                        continue
                    c_exy = self._entity_xy(candidate.get("tile"))
                    if c_exy is not None and max(abs(pxy0[0] - c_exy[0]), abs(pxy0[1] - c_exy[1])) <= 1:
                        matches.append(candidate)
                if len(matches) == 1:
                    entity = matches[0]
                    target_id = entity.get("id", target_id)
                elif len(matches) > 1:
                    match_ids = ", ".join(e.get("id", "?") for e in matches)
                    return {"status": "rejected",
                            "reason": f"Multiple {target_id}s within reach; specify exact target_id ({match_ids})"}

        if entity is not None:
            etile = entity.get("tile")
            if isinstance(etile, list):
                etile = tuple(etile)
            pos = self._world_state.tile_occupancy.get(agent_ref)
            pxy = self._tile_xy(pos)
            exy = self._entity_xy(etile)
            if pxy is None or exy is None or max(
                    abs(pxy[0] - exy[0]), abs(pxy[1] - exy[1])) > FAUNA_ACTION_REACH:
                return {"status": "rejected",
                        "reason": "The animal is not within reach"}

            inventory = load_inventory(self._store).get(agent_ref, {})
            entity, dmg, killed, meat = wildlife.strike(entity, inventory)
            wear = self._wear_preferred_attack_tool(agent_ref)
            kind = entity.get("kind", "animal")
            if killed:
                if kind == "wolf":
                    detail = f"Struck wolf for {dmg} damage; wolf fled the area and left {meat} meat"
                else:
                    detail = f"Struck deer for {dmg} damage; deer killed and dropped {meat} meat"
            else:
                detail = f"Struck {kind} for {dmg} damage ({entity.get('hp')} HP remaining)"
            if wear.get("used"):
                detail += f"; used {wear['used']} ({wear['remaining']} use(s) left"
                detail += ", broke)" if wear.get("broke") else ")"

            outcome = {
                "status": "success",
                "target_id": target_id,
                "target_kind": kind,
                "damage": dmg,
                "killed": killed,
                "driven_off": (killed and kind == "wolf"),
                "meat": meat,
                "detail": detail,
                "tool_used": wear.get("used"),
                "tool_remaining": wear.get("remaining", 0),
                "tool_broke": bool(wear.get("broke")),
            }
            if killed:
                self._world_state.wildlife = [e for e in entities if e.get("id") != target_id]
                if meat:
                    add_to_inventory(self._store, agent_ref, wildlife.MEAT, meat)
                    self._record_food_birth(agent_ref, wildlife.MEAT, meat, hb)
                    outcome["meat_held"] = meat
            else:
                self._world_state.wildlife = [
                    e if e.get("id") != target_id else entity for e in entities]
            return outcome

        faunae = getattr(self._world_state, "fauna", []) or []
        target = next((e for e in faunae if e.get("id") == target_id), None)
        if target is None:
            return {"status": "rejected", "reason": "No such animal here"}

        kind = target.get("kind", "animal")
        if kind != "snake":
            return {"status": "rejected",
                    "reason": "This animal is not hostile"}

        etile = target.get("tile")
        if isinstance(etile, list):
            etile = tuple(etile)
        pos = self._world_state.tile_occupancy.get(agent_ref)
        pxy = self._tile_xy(pos)
        exy = self._entity_xy(etile)
        if pxy is None or exy is None or max(
                abs(pxy[0] - exy[0]), abs(pxy[1] - exy[1])) > FAUNA_ACTION_REACH:
            return {"status": "rejected", "reason": "The animal is not within reach"}

        inventory = load_inventory(self._store).get(agent_ref, {})
        target, dmg, killed, meat = fauna.strike_snake(target, inventory)
        wear = self._wear_preferred_attack_tool(agent_ref)
        outcome = {
            "status": "success",
            "target_id": target_id,
            "target_kind": kind,
            "damage": dmg,
            "killed": killed,
            "meat": meat,
            "driven_off": False,
            "tool_used": wear.get("used"),
            "tool_remaining": wear.get("remaining", 0),
            "tool_broke": bool(wear.get("broke")),
        }
        if killed:
            self._world_state.fauna = [e for e in faunae if e.get("id") != target_id]
            if meat:
                add_to_inventory(self._store, agent_ref, wildlife.MEAT, meat)
                self._record_food_birth(agent_ref, wildlife.MEAT, meat, hb)
                outcome["meat_held"] = meat
        else:
            self._world_state.fauna = [
                e if e.get("id") != target_id else target for e in faunae]
        return outcome

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, agent_ref: str, action: dict | None, heartbeat_number: int) -> dict:
        self._age_and_spoil_world_food(heartbeat_number)
        if action is None:
            return {"status": "no_action", "detail": "No action chosen"}
        action_type = action.get("action_type")

        # A collapsed body cannot act. What it CAN do: cry for help, and
        # eat — a hand can still reach a pocket, and food on the tile is
        # auto-fed by the physics (see apply_survival_to_all). Blocking
        # eat while holding food would recreate the retired model's
        # impossible board: starving with full pockets.
        # Phase 10QI: a collapsed body keeps its legs. Operator: "we should
        # help them while they are learning instead of leaving them on the
        # ground? would you want us to sit here for hours if you were dying of
        # thirst on the ground?" It could not move at all: both partners of a
        # pair are usually down together, the operator has no mechanic to
        # deliver anything, and self-recovery is 0.15/hb - four hours of lying
        # still. So `move` is permitted while collapsed (a CRAWL: one edge per
        # heartbeat, same as walking, with nothing else available), which makes
        # the river five tiles away, the partner on the next tile and the
        # cistern at home reachable. Collapse takes your hands, not your legs.
        if self._vitals_for(agent_ref).get("downed"):
            if action_type not in ("leave_public_message", "ask_human",
                                   "no_action", "eat", "drink", "move"):
                return {
                    "status": "rejected",
                    "reason": ("You have collapsed. You cannot gather, build, "
                               "craft or work while your body is down, but you "
                               "can crawl to an adjacent tile, drink, eat, "
                               "speak and ask. Food or water brought to your "
                               "tile is drunk and eaten; otherwise rest."),
                }

        if action_type == "eat":
            return self._eat_satisfaction(agent_ref, action.get("resource_kind"))
        if action_type == "drink":
            return self._execute_drink(agent_ref, action, heartbeat_number)
        if action_type == "offer_food":
            return self._execute_offer_food(agent_ref, action, heartbeat_number)
        if action_type == "milk_animal":
            return self._execute_milk_animal(agent_ref, action, heartbeat_number)
        if action_type == "attack":
            return self._execute_attack(agent_ref, action, heartbeat_number)
        if action_type == "move":
            return self._execute_move(agent_ref, action)
        if action_type == "create_public_object":
            return self._execute_create_public_object(agent_ref, action, heartbeat_number)
        if action_type == "inspect_public_object":
            return self._execute_inspect_public_object(action)
        if action_type == "use_object":
            return self._execute_use_object(agent_ref, action, heartbeat_number)
        if action_type == "modify_owned_public_object":
            return self._execute_modify_owned_public_object(agent_ref, action, heartbeat_number)
        if action_type == "leave_public_message":
            return self._execute_leave_public_message(agent_ref, action, heartbeat_number)
        if action_type == "ask_human":
            return self._execute_ask_human(agent_ref, action, heartbeat_number)
        if action_type == "request_capability":
            return self._execute_request_capability(agent_ref, action, heartbeat_number)
        if action_type == "gather":
            return self._execute_gather(agent_ref, action, heartbeat_number)
        if action_type == "revise_charter":
            return self._execute_revise_charter(agent_ref, action, heartbeat_number)
        if action_type == "build":
            return self._execute_build(agent_ref, action, heartbeat_number)
        if action_type == "hew_timber":
            return self._execute_hew_timber(agent_ref, action, heartbeat_number)
        if action_type == "plant_crop":
            return self._execute_plant_crop(agent_ref, action, heartbeat_number)
        if action_type == "harvest_crop":
            return self._execute_harvest_crop(agent_ref, action, heartbeat_number)
        return {"status": "unknown_action", "action": action}

    def _execute_hew_timber(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Causal tree felling: converts trees on tile into heavy structural timber."""
        position = self._world_state.tile_occupancy.get(agent_ref)
        if not position:
            return {"status": "rejected", "reason": "No current position"}

        inv = self._get_agent_inventory(agent_ref)
        has_axe = inv.get("stone_axe", 0) > 0 or inv.get("iron_axe", 0) > 0 or inv.get("axe", 0) > 0
        has_knife = inv.get("flint_knife", 0) > 0 or inv.get("knife", 0) > 0 or inv.get("knapped_flint", 0) > 0

        # Phase 10PT: knapping fallback. A worn-out axe retired East Adam's only
        # blade and left him unable to produce any timber at all, which starved
        # the whole lane's build loop. With no blade held, 2 stone + 1 wood knap
        # a throwaway blade -- the exact cost of a flint_knife -- and the hew
        # proceeds at blade yield. This is never cheaper than owning a knife,
        # so it does not make axes redundant; it removes the dead end.
        knapped = False
        if not (has_axe or has_knife):
            stone_held = int(inv.get("stone", 0) or 0)
            wood_held = int(inv.get("wood", 0) or 0)
            if stone_held >= 2 and wood_held >= 1:
                add_to_inventory(self._store, agent_ref, "stone", -2)
                add_to_inventory(self._store, agent_ref, "wood", -1)
                # The blade is consumed by this single hew: it is spent, not
                # carried, so it never enters the durability ledger.
                knapped = True
                has_knife = True
                inv = self._get_agent_inventory(agent_ref)
            else:
                return {
                    "status": "rejected",
                    "reason": "Cannot hew timber bare-handed. Holds no axe or knapped blade; "
                              "with 2 stone and 1 wood a blade can be knapped on the spot.",
                }

        tile_res = [r for r in self._current_tile_resources.get(position, []) if r.get("kind") in ("wood", "timber") and r.get("amount", 0) > 0]
        if tile_res:
            res = tile_res[0]
            res["amount"] = max(0, res.get("amount", 0) - 1)

        timber_yield = 2 if has_axe else 1
        add_to_inventory(self._store, agent_ref, "timber", timber_yield)
        detail = f"Hewn {timber_yield} structural timber logs from tree."
        if knapped:
            detail = "Knapped a throwaway blade from 2 stone and 1 wood. " + detail
            wear = {"used": None, "remaining": 0, "broke": False}
        else:
            tool_kind = (
                "iron_axe" if inv.get("iron_axe", 0) > 0
                else "stone_axe" if has_axe
                else "flint_knife"
            )
            wear = self._use_best_tool(agent_ref, (tool_kind,))
        if wear.get("used"):
            detail += (
                f" {wear['used']} condition left {wear['remaining']} use(s)"
            )
            if wear.get("broke"):
                detail += ", broke"
        return {
            "status": "success",
            "action_type": "hew_timber",
            "timber_yield": timber_yield,
            "tool_used": wear.get("used"),
            "tool_remaining": wear.get("remaining", 0),
            "tool_broke": bool(wear.get("broke")),
            "remaining": self._get_agent_inventory(agent_ref),
            "detail": detail,
        }

    def _execute_plant_crop(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Sow seed or root crop into an enclosed garden plot."""
        target_id = action.get("target_id")
        resource_kind = action.get("resource_kind", "")
        if not target_id:
            return {"status": "rejected", "reason": "Missing target_id for garden plot"}
        obj = self._world_state.public_objects.get(target_id)
        if not obj or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Garden plot '{target_id}' does not exist"}
        obj_type = str(obj.get("object_type", "")).lower()
        if "garden" not in obj_type:
            return {"status": "rejected", "reason": f"Object '{target_id}' is not an enclosed garden plot"}

        pos = self._world_state.tile_occupancy.get(agent_ref)
        target_pos = obj.get("tile_id")
        if pos != target_pos:
            pxy = self._tile_xy(pos)
            txy = self._tile_xy(target_pos)
            if pxy is None or txy is None or max(abs(pxy[0] - txy[0]), abs(pxy[1] - txy[1])) > 1:
                return {"status": "rejected", "reason": f"Too far from garden plot '{target_id}'"}

        valid_crops = ("wild_berries", "edible_roots", "wild_grain")
        if resource_kind not in valid_crops:
            return {"status": "rejected", "reason": f"Invalid crop '{resource_kind}'. Valid crops are: {', '.join(valid_crops)}"}

        inv = self._get_agent_inventory(agent_ref)
        if inv.get(resource_kind, 0) < 1:
            return {"status": "rejected", "reason": f"Insufficient {resource_kind}: need 1 to plant"}

        add_to_inventory(self._store, agent_ref, resource_kind, -1)
        self._remove_food_lots(agent_ref, resource_kind, 1)
        obj["crop"] = {
            "kind": resource_kind,
            "planted_heartbeat": heartbeat_number,
        }
        return {
            "status": "success",
            "action_type": "plant_crop",
            "target_id": target_id,
            "crop_planted": resource_kind,
            "remaining": self._get_agent_inventory(agent_ref),
        }

    def _execute_harvest_crop(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Harvest mature crops from an enclosed garden plot."""
        target_id = action.get("target_id")
        if not target_id:
            return {"status": "rejected", "reason": "Missing target_id for garden plot"}
        obj = self._world_state.public_objects.get(target_id)
        if not obj or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Garden plot '{target_id}' does not exist"}

        crop = obj.get("crop")
        if not crop or not isinstance(crop, dict):
            return {"status": "rejected", "reason": f"Garden plot '{target_id}' has no planted crop"}

        planted_hb = crop.get("planted_heartbeat", 0)
        age = heartbeat_number - planted_hb
        if age < 61:
            stage = "seeded" if age < 25 else "growing"
            return {"status": "rejected", "reason": f"Crop is not mature yet (current stage: {stage}, age: {age} heartbeats; matures at 61)"}

        crop_kind = crop.get("kind", "wild_berries")
        yield_amount = 4
        add_to_inventory(self._store, agent_ref, crop_kind, yield_amount)
        self._record_food_birth(agent_ref, crop_kind, yield_amount, heartbeat_number)
        obj["crop"] = None

        return {
            "status": "success",
            "action_type": "harvest_crop",
            "target_id": target_id,
            "crop_harvested": crop_kind,
            "amount_gathered": yield_amount,
            "remaining": self._get_agent_inventory(agent_ref),
        }

    def _execute_gather(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Collect a resource from the current tile."""
        resource_kind = action.get("resource_kind", "")
        if not resource_kind:
            return {"status": "rejected", "reason": "Missing resource_kind"}

        position = self._world_state.tile_occupancy.get(agent_ref)
        if not position:
            return {"status": "rejected", "reason": "No current position"}

        # Find the resource on this tile
        tile_resources = [
            r for r in self._current_tile_resources.get(position, [])
            if r.get("kind") == resource_kind and r.get("amount", 0) > 0
        ]
        if not tile_resources:
            listed = sorted(
                {
                    str(r.get("kind"))
                    for r in self._current_tile_resources.get(position, [])
                    if r.get("kind") and r.get("amount", 0) > 0
                }
            )
            if listed:
                tail = "it lists: " + ", ".join(listed)
            else:
                tail = "it lists nothing gatherable"
            return {
                "status": "rejected",
                "reason": f"No {resource_kind} available on this tile; {tail}",
            }

        resource = tile_resources[0]
        available = resource.get("amount", 0)

        # Causal tool utility (Phase 10JI):
        # Holding relevant tools significantly boosts gathering yields.
        inv = self._get_agent_inventory(agent_ref)
        gather_yield = GATHER_YIELD
        tool_detail = ""
        tool_kind_used = None
        if resource_kind == "wood" and (inv.get("stone_axe", 0) > 0 or inv.get("iron_axe", 0) > 0):
            gather_yield = 5
            tool_detail = " (hewn with axe)"
            tool_kind_used = "iron_axe" if inv.get("iron_axe", 0) > 0 else "stone_axe"
        elif resource_kind in ("wild_berries", "mushrooms", "edible_roots") and inv.get("woven_basket", 0) > 0:
            gather_yield = 3
            tool_detail = " (gathered with woven basket)"
            tool_kind_used = "woven_basket"

        take = min(gather_yield, available)

        resource["amount"] = available - take

        # Belongings persist: holdings live in the store, not in memory,
        # so what is gathered survives restarts.
        add_to_inventory(self._store, agent_ref, resource_kind, take)
        self._record_food_birth(agent_ref, resource_kind, take, heartbeat_number)
        wear = (
            self._use_best_tool(agent_ref, (tool_kind_used,))
            if tool_kind_used
            else {"used": None, "remaining": 0, "broke": False}
        )

        outcome = {
            "status": "success",
            "resource_kind": resource_kind,
            "amount_gathered": take,
            "remaining_on_tile": resource.get("amount", 0),
            "tool_used": wear.get("used"),
            "tool_remaining": wear.get("remaining", 0),
            "tool_broke": bool(wear.get("broke")),
        }
        if tool_detail:
            outcome["detail"] = f"Gathered {take} {resource_kind}{tool_detail}"
            if wear.get("used"):
                outcome["detail"] += (
                    f"; {wear['used']} condition left {wear['remaining']} use(s)"
                )
                if wear.get("broke"):
                    outcome["detail"] += f", broke"

        # Micro-ecology: wild bee colonies defend honeycomb unless calmed or dormant
        if resource_kind == "honeycomb":
            near_smoke = self._nearby_smoke(position, heartbeat_number)
            forecast = survival.weather_forecast(self._pair_id, heartbeat_number)
            weather_name = forecast["current"]
            temp = survival.effective_temperature(heartbeat_number, weather_name)
            is_night = survival.is_night(heartbeat_number)
            colony_state = insects.bee_colony_state(weather_name, temp, is_night, near_smoke)
            vitals = self._vitals_for(agent_ref)
            cur_vit = vitals.get("vitality", 100.0)
            dmg, bee_msg = insects.resolve_bee_gather(colony_state, cur_vit)
            if dmg > 0:
                new_vit = round(max(0.0, cur_vit - dmg), 2)
                vitals["vitality"] = new_vit
                if new_vit <= 0.0:
                    vitals["downed"] = True
            outcome["bee_colony_state"] = colony_state
            outcome["sting_damage"] = dmg
            outcome["detail"] = bee_msg

        return outcome

    def _execute_revise_charter(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Persist one self-authored charter version (append-only).

        The agent may only ever revise its own charter; ownership is bound
        to this agent's identity. A revision whose text is identical to the
        current version is a rejected no-op (nothing persisted — identity is
        not re-persisted when it has not changed). Earlier versions are
        preserved byte-for-byte forever.
        """
        view = self._agent_view(agent_ref)
        charter_text = (action.get("charter_text") or "").strip()
        if not charter_text:
            return {"status": "rejected", "reason": "Missing charter_text"}

        existing = load_latest_charter(self._store, agent_ref, view["agent_id"])
        if existing and existing.charter_text == charter_text:
            return {
                "status": "rejected",
                "reason": "charter text unchanged from current version",
                "charter_version_id": existing.charter_version_id,
            }

        versions = load_charter_versions(self._store)
        n_mine = sum(
            1 for v in versions
            if v.agent_ref == agent_ref and v.agent_id == view["agent_id"]
        )
        record = CharterVersionRecord(
            # agent_ref is unique per agent across all pairs; agent_id
            # prefixes are NOT (all genesis IDs share "genesis-agent"), so
            # the ref carries the identity here.
            charter_version_id=f"charter-{agent_ref}-v{n_mine + 1}",
            agent_id=view["agent_id"],
            agent_ref=agent_ref,
            pair_id=self._pair_id,
            heartbeat=heartbeat_number,
            charter_text=charter_text,
            decision_summary="",
        ).seal()
        if not append_charter_version(self._store, record):
            return {"status": "rejected", "reason": "charter version already persisted"}

        return {
            "status": "success",
            "charter_version_id": record.charter_version_id,
            "charter_chars": len(charter_text),
            "heartbeat": heartbeat_number,
        }

    def _advance_construction(self, agent_ref: str, action: dict, object_id: str,
                             record: dict, rung_record: dict,
                             heartbeat_number: int) -> dict:
        """Advance an in-progress structure by one stage (Phase 10PW).

        Same object_id, same agent, and the stage plan is spent a step at a
        time. Each step validates against holdings before anything is applied,
        so abandoning a project leaves an honest partial structure.
        """
        view = self._agent_view(agent_ref)
        stages = _CONSTRUCTION_STAGES
        current = str(record.get("construction_stage") or stages[0])
        if current not in stages:
            current = stages[0]
        index = stages.index(current)
        if current == "finished":
            return {
                "status": "rejected",
                "reason": f"{object_id} is already finished; a new object_id starts a new build",
            }
        if index + 1 >= len(stages):
            next_stage = "finished"
        else:
            next_stage = stages[index + 1]

        tile_id = action.get("tile_id") or record.get("tile_id")
        position = self._world_state.tile_occupancy.get(
            agent_ref, self._habitat["starting_tile_ids"][agent_ref]
        )
        if tile_id != position:
            return {
                "status": "rejected",
                "reason": f"Cannot build on tile {tile_id}: you are at {position}",
            }

        plan = record.get("stage_plan")
        if not isinstance(plan, dict):
            plan = _stage_material_plan(rung_record["floor"])
        stage_materials = plan.get(next_stage)
        if not isinstance(stage_materials, dict):
            stage_materials = {}

        holdings = self._get_agent_inventory(agent_ref)
        for kind, amount in stage_materials.items():
            amount = int(amount or 0)
            if amount <= 0:
                continue
            if holdings.get(kind, 0) < amount:
                summary = _holdings_summary(holdings, exclude=kind)
                reason = (f"Insufficient {kind} for the {next_stage} stage of "
                          f"{object_id}: need {amount}, hold {holdings.get(kind, 0)}")
                if summary:
                    reason += f"; {summary}"
                return {"status": "rejected", "reason": reason}

        for kind, amount in stage_materials.items():
            amount = int(amount or 0)
            if amount > 0:
                add_to_inventory(self._store, agent_ref, kind, -amount)

        remaining = dict(record.get("remaining_floor") or {})
        for kind, amount in stage_materials.items():
            if kind in remaining:
                remaining[kind] = max(0, int(remaining.get(kind, 0)) - int(amount or 0))

        record["construction_stage"] = next_stage
        record["construction_progress"] = stages.index(next_stage)
        record["remaining_floor"] = remaining
        materials_now = record.get("materials")
        if not isinstance(materials_now, dict):
            materials_now = {}
        for kind, amount in stage_materials.items():
            if int(amount or 0) > 0:
                materials_now[kind] = int(materials_now.get(kind, 0)) + int(amount)
        record["materials"] = materials_now
        if next_stage == "finished":
            record["construction_project"] = False
            record["finished_heartbeat"] = heartbeat_number

        self._world_state.public_objects[object_id] = record

        detail = (f"{object_id}: {next_stage}"
                  + (f" (spent {stage_materials})" if any(
                      int(v or 0) > 0 for v in stage_materials.values()) else ""))
        return {
            "status": "success",
            "action_type": "build",
            "object_id": object_id,
            "object_type": record.get("object_type"),
            "stage": next_stage,
            "progress": stages.index(next_stage),
            "stages_total": len(stages),
            "shelters": next_stage in _SHELTERING_STAGES,
            "rung": record.get("structure_rung"),
            "remaining_floor": dict(remaining),
            "detail": detail,
        }

    def _execute_build(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Construct an agent-defined object from persisted holdings.

        The agent declares WHAT to make and WHAT it is made of; the runtime
        enforces placement (same rules as create_public_object), validates
        the materials declaration, checks affordability, then deducts and
        creates. No partial builds, no debt: insufficient holdings reject
        the whole build with everything untouched.
        """
        view = self._agent_view(agent_ref)
        object_id = action.get("object_id")
        object_type = action.get("object_type", "generic")
        raw_description = action.get("description", "")
        tile_id = action.get("tile_id")
        materials = action.get("materials")

        # The famished build gate is retired: the world no longer
        # withholds construction from an agent for lacking food.
        if not _is_safe_object_id(str(object_id or "")):
            return {"status": "rejected", "reason": "Invalid object_id"}

        # Phase 10PW: a build naming THIS agent's in-progress project on this
        # tile is a continuation, not a duplicate. Checked before the duplicate
        # branch so a half-built house can be advanced with the same object_id.
        rung_record = _structure_rung_of(object_type)
        structural_build = bool(rung_record)
        if structural_build and object_id in self._world_state.public_objects:
            existing_obj = self._world_state.public_objects.get(object_id)
            if (isinstance(existing_obj, dict)
                    and existing_obj.get("tile_id") == tile_id
                    and existing_obj.get("creator_agent_id") == view["agent_id"]):
                return self._advance_construction(
                    agent_ref, action, object_id, existing_obj,
                    rung_record, heartbeat_number,
                )

        if object_id in self._world_state.public_objects:
            existing_obj = self._world_state.public_objects.get(object_id)
            existing_tile = existing_obj.get("tile_id") if isinstance(existing_obj, dict) else None
            if existing_tile == tile_id:
                existing_type = (
                    existing_obj.get("object_type", "object")
                    if isinstance(existing_obj, dict) else "object"
                )
                return {
                    "status": "rejected",
                    "reason": (
                        f"Duplicate object_id: {object_id} "
                        f"(existing: {existing_type} on {existing_tile})"
                    ),
                }
            base_id = str(object_id)
            candidate_id = f"{base_id}-hb{heartbeat_number}"
            suffix = 2
            while candidate_id in self._world_state.public_objects or not _is_safe_object_id(candidate_id):
                candidate_id = f"{base_id}-hb{heartbeat_number}-{suffix}"
                suffix += 1
            object_id = candidate_id
        addon_to = action.get("addon_to")
        parent_record = None
        if addon_to:
            parent_record = self._world_state.public_objects.get(addon_to)
            if not parent_record or not isinstance(parent_record, dict):
                return {"status": "rejected", "reason": f"Parent structure '{addon_to}' does not exist (nonexistent parent)"}
            parent_tile = parent_record.get("tile_id")
            parent_xy = self._tile_xy(parent_tile)
            target_xy = self._tile_xy(tile_id)
            if parent_xy is None or target_xy is None or max(abs(parent_xy[0] - target_xy[0]), abs(parent_xy[1] - target_xy[1])) > 1:
                return {
                    "status": "rejected",
                    "reason": f"Addon tile {tile_id} is not adjacent to parent structure {addon_to} (tile: {parent_tile})"
                }
            current_pos = self._world_state.tile_occupancy.get(
                agent_ref, self._habitat["starting_tile_ids"][agent_ref]
            )
            if tile_id != current_pos and parent_tile != current_pos:
                return {"status": "rejected", "reason": f"Cannot build addon on tile {tile_id}: you are at {current_pos}"}
        else:
            current_pos = self._world_state.tile_occupancy.get(
                agent_ref, self._habitat["starting_tile_ids"][agent_ref]
            )
            if tile_id != current_pos:
                return {"status": "rejected", "reason": f"Cannot build on tile {tile_id}: you are at {current_pos}"}
        # Placement authority: you may always build on the tile you stand
        # on. Movement already governed how you got here (fog-derived
        # effective tiles grow with exploration); the old static policy
        # whitelist was never updated and refused the agent's own tile
        # after she moved (HB701-743: 26 build attempts on her own tile,
        # all refused "Tile ... not in allowed tiles").

        # Phase 10KM / 10LM: structural builds are load-bearing. Anything carrying a
        # roof must include hewn structural timber, which can only come from
        # hew_timber with an axe or knapped blade -- which needs a crafted
        # tool -- which needs a crafting surface. Attaching a room shares
        # walls, so the structural component (both the timber floor and all
        # declared structural materials) is discounted by half (rounding up).
        # Non-structural types (campfire, crafting_surface, enclosed_garden,
        # storage) are unaffected: fire must stay cheap.
        lowered_type = str(object_type or "").lower()
        timber_min = 0
        for structural, minimum in _STRUCTURAL_TIMBER_MIN.items():
            if structural in lowered_type:
                timber_min = max(timber_min, minimum)
                break
        is_discounted_structural_addon = bool(timber_min and addon_to and parent_record)
        if is_discounted_structural_addon:
            timber_min = (
                timber_min + _ADDON_STRUCTURAL_DISCOUNT_DIVISOR - 1
            ) // _ADDON_STRUCTURAL_DISCOUNT_DIVISOR
        if timber_min:
            declared_timber = 0
            if isinstance(materials, dict):
                try:
                    declared_timber = int(materials.get("timber", 0) or 0)
                except (TypeError, ValueError):
                    declared_timber = 0
            if declared_timber < timber_min:
                return {
                    "status": "rejected",
                    "reason": (
                        f"A {object_type} needs at least {timber_min} structural "
                        f"timber to bear its own weight; you declared "
                        f"{declared_timber}. Fell trees with hew_timber once you "
                        f"hold an axe (stone_axe, iron_axe) or knapped blade "
                        f"(flint_knife)."
                    ),
                }

        # Phase 10PW: the closed structure vocabulary. A roofed DWELLING must
        # name one of the five canonical rungs (or a legacy name already in the
        # lanes, grandfathered to its rung). This closes the free-string hole
        # where "house" with one wood was a legal shelter. Non-roofed types --
        # campfire, crafting_surface, garden, storage, and the like -- are not
        # structures at all and keep their existing rules: fire stays cheap.
        # Load-bearing components (wall, roof, fence, ...) pass through and
        # keep the atomic build contract.
        if (not structural_build
                and not _is_non_structural_type(object_type)
                and not _is_structural_component_type(object_type)):
            return {
                "status": "rejected",
                "reason": (
                    f"A {object_type} is not a structure this world knows how to "
                    f"raise. Legal roofed structures: {_STRUCTURE_RUNG_NAMES}."
                ),
            }

        sanitized = sanitize_public_text(raw_description)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty public_description after sanitization"}

        if not isinstance(materials, dict) or not materials:
            return {"status": "rejected", "reason": "Missing or empty materials"}
        for kind, amount in materials.items():
            if not isinstance(kind, str) or not kind.strip():
                return {"status": "rejected", "reason": "Invalid material kind"}
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                return {"status": "rejected", "reason": f"Invalid material amount for {kind}"}

        effective_materials: dict[str, int] = {}
        for kind, amount in materials.items():
            if is_discounted_structural_addon and kind != "timber":
                effective_materials[kind] = max(
                    1,
                    (amount + _ADDON_STRUCTURAL_DISCOUNT_DIVISOR - 1)
                    // _ADDON_STRUCTURAL_DISCOUNT_DIVISOR,
                )
            elif is_discounted_structural_addon and kind == "timber":
                effective_materials[kind] = max(
                    timber_min,
                    (amount + _ADDON_STRUCTURAL_DISCOUNT_DIVISOR - 1)
                    // _ADDON_STRUCTURAL_DISCOUNT_DIVISOR,
                )
            else:
                effective_materials[kind] = amount

        holdings = self._get_agent_inventory(agent_ref)

        # Phase 10PW: a roofed structure starts as a visible project. Only the
        # FIRST stage's materials are spent now; the rest are spent as the
        # agent advances it, so a half-built house is an honest half-built
        # house rather than a debt. Non-structural builds keep the 10KM rule:
        # the whole declaration is validated, then spent, atomically.
        stage_floor = dict(rung_record["floor"]) if structural_build else {}
        if structural_build and is_discounted_structural_addon:
            # An attached room shares walls, so EVERY structural component is
            # discounted, not only the timber (docs/10LM: the structural
            # component and all declared structural materials are halved).
            stage_floor = {
                kind: max(
                    1,
                    (amount + _ADDON_STRUCTURAL_DISCOUNT_DIVISOR - 1)
                    // _ADDON_STRUCTURAL_DISCOUNT_DIVISOR,
                )
                for kind, amount in stage_floor.items()
            }
        stage_plan = _stage_material_plan(stage_floor) if structural_build else None
        first_stage = _CONSTRUCTION_STAGES[0] if structural_build else None

        if structural_build:
            # 10KM's structural timber floor still applies to the FIRST stage,
            # so a build cannot begin without hewn timber for its frame work.
            # An attached room shares walls, so the floor is discounted by the
            # same 10LM divisor the legacy check already applied.
            stage_materials = dict(stage_plan[first_stage])
            floor_timber = int(rung_record["floor"].get("timber", 0) or 0)
            if is_discounted_structural_addon:
                floor_timber = (
                    floor_timber + _ADDON_STRUCTURAL_DISCOUNT_DIVISOR - 1
                ) // _ADDON_STRUCTURAL_DISCOUNT_DIVISOR
            declared_timber = 0
            if isinstance(materials, dict):
                try:
                    declared_timber = int(materials.get("timber", 0) or 0)
                except (TypeError, ValueError):
                    declared_timber = 0
            if floor_timber and declared_timber < floor_timber:
                return {
                    "status": "rejected",
                    "reason": (
                        f"A {object_type} needs at least {floor_timber} structural "
                        f"timber to bear its own weight; you declared "
                        f"{declared_timber}. Fell trees with hew_timber once you "
                        f"hold an axe (stone_axe, iron_axe) or knapped blade "
                        f"(flint_knife)."
                    ),
                }
            spend = stage_materials
        else:
            spend = dict(effective_materials)


        for kind, amount in spend.items():
            if holdings.get(kind, 0) < amount:
                summary = _holdings_summary(holdings, exclude=kind)
                reason = f"Insufficient {kind}: need {amount}, hold {holdings.get(kind, 0)}"
                # Phase 10PW: a staged build's first action costs only its own
                # stage, so name the whole project too. Otherwise an agent
                # reads "need 1" and believes one log raises a house.
                if structural_build and amount < int(stage_floor.get(kind, amount) or amount):
                    total = sum(stage_plan[stage].get(kind, 0)
                                for stage in _CONSTRUCTION_STAGES)
                    reason += (f" for the {first_stage} stage "
                               f"({total} for the whole {object_type})")
                if summary:
                    reason += f"; {summary}"
                return {"status": "rejected", "reason": reason}

        for kind, amount in spend.items():
            add_to_inventory(self._store, agent_ref, kind, -amount)

        envelope = PublicObjectRecord(
            object_id=object_id,
            creator_agent_id=view["agent_id"],
            tile_id=tile_id,
            object_type=object_type,
            public_description=sanitized,
            created_heartbeat=heartbeat_number,
            materials=dict(spend),
        ).to_envelope()
        if structural_build:
            envelope["construction_project"] = True
            envelope["structure_rung"] = rung_record["rung"]
            envelope["rung_weight"] = rung_record["weight"]
            envelope["construction_stage"] = first_stage
            envelope["construction_progress"] = 0
            envelope["stage_plan"] = stage_plan
            envelope["remaining_floor"] = {
                kind: int(stage_floor.get(kind, 0) or 0) - int(spend.get(kind, 0))
                for kind in stage_floor
            }
        self._world_state.public_objects[object_id] = envelope

        # Phase 10JX: Compound network tracking
        if addon_to and parent_record:
            if not hasattr(self._world_state, "compounds") or self._world_state.compounds is None:
                self._world_state.compounds = {}
            target_xy = self._tile_xy(tile_id)
            parent_tile = parent_record.get("tile_id")
            parent_xy = self._tile_xy(parent_tile)
            target_compound = None
            for c in self._world_state.compounds.values():
                if addon_to in c.get("rooms", {}):
                    target_compound = c
                    break
            is_hearth = "hearth" in str(object_type).lower() or "fire" in str(object_type).lower()
            if target_compound is None:
                compound_id = f"compound-{agent_ref}-{heartbeat_number}"
                parent_is_hearth = "hearth" in str(parent_record.get("object_type", "")).lower() or "fire" in str(parent_record.get("object_type", "")).lower()
                rooms = {
                    addon_to: {
                        "room_type": parent_record.get("object_type", "living_hearth"),
                        "tile": list(parent_xy) if parent_xy else None,
                        "tile_id": parent_tile,
                        "roofed": True,
                        "walls": True,
                        "has_hearth": parent_is_hearth,
                    },
                    object_id: {
                        "room_type": object_type,
                        "tile": list(target_xy) if target_xy else None,
                        "tile_id": tile_id,
                        "roofed": True if "garden" not in str(object_type).lower() else False,
                        "walls": True,
                        "addon_to": addon_to,
                        "has_hearth": is_hearth,
                    }
                }
                hearth_tile = parent_tile if parent_is_hearth else (tile_id if is_hearth else None)
                self._world_state.compounds[compound_id] = {
                    "compound_id": compound_id,
                    "owner_agent_id": view["agent_id"],
                    "root_object_id": addon_to,
                    "rooms": rooms,
                    "thermal_mass": sum(1 for r in rooms.values() if r.get("roofed")),
                    "active_hearth_tile": hearth_tile,
                }
            else:
                target_compound["rooms"][object_id] = {
                    "room_type": object_type,
                    "tile": list(target_xy) if target_xy else None,
                    "tile_id": tile_id,
                    "roofed": True if "garden" not in str(object_type).lower() else False,
                    "walls": True,
                    "addon_to": addon_to,
                    "has_hearth": is_hearth,
                }
                target_compound["thermal_mass"] = sum(1 for r in target_compound["rooms"].values() if r.get("roofed"))
                if is_hearth:
                    target_compound["active_hearth_tile"] = tile_id
        return {
            "status": "success",
            "object_id": object_id,
            "tile_id": tile_id,
            "object_type": object_type,
            "materials_spent": dict(effective_materials),
            "remaining": self._get_agent_inventory(agent_ref),
        }

    def _execute_move(self, agent_ref: str, action: dict) -> dict:
        if not self._habitat or not self._world_state:
            return {"status": "error", "reason": "Runtime not initialized"}
        if self._capability_grant is not None and self._capability_grant.status != "granted":
            return {"status": "blocked", "reason": f"Grant status is {self._capability_grant.status}"}
        if not self._movement_grant_active():
            return {"status": "blocked", "reason": "No active movement grant. Request capability from human operator."}

        target = action.get("target_tile")
        allowed = self._get_effective_allowed_tiles()
        if target not in allowed:
            # A wall teaches nothing if the refusal is opaque. Name the
            # barrier's own hazard (world_walls_spec §2) — state what is
            # true, never what to do. Unknown/unseen targets keep the
            # generic reason.
            hazards = self._known_hazards_for(agent_ref, target)
            if hazards:
                return {
                    "status": "blocked",
                    "reason": (
                        f"Cannot move to {target}: {', '.join(hazards)}"
                    ),
                }
            return {"status": "blocked", "reason": f"Tile {target} not in runtime policy allowed tiles"}

        current_pos = self._world_state.tile_occupancy.get(agent_ref)
        if current_pos is None:
            current_pos = self._habitat["starting_tile_ids"].get(agent_ref)

        # Adjacent-only movement (fog-derived or legacy policy)
        adjacent = self._get_effective_adjacency(current_pos)
        if target not in adjacent:
            return {"status": "blocked", "reason": f"Cannot move from {current_pos} to {target}: not adjacent (adjacent: {adjacent})"}

        # Co-location is permitted on any valid traversable tile
        # (the old shared-center-only restriction was removed for the
        # expanded world; 10IZ §2.7 documented this as a near-term
        # design decision and the operator approved the generalization)

        self._world_state.tile_occupancy[agent_ref] = target
        return {"status": "success", "from": current_pos, "to": target}

    def _execute_create_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        object_id = action.get("object_id")
        object_type = action.get("object_type", "generic")
        raw_description = action.get("description", "")
        tile_id = action.get("tile_id") or self._habitat["starting_tile_ids"][agent_ref]

        if not _is_safe_object_id(str(object_id or "")):
            return {"status": "rejected", "reason": "Invalid object_id"}
        if object_id in self._world_state.public_objects:
            return {"status": "rejected", "reason": f"Duplicate object_id: {object_id}"}

        # Physical functional structures cannot be created without construction materials.
        lowered_type = str(object_type or "").lower()
        functional_types = (
            "campfire", "fire", "hearth", "forge", "furnace", "brazier",
            "shelter", "cabin", "hut", "lean-to", "lean_to", "lean", "roof", "wall", "tent",
        )
        if any(ft in lowered_type for ft in functional_types):
            return {
                "status": "rejected",
                "reason": f"Physical {object_type} cannot be created without construction materials. Use the 'build' action to construct physical structures with materials.",
            }

        # Must place on current tile
        current_pos = self._world_state.tile_occupancy.get(
            agent_ref, self._habitat["starting_tile_ids"][agent_ref]
        )
        if tile_id != current_pos:
            return {"status": "rejected", "reason": f"Cannot place object on tile {tile_id}: you are at {current_pos}"}
        # Placement authority: the tile you stand on is always placeable
        # (same seam fix as build — movement, not a stale whitelist,
        # governs where an agent may be).

        sanitized = sanitize_public_text(raw_description)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty public_description after sanitization"}

        record = PublicObjectRecord(
            object_id=object_id,
            creator_agent_id=view["agent_id"],
            tile_id=tile_id,
            object_type=object_type,
            public_description=sanitized,
            created_heartbeat=heartbeat_number,
        )
        self._world_state.public_objects[object_id] = record.to_envelope()
        return {
            "status": "success",
            "object_id": object_id,
            "tile_id": tile_id,
            "object_type": object_type,
            "sanitized_description": sanitized[:200],
        }

    def _execute_inspect_public_object(self, action: dict) -> dict:
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        return {"status": "success", "object": obj}

    # Phase 10PT: object types that hold shared stores. Adjacency-tolerant
    # deposit/extract applies to these and nothing else.
    _CONTAINER_TYPE_TERMS = (
        "container", "storage", "cache", "chest", "barrel", "crate",
        "box", "well", "cellar", "basket", "pot", "urn", "cask",
    )

    @classmethod
    def _is_container_type(cls, object_type: str) -> bool:
        otype = str(object_type or "").casefold()
        return any(term in otype for term in cls._CONTAINER_TYPE_TERMS)

    def _execute_use_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        """Interact with a public object on the agent's tile.

        docs/object_interaction_spec.md. Eve at HB1864 asked for exactly
        this: "put materials into an object and get something back out."
        Three operations: deposit (inventory -> contents), extract
        (contents -> inventory), inspect (read contents). Any object can
        hold contents — type-blind, same principle as the sightline
        extension. The object must be on the agent's current tile.
        """
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}

        position = (self._world_state.tile_occupancy or {}).get(agent_ref)
        obj_tile = obj.get("tile_id", "")
        # Phase 10PT: containers reachable from an adjacent tile. deposit and
        # extract are the ONLY inventory-to-inventory channel between the two
        # agents, and requiring the agent to stand on the container tile made
        # the partner's hoard unreachable in practice. Same Chebyshev <= 1
        # rule the drink path already uses for vessels. Every other operation
        # keeps the original on-your-tile requirement.
        operation_for_gate = action.get("operation", "inspect")
        adjacency_eligible = (
            operation_for_gate in ("deposit", "extract")
            and self._is_container_type(str(obj.get("object_type", "")))
        )
        reachable = True
        if position and obj_tile != position:
            if adjacency_eligible:
                pos_xy = self._tile_xy(position)
                obj_xy = self._entity_xy(obj_tile) or self._tile_xy(str(obj_tile))
                if pos_xy is None or obj_xy is None or max(
                    abs(obj_xy[0] - pos_xy[0]), abs(obj_xy[1] - pos_xy[1])
                ) > 1:
                    reachable = False
            else:
                reachable = False
        if not reachable:
            if adjacency_eligible:
                return {"status": "rejected",
                        "reason": f"Object {obj_id} is on {obj_tile}, not your tile or a tile beside it"}
            return {"status": "rejected",
                    "reason": f"Object is on {obj_tile}, not your current tile"}

        operation = action.get("operation", "inspect")
        if operation not in ("deposit", "extract", "inspect", "smelt", "craft", "cook"):
            return {"status": "rejected",
                    "reason": f"Unknown operation: {operation}. Use deposit, extract, inspect, smelt, craft, or cook."}

        obj_type = str(obj.get("object_type", "")).casefold()

        # Type-dependent operations: the world has rules about what each
        # object does. The agent discovers them by testing.
        if operation == "smelt" and "furnace" not in obj_type and "foundry" not in obj_type:
            return {"status": "rejected",
                    "reason": f"Smelting requires a furnace or foundry, not a {obj.get('object_type')}"}
        if operation == "craft" and not any(term in obj_type for term in ("crafting_surface", "forge", "workbench", "workshop")):
            return {"status": "rejected",
                    "reason": f"Crafting requires a crafting surface, not a {obj.get('object_type')}"}
        if operation == "cook":
            # Phase 10QC: rung 4's promised effect finally exists. A proper
            # home has a hearth built in, so a SHELTERING house or longhouse
            # cooks without a separate fire object -- the first thing in the
            # world a rung-4 structure does that a cabin cannot. A rung-3
            # cabin, and any half-built project, still needs its own fire.
            if not self._is_hearth_dwelling(obj):
                valid_cooking_types = ("fire", "campfire", "hearth", "cooker", "oven")
                if not any(term in obj_type for term in valid_cooking_types):
                    return {"status": "rejected",
                            "reason": f"Cooking requires a fire, campfire, or hearth, not a {obj.get('object_type')}"}
                if not self._is_functional_fire(obj):
                    return {"status": "rejected",
                            "reason": f"The {obj.get('object_type')} at {obj_id} has no fuel materials and is unlit"}
                weather, _ = survival.weather_at(self._pair_id, heartbeat_number)
                if weather in ("rain", "storm", "blizzard") and not self._in_shelter(obj.get("tile_id", "")):
                    return {"status": "rejected",
                            "reason": f"The fire at {obj_id} is snuffed by the {weather} (build a shelter or roof to protect it)"}

        # Initialize contents if the object predates the field
        if "contents" not in obj or not isinstance(obj.get("contents"), dict):
            obj["contents"] = {}

        if operation == "inspect":
            return {"status": "success", "object_id": obj_id,
                    "contents": dict(obj["contents"]),
                    "object_type": obj.get("object_type", "")}

        materials = action.get("materials")
        if not isinstance(materials, dict) or not materials:
            return {"status": "rejected",
                    "reason": f"{operation} requires a materials dict like "
                              f'{{"stone": 2}}'}

        # Strict material validation for all mutating operations
        if operation in ("craft", "cook", "deposit", "extract"):
            for kind, amount in materials.items():
                if not isinstance(kind, str) or not kind.strip():
                    return {"status": "rejected", "reason": "Invalid material name"}
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
                    return {"status": "rejected", "reason": f"Invalid amount for {kind}: {amount} (must be a positive integer)"}

        if operation == "smelt":
            return self._smelt_materials(obj_id, obj, materials)

        if operation == "craft":
            return self._craft_on_surface(obj_id, obj, materials, agent_ref, heartbeat_number)

        if operation == "cook":
            return self._cook_on_fire(obj_id, obj, materials, agent_ref, heartbeat_number)

        if operation == "deposit":
            from backend.world.first_pair_persistence import add_to_inventory
            inventory = self._get_agent_inventory(agent_ref)
            for kind, amount in materials.items():
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
                    return {"status": "rejected",
                            "reason": f"Invalid amount for {kind}: {amount}"}
                held = inventory.get(kind, 0)
                if held < amount:
                    return {"status": "rejected",
                            "reason": f"Not enough {kind}: you hold {held}, "
                                      f"tried to deposit {amount}"}
            # Phase 10PJ: storage_cellar food capacity scales with the
            # connected home's roofed footprint; existing contents are
            # grandfathered, only new deposits encounter the budget.
            cellar_capacity = None
            if "cellar" in obj_type:
                cellar_capacity = self._cellar_food_capacity(obj_id)
                edible_kinds = set(survival.EAT_SATISFACTION)
                current_food = 0
                _, network_ids = self._connected_home_network(str(obj.get("tile_id", "")))
                for oid in network_ids:
                    record = (self._world_state.public_objects or {}).get(oid) or {}
                    if not isinstance(record, dict):
                        continue
                    if "cellar" not in str(record.get("object_type", "")).casefold():
                        continue
                    contents = record.get("contents") or {}
                    current_food += sum(
                        int(contents.get(kind, 0) or 0) for kind in edible_kinds
                    )
                incoming_food = sum(
                    int(amount) for kind, amount in materials.items()
                    if kind in edible_kinds
                )
                if incoming_food and current_food + incoming_food > cellar_capacity:
                    return {
                        "status": "rejected",
                        "reason": (
                            f"Cellar food budget exceeded: stores {current_food} "
                            f"of {cellar_capacity} home food units"
                        ),
                    }
            # Phase 10QF: a cistern's capacity is about WATER, not food. It
            # is the first object in the world whose store is measured in
            # units someone carried home.
            if obj_type.strip().lower() == "cistern":
                capacity = _CISTERN_WATER_CAPACITY
                current_water = int((obj.get("contents") or {}).get("fresh_water", 0) or 0)
                incoming_water = int(materials.get("fresh_water", 0) or 0)
                if incoming_water and current_water + incoming_water > capacity:
                    return {
                        "status": "rejected",
                        "reason": (
                            f"Cistern water capacity exceeded: holds {current_water} "
                            f"of {capacity} units"
                        ),
                    }
            # All checks pass; move the materials via the persistence layer
            for kind, amount in materials.items():
                self._ensure_life_state(agent_ref, heartbeat_number)
                removed_lots = self._remove_food_lots(agent_ref, kind, amount)
                add_to_inventory(self._store, agent_ref, kind, -amount)
                obj["contents"][kind] = obj["contents"].get(kind, 0) + amount
                if removed_lots:
                    ages = obj.get("contents_age")
                    if not isinstance(ages, dict):
                        ages = {}
                        obj["contents_age"] = ages
                    born_hb = min(lot["born_hb"] for lot in removed_lots)
                    if kind not in ages or born_hb < ages[kind]:
                        ages[kind] = born_hb
                if kind in _TOOL_DURABILITY:
                    self._sync_tool_condition(agent_ref)
            detail = f"Deposited {materials} into {obj_id}"
            outcome = {
                "status": "success",
                "detail": detail,
                "contents": dict(obj["contents"]),
            }
            if cellar_capacity is not None:
                outcome["storage_budget"] = cellar_capacity
            return outcome

        if operation == "extract":
            from backend.world.first_pair_persistence import add_to_inventory
            for kind, amount in materials.items():
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
                    return {"status": "rejected",
                            "reason": f"Invalid amount for {kind}: {amount}"}
                contained = obj["contents"].get(kind, 0)
                if contained < amount:
                    return {"status": "rejected",
                            "reason": f"Not enough {kind} in object: holds "
                                      f"{contained}, tried to extract {amount}"}
            # All checks pass; move the materials via the persistence layer
            for kind, amount in materials.items():
                obj_contents = obj["contents"]
                obj_contents[kind] = obj_contents.get(kind, 0) - amount
                if obj_contents[kind] <= 0:
                    del obj_contents[kind]
                add_to_inventory(self._store, agent_ref, kind, amount)
                born_hb = heartbeat_number
                ages = obj.get("contents_age")
                if isinstance(ages, dict) and isinstance(ages.get(kind), int):
                    born_hb = ages[kind]
                self._record_food_birth(agent_ref, kind, amount, born_hb)
                if kind in _TOOL_DURABILITY:
                    self._register_tool(agent_ref, kind, amount)
            return {"status": "success",
                    "detail": f"Extracted {materials} from {obj_id}",
                    "contents": dict(obj["contents"])}

        return {"status": "rejected", "reason": f"Unhandled operation: {operation}"}

    # Crafting recipes: materials → tool. Discoverable by testing.
    # Keys are sorted tuples of (kind, amount) pairs — not frozensets,
    # because frozenset(dict) drops the amounts and collapses different
    # recipes that share material types.
    _CRAFT_RECIPES = {
        (("stone", 2), ("wood", 1)): "stone_axe",
        (("fiber_plants", 3),): "fiber_rope",
        (("stone", 1), ("wood", 2)): "stone_hammer",
        (("flint", 2), ("wood", 1)): "flint_knife",
        (("fiber_plants", 1), ("flint", 1), ("wood", 2)): "flint_spear",
        (("fiber_plants", 4), ("wood", 2)): "woven_basket",
        (("clay", 3),): "clay_pot",
        (("iron", 2), ("wood", 1)): "iron_axe",
        (("fiber_plants", 1), ("iron", 1), ("wood", 2)): "iron_spear",
    }

    _SMELT_RECIPES = {
        "iron_ore": {"input": 3, "output": "iron", "output_amount": 1},
    }

    _COOK_RECIPES = {
        (("edible_roots", 1), ("wild_berries", 2)): "cooked_meal",
        (("wild_berries", 3),): "cooked_meal",
        (("edible_roots", 2),): "cooked_meal",
        (("fish", 1),): "cooked_meal",
        (("meat", 1),): "cooked_meal",
        (("wild_grain", 2),): "cooked_meal",
        (("honeycomb", 1), ("wild_berries", 1)): "cooked_meal",
    }

    def _smelt_materials(self, obj_id: str, obj: dict, materials: dict) -> dict:
        """Smelt ore into metal. The furnace consumes ore from its
        contents and produces metal in its contents. The agent extracts
        the metal afterward."""
        if len(materials) != 1:
            return {"status": "rejected",
                    "reason": "Smelting converts one material at a time"}
        kind, amount = next(iter(materials.items()))
        recipe = self._SMELT_RECIPES.get(kind)
        if not recipe:
            return {"status": "rejected",
                    "reason": f"Cannot smelt {kind}"}
        contained = obj["contents"].get(kind, 0)
        needed = recipe["input"]
        if contained < amount:
            return {"status": "rejected",
                    "reason": f"Not enough {kind} in furnace: holds {contained}, "
                              f"needs {amount}"}
        if amount < needed:
            return {"status": "rejected",
                    "reason": f"Cannot smelt {amount} {kind}: the furnace requires "
                              f"at least {needed} per batch"}
        output_amount = (amount // needed) * recipe["output_amount"]
        output_kind = recipe["output"]
        obj["contents"][kind] = contained - amount
        obj["contents"][output_kind] = obj["contents"].get(output_kind, 0) + output_amount
        return {"status": "success",
                "detail": f"Smelted {amount} {kind} into {output_amount} {output_kind}",
                "contents": dict(obj["contents"])}

    def _craft_on_surface(self, obj_id: str, obj: dict, materials: dict,
                          agent_ref: str, heartbeat_number: int | None = None) -> dict:
        """Combine materials into a tool. The crafting surface doesn't
        store anything — the materials are consumed from the agent's
        inventory and the tool goes into their inventory."""
        from backend.world.first_pair_persistence import modify_inventory_batch, load_inventory

        hb = int(heartbeat_number if heartbeat_number is not None else self._world_state.tick)
        inventory = load_inventory(self._store).get(agent_ref, {})
        material_set = tuple(sorted(materials.items()))

        recipe = self._CRAFT_RECIPES.get(material_set)
        if not recipe:
            return {"status": "rejected",
                    "reason": f"Unknown recipe: {dict(materials)}. The "
                              f"crafting surface combines specific materials."}

        for kind, amount in materials.items():
            held = inventory.get(kind, 0)
            if held < amount:
                return {"status": "rejected",
                        "reason": f"Not enough {kind}: you hold {held}, needs {amount}"}

        self._ensure_life_state(agent_ref, hb)
        for kind, amount in materials.items():
            self._remove_food_lots(agent_ref, kind, amount)
        deltas = {kind: -amount for kind, amount in materials.items()}
        deltas[recipe] = deltas.get(recipe, 0) + 1
        modify_inventory_batch(self._store, agent_ref, deltas)
        if recipe in _TOOL_DURABILITY:
            self._register_tool(agent_ref, recipe)
        return {"status": "success", "detail": f"Crafted {recipe}", "crafted": recipe}

    def _cook_on_fire(self, obj_id: str, obj: dict, materials: dict,
                      agent_ref: str, heartbeat_number: int | None = None) -> dict:
        """Cook raw ingredients into cooked meals over an active fire."""
        from backend.world.first_pair_persistence import modify_inventory_batch, load_inventory

        hb = int(heartbeat_number if heartbeat_number is not None else self._world_state.tick)
        inventory = load_inventory(self._store).get(agent_ref, {})
        material_set = tuple(sorted(materials.items()))

        recipe = self._COOK_RECIPES.get(material_set)
        if not recipe:
            return {"status": "rejected",
                    "reason": f"Unknown cooking recipe: {dict(materials)}. Fire cooks specific food combinations."}

        for kind, amount in materials.items():
            held = inventory.get(kind, 0)
            if held < amount:
                return {"status": "rejected",
                        "reason": f"Not enough {kind}: you hold {held}, needs {amount}"}

        self._ensure_life_state(agent_ref, hb)
        for kind, amount in materials.items():
            self._remove_food_lots(agent_ref, kind, amount)
        deltas = {kind: -amount for kind, amount in materials.items()}
        deltas[recipe] = deltas.get(recipe, 0) + 1
        modify_inventory_batch(self._store, agent_ref, deltas)
        self._record_food_birth(agent_ref, recipe, 1, hb)
        return {"status": "success", "detail": f"Cooked {recipe} over {obj_id}", "cooked": recipe}

    def _execute_modify_owned_public_object(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        obj_id = action.get("target_object_id")
        if not obj_id or not isinstance(obj_id, str):
            return {"status": "rejected", "reason": "Missing or invalid target_object_id"}
        obj = self._world_state.public_objects.get(obj_id)
        if obj is None or not isinstance(obj, dict):
            return {"status": "rejected", "reason": f"Object not found: {obj_id}"}
        if obj.get("creator_agent_id") != view["agent_id"]:
            return {"status": "rejected", "reason": "Not the owner of this object"}
        modifications = action.get("modifications")
        if not isinstance(modifications, dict):
            return {"status": "rejected", "reason": "Missing or invalid modifications"}
        applied: dict[str, Any] = {}
        for key, value in modifications.items():
            if key not in _ALLOWED_MUTABLE_FIELDS:
                return {"status": "rejected", "reason": f"Cannot modify field: {key}"}
            if isinstance(value, str):
                sanitized = sanitize_public_text(value)
                if not sanitized.strip():
                    return {"status": "rejected", "reason": f"Empty text after sanitization for {key}"}
                obj[key] = sanitized
                applied[key] = sanitized
            else:
                obj[key] = value
                applied[key] = value
        obj["modified_heartbeat"] = heartbeat_number
        applied["modified_heartbeat"] = heartbeat_number
        return {
            "status": "success",
            "object_id": obj_id,
            "updates": list(modifications.keys()),
            "applied_values": applied,
        }

    def _execute_leave_public_message(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        message = action.get("message", "")
        if not isinstance(message, str) or not message.strip():
            return {"status": "rejected", "reason": "Missing or empty message"}
        sanitized = sanitize_public_text(message)
        if not sanitized.strip():
            return {"status": "rejected", "reason": "Empty after sanitization"}
        recipient = action.get("recipient", "all")
        from hashlib import sha256
        message_id = f"msg-{sha256(f'{agent_ref}{heartbeat_number}{sanitized[:50]}'.encode()).hexdigest()[:12]}"
        msg_record = {
            "message_id": message_id,
            "sender_agent_id": view["agent_id"],
            "message": sanitized[:2000],
            "recipient": recipient,
            "heartbeat": heartbeat_number,
            "sent_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._world_state.public_messages.append(msg_record)
        return {
            "status": "success",
            "message_id": message_id,
            "message_preview": sanitized[:200],
        }

    def _execute_ask_human(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        question_id = action.get("question_id")
        question = action.get("question", "")
        reason = action.get("reason_for_asking", "")
        if not question_id or not question or not reason:
            return {"status": "rejected", "reason": "Missing question_id, question, or reason_for_asking"}
        if not _is_safe_object_id(str(question_id)):
            return {"status": "rejected", "reason": "Invalid question_id"}
        # Re-asking the same question_id is a legitimate act of persistence:
        # both East agents asked the same "food conversion" question three
        # times each across HB803-809 and were then REJECTED for it, which
        # reads to an agent as the world refusing to hear it rather than
        # the question already being on record. The record stays one entry
        # per question_id (unheard, append-only, still awaiting a human);
        # what changes is that a repeat is accepted as a restatement and
        # counted, instead of refused.
        for existing in self._questions:
            if existing.question_id == question_id:
                return {"status": "proposed", "question_id": question_id,
                        "sink": "already-canonical", "repeat": True}
        try:
            records = load_agent_question_proposals(self._store)
            for record in records:
                if record.get("question_id") == question_id:
                    record["restated_heartbeat"] = heartbeat_number
                    record["restated_at_utc"] = datetime.now(
                        timezone.utc).isoformat()
                    record["restatement_count"] = int(
                        record.get("restatement_count", 0)) + 1
                    save_agent_question_proposals(self._store, records)
                    return {"status": "proposed", "question_id": question_id,
                            "sink": "agent_questions.json", "repeat": True,
                            "restatements": record["restatement_count"]}
        except Exception:
            pass  # dedupe/restatement is best-effort; never block the ask
        # in-memory fallback (the durable log is normally authoritative,
        # since each heartbeat is a fresh process)
        for existing_proposal in self._question_proposals:
            if existing_proposal.question_id == question_id:
                return {"status": "proposed", "question_id": question_id,
                        "sink": "already-proposed", "repeat": True}
        agent_id = (
            self._identity_record.adam_agent_id
            if agent_ref == self._adam_ref
            else self._identity_record.eve_agent_id
        )
        urgency = action.get("urgency", "low")
        if urgency not in ("low", "medium", "high"):
            return {"status": "rejected", "reason": "Invalid urgency value"}
        proposal = QuestionProposal(
            question_id=question_id,
            asking_agent_id=agent_id,
            related_goal_id=action.get("related_goal_id"),
            question=question,
            reason_for_asking=reason,
            requested_human_capability=action.get("requested_human_capability", ""),
            urgency=urgency,
        )
        self._question_proposals.append(proposal)
        # Noncanonical sink: the ask is appended to agent_questions.json
        # (no authority, no signature, never questions.json) so the
        # operator can hear it. Fail-closed: a sink failure never turns a
        # heard ask into a crash or a canonical write.
        sink = "agent_questions.json"
        try:
            append_agent_question_proposal(self._store, {
                "question_id": proposal.question_id,
                "asking_agent_id": agent_id,
                "agent_ref": agent_ref,
                "pair_id": self._pair_id,
                "heartbeat": heartbeat_number,
                "question": question,
                "reason_for_asking": reason,
                "requested_human_capability": proposal.requested_human_capability,
                "urgency": urgency,
                "raised_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "unheard",
            })
        except Exception:
            sink = "memory-only"
        # No signature, no authority, no persistence to questions.json.
        return {
            "status": "proposed",
            "question_id": question_id,
            "proposal": asdict(proposal),
            "sink": sink,
        }

    def _execute_request_capability(self, agent_ref: str, action: dict, heartbeat_number: int) -> dict:
        view = self._agent_view(agent_ref)
        cap_id = action.get("capability_id")
        cap_reason = action.get("capability_reason", "")
        if not cap_id or not isinstance(cap_id, str) or not cap_id.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_id"}
        if not cap_reason or not isinstance(cap_reason, str) or not cap_reason.strip():
            return {"status": "rejected", "reason": "Missing or empty capability_reason"}
        # Only honest grant results here: never a success that changed
        # nothing. If the requested capability already appears in the grant
        # ledger, the call changes nothing and must say so plainly. If it
        # appears never, it must also say so plainly. No case returns
        # success without consequence.
        old_grants = {r.get("capability_id")
                      for r in (self._world_state.capability_requests or [])
                      if isinstance(r, dict)}
        if cap_id in old_grants:
            return {
                "status": "already_present",
                "capability_id": cap_id,
                "reason": (
                    f"Request for '{cap_id}' is a repeat - it already appears "
                    f"in your grant history and adds nothing."
                ),
            }
        record = {
            "capability_id": cap_id,
            "requesting_agent_id": view["agent_id"],
            "reason": cap_reason,
            "heartbeat": heartbeat_number,
            "status": "not_achieved",
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "outcome": (
                f"Not granted. The action you asked for does not exist in this "
                f"world's action set and no additional action appears in "
                f"your contract."
            ),
        }
        self._world_state.capability_requests.append(record)
        return {
            "status": "not_achieved",
            "capability_id": cap_id,
            "reason": (
                f"Request was accepted and delivered no action. Nothing "
                f"appeared because no such action exists in your contract."
            ),
        }

    def _execute_modify_world(self, agent_ref: str, action: dict) -> dict:
        return {"status": "not_implemented", "action": action}

    # ------------------------------------------------------------------
    # Cognition output application
    # ------------------------------------------------------------------

    def _apply_cognition_output(
        self, agent_ref: str, output: Any, heartbeat_number: int
    ) -> None:
        # --- Free speech (docs/free_messaging_spec.md) ---
        # Delivered here, beside the action's own bookkeeping, so speaking
        # costs no part of the cycle. Delivery is deliberately independent
        # of the action's outcome: a refusal ("water_too_deep_to_wade") is
        # the most speakable thing that can happen to an agent, and a
        # message about it must not be swallowed by it. A malformed
        # message is dropped silently rather than allowed to disturb the
        # action, which has already been executed by this point.
        free_msg = getattr(output, "message", None)
        if isinstance(free_msg, dict) and free_msg.get("message"):
            self._execute_leave_public_message(
                agent_ref,
                {
                    "action_type": "leave_public_message",
                    "message": free_msg.get("message"),
                    "recipient": free_msg.get("recipient") or "all",
                },
                heartbeat_number,
            )

        goal_updates = output.goal_updates if isinstance(output.goal_updates, list) else []
        for gu in goal_updates:
            if not isinstance(gu, dict):
                continue
            existing = next(
                (g for g in self._goals if g.goal_id == gu.get("goal_id")), None
            )
            if existing:
                existing.status = gu.get("status", existing.status)
                existing.description = gu.get("description", existing.description)
            else:
                self._goals.append(GoalRecord(
                    goal_id=gu["goal_id"],
                    agent_id=gu["agent_id"],
                    description=gu["description"],
                    status=gu.get("status", "active"),
                    created_heartbeat=gu.get("created_heartbeat", heartbeat_number),
                ))

        # --- Continuity metadata (piggyback, never a veto) ---
        # getattr-guarded: outputs predating the slot have no such field.
        cont_meta = getattr(output, "continuity_update", None)
        if isinstance(cont_meta, dict) and cont_meta:
            updated = update_continuity(
                load_continuity(self._store, agent_ref),
                cont_meta,
                heartbeat_number,
            )
            save_continuity(self._store, agent_ref, updated)

        memory_writes = output.memory_write if isinstance(output.memory_write, list) else []
        for mw in memory_writes:
            if not isinstance(mw, dict):
                continue
            target_list = (
                self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
            )
            target_list.append({
                **mw,
                "heartbeat": heartbeat_number,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            })

        questions = (
            output.questions_raised if isinstance(output.questions_raised, list) else []
        )
        for q in questions:
            if not isinstance(q, dict):
                continue
            qid = q.get("question_id")
            question_text = q.get("question")
            reason_text = q.get("reason_for_asking")
            if not isinstance(qid, str) or not qid:
                continue
            if not isinstance(question_text, str) or not question_text.strip():
                continue
            if not isinstance(reason_text, str) or not reason_text.strip():
                continue
            # Deduplicate against existing canonical questions AND proposals
            if any(existing.question_id == qid for existing in self._questions):
                continue
            if any(p.question_id == qid for p in self._question_proposals):
                continue
            agent_id = (
                self._identity_record.adam_agent_id
                if agent_ref == self._adam_ref
                else self._identity_record.eve_agent_id
            )
            proposal = QuestionProposal(
                question_id=qid,
                asking_agent_id=agent_id,
                related_goal_id=q.get("related_goal_id"),
                question=question_text,
                reason_for_asking=reason_text,
                requested_human_capability=q.get("requested_human_capability", ""),
                urgency=q.get("urgency", "low"),
            )
            self._question_proposals.append(proposal)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, start_heartbeat: int | None = None) -> dict:
        self._load_or_initialize()
        self._current_run_cognition: dict[str, dict] = {
            self._adam_ref: {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
            self._eve_ref: {"observation_summary": "", "decision_summary": "", "uncertainty": ""},
        }

        history = load_heartbeat_history(self._store)
        if start_heartbeat is not None:
            current = start_heartbeat
        elif history:
            current = history[-1].heartbeat_number + 1
        else:
            current = 1

        # Capture pre-run state for evidence export
        from backend.world.first_pair_persistence import (
            load_memory_selection_manifests as _load_manifests,
            load_summaries as _load_summaries,
            load_relationship_events as _load_rel_events,
        )
        self._evidence_pre = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "adam_mem_before": len(self._adam_memory),
            "eve_mem_before": len(self._eve_memory),
            "cumulative_hb_before": len(history),
            "final_hb_before": history[-1].heartbeat_number if history else 0,
            "manifest_count_before": len(_load_manifests(self._store)),
            "summary_count_before": len(_load_summaries(self._store)),
            "rel_event_count_before": len(_load_rel_events(self._store)),
            "run_start_hb": current,
        }
        self._run_backend_label = self._backend

        results: dict = {"heartbeats_completed": 0, "errors": []}

        for hb in range(current, current + self._heartbeat_limit):
            adam_action: dict | None = None
            adam_outcome: dict = {}
            eve_action: dict | None = None
            eve_outcome: dict = {}
            world_mutations: list[dict] = []

            # Load gatherable resources for this heartbeat
            self._load_tile_resources()
            self._pressure_tick = {}
            self._reconcile_capability_requests()
            for ref in (self._adam_ref, self._eve_ref):
                self.retire_stale_goals(ref, hb)

            # epistemic.4: one heartbeat of embodiment before the agents
            # reason — hunger rises, night cold bites, fires warm. The
            # observation each agent receives this heartbeat carries the
            # body it is about to act with.
            self.apply_survival_to_all(hb)

            # epistemic.7: the wild. Spawn, move, bite - the entities
            # live in world_state and persist across restarts.
            self.wildlife_tick(hb)
            self.fauna_tick(hb)

            hb_observations: dict = {}
            for agent_ref in (self._adam_ref, self._eve_ref):
                backend = self._get_cognition_backend(agent_ref)
                cycle = CognitiveCycle(backend)
                ctx = self._build_context(agent_ref, hb)
                hb_observations[agent_ref] = ctx.observation
                output = cycle.run_cycle(ctx)
                serving = getattr(backend, "serving_provider_type", "")
                cycle_fallback_used = getattr(backend, "fallback_used", False)
                cycle_primary_failure = getattr(
                    backend, "primary_failure_reason", ""
                )
                if cycle_fallback_used and serving:
                    # A fallback lane served this cycle: sticky for the run.
                    self._fallback_used = True
                    self._serving_provider_type = serving
                elif not cycle_primary_failure and serving:
                    # Primary served this cycle; recorded only while no
                    # fallback has served any earlier cycle in this run.
                    # A cycle that failed entirely never touches serving.
                    if not getattr(self, "_fallback_used", False):
                        self._serving_provider_type = serving
                if cycle_primary_failure and not getattr(
                    self, "_primary_failure_reason", ""
                ):
                    self._primary_failure_reason = cycle_primary_failure
                # Fog: merge observation into the known map BEFORE acting.
                # Reachability is derived from the known map, so a tile the
                # agent has just been SHOWN must already be there when the
                # action is judged - otherwise the world advertises a tile
                # and the rules refuse it one tick later. Measured at HB942:
                # east_adam saw cont_a_gen_1_2, walked to it, and was blocked
                # "not in runtime policy allowed tiles". This is the same seam
                # the build path was already fixed for (see the placement
                # authority comment in _execute_create_public_object).
                # Fail-closed is preserved: a FogAdapterError still leaves the
                # minimal observation unmerged and does not crash the cycle.
                if self._fog_active():
                    try:
                        self._merge_and_persist_known_map(
                            agent_ref, ctx.observation, hb
                        )
                    except FogAdapterError:
                        pass  # Known-map persist failure noted; don't crash the cycle

                outcome = self._execute_action(agent_ref, output.action, hb)

                if agent_ref == self._adam_ref:
                    adam_action = output.action
                    adam_outcome = outcome
                    self._current_run_cognition[self._adam_ref]["observation_summary"] = output.observation_summary
                    self._current_run_cognition[self._adam_ref]["decision_summary"] = output.decision_summary
                    self._current_run_cognition[self._adam_ref]["uncertainty"] = output.uncertainty
                else:
                    eve_action = output.action
                    eve_outcome = outcome
                    self._current_run_cognition[self._eve_ref]["observation_summary"] = output.observation_summary
                    self._current_run_cognition[self._eve_ref]["decision_summary"] = output.decision_summary
                    self._current_run_cognition[self._eve_ref]["uncertainty"] = output.uncertainty

                reflection = cycle.reflect(ctx, output.action, outcome)
                self._apply_cognition_output(agent_ref, output, hb)

                memory_list = (
                    self._adam_memory if agent_ref == self._adam_ref else self._eve_memory
                )
                if not _reflection_is_echo(memory_list, reflection):
                    memory_list.append({
                        "type": "reflection",
                        "content": reflection,
                        "heartbeat": hb,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    })

                # Structured mutation evidence — only actual state mutations
                if outcome.get("status") == "success":
                    action_type = (output.action or {}).get("action_type", "unknown")
                    # Only world-changing actions count as mutations
                    if action_type in (
                        "create_public_object",
                        "modify_owned_public_object",
                        "leave_public_message",
                        "request_capability",
                        "move",
                        "build",
                    ):
                        view = self._agent_view(agent_ref)
                        mutation = {
                            "acting_agent_id": view["agent_id"],
                            "heartbeat": hb,
                            "action_type": action_type,
                            "target": outcome.get("object_id") or outcome.get("target_tile") or outcome.get("message_id", ""),
                            "input": dict(output.action) if output.action else {},
                            "outcome": outcome,
                        }
                        world_mutations.append(mutation)

                    # Record social continuity event for validated public interactions
                    if action_type in (
                        "leave_public_message", "move", "create_public_object",
                        "inspect_public_object",
                    ):
                        view = self._agent_view(agent_ref)
                        other_id = view["other_agent_id"]
                        maybe_record_relationship_event(
                            self._store, hb, agent_ref,
                            view["agent_id"], other_id,
                            action_type, outcome, view,
                            self._world_state,
                        )

            # Set world_state.tick to actual heartbeat before saving
            self._world_state.tick = hb
            self._world_state.updated_at_utc = datetime.now(timezone.utc).isoformat()

            # End-of-tick persistence
            self._persist_shared_state(
                hb, adam_action, adam_outcome, eve_action, eve_outcome,
                world_mutations, observations=hb_observations,
            )
            results["heartbeats_completed"] += 1

        return results

    def _audit_observations(self, observations: dict) -> dict:
        """Per-agent observation snapshot for the heartbeat record.

        Read-only audit projection. It stores exactly what the cognition layer
        received and nothing more: no true-map identifiers, no known-map
        internals, no credentials. The per-agent keying is deliberate - two
        agents standing on different tiles saw different worlds, and a single
        merged map would misrepresent both.
        """
        snapshot: dict = {}
        for agent_ref, obs in (observations or {}).items():
            if not isinstance(obs, dict):
                continue
            entry: dict = {}
            for key in ("tile_id", "visible_tiles", "visible_tile_details",
                        "objects_here", "fog_error", "conditions"):
                if key in obs:
                    entry[key] = obs[key]
            if entry:
                snapshot[agent_ref] = entry
        return snapshot

    def _persist_shared_state(
        self,
        heartbeat_number: int,
        adam_action: dict | None = None,
        adam_outcome: dict | None = None,
        eve_action: dict | None = None,
        eve_outcome: dict | None = None,
        world_mutations: list[dict] | None = None,
        observations: dict | None = None,
    ) -> None:
        # The heartbeat ledger is written FIRST, the world state (tick)
        # LAST. A crash between these two writes then leaves the ledger
        # ahead of the tick - the truthful direction: the record proves
        # the heartbeat happened and recovery rolls the tick forward.
        # The previous order (tick first, ledger second) left the tick
        # ahead on crash, which claimed progress the ledger could not
        # prove; repairing that meant rolling history back and hoping
        # nothing was double-applied. It happened twice: HB1328 and
        # HB1646, both during power loss.
        shared_memory = {
            self._adam_ref: list(self._adam_memory),
            self._eve_ref: list(self._eve_memory),
        }
        save_memory(self._store, shared_memory)
        save_goals(self._store, self._goals)
        self._persist_questions_without_stale_overwrite()

        actions_taken = {}
        if adam_action:
            actions_taken[self._adam_ref] = adam_action
        if eve_action:
            actions_taken[self._eve_ref] = eve_action

        action_outcomes = {}
        if adam_outcome:
            action_outcomes[self._adam_ref] = adam_outcome
        if eve_outcome:
            action_outcomes[self._eve_ref] = eve_outcome

        # Retain what the agents were actually shown this heartbeat.
        # Previously this was hardcoded `{}`, which made the record unable to
        # answer "what did they see when they decided that?" - see
        # docs/world_observation_transmission_spec.md §7. An empty observation
        # remains distinguishable from a populated one: if the fog adapter
        # failed, the record carries the fog_error and an empty map, which is
        # itself the audit signal.
        hb_record = HeartbeatRecord(
            heartbeat_number=heartbeat_number,
            agent_id="both",
            position="",
            observation=self._audit_observations(observations),
            action_taken=actions_taken if actions_taken else None,
            world_mutations=world_mutations or [],
            goals_updated=[g.goal_id for g in self._goals],
            questions_raised=[
                q.question_id for q in self._questions if q.status == "pending"
            ],
            action_outcomes=action_outcomes,
        )
        append_heartbeat(self._store, hb_record)

        # The tick advances only after the ledger entry it names is on
        # disk. This is the second half of the HB1328/HB1646 fix: the
        # world state may lag the ledger by one write on a crash, never
        # lead it.
        save_world_state(self._store, self._world_state)

    def _persist_questions_without_stale_overwrite(self) -> None:
        """Reconcile canonical questions WITHOUT writing back local state.

        Canonical questions are store-owned. The runtime no longer mints
        questions (proposals are noncanonical), so it has no authority to write
        ``questions.json``. On every tick it re-syncs ``self._questions`` from the
        canonical store, guaranteeing that stale in-memory state (e.g. an old
        pending Q1) can never overwrite a newer governed answer.
        """
        self._questions = load_questions(self._store)

    # ------------------------------------------------------------------
    # Evidence / inspection
    # ------------------------------------------------------------------

    def export_evidence(self, output_path: Path, run_id: str = "") -> dict[str, Any]:
        history = load_heartbeat_history(self._store)
        process_start = datetime.now(timezone.utc)

        adam_view = self._agent_view(self._adam_ref) if self._identity_record else {}
        eve_view = self._agent_view(self._eve_ref) if self._identity_record else {}

        # --- Resolve run boundaries from pre-run state ---
        pre = getattr(self, "_evidence_pre", None)
        if pre is not None and pre.get("run_start_hb"):
            new_count = history[-1].heartbeat_number - pre["final_hb_before"] if history else 0
            start_hb = pre["run_start_hb"]
            end_hb = pre["run_start_hb"] + new_count - 1 if new_count > 0 else None
        else:
            new_count = 0
            start_hb = None
            end_hb = None

        cumulative_count = len(history)
        adam_mem_before = pre["adam_mem_before"] if pre else len(self._adam_memory)
        eve_mem_before = pre["eve_mem_before"] if pre else len(self._eve_memory)

        # --- Run-specific records (by count slicing) ---
        all_manifests = load_memory_selection_manifests(self._store)
        all_summaries = load_summaries(self._store)
        all_rel_events = load_relationship_events(self._store)

        manifest_before = pre["manifest_count_before"] if pre else len(all_manifests)
        summary_before = pre["summary_count_before"] if pre else len(all_summaries)
        rel_before = pre["rel_event_count_before"] if pre else len(all_rel_events)

        run_manifests = list(all_manifests[manifest_before:])
        run_summaries = list(all_summaries[summary_before:])
        run_rel_events = list(all_rel_events[rel_before:])

        # --- Cumulative heartbeat detail ---
        heartbeats_export: list[dict] = []
        for h in history:
            entry: dict = {"heartbeat_number": h.heartbeat_number}
            actions = h.action_taken or {}
            entry["adam_action"] = actions.get(self._adam_ref)
            entry["eve_action"] = actions.get(self._eve_ref)
            entry["questions_raised"] = h.questions_raised
            entry["goals_updated"] = h.goals_updated
            entry["world_mutations"] = [
                m for m in (h.world_mutations or [])
                if m.get("action_type") in (
                    "create_public_object", "modify_owned_public_object",
                    "leave_public_message", "request_capability", "move",
                ) and m.get("outcome", {}).get("status") == "success"
            ]
            hb_manifests = [m for m in all_manifests if m.get("heartbeat", 0) == h.heartbeat_number]
            if hb_manifests:
                entry["memory_selection_manifests"] = hb_manifests
            heartbeats_export.append(entry)

        # --- Run-specific heartbeat list ---
        run_heartbeats = [h for h in heartbeats_export
                          if start_hb is not None and end_hb is not None
                          and start_hb <= h["heartbeat_number"] <= end_hb]

        # --- Privacy manifest ---
        privacy_manifest = {
            "requesting_agent_id_adam": adam_view.get("agent_id", ""),
            "requesting_agent_id_eve": eve_view.get("agent_id", ""),
            "adam_private_memory_count": len(self._adam_memory),
            "eve_private_memory_count": len(self._eve_memory),
            "other_agent_private_memory_included": 0,
            "public_evidence_count": len(self._world_state.public_objects) + len(self._world_state.public_messages) if self._world_state else 0,
            "answered_question_count": len([q for q in self._questions if q.status == "answered"]) if self._questions else 0,
            "canonical_request_hash": hashlib.sha256(
                json.dumps({
                    "adam_mem_count": len(self._adam_memory),
                    "eve_mem_count": len(self._eve_memory),
                    "public_obj_count": len(self._world_state.public_objects) if self._world_state else 0,
                    "goal_count": len(self._goals),
                }, sort_keys=True).encode()
            ).hexdigest()[:16],
        }

        # --- Provider / backend label ---
        provider_type = ""
        model_name = ""
        backend_label = getattr(self, "_run_backend_label", self._backend)
        try:
            backend = self._get_cognition_backend(self._adam_ref)
            if hasattr(backend, "provider_type"):
                provider_type = backend.provider_type
            if hasattr(backend, "model_name"):
                model_name = backend.model_name
        except Exception:
            pass

        # Lane that actually served cognition during this run (equals
        # provider_type when no fallback lane served), plus fallback
        # provenance: the sanitized primary failure that triggered the
        # fallback is preserved even when the fallback succeeded.
        serving_provider_type = (
            getattr(self, "_serving_provider_type", "") or provider_type
        )
        fallback_used = bool(getattr(self, "_fallback_used", False))
        primary_failure_reason = getattr(self, "_primary_failure_reason", "")[:600]

        bundle: dict[str, Any] = {
            "evidence_schema_version": "10FN.2",
            "run_id": run_id,
            "backend_label": backend_label,
            "provider_type": provider_type,
            "primary_provider_type": provider_type,
            "model_name": model_name,
            "serving_provider_type": serving_provider_type,
            "fallback_used": fallback_used,
            "primary_failure_reason": primary_failure_reason,
            "root": str(self._store.root) if self._store else "",
            "process_started_at_utc": pre["started_at_utc"] if pre else "",
            "process_finished_at_utc": process_start.isoformat(),
            "start_heartbeat": start_hb,
            "end_heartbeat": end_hb,
            "new_heartbeat_count": new_count,
            "cumulative_heartbeat_count": cumulative_count,
            "initialized_or_resumed": "resumed" if cumulative_count > 1 else "initialized",
            "adam_id": adam_view.get("agent_id", ""),
            "eve_id": eve_view.get("agent_id", ""),
            "adam_memory_count_before": adam_mem_before,
            "adam_memory_count_after": len(self._adam_memory),
            "eve_memory_count_before": eve_mem_before,
            "eve_memory_count_after": len(self._eve_memory),
            "adam_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == adam_view.get("agent_id", "")]),
            "eve_selected_memory_count": len([m for m in run_manifests if m.get("requesting_agent_id") == eve_view.get("agent_id", "")]),
            "summary_count": len(all_summaries),
            "relationship_event_count": len(all_rel_events),
            "goals_before": [],
            "goals_after": [g.__dict__ for g in self._goals],
            "questions_answered_during_run": [
                q.__dict__ for q in self._questions if q.status == "answered"
            ],
            "active_capability_grants": [
                self._capability_grant.__dict__
            ] if self._capability_grant else [],
            "adam_observation_summary": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("observation_summary", ""),
            "adam_decision_summary": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("decision_summary", ""),
            "adam_uncertainty": getattr(self, "_current_run_cognition", {}).get(self._adam_ref, {}).get("uncertainty", ""),
            "eve_observation_summary": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("observation_summary", ""),
            "eve_decision_summary": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("decision_summary", ""),
            "eve_uncertainty": getattr(self, "_current_run_cognition", {}).get(self._eve_ref, {}).get("uncertainty", ""),
            # Run-specific sections
            "heartbeats": run_heartbeats,
            "memory_selection_manifests": run_manifests,
            "memory_summaries": [asdict(s) for s in run_summaries],
            "relationship_events": [asdict(e) for e in run_rel_events],
            # Cumulative state
            "cumulative": {
                "heartbeats": heartbeats_export,
                "memory_selection_manifests": all_manifests,
                "memory_summaries": [asdict(s) for s in all_summaries],
                "relationship_events": [asdict(e) for e in all_rel_events],
            },
            "privacy_manifest": privacy_manifest,
            "adam_memory": self._adam_memory,
            "eve_memory": self._eve_memory,
            "goals": [g.__dict__ for g in self._goals],
            "questions": [q.__dict__ for q in self._questions],
            "exported_at_utc": process_start.isoformat(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, default=str, sort_keys=True)
        return bundle

    def validate_state(self) -> dict:
        return validate_persistence_integrity(self._store)


def run_first_pair_demo(
    heartbeats: int = 5,
    persistence_root: Path | None = None,
    export_path: Path | None = None,
    backend: str = "stub",
) -> dict:
    """Convenience harness — builds a fresh runtime and runs it once."""
    runtime = FirstPairRuntime(
        persistence_root=persistence_root,
        heartbeat_limit=heartbeats,
        backend=backend,
    )
    results = runtime.run()
    if export_path:
        runtime.export_evidence(export_path)
    return results
