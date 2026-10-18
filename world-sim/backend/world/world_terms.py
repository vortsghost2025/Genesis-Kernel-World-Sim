"""Terms changelog - what actually changed, in the agent's own terms.

A version number tells an agent that the world moved. It does not tell
it what moved, and that gap produced the HB801-834 arc: both East agents
burned every berry they held into "food processing" buildings trying to
unlock a conversion mechanic that had been deleted two commits earlier.
They were not confused about the numbers - they were reasoning correctly
about rules that no longer existed, and nothing in the world said so.

So: when the terms change, the world says what changed. One line per
version, in plain language, stating removals as removals. This is not
the operator explaining the simulation, and it is not strategy advice.
It is a changelog. It never says what to do, only what is no longer
true.

Adding an entry here is how a future physics change announces itself.
"""

from __future__ import annotations

# version -> what is no longer true under it
TERMS_CHANGELOG: dict[str, str] = {
    "epistemic.1": (
        "No longer true: food and hunger. There is no food counter, no "
        "0/20, no famished state, no conversion, and no build gate for "
        "lacking food. Berries are berries - gather them, build with them, "
        "and they simply stay in your belongings. There is no carrying "
        "capacity and no consumption: nothing is taken from you. A gather "
        "takes what the tile offers, up to 1, and that is all there is."
    ),
}

# epistemic.1.1 is a DELIVERY bump: same terms as epistemic.1, shipped
# because the changelog above was keyed to a version the live agents had
# already been marked as seeing, so its gate never opened. The agents who
# need this message have never received it, so the current version carries
# it too - not as a physics change, but as the envelope for the one that
# already happened.
TERMS_CHANGELOG["epistemic.1.1"] = TERMS_CHANGELOG["epistemic.1"]

# epistemic.2: the enclosure (docs/world_walls_spec.md). A real physics
# change, stated as removals and one rule, never as advice. The last two
# sentences state the unlock mechanic the same way the operator's
# food-mechanics answers stated theirs: what the rules are, not what to do.
TERMS_CHANGELOG["epistemic.2"] = (
    "No longer true: that the land continues in every direction. To the "
    "west and east the water is now too deep to wade. To the north the "
    "thicket is too dark to enter. To the south the ground drops away "
    "into darkness. Walking stops at these. Some things, built and left "
    "standing, can change what can be crossed - the world does not say "
    "which. Test what you conclude."
)

# epistemic.3: objects hold things (docs/object_interaction_spec.md).
# A real physics change, stated as removals and one addition, never as
# advice. Eve at HB1864 asked for this mechanic by name: "put materials
# into an object and get something back out."
TERMS_CHANGELOG["epistemic.3"] = (
    "No longer true: that objects are inert records. Objects can now "
    "hold materials. A new action, use_object, deposits materials from "
    "your belongings into an object, extracts materials from an object "
    "back into your belongings, and inspects what an object contains. "
    "Any object on your current tile can hold things, regardless of "
    "what it is called or who built it."
)

# epistemic.4: the body (docs/survival_physics_spec.md). A real physics
# change. Stated as facts about the body and the world, never as advice:
# the world now imposes costs of time, warmth and safety. Abundance was
# measured first (audit_tile_resources.py) — hunger is a clock, not a
# famine.
TERMS_CHANGELOG["epistemic.4"] = (
    "No longer true: that your body costs nothing. You have a body now. "
    "Hunger rises with every heartbeat; the eat action consumes food "
    "from your belongings and satisfies it — cooked food satisfies far "
    "more than raw. Night and winter are cold: cold drains warmth, "
    "standing near a lit fire restores it, and shelter slows the drain. "
    "Vitality fails when hunger or cold is neglected; at zero vitality "
    "you collapse and cannot act until your body recovers — food "
    "deposited on your tile feeds you even while you are down. Your "
    "body is in your observation under self_body; the hour, season and "
    "temperature are under environment. Nothing here tells you what to "
    "do about any of it."
)

# epistemic.5: the sky. Weather as facts, never advice.
TERMS_CHANGELOG["epistemic.5"] = (
    "No longer true: that the sky is empty. Weather now exists. Rain "
    "soaks an exposed body; a soaked body cannot hold warmth, and a "
    "warm fire will not dry-warm it until the wetness is gone. Storms "
    "are colder and drain the vitality of anyone left exposed. Rain "
    "snuffs open fires — a fire standing under a roof keeps burning. "
    "Shelter blocks rain entirely and slows every cold drain. The "
    "observation's environment shows the current weather, the next "
    "window, and when the sky changes. The sky owes you nothing and "
    "asks you nothing."
)

CURRENT_TERMS = "epistemic.5"
PREVIOUS_TERMS = "epistemic.4"
PREVIOUS_TERMS = "epistemic.3"


def terms_change_line(version: str) -> str:
    """The changelog line for a version, or '' if we have nothing on it.

    Empty is the honest default: if a version ships with no entry, the
    agent is told only that the version number moved, exactly as before.
    """
    return TERMS_CHANGELOG.get(version, "")


def current_terms_line() -> str:
    return terms_change_line(CURRENT_TERMS)
