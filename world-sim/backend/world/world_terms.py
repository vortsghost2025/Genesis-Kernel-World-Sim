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

CURRENT_TERMS = "epistemic.1"


def terms_change_line(version: str) -> str:
    """The changelog line for a version, or '' if we have nothing on it.

    Empty is the honest default: if a version ships with no entry, the
    agent is told only that the version number moved, exactly as before.
    """
    return TERMS_CHANGELOG.get(version, "")


def current_terms_line() -> str:
    return terms_change_line(CURRENT_TERMS)
