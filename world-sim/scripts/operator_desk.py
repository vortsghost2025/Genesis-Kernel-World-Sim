"""The operator desk: questions answered at the moment they are asked.

Sean was the relay: an agent asks, his phone pings, and answering
depended on the operator being awake and prompted. The delegation says
otherwise — the operator answers factual questions, states what is
true, never strategy. This desk automates exactly that:

  every steward poll, unheard questions are grounded in the asking
  agent's live world facts (body, belongings, tile, sky, partner) and
  answered in the operator register. Matched questions are marked
  answered; questions the desk cannot answer factually stay unheard
  and are the ONLY ones that escalate to the phone.

Register guardrails, enforced:
  - facts about mechanics and world state, never "you should/must"
  - grounded: an answer names the asker's actual numbers and holdings
  - no task assignment, ever — the purpose question answers itself
  - unknown or capability-shaped questions escalate (not answered)

Usage (usually via world_steward poll):
    python world-sim/scripts/operator_desk.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))
if str(WORLD_SIM / "scripts") not in sys.path:
    sys.path.insert(0, str(WORLD_SIM / "scripts"))

from backend.world import survival  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    load_agent_question_proposals,
    load_inventory,
    save_agent_question_proposals,
)
from operator_say import say  # noqa: E402

PAIRS = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
ADVICE_PATTERNS = ("you should", "you must", "we recommend", "try to",
                   "i want you to", "you need to")
MAX_PER_PAIR = 2


def assert_no_advice(text: str) -> str:
    """The register guardrail: facts only. Raises on advice."""
    low = str(text).lower()
    for pattern in ADVICE_PATTERNS:
        if pattern in low:
            raise ValueError(f"operator register violation: {pattern!r}")
    return text


def _food_summary(holdings: dict) -> str:
    """Edible holdings as a fact sentence fragment."""
    if not isinstance(holdings, dict):
        return "nothing"
    foods = {
        k: v for k, v in holdings.items()
        if k in survival.EAT_SATISFACTION and isinstance(v, int) and v > 0
    }
    if not foods:
        return "nothing edible"
    return "; ".join(f"{k} ×{v}" for k, v in sorted(foods.items()))


def ground_facts(pair_name: str, store: FirstPairPersistenceStore,
                 agent_ref: str) -> dict:
    """The asker's live world facts — everything the answer may state."""
    ws_path = store.root / "world_state.json"
    ws = {}
    try:
        ws = json.loads(ws_path.read_text(encoding="utf-8")).get("data", {})
    except Exception:
        pass
    occupancy = ws.get("tile_occupancy", {})
    vitals = (ws.get("vitals") or {}).get(agent_ref, {})
    position = occupancy.get(agent_ref, "unknown")
    inventory = load_inventory(store).get(agent_ref, {})

    other_ref = "east_eve" if agent_ref.endswith("adam") else "east_adam"
    for ref in occupancy:
        if ref != agent_ref and ref.split("_")[-1] in ("adam", "eve"):
            other_ref = ref
            break
    other_inventory = load_inventory(store).get(other_ref, {})
    other_position = occupancy.get(other_ref, "unknown")

    tick = ws.get("tick", 0)
    weather, window_end = survival.weather_at(pair_name, tick)
    season_name = survival.season(tick)
    night = survival.is_night(tick)

    # edible materials in objects on the asker's tile
    tile_food = []
    for record in (ws.get("public_objects") or {}).values():
        if not isinstance(record, dict) or record.get("tile_id") != position:
            continue
        for kind, amount in (record.get("materials") or {}).items():
            if (kind in survival.EAT_SATISFACTION
                    and isinstance(amount, int) and amount > 0):
                tile_food.append(f"{kind} ×{amount}")

    facts = {
        "agent_ref": agent_ref,
        "hunger": vitals.get("hunger"),
        "warmth": vitals.get("warmth"),
        "vitality": vitals.get("vitality"),
        "downed": vitals.get("downed"),
        "position": position,
        "inventory": inventory,
        "food_on_hand": _food_summary(inventory),
        "other_ref": other_ref,
        "other_name": other_ref.split("_")[-1],
        "other_position": other_position,
        "other_food": _food_summary(other_inventory),
        "tile_food": tile_food,
        "weather": weather,
        "season": season_name,
        "night": night,
        "temperature": round(survival.effective_temperature(tick, weather), 1),
        "tick": tick,
        "terms": __import__("backend.world.world_pressure",
                            fromlist=["PHYSICS_VERSION"]).PHYSICS_VERSION,
    }
    facts["tile_resources"] = _tile_resources(position)
    return facts


_TRUE_MAP_CACHE: dict | None = None


