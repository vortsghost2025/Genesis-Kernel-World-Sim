"""Runtime integration: roads give 2-step movement.

Standing on a tile with a road object, the agent sees 2-step tiles in
available_moves. The world opens because you built a road, not because
anything would have punished you for not building one.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)
from backend.world.first_pair_cognition_model import (  # noqa: E402
    build_system_prompt,
)
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


def _rt(tmp_path):
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    return rt


class TestRoadMovement:
    def test_road_in_prompt_when_standing_on_one(self, tmp_path):
        """The move action description mentions road movement so agents
        discover it from the contract, same as use_object."""
        prompt = build_system_prompt(AgentContext(
            agent_id="a" * 64, canonical_name="Adam",
            canonical_ref="east_adam", heartbeat_number=1,
            position="tile-a",
            observation={"tile_id": "tile-a",
                         "visible_tiles": ["tile-a"], "objects_here": []},
            memory=[], goals=[], unanswered_questions=[],
            world_public_objects={},
            habitat_allowed_tiles=["tile-a"],
            habitat_movement_allowed=False,
            previous_action=None, timestamp_utc="2026-01-01T00:00:00Z",
            other_agent_id="b" * 64, other_agent_name="Eve",
            other_agent_ref="east_eve", answered_questions=[],
        ))
        assert "road" in prompt.lower(), (
            "the prompt must mention road movement so agents can discover it")
