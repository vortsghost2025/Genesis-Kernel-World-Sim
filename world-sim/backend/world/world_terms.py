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

CURRENT_TERMS = "epistemic.2"
PREVIOUS_TERMS = "epistemic.1.1"


def terms_change_line(version: str) -> str:
    """The changelog line for a version, or '' if we have nothing on it.

    Empty is the honest default: if a version ships with no entry, the
    agent is told only that the version number moved, exactly as before.
    """
    return TERMS_CHANGELOG.get(version, "")


def current_terms_line() -> str:
    return terms_change_line(CURRENT_TERMS)
