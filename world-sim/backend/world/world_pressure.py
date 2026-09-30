"""World physics — the world's costs and constants.

This module was the hunger/capacity pressure model (FOOD_CAP, GOODS_CAP,
per-heartbeat consumption, the famished build gate). It was RETIRED after
the HB701-800 arc measured it failing, and the removal is what remains
here.

What went wrong, in one table: east_adam's home tile
(`public-start-adam`) yields exactly one wild_berry per heartbeat, and
consumption removed exactly one per heartbeat. His food was pinned at 0
for over 100 heartbeats. He reported it as a bug at HB797 - "or is there a
bug?" - and he was right. The East pair's 0% build rate was not apathy; it
was two agents correctly refusing to act on a board where action was
impossible, and it was misread as "the world asks nothing of them."
Meanwhile 5 of 5 objects the other pair built said, in their own words,
"to reduce goods overcapacity": the cap had turned minds into
inventory accountants.

What is left is deliberately almost nothing:

  GATHER_YIELD      how much one gather action takes from a tile
  PHYSICS_VERSION   which version of the world's terms agents have been
                    shown, so a model formed under older terms can notice
                    the terms changed

The world now has no costs. That is a real risk - an unpressured world
may let agents drift further into their loops - and it is stated in
docs/epistemic_pressure_spec.md §7. It is also the only sound basis for
designing the next pressure: the previous two were designed by reasoning
about what agents would find interesting, and both were wrong in ways one
table of resource data would have shown. Measure the board first;
scripts/audit_tile_resources.py is the standing guard for that.
"""

from __future__ import annotations

# How much a single gather action takes from what the tile offers,
# bounded by what is actually there.
GATHER_YIELD = 1

# Bumped whenever the world's observable terms change. It rides in every
# observation and in the prompt, so an agent whose self-authored model was
# formed under older terms can notice the world it remembers is not the
# world it is standing in. (HB701-743: an agent concluded "build is
# impossible while over capacity" from refusals caused by a placement
# bug, and had no way to learn the rule had changed.)
#
# epistemic.1.1 is a delivery bump, not a physics change: the terms
# changelog for epistemic.1 shipped keyed to a version the live agents
# had ALREADY been recorded as seeing, so its gate (new_to_agent) was
# False forever and the message never reached the only agents it was
# written for - verified live, they kept burning berries at HB842-846.
# The bump re-arms the gate once for every agent.
# epistemic.2 is a REAL physics change (docs/world_walls_spec.md): the
# enclosure. The world is now bounded near the explored frontier by deep
# water west and east, a dark thicket north, a ravine south. The changelog
# entry states the removals and the one rule addition, nothing else.
PHYSICS_VERSION = "epistemic.2"
