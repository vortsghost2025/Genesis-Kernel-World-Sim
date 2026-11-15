"""Phase 10RJ — a collapsed body is offered only the actions it can take.

Measured 2026-11-14 on the live east lane: east_eve spent FIVE consecutive
heartbeats proposing actions the collapse gate refuses (extract edible_roots,
then gather edible_roots), with the full 18-action menu in front of her and the
runtime answering each attempt with a refusal that named her own action. Telling
a small model "no, not that" five times is worse than not offering it.

The fix is disclosure, and it is kept honest by construction: the menu is
rendered FROM the same tuple the runtime gates on, and the model asserts at
import that its per-action lines cover that tuple exactly. So the prompt cannot
offer a blocked action or hide an allowed one, and editing one side without the
other fails loudly instead of drifting.

10QI's contract is unchanged and asserted here too: collapse takes your hands,
not your legs or your reach -- eat, drink, move (crawl), speak and ask all still
work.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    COLLAPSED_PERMITTED_ACTIONS,
)


def _menu_actions(text: str) -> set[str]:
    """The action names the menu bullet-lists."""
    found = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            name = line[2:].split(":", 1)[0].strip()
            if name.isidentifier():
                found.add(name)
    return found


# --- one source of truth ----------------------------------------------------

def test_the_collapsed_menu_is_exactly_the_permitted_set():
    """Rendered from the gate's own tuple, so they cannot disagree."""
    assert _menu_actions(m._COLLAPSED_ACTIONS_DESC) == set(COLLAPSED_PERMITTED_ACTIONS)


def test_the_collapsed_menu_omits_every_blocked_action():
    """The whole point: the blocked actions are not on the list at all."""
    actions = _menu_actions(m._COLLAPSED_ACTIONS_DESC)
    for blocked in ("gather", "build", "craft", "use_object", "hew_timber",
                    "plant_crop", "harvest_crop", "attack", "milk_animal",
                    "create_public_object", "modify_owned_public_object",
                    "request_capability", "revise_charter", "offer_food"):
        assert blocked not in actions, f"{blocked} must not be offered while down"


def test_the_full_menu_still_offers_everything_when_standing():
    """Only the collapsed case is scoped; a standing body is untouched."""
    actions = _menu_actions(m._AVAILABLE_ACTIONS_DESC)
    # `craft` is not its own action -- it is an operation of use_object -- so it
    # is not in the bullet list on either menu.
    for available in ("gather", "build", "use_object", "hew_timber",
                      "plant_crop", "harvest_crop", "attack", "offer_food",
                      "milk_animal", "eat", "drink", "move", "ask_human"):
        assert available in actions, available
    assert len(actions) > 12, "the full menu should still be the full menu"


def test_it_says_the_blocked_things_are_unavailable():
    """Scoping the menu must not make the world's rules invisible."""
    text = m._COLLAPSED_ACTIONS_DESC
    assert "your body has collapsed" in text
    assert "Unavailable until you recover" in text
    for word in ("gathering", "building", "crafting", "deposit", "extract"):
        assert word in text, word


# --- the prompt actually switches ------------------------------------------

def _prompt(downed: bool) -> str:
    from backend.world.first_pair_cognition_interface import AgentContext

    ctx = AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0",
        observation={"self_body": {"downed": downed, "vitality": 3.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 19.0, "wetness": 100.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    return m.build_system_prompt(ctx)


def test_a_downed_prompt_carries_the_collapsed_menu_and_not_the_full_one():
    prompt = _prompt(True)
    assert "so this is the WHOLE list" in prompt
    assert "- gather: collect a resource from your current tile" not in prompt
    assert "- use_object: interact with a public object" not in prompt
    assert "- eat: eat one unit of a food you are carrying (requires: "\
           "resource_kind) — this works" in prompt


def test_a_standing_prompt_carries_the_full_menu():
    prompt = _prompt(False)
    assert "so this is the WHOLE list" not in prompt
    assert "- gather: collect a resource from your current tile" in prompt
    assert "- use_object: interact with a public object" in prompt


# --- the gate itself must not have moved ------------------------------------

def test_the_runtime_gate_uses_the_same_tuple():
    src = (WORLD_SIM / "backend" / "world" / "first_pair_runtime.py").read_text(
        encoding="utf-8")
    assert "if action_type not in COLLAPSED_PERMITTED_ACTIONS:" in src
    assert '"leave_public_message", "ask_human",' not in src, (
        "the inline tuple is what drifted; the shared constant replaced it")


def test_the_permitted_set_is_the_one_10qi_promised():
    """Collapse takes your hands, not your legs or your reach."""
    assert set(COLLAPSED_PERMITTED_ACTIONS) == {
        "no_action", "move", "eat", "drink", "leave_public_message", "ask_human"}
