"""Phase B — an agent's own built things must survive memory selection.

`docs/build_meaning_spec.md`. The substrate shows an agent ~1% of its own
history each heartbeat (epistemic_pressure_spec.md §2). The charter is
verbatim and unbounded, and 0 of 4 agents have ever written one. Phase B
gives the *other* half of the same guarantee to findings: when an agent
writes a thing down, the runtime presents it back to that agent, verbatim,
outside the selection pipeline.

No new verb, no new object type. Authorship is what separates an anchor from
ordinary shared state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.world.first_pair_cognition_model as cm
from backend.world.first_pair_cognition_interface import AgentContext

WORLD_SIM = Path(__file__).resolve().parents[1]


def _obj(obj_id: str, creator: str, tile: str, desc: str) -> dict:
    return {
        "object_id": obj_id,
        "creator_agent_id": creator,
        "tile_id": tile,
        "object_type": "landmark",
        "public_description": desc,
        "created_heartbeat": 10,
    }


def _ctx(agent_id: str, objects: dict) -> AgentContext:
    return AgentContext(
        agent_id=agent_id,
        canonical_name=agent_id,
        canonical_ref=agent_id,
        other_agent_id="other",
        other_agent_name="Other",
        other_agent_ref="other",
        heartbeat_number=11,
        position="t1",
        observation={"tile_id": "t1", "visible_tiles": ["t1"]},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects=objects,
        habitat_allowed_tiles=["t1"],
        habitat_movement_allowed=True,
        previous_action=None,
        timestamp_utc="2026-09-28T00:00:00+00:00",
    )


def _prompt(agent_id: str, objects: dict) -> str:
    return cm.build_system_prompt(_ctx(agent_id, objects))


def _anchor_block(prompt: str) -> str:
    """The anchors section only - bounded at the next section header.

    Slicing to end-of-prompt would swallow the shared objects list, where the
    OTHER agent's text legitimately appears. That is exactly the
    cross-contamination the authorship rule exists to prevent, so the
    boundary has to be the section, not the document.
    """
    assert "YOUR ANCHORS" in prompt, "no anchor section in prompt"
    rest = prompt.split("YOUR ANCHORS", 1)[1]
    end = rest.find("\n--- ")
    return rest if end == -1 else rest[:end]


class TestAnchorsAreSeparatedByAuthorship:
    def test_own_objects_appear_in_the_anchors_section(self):
        objects = {"a1": _obj("a1", "east_adam", "t1", "I found drinkable water.")}
        prompt = _prompt("east_adam", objects)
        assert "ANCHOR" in prompt.upper()
        assert "I found drinkable water." in prompt

    def test_other_agents_objects_do_not_anchor(self):
        objects = {
            "a1": _obj("a1", "east_eve", "t2", "Eve's finding, not mine."),
        }
        prompt = _prompt("east_adam", objects)
        assert "Eve's finding, not mine." not in _anchor_block(prompt)

    def test_both_authorships_anchor_for_their_own_owner(self):
        objects = {
            "a1": _obj("a1", "east_adam", "t1", "Adam wrote this."),
            "e1": _obj("e1", "east_eve", "t2", "Eve wrote this."),
        }
        adam = _prompt("east_adam", objects)
        eve = _prompt("east_eve", objects)
        assert "Adam wrote this." in _anchor_block(adam)
        assert "Eve wrote this." not in _anchor_block(adam)
        assert "Eve wrote this." in _anchor_block(eve)
        assert "Adam wrote this." not in _anchor_block(eve)

    def test_anchors_do_not_cross_contaminate_between_agents(self):
        """The two agents must never see each other's anchor slot."""
        objects = {
            "a1": _obj("a1", "east_adam", "t1", "Adam private note."),
        }
        eve_prompt = _prompt("east_eve", objects)
        assert "Adam private note." not in _anchor_block(eve_prompt)


class TestAnchorsAreVerbatim:
    def test_anchor_text_is_not_summarized_or_truncated(self):
        long_text = "S" * 900
        objects = {"a1": _obj("a1", "east_adam", "t1", long_text)}
        prompt = _prompt("east_adam", objects)
        assert long_text in prompt, "anchor text must survive verbatim"

    def test_unicode_anchor_survives(self):
        text = "The river at origin 000 — 饮水 — still flows."
        objects = {"a1": _obj("a1", "east_adam", "t1", text)}
        assert text in _prompt("east_adam", objects)


class TestNeutralCases:
    def test_no_objects_yields_a_neutral_anchor_section(self):
        prompt = _prompt("east_adam", {})
        assert "ANCHOR" in prompt.upper()
        block = _anchor_block(prompt)
        assert "Traceback" not in block
        assert "You have not built anything yet." in block

    def test_object_without_description_produces_no_empty_anchor(self):
        obj = _obj("a1", "east_adam", "t1", "")
        prompt = _prompt("east_adam", {"a1": obj})
        block = _anchor_block(prompt)
        assert "nothing to anchor yet" in block
        assert "- [" not in block, "no empty bullet for a descriptionless object"

    def test_anchor_section_does_not_duplicate_the_shared_object_list(self):
        """The shared list must stay exactly as it was."""
        objects = {"a1": _obj("a1", "east_adam", "t1", "visible to both.")}
        prompt = _prompt("east_eve", objects)
        # Eve does not anchor it, but it must still be in the shared JSON.
        assert "visible to both." in prompt
        assert '"object_id": "a1"' in prompt


class TestMemorySelectionIsUntouched:
    def test_anchor_builder_does_not_touch_selection(self):
        """Anchors sit outside selection, like the charter. The builder must
        not read the selection pipeline or its budgets."""
        source = (WORLD_SIM / "backend" / "world"
                  / "first_pair_cognition_model.py").read_text(encoding="utf-8")
        block = _anchor_source_block(source)
        for forbidden in ("_MAX_SELECTED_", "selected_private_memories",
                          "derived_memory_summaries", "memory_selection_manifest"):
            assert forbidden not in block, (
                f"anchor builder must not reference {forbidden}"
            )

    def test_anchor_builder_reads_only_its_own_objects(self):
        source = (WORLD_SIM / "backend" / "world"
                  / "first_pair_cognition_model.py").read_text(encoding="utf-8")
        block = _anchor_source_block(source)
        assert "world_public_objects" in block
        assert "creator_agent_id" in block
        assert "private_memor" not in block.lower()


def _anchor_source_block(source: str) -> str:
    """The source slice that builds the anchor section, bounded at the charter
    comment that follows it."""
    start = source.find("# --- Anchors (Phase B)")
    if start == -1:
        return "<not implemented>"
    end = source.find("# --- Charter", start)
    assert end != -1, "anchor block must be bounded by the charter section"
    return source[start:end]


class TestNoImplementationNamesLeak:
    def test_prompt_carries_no_implementation_terms(self):
        objects = {"a1": _obj("a1", "east_adam", "t1", "a finding")}
        text = _prompt("east_adam", objects)
        for forbidden in ("known_map", "true_map", "creator_agent_id"):
            if forbidden == "creator_agent_id":
                continue  # may legitimately appear in the shared JSON list
            assert forbidden not in text
