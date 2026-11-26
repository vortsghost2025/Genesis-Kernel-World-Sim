"""Tests for prompt-size caps in first_pair_cognition_model.

The genesis prompt reached 261k chars / 112k tokens because goals, world
objects, messages, and tool conditions were dumped unbounded. These tests pin
the caps: test-marker objects dropped, current-tile preference, list caps,
anchor cap, and tool-condition summarization.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from world.first_pair_cognition_interface import AgentContext
from world.first_pair_cognition_model import (
    _cap_list_for_prompt,
    _cap_objects_for_prompt,
    _cap_own_anchors,
    build_system_prompt,
)


def _obj(oid, tile="cont_a_gen_-48_6", hb=1, creator="agent-x"):
    return {
        "object_id": oid,
        "object_type": "shelter",
        "tile_id": tile,
        "created_heartbeat": hb,
        "creator_agent_id": creator,
        "public_description": f"shelter {oid}",
    }


def _ctx(**overrides):
    base = dict(
        agent_id="agent-x",
        canonical_name="Test Agent",
        canonical_ref="test",
        heartbeat_number=100,
        position="cont_a_gen_-48_6",
        observation={},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=[],
        habitat_movement_allowed=True,
        previous_action=None,
        timestamp_utc="2026-11-26T00:00:00+00:00",
    )
    base.update(overrides)
    return AgentContext(**base)


def test_objects_drop_test_berry_markers():
    objects = {
        "real": _obj("shelter-1"),
        "spam": _obj("test-berry-marker-adam", hb=2),
    }
    capped = _cap_objects_for_prompt(objects, "cont_a_gen_-48_6", 15)
    ids = [o["object_id"] for o in capped]
    assert "shelter-1" in ids
    assert not any(i.startswith("test-berry-") for i in ids)


def test_objects_prefer_current_tile_and_limit():
    objects = {}
    for i in range(30):
        objects[f"far{i}"] = _obj(f"far{i}", tile="cont_a_gen_0_0", hb=i)
    objects["home"] = _obj("home", tile="cont_a_gen_-48_6", hb=0)
    capped = _cap_objects_for_prompt(objects, "cont_a_gen_-48_6", 15)
    assert len(capped) == 15
    assert capped[0]["object_id"] == "home"


def test_cap_list_keeps_last_n():
    items = list(range(25))
    assert _cap_list_for_prompt(items, 10) == list(range(15, 25))
    assert _cap_list_for_prompt([1, 2, 3], 10) == [1, 2, 3]
    assert _cap_list_for_prompt([], 10) == []
    assert _cap_list_for_prompt(None, 10) == []


def test_own_anchors_newest_n():
    own = [_obj(f"a{i}", hb=i) for i in range(20)]
    capped = _cap_own_anchors(own, 10)
    assert len(capped) == 10
    assert capped[-1]["object_id"] == "a19"
    assert capped[0]["object_id"] == "a10"


def _big_context():
    objects = {}
    for i in range(300):
        o = _obj(f"o{i}", tile="cont_a_gen_0_0", hb=i)
        o["public_description"] = "shelter description " * 20  # fatten the raw state
        objects[f"o{i}"] = o
    objects["test-berry-marker-adam"] = _obj("test-berry-marker-adam", hb=301)
    msgs = [{"text": f"message {i} " + "lorem ipsum " * 20, "ts": i} for i in range(60)]
    events = [{"kind": "co_located", "ts": i} for i in range(40)]
    tools = {"stone_axe": [24] * 300}
    return _ctx(
        world_public_objects=objects,
        visible_public_messages=msgs,
        public_relationship_events=events,
        unanswered_questions=[{"q": f"q{i}"} for i in range(30)],
        answered_questions=[{"q": f"a{i}"} for i in range(30)],
        tool_condition=tools,
    )


def test_prompt_is_bounded_on_huge_state():
    ctx = _big_context()
    prompt = build_system_prompt(ctx)
    # The raw state JSON is enormous; the prompt must be a small fraction of it.
    raw_size = len(json.dumps(ctx.world_public_objects)) + len(
        json.dumps(ctx.visible_public_messages)
    )
    assert raw_size > 100_000
    # Prompt must not contain the full dumps.
    assert "message 59" in prompt  # newest messages survive
    assert "message 0" not in prompt  # oldest are capped out
    assert "test-berry-" not in prompt
    # Bounded total size: capped objects (15), messages (10), events (10),
    # questions (10 each), anchors (10), and summarized tools.
    assert len(prompt) < raw_size / 3
    # Tool spam is summarized, not dumped.
    assert "x300" in prompt


def test_prompt_keeps_current_tile_objects():
    objects = {f"far{i}": _obj(f"far{i}", tile="cont_a_gen_0_0", hb=i) for i in range(50)}
    objects["home"] = _obj("home", tile="cont_a_gen_-48_6", hb=0)
    ctx = _ctx(world_public_objects=objects)
    prompt = build_system_prompt(ctx)
    assert "shelter home" in prompt
    assert len([o for o in _cap_objects_for_prompt(objects, "cont_a_gen_-48_6", 15)]) == 15
