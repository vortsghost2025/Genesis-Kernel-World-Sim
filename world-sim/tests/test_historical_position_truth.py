"""Historical position truth and chronicle reconstruction regression suite.

Verifies that:
1. Successful movement advances position.
2. Rejected movement does not advance position.
3. Missing outcome evidence is handled safely (never assumed successful).
4. HB 4007 rejection leaves west_eve at cont_b_origin_000.
5. Historical positions do not inherit phantom movement in subsequent heartbeats (HB 4008-4017).
6. Chronicle includes relevant rejected outcomes (collapse events during move/gather).
7. Existing viewer consumers remain compatible with the position_timeline and chronicle schema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from scripts.export_viewer_snapshot import (  # noqa: E402
    build_chronicle,
    reconstruct_positions,
)


@pytest.fixture
def sample_start_tiles():
    return {
        "west_adam": "cont_b_gen_34_51",
        "west_eve": "cont_b_origin_000",
    }


def test_successful_movement_advances_position(sample_start_tiles):
    """Authoritative success in action_outcomes advances the agent's position."""
    heartbeats = [
        {
            "heartbeat_number": 10,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_001",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "success",
                    "from": "cont_b_origin_000",
                    "to": "cont_b_origin_001",
                }
            },
            "world_mutations": [],
        }
    ]
    timeline = reconstruct_positions(heartbeats, sample_start_tiles)
    assert timeline["10"]["west_eve"] == "cont_b_origin_001"
    assert timeline["10"]["west_adam"] == "cont_b_gen_34_51"


def test_successful_movement_via_world_mutations(sample_start_tiles):
    """Authoritative success recorded in world_mutations advances position when outcomes is empty."""
    heartbeats = [
        {
            "heartbeat_number": 2,
            "action_taken": {
                "west_adam": {
                    "action_type": "move",
                    "target_tile": "cont_b_gen_49_50",
                }
            },
            "action_outcomes": {},
            "world_mutations": [
                {
                    "action_type": "move",
                    "acting_agent_id": "west_adam",
                    "outcome": {
                        "status": "success",
                        "from": "cont_b_gen_34_51",
                        "to": "cont_b_gen_49_50",
                    },
                }
            ],
        }
    ]
    timeline = reconstruct_positions(heartbeats, sample_start_tiles)
    assert timeline["2"]["west_adam"] == "cont_b_gen_49_50"


def test_rejected_movement_does_not_advance_position(sample_start_tiles):
    """Authoritative rejection in action_outcomes leaves the agent unmoved."""
    heartbeats = [
        {
            "heartbeat_number": 10,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_001",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "rejected",
                    "reason": "You have collapsed (vitality 0). Your body cannot act.",
                }
            },
            "world_mutations": [],
        }
    ]
    timeline = reconstruct_positions(heartbeats, sample_start_tiles)
    assert timeline["10"]["west_eve"] == "cont_b_origin_000"


def test_missing_outcome_evidence_handled_safely(sample_start_tiles):
    """If outcome evidence is missing, unverified moves must NOT advance position."""
    heartbeats = [
        {
            "heartbeat_number": 1,
            "action_taken": {
                "west_adam": {
                    "action_type": "move",
                    "target_tile": "cont_b_gen_49_50",
                }
            },
            "action_outcomes": {},
            "world_mutations": [],
        }
    ]
    timeline = reconstruct_positions(heartbeats, sample_start_tiles)
    assert timeline["1"]["west_adam"] == "cont_b_gen_34_51"


def test_hb4007_rejection_leaves_eve_unmoved():
    """Real store fixture: HB 4007 rejection leaves Eve at cont_b_origin_000."""
    hb4007 = {
        "heartbeat_number": 4007,
        "action_taken": {
            "west_adam": {"action_type": "eat", "resource_kind": "wild_berries"},
            "west_eve": {
                "action_type": "move",
                "reason": "to gather wild_berries and recover vitality",
                "target_tile": "cont_b_origin_001",
            },
        },
        "action_outcomes": {
            "west_adam": {
                "hunger_now": 0.0,
                "hunger_satisfied": 18.0,
                "resource_kind": "wild_berries",
                "status": "success",
            },
            "west_eve": {
                "reason": "You have collapsed (vitality 0). Your body cannot act. If food is brought to your tile you will eat and recover; otherwise rest.",
                "status": "rejected",
            },
        },
        "world_mutations": [],
    }
    start = {"west_adam": "cont_b_gen_34_51", "west_eve": "cont_b_origin_000"}
    timeline = reconstruct_positions([hb4007], start)
    assert timeline["4007"]["west_eve"] == "cont_b_origin_000"
    assert timeline["4007"]["west_adam"] == "cont_b_gen_34_51"


