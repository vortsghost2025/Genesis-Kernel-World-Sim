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


def gather_rejection(
    resource_kind, holdings, food_start: int, goods_start: int
) -> str | None:
    """The precise per-ledger cap rule.

    Rule, precise. Food ledger: allowed iff post-gather total <=
    max(FOOD_CAP, food_start) — fill to the cap, or when over the cap
    replace only what this tick's consumption just removed (food_start is
    pre-consumption). A famished agent (food_start == 0) can always gather
    food, so no famished-and-frozen state exists. Goods ledger: allowed
    iff post-gather total <= GOODS_CAP — the goods ledger is never
    consumed, so an over-cap goods ledger may not gather at all; it
    shrinks only by building, which is what makes construction the
    question goods ask.
    """
    if not isinstance(resource_kind, str) or not resource_kind.strip():
        return None  # not a cap question; the executor's own validation answers
    led = split_ledgers(holdings)
    is_food = resource_kind in FOOD_KINDS
    current = led["food"] if is_food else led["goods"]
    cap = FOOD_CAP if is_food else GOODS_CAP
    if is_food:
        if current + 1 <= max(cap, food_start):
            return None
        return GATHER_REJECT_FOOD
    if current + 1 <= cap:
        return None
    return GATHER_REJECT_GOODS


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
