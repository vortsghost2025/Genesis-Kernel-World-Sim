"""A refusal must state the number it ENFORCES.

Found by the day's audit, 2026-11-16. east's top refusal was, 29 times:

    "A roof needs at least 1 structural timber to bear its own weight; you
     declared 0"

and, six times:

    "A lean-to needs at least 0 structural timber to bear its own weight; you
     declared 0"

The second is incoherent: a requirement of ZERO, refusing. The check was right
(`if floor_timber and declared_timber < floor_timber`) and the message printed a
DIFFERENT variable (`timber_min`, which is 0 for every type absent from
`_STRUCTURAL_TIMBER_MIN` -- lean-to, house, longhouse, cistern). So an agent was
told the requirement was zero and refused for meeting it, with no way to fix its
declaration.

That is the disclosure-versus-physics class again, inside a refusal: the sentence
described a rule the code does not have.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import (  # noqa: E402
    _STRUCTURAL_TIMBER_MIN,
    _STRUCTURE_RUNGS,
    FirstPairRuntime,
)

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._vitals_for("east_adam")
    return rt


def _build(rt: FirstPairRuntime, otype: str, materials: dict, hb: int, oid: str,
           tile: str = TILE):
    return rt._execute_action("east_adam", {
        "action_type": "build", "object_id": oid, "object_type": otype,
        "description": "t", "tile_id": tile, "materials": materials}, hb)


def test_the_live_case_states_the_floor_it_enforces(tmp_path):
    """lean-to: rung floor timber 1, and it is ABSENT from _STRUCTURAL_TIMBER_MIN
    -- which is exactly why the old message printed 0. The live refusal came from
    the INITIAL build of a staged project, so the bad attempt is a fresh project
    on a tile that has none (a second lean-to on the same tile would be routed
    into advancing the first)."""
    rt = _runtime(tmp_path)
    assert "lean-to" not in _STRUCTURAL_TIMBER_MIN
    assert _STRUCTURE_RUNGS["lean-to"]["floor"]["timber"] == 1
    add_to_inventory(rt._store, "east_adam", "timber", 5)

    ok = _build(rt, "lean-to", {"timber": 1}, 100, "lt-1")
    assert ok["status"] == "success", ok

    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_1_0"
    # a NON-empty declaration that simply omits timber -- an empty materials
    # dict is rejected earlier as "Missing or empty materials", which is why the
    # live message said "you declared 0" rather than "missing".
    bad = _build(rt, "lean-to", {"stone": 1}, 101, "lt-2",
                 tile="cont_a_gen_1_0")
    assert bad["status"] == "rejected", bad
    assert "needs at least 1 structural timber" in bad["reason"], bad["reason"]
    assert "needs at least 0" not in bad["reason"], (
        "a requirement of zero cannot be refused")


def test_the_number_named_is_the_number_checked():
    """Source-level: the refusal prints the variable its own condition tests."""
    src = (WORLD_SIM / "backend" / "world" / "first_pair_runtime.py").read_text(
        encoding="utf-8")
    assert ("if floor_timber and declared_timber < floor_timber:\n"
            "                return {\n"
            '                    "status": "rejected",\n'
            '                    "reason": (\n'
            '                        f"A {object_type} needs at least {floor_timber} structural "'
            ) in src


def test_the_rung_minimum_refusal_still_states_its_own_number():
    """The other site checks `timber_min` and must keep printing it."""
    src = (WORLD_SIM / "backend" / "world" / "first_pair_runtime.py").read_text(
        encoding="utf-8")
    assert ('if declared_timber < timber_min:' in src
            and 'f"A {object_type} needs at least {timber_min} structural "' in src)


def test_the_insufficient_timber_refusal_names_the_nearest_forest(tmp_path):
    """Phase 10UC: every tile the four agents stand on lacks a wood resource, so
    they CANNOT hew where they stand. The old message said only 'fell trees with
    hew_timber' and never said WHERE, which is why the loop repeated for days.
    A wood tile IS a forest: the refusal must name it and the route."""
    from backend.world.first_pair_fog_adapter import persist_known_map
    rt = _runtime(tmp_path)
    persist_known_map(rt._store.root, "east_adam", {
        "schema_version": 1, "agent_id": "x",
        "known_tiles": {"cont_a_gen_2_0": {"observed_resources": ["wood"]}},
        "known_landmarks": {}, "named_places": {}, "routes": [],
        "hypotheses": [], "myths": [], "contact_evidence": [],
        "last_observation_tick": 1,
    })
    add_to_inventory(rt._store, "east_adam", "timber", 5)
    ok = _build(rt, "lean-to", {"timber": 1}, 100, "lt-forest-1")
    assert ok["status"] == "success", ok

    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_1_0"
    bad = _build(rt, "lean-to", {"stone": 1}, 101, "lt-forest-2", tile="cont_a_gen_1_0")
    assert bad["status"] == "rejected", bad
    assert "nearest forest" in bad["reason"], bad["reason"]
    assert "cont_a_gen_2_0" in bad["reason"], bad["reason"]
    assert "hew_timber" in bad["reason"], bad["reason"]
    assert "1 tile east" in bad["reason"], bad["reason"]


def test_the_forest_hint_is_silent_when_no_forest_is_known(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "timber", 5)
    ok = _build(rt, "lean-to", {"timber": 1}, 100, "lt-forest-3")
    assert ok["status"] == "success", ok
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_1_0"
    bad = _build(rt, "lean-to", {"stone": 1}, 101, "lt-forest-4", tile="cont_a_gen_1_0")
    assert bad["status"] == "rejected"
    assert "nearest forest" not in bad["reason"], bad["reason"]


def test_a_compliant_declaration_still_advances(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "timber", 5)
    assert _build(rt, "lean-to", {"timber": 1}, 100, "lt-3")["status"] == "success"
    ok = _build(rt, "lean-to", {"timber": 1}, 101, "lt-3")
    assert ok["status"] == "success", ok