def test_subsequent_heartbeats_do_not_inherit_phantom_movement():
    """Eve remains at cont_b_origin_000 at HB 4014 and only moves at HB 4018."""
    heartbeats = [
        # HB 4006: baseline before attempt
        {
            "heartbeat_number": 4006,
            "action_taken": None,
            "action_outcomes": {},
            "world_mutations": [],
        },
        # HB 4007: rejected move to cont_b_origin_001
        {
            "heartbeat_number": 4007,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_001",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "rejected",
                    "reason": "You have collapsed (vitality 0).",
                }
            },
            "world_mutations": [],
        },
        # HB 4014: Eve asks operator remote help while downed at cont_b_origin_000
        {
            "heartbeat_number": 4014,
            "action_taken": {
                "west_eve": {
                    "action_type": "ask_human",
                    "question": "Can you provide wild_berries or feed me while I am downed at cont_b_origin_000?",
                }
            },
            "action_outcomes": {"west_eve": {"status": "proposed"}},
            "world_mutations": [],
        },
        # HB 4018: Successful move to cont_b_origin_002
        {
            "heartbeat_number": 4018,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_002",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "success",
                    "from": "cont_b_origin_000",
                    "to": "cont_b_origin_002",
                }
            },
            "world_mutations": [],
        },
    ]
    start = {"west_eve": "cont_b_origin_000"}
    timeline = reconstruct_positions(heartbeats, start)

    # HB 4006: at origin_000
    assert timeline["4006"]["west_eve"] == "cont_b_origin_000"
    # HB 4007: move rejected, stays at origin_000
    assert timeline["4007"]["west_eve"] == "cont_b_origin_000"
    # HB 4014: does NOT inherit phantom move to origin_001; remains at origin_000
    assert timeline["4014"]["west_eve"] == "cont_b_origin_000"
    # HB 4018: legitimately advances to origin_002
    assert timeline["4018"]["west_eve"] == "cont_b_origin_002"


def test_chronicle_includes_relevant_rejected_outcomes():
    """build_chronicle must capture collapse events even when action_type is move or gather."""
    heartbeats = [
        # Adam collapsed during gather
        {
            "heartbeat_number": 3987,
            "action_taken": {
                "west_adam": {
                    "action_type": "gather",
                    "resource_kind": "edible_roots",
                }
            },
            "action_outcomes": {
                "west_adam": {
                    "status": "rejected",
                    "reason": "You have collapsed (vitality 0). Your body cannot act.",
                }
            },
        },
        # Eve collapsed during move
        {
            "heartbeat_number": 4007,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_001",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "rejected",
                    "reason": "You have collapsed (vitality 0). Your body cannot act.",
                }
            },
        },
    ]
    name_by_hash = {"west_adam": "adam", "west_eve": "eve"}
    events = build_chronicle(heartbeats, name_by_hash)
    collapses = [e for e in events if e["kind"] == "collapse"]
    assert len(collapses) == 2, f"Expected 2 collapse events, got {len(collapses)}"
    assert collapses[0]["who"] == "adam"
    assert collapses[0]["hb"] == 3987
    assert collapses[1]["who"] == "eve"
    assert collapses[1]["hb"] == 4007


def test_existing_viewer_consumers_remain_compatible(sample_start_tiles):
    """Schema compatibility: position_timeline must be dict[str, dict[str, str]] with valid keys."""
    heartbeats = [
        {
            "heartbeat_number": 1,
            "action_taken": {
                "west_eve": {
                    "action_type": "move",
                    "target_tile": "cont_b_origin_001",
                }
            },
            "action_outcomes": {
                "west_eve": {
                    "status": "success",
                    "to": "cont_b_origin_001",
                }
            },
        }
    ]
    timeline = reconstruct_positions(heartbeats, sample_start_tiles)
    assert isinstance(timeline, dict)
    for tick_str, pos_map in timeline.items():
        assert isinstance(tick_str, str)
        assert tick_str.isdigit()
        assert isinstance(pos_map, dict)
        for agent, tile in pos_map.items():
            assert isinstance(agent, str)
            assert isinstance(tile, str)