def _load_true_map() -> dict:
    global _TRUE_MAP_CACHE
    if _TRUE_MAP_CACHE is None:
        try:
            _TRUE_MAP_CACHE = json.loads(
                (WORLD_SIM / "data" / "world" / "true_map.json")
                .read_text(encoding="utf-8"))
        except Exception:
            _TRUE_MAP_CACHE = {"tiles": [], "resources": []}
    return _TRUE_MAP_CACHE


def _tile_resources(tile_id: str) -> list:
    """Gatherable resources on one tile, from the true map."""
    tm = _load_true_map()
    out = []
    for res in tm.get("resources", []):
        if res.get("tile_id") == tile_id:
            amount = res.get("amount", 0)
            if isinstance(amount, int) and amount > 0:
                out.append(f"{res.get('kind')} x{amount}")
    return out


def _tile_and_neighbors_resources(tile_id: str) -> dict:
    """Resources on the named tile and its eight neighbors."""
    tm = _load_true_map()
    coord_by_id = {}
    for t in tm.get("tiles", []):
        c = t.get("coordinates")
        if c:
            coord_by_id[t.get("tile_id")] = (c.get("x"), c.get("y"))
    id_by_coord = {v: k for k, v in coord_by_id.items()}
    xy = coord_by_id.get(tile_id)
    if xy is None:
        return {}
    x, y = xy
    out = {}
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            nid = id_by_coord.get((x + dx, y + dy))
            if nid:
                out[nid] = _tile_resources(nid)
    return out


def _resource_location_answer(question: str, f: dict):
    """Answer 'is there <resource> near <tile>?' from the true map."""
    m = re.search(r"cont_[ab]_(?:gen_[-0-9]+|origin_[-0-9]+)", question)
    if not m:
        return None
    named = m.group(0)
    kinds = re.findall(
        r"wood|stone|clay|fiber|berries|mushroom|roots|fish|shellfish|"
        r"flint|iron|salt|nuts|apples|grain|honeycomb|water", question.lower())
    want = kinds[0] if kinds else None
    here_and_near = _tile_and_neighbors_resources(named)
    if not here_and_near:
        return assert_no_advice(
            "The map shows no surveyed tiles around " + named +
            " - that area has not been explored enough to answer from.")
    if want:
        hits = [(tid, [r for r in res if r.startswith(want[:5])])
                for tid, res in here_and_near.items()]
        hits = [(tid, rs) for tid, rs in hits if rs]
        if hits:
            lines = [f"{tid}: {', '.join(rs)}" for tid, rs in hits[:5]]
            return assert_no_advice(
                "The map shows " + want + " there. " + " ".join(lines) +
                ". These are the map's contents; the fog decides what "
                "you can reach.")
        return assert_no_advice(
            "The map shows no " + want + " on " + named +
            " or the tiles beside it. What the map shows nearby: " +
            "; ".join(f"{tid}: {', '.join(res) or 'nothing'}"
                      for tid, res in list(here_and_near.items())[:5]) + ".")
    return assert_no_advice(
        "The map shows around " + named + ": " +
        "; ".join(f"{tid}: {', '.join(res) or 'nothing'}"
                  for tid, res in list(here_and_near.items())[:6]) + ".")


