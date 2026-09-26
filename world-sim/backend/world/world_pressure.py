"""World pressure — pure physics module (docs/world_pressure_spec.md, v2).

Provision: every heartbeat the world takes FOOD_PER_HEARTBEAT food units
from what an agent holds; an agent holding no food is famished for that
heartbeat (famished blocks build; nothing else). Capacity: holdings are
carried in two ledgers — food <= FOOD_CAP, goods <= GOODS_CAP — with a
precise per-ledger gather rule: fill up to the cap, or when over the cap
replace only what was just consumed. Construction is the only way past
the goods cap: materials spent on build leave the ledgers at build time.

This module is pure: no I/O, no store access, no runtime imports. The
runtime applies the decisions; the store persists them. Fail-closed:
malformed holdings never raise, they read as empty hands.

Physics constants are operator-set world terms. Rejection strings are a
frozen contract: the live behavior census and the public show count them
verbatim — never reword casually.
"""

from __future__ import annotations

FOOD_CAP = 20
GOODS_CAP = 20
FOOD_PER_HEARTBEAT = 1
# A gather takes up to GATHER_YIELD units of what the tile offers, bounded
# by cap room (partial takes top off a nearly-full ledger). GATHER_YIELD
# must exceed FOOD_PER_HEARTBEAT, or food becomes mathematically
# unbankable: with yield <= consumption an agent can never hold more than
# its per-tick burn, so the famished build-gate can never clear (found by
# the HB701-743 live arc: East pair pinned at 0-1 food forever).
GATHER_YIELD = 3

# Bumped whenever the world's observable terms change (caps, consumption,
# yield, placement, gates). It rides in every observation and in the
# prompt, so an agent whose self-authored model was formed under older
# terms can notice that the world it remembers is not the world it is
# standing in (HB701-743: an agent concluded "build is impossible while
# over capacity" from refusals caused by a placement bug, and had no way
# to learn the rule had changed).
PHYSICS_VERSION = "pressure.2"

FOOD_KINDS = frozenset(
    {"wild_berries", "mushrooms", "edible_roots", "fish", "shellfish"}
)

GATHER_REJECT_GOODS = "hands full"
GATHER_REJECT_FOOD = "food store full"
BUILD_REJECT_FAMISHED = "famished: you cannot build on an empty stomach"


def _clean_holdings(holdings) -> dict:
    """Keep only well-formed entries: str kind, positive int amount."""
    if not isinstance(holdings, dict):
        return {}
    out = {}
    for kind, amount in holdings.items():
        if not isinstance(kind, str):
            continue
        if not isinstance(amount, int) or isinstance(amount, bool):
            continue
        if amount <= 0:
            continue
        out[kind] = amount
    return out


def split_ledgers(holdings) -> dict:
    """Split holdings into {food, goods} unit totals. Malformed reads as 0."""
    food = 0
    goods = 0
    for kind, amount in _clean_holdings(holdings).items():
        if kind in FOOD_KINDS:
            food += amount
        else:
            goods += amount
    return {"food": food, "goods": goods}


def consume_choice(holdings) -> str | None:
    """Pick the food kind the world consumes this heartbeat.

    Most-held food kind; ties break alphabetically (deterministic).
    None when no food is held (famished).
    """
    foods = {
        k: v for k, v in _clean_holdings(holdings).items() if k in FOOD_KINDS
    }
    if not foods:
        return None
    return sorted(foods.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def gather_allowance(
    resource_kind, holdings, food_start: int, goods_start: int, available: int
) -> tuple:
    """How much a gather may take right now: (take, reason).

    `available` is what the tile offers (pre-decrement); `take` is
    min(GATHER_YIELD, available, cap room) — partial takes top off a
    nearly-full ledger instead of failing it. `reason` is the frozen
    rejection string when take == 0, else None.

    Rule, precise. Food ledger: the room is max(FOOD_CAP, food_start) —
    at/under cap you fill to the cap; over cap you may replace only what
    this tick's consumption took (food_start is pre-consumption), never
    grow. Goods ledger: the room is GOODS_CAP outright — goods are never
    consumed, so an over-cap goods ledger takes nothing and shrinks only
    by building. A famished agent (food_start == 0) can always gather
    food, so no famished-and-frozen state exists.
    """
    if not isinstance(resource_kind, str) or not resource_kind.strip():
        return 0, None  # not a cap question; the executor's own validation answers
    led = split_ledgers(holdings)
    is_food = resource_kind in FOOD_KINDS
    current = led["food"] if is_food else led["goods"]
    room = (
        max(FOOD_CAP, food_start) if is_food else GOODS_CAP
    ) - current
    take = min(GATHER_YIELD, available, room) if available > 0 else 0
    if take <= 0:
        return 0, GATHER_REJECT_FOOD if is_food else GATHER_REJECT_GOODS
    return take, None


def provisions_view(holdings, famished: bool) -> dict:
    """Per-agent personal state for the observation. No map data."""
    return {"food_units": split_ledgers(holdings)["food"],
            "famished": bool(famished)}


def carrying_view(holdings) -> dict:
    """Per-agent personal state for the observation. No map data."""
    led = split_ledgers(holdings)
    return {
        "food_used": led["food"],
        "food_cap": FOOD_CAP,
        "goods_used": led["goods"],
        "goods_cap": GOODS_CAP,
    }
