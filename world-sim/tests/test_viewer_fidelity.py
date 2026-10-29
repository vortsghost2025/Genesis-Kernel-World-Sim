"""Test suite for Phase 10KB/10KH: Continuous World Observatory Visual Fidelity & Contract Hardening.

Hardened regression gate verifying:
1. Export contract (functional): build_pair_snapshot emits fauna, compounds, and shelter_occupancy.
2. Shelter detection (parametric): table-driven tests over shelter kinds, compound rooms, destroyed states.
3. Animal species coverage: createAnimalCanvasTexture handles cow, horse, snake, deer, and wolf.
4. Action FX dispatch: updateAgentActionFx dispatches woodchip, scaffold, crop, and fauna FX.
5. Smart recent replay: replayRecentActivity rewinds and starts 2x playback.
6. Interior cutaway mode: toggleInteriorCutaway hides roof and manages hearth group.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
EXPORTER_PATH = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"
PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"

import sys
if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))
from scripts import export_viewer_snapshot


def test_exporter_contract_functional():
    """Invoke build_pair_snapshot against a fixture store and verify emitted structure."""
    with tempfile.TemporaryDirectory(dir="C:/Users/seand/AppData/Local/Temp") as td:
        store = Path(td)
        # Seed minimal fixture store
        (store / "heartbeat.json").write_text(json.dumps({
            "data": [{
                "heartbeat_number": 100,
                "action_taken": {},
                "action_outcomes": {},
                "observation": {}
            }]
        }), encoding="utf-8")

        (store / "world_state.json").write_text(json.dumps({
            "data": {
                "tick": 100,
                "tile_occupancy": {"east_adam": "cont_a_gen_10_10", "east_eve": "cont_a_gen_12_12"},
                "fauna": [
                    {"id": "cow-1", "kind": "cow", "tile": [10, 11], "trust": 0, "tamed": False}
                ],
                "compounds": {
                    "comp-1": {"compound_id": "comp-1", "rooms": {}}
                },
                "public_objects": {
                    "hut-1": {
                        "object_id": "hut-1",
                        "object_type": "shelter_hut",
                        "tile_id": "cont_a_gen_10_10",
                        "status": "active"
                    }
                }
            }
        }), encoding="utf-8")

        snapshot = export_viewer_snapshot.build_pair_snapshot("east", store, true_map={"tiles": []})
        assert snapshot is not None, "Snapshot must not be None for valid fixture store"

        # Structural assertions
        assert "fauna" in snapshot, "Snapshot must emit 'fauna'"
        assert isinstance(snapshot["fauna"], list), "'fauna' must be a list"
        assert len(snapshot["fauna"]) == 1
        assert snapshot["fauna"][0]["id"] == "cow-1"

        assert "compounds" in snapshot, "Snapshot must emit 'compounds'"
        assert isinstance(snapshot["compounds"], dict), "'compounds' must be a dict"
        assert "comp-1" in snapshot["compounds"]

        assert "shelter_occupancy" in snapshot, "Snapshot must emit 'shelter_occupancy'"
        assert isinstance(snapshot["shelter_occupancy"], dict), "'shelter_occupancy' must be a dict"
        assert snapshot["shelter_occupancy"]["east_adam"] is True
        assert snapshot["shelter_occupancy"]["east_eve"] is False


@pytest.mark.parametrize("scenario,agent_tile,public_objects,compounds,expected", [
    (
        "agent on active shelter tile",
        "cont_a_gen_10_10",
        {"s1": {"object_type": "shelter_hut", "tile_id": "cont_a_gen_10_10", "status": "active"}},
        {},
        True,
    ),
    (
        "agent inside roofed compound room",
        "cont_a_gen_20_20",
        {},
        {"c1": {"rooms": {"r1": {"tile_id": "cont_a_gen_20_20", "roofed": True}}}},
        True,
    ),
    (
        "agent in unroofed compound garden",
        "cont_a_gen_20_20",
        {},
        {"c1": {"rooms": {"r1": {"tile_id": "cont_a_gen_20_20", "roofed": False}}}},
        False,
    ),
    (
        "agent on bare terrain far from shelter",
        "cont_a_gen_0_0",
        {"s1": {"object_type": "shelter", "tile_id": "cont_a_gen_50_50", "status": "active"}},
        {},
        False,
    ),
    (
        "dismantled shelter excluded",
        "cont_a_gen_10_10",
        {"s1": {"object_type": "shelter_cabin", "tile_id": "cont_a_gen_10_10", "status": "dismantled"}},
        {},
        False,
    ),
    (
        "public_objects as list of active dicts",
        "cont_a_gen_10_10",
        [{"object_type": "shelter", "tile_id": "cont_a_gen_10_10", "status": "active"}],
        {},
        True,
    ),
    (
        "missing agent not in tile_occupancy",
        "",
        {"s1": {"object_type": "shelter", "tile_id": "cont_a_gen_10_10", "status": "active"}},
        {},
        False,
    ),
])
def test_shelter_detection_parametric(scenario, agent_tile, public_objects, compounds, expected):
    """Parametric evaluation of is_agent_sheltered across varied topologies and statuses."""
    world_state = {
        "tile_occupancy": {"test_agent": agent_tile} if agent_tile else {},
        "public_objects": public_objects,
        "compounds": compounds,
    }
    result = export_viewer_snapshot.is_agent_sheltered("test_agent", world_state)
    assert result == expected, f"Failed scenario: {scenario}"


def test_prototype_html_fauna_texture_registry():
    """Verify createAnimalCanvasTexture handles all 5 species (cow, horse, snake, deer, wolf)."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    match = re.search(r'function createAnimalCanvasTexture\((.*?)\)\s*\{(.*?)\n\}', html, re.DOTALL)
    assert match, "createAnimalCanvasTexture must be defined in index.html"
    body = match.group(2).lower()

    required_species = ["cow", "horse", "snake", "deer", "wolf"]
    for species in required_species:
        assert species in body, (
            f"createAnimalCanvasTexture must explicitly dispatch texture generation for '{species}'"
        )