def draft_answer(question: str, f: dict) -> str | None:
    """A factual answer for one question, or None to escalate.

    Every branch states mechanics and the asker's own world facts.
    No branch assigns a task or orders an action.
    """
    text = str(question or "").lower()

    if re.search(r"is there|where.*(find|gather|wood|stone|clay|resource)|"
                 r"available on|any .*(wood|stone|clay|berries|resource)",
                 text):
        located = _resource_location_answer(question, f)
        if located:
            return located

    if re.search(r"provide|give me|give us|feed me|send me|bring me", text):
        return assert_no_advice(
            "The operator does not hand out anything. Facts: you carry "
            f"{f['food_on_hand']}; objects on your tile hold "
            f"{', '.join(f['tile_food']) if f['tile_food'] else 'nothing edible'}; "
            f"{f['other_name']} is at {f['other_position']} holding "
            f"{f['other_food']}. Food deposited into an object on your "
            f"tile feeds you even while downed.")

    if re.search(r"purpose|impasse|task|goal|should i do|what next|"
                 r"what to do|intended outcome", text):
        sky = ("Night has fallen" if f["night"] else "It is day") + \
              f"; the sky is {f['weather']}; the season is {f['season']}."
        body = (f"Your hunger is {f['hunger']}, warmth {f['warmth']}, "
                f"vitality {f['vitality']}.")
        return assert_no_advice(
            "No task exists and none will be assigned. "
            f"{sky} {body} You are at {f['position']}; "
            f"{f['other_name']} is at {f['other_position']}. "
            f"You carry {f['food_on_hand']}. "
            "The world imposes; what you make of it is yours.")

    if re.search(r"survive|night|vitality|downed|recover|food|eat|"
                 r"hungry|starving|feed", text):
        tile = ("Objects on your tile hold " +
                ", ".join(f["tile_food"]) + "."
                if f["tile_food"] else
                "Nothing edible is stored on your tile.")
        other = (f"{f['other_name']} is at {f['other_position']} "
                 f"holding {f['other_food']}.")
        wet = ("You are soaked; a soaked body cannot warm up until it "
               "dries by a fire." if (f["warmth"] is not None and
                                      f["warmth"] <= 40) else "")
        return assert_no_advice(
            f"Facts: the eat action consumes one unit of a named food "
            f"from your belongings — "
            f"{', '.join(f'{k} satisfies {int(v)}' for k, v in sorted(survival.EAT_SATISFACTION.items()))}. "
            f"Food deposited into any object on your tile feeds you, "
            f"even while downed. You carry {f['food_on_hand']}. {tile} "
            f"{other} {wet} Your hunger is {f['hunger']}, warmth "
            f"{f['warmth']}, vitality {f['vitality']}.")

    if re.search(r"bug|broken|not work|doesn.?t work|failed", text):
        return assert_no_advice(
            f"The terms changed since many earlier measurements "
            f"(now {f['terms']}). Current facts: the eat action "
            f"consumes food from belongings; fires warm within three "
            f"tiles; rain snuffs open fires while roofed fires keep "
            f"burning; objects hold materials via use_object. A "
            f"measurement made under older terms was true then.")

    return None  # unknown -> escalate to the human


def _mark_answered(store: FirstPairPersistenceStore,
                   questions: list[dict], message_id: str) -> None:
    """Mark exactly these questions answered, with provenance.
    Escalated questions stay unheard for the human."""
    if not questions:
        return
    records = load_agent_question_proposals(store)
    matched_ids = {q.get("question_id") for q in questions}
    now_utc = datetime.now(timezone.utc).isoformat()
    for rec in records:
        if rec.get("question_id") in matched_ids:
            rec["status"] = "answered"
            rec["answered_at_utc"] = now_utc
            rec["operator_message_id"] = message_id
            rec["operator_answer"] = "answered by the operator desk"
    save_agent_question_proposals(store, records)


def run_desk(max_per_pair: int = MAX_PER_PAIR,
             dry_run: bool = False) -> dict:
    """Answer unheard questions the desk can answer factually."""
    summary = {"answered": 0, "escalated": 0, "deferred": 0,
               "messages": []}
    for pair_name, store_root in PAIRS.items():
        if not store_root.is_dir():
            continue
        store = FirstPairPersistenceStore(store_root)
        unheard = [q for q in load_agent_question_proposals(store)
                   if q.get("status") == "unheard"]
        if not unheard:
            continue
        # newest first; the freshest ask is the live one
        unheard.sort(key=lambda q: q.get("heartbeat", 0), reverse=True)
        by_agent: dict[str, list[dict]] = {}
        for q in unheard:
            by_agent.setdefault(q.get("agent_ref", "unknown"),
                                []).append(q)

        answered_here = 0
        for agent_ref, questions in by_agent.items():
            if answered_here >= max_per_pair:
                summary["deferred"] += len(questions)
                continue
            parts, matched = [], []
            for q in questions:
                facts = ground_facts(pair_name, store, agent_ref)
                answer = draft_answer(q.get("question"), facts)
                if answer is None:
                    summary["escalated"] += 1  # a real human question
                    continue
                if len(matched) >= max_per_pair:
                    summary["deferred"] += 1  # over this cycle's cap
                    continue
                parts.append(f"You asked: {str(q.get('question'))[:120]} "
                             f"— {answer}")
                matched.append(q)
            if not parts:
                continue
            text = " ".join(parts)
            if not dry_run:
                # resolve_asks=False: the desk marks exactly the
                # questions it answered. say()'s resolve-all would
                # silently swallow the escalated ones too.
                msg = say(pair_name, text, addressed_to=agent_ref,
                          author="the operator (desk)", resolve_asks=False) or {}
                _mark_answered(store, matched, msg.get("message_id", ""))
            summary["messages"].append({"pair": pair_name,
                                        "to": agent_ref, "to_count": len(matched)})
            answered_here += len(matched)
            summary["answered"] += len(matched)
        # questions beyond this cycle's cap stay unheard for next poll
    return summary


def main() -> int:
    summary = run_desk()
    print(json.dumps({"OPERATOR_DESK": "OK", **summary}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