def test_prototype_html_action_fx_dispatch():
    """Verify updateAgentActionFx dispatches the 4 required physical action particle FX."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    match = re.search(r'function updateAgentActionFx\((.*?)\)\s*\{(.*?)\n\}', html, re.DOTALL)
    assert match, "updateAgentActionFx must be defined in index.html"
    body = match.group(2)

    assert '"woodchip"' in body, "updateAgentActionFx must support 'woodchip' FX for hew_timber"
    assert '"scaffold"' in body, "updateAgentActionFx must support 'scaffold' FX for build/addon_to"
    assert '"crop"' in body, "updateAgentActionFx must support 'crop' FX for harvest/plant"
    assert '"fauna"' in body, "updateAgentActionFx must support 'fauna' FX for animal interactions"


def test_prototype_html_smart_recent_replay_implementation():
    """Verify replayRecentActivity sets 2x speed, initiates playback, and rewinds."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    match = re.search(r'function replayRecentActivity\((.*?)\)\s*\{(.*?)\n\}', html, re.DOTALL)
    assert match, "replayRecentActivity must be defined in index.html"
    body = match.group(2)

    assert "isPlaying = true" in body, "replayRecentActivity must set isPlaying = true"
    assert "playSpeed = 2" in body, "replayRecentActivity must set playSpeed = 2"
    assert "currentHb" in body, "replayRecentActivity must rewind currentHb"


def test_prototype_html_interior_cutaway_implementation():
    """Verify toggleInteriorCutaway manages interiorGroup visibility and cutaway shelter prop."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    match = re.search(r'function toggleInteriorCutaway\((.*?)\)\s*\{(.*?)\n\}', html, re.DOTALL)
    assert match, "toggleInteriorCutaway must be defined in index.html"
    body = match.group(2)

    assert "interiorGroup.visible" in body, "toggleInteriorCutaway must control interiorGroup.visible"
    assert "cutawayShelterProp" in body, "toggleInteriorCutaway must track and restore cutawayShelterProp"
