# Phase 10JL Specification: Fauna, Domestication & Snake Hazard

**Status:** SPECIFICATION ONLY — DOCS-ONLY
**Date:** 2026-10-26
**Phase Chain:** 10JL (spec, L) -> 10JM (metadata sync, L+1) -> 10JN (implementation candidate, L+2, NOT started, NOT authorized)

**Origin:** Operator mandate: add discoverable animal life — cows and milk, tameable horses, dangerous snakes — without turning the world into forced chores or breaking core movement invariants.

## 1. Problem & Opportunity

The current world already has:

- wolves and deer in `backend/world/wildlife.py`
- survival hunger/eat mechanics in `backend/world/survival.py`
- weather, shelter, fire, and wildlife observations in `first_pair_runtime.py`
- micro-ecology precedent in `backend/world/insects.py`

What it does not yet have is a **domesticatable fauna layer**. The agents can hunt wild deer and avoid wolves, but they cannot build a biological relationship with an animal. There is no cow, no milk, no trustworthy horse companion, and no environmental snake threat.

The opportunity is to make animals a discoverable, causal part of life:

- horses can be approached and trusted
- cows can be trusted and milked
- snakes can make some places dangerous without becoming an executioner
- weather can shape animal behavior

## 2. Scope

### 2.1 In scope

Phase 10JN, when authorized, must implement:

1. A new pure fauna module: `backend/world/fauna.py`
2. New persisted fauna state: `world_state.fauna`
3. A sibling runtime tick: `FirstPairRuntime.fauna_tick()`
4. New observation data for fauna IDs and legible state
5. Two new animal interactions:
   - `offer_food`
   - `milk_animal`
6. Snake hazard behavior and snake strike handling
7. New food resource: `milk`
8. Extracted cognition/prompt grounding for fauna and milk
9. Recoverable interaction transaction behavior for feeding and milking

### 2.2 Out of scope

Phase 10JN must not implement:

- Horse riding, faster movement, mounted travel, or load/carry effects
- Animal breeding, herds, genetics, or population growth
- Apple trees, orchards, gardens, farming, or crop mechanics
- New weather-generation models or multi-day climate systems
- New object types for liquid containers
- Viewer icon/model changes beyond data already carried in observation
- Forced animal goals, pathing scripts, or “tutorial” instructions
- Changes to canonical stores unrelated to the authorized fauna feature

Weather affects fauna behavior in this phase, but weather generation itself is deferred to a later phase.

## 3. Design Invariants

Phase 10JN must preserve these invariants:

1. **No forced strategy.** The runtime states observable facts and affordances. It never tells an agent to tame a specific animal, build a specific pen, travel to a destination, or milk at a specific time.

2. **Movement stays one edge per heartbeat.** Fauna movement is not agent movement. A tamed horse is a companion in Phase 1; it grants no speed, reach, or carry effect.

3. **Fail-closed interactions.** Any malformed, out-of-reach, wrong-target, non-diet, cooldown, or unearned interaction rejects before mutation.

4. **No partial inventory mutation.** Feeding and milking must not partially consume inventory or grant duplicate output.

5. **Recoverable animal/inventory transactions.** Feeding and milking change two persisted domains: inventory and fauna/world state. A crash must not leave an unrecoverable half-effect. The implementation must use a durable interaction intent and idempotent recovery.

6. **No ambush.** Snakes and other fauna must not spawn adjacent to an agent or inside immediate protection. Initial dangerous contact must come after observable proximity.

7. **Survivable danger.** A snake bite is meaningful but not an executioner. Existing wolves remain more dangerous than snakes.

8. **Canonical preservation.** Existing wolves, deer, public objects, inventories, ledgers, memories, questions, and west/east stores must be preserved. Fauna state must initialize safely for existing stores.

9. **Determinism.** Spawn and movement must be pure and deterministic for a given pair and heartbeat.

## 4. Module Architecture

### 4.1 `wildlife.py` remains wild

`backend/world/wildlife.py` continues to own:

- wolves
- deer
- deer/wolf strike behavior
- fire/shelter safety rules for wolves

Do not add cow, horse, or snake logic to this module.

### 4.2 New `fauna.py` owns domesticatable and ambient fauna

`backend/world/fauna.py` is new and pure: `(entities, environment, rng) -> entities`.

It owns:

- cow spawning, movement, trust, milk readiness
- horse spawning, movement, trust, fleeing
- snake spawning, movement, dormancy, biting hazard
- snake strike/drop behavior
- accepted animal food values
- animal state validation helpers

Suggested entity shapes:

```json
{
  "id": "cow-1000-0",
  "kind": "cow",
  "tile": [3, 4],
  "hp": 4,
  "trust": 0,
  "tamed": false,
  "milk_ready": false,
  "milk_ready_at_hb": 0,
  "anchor_tile": null
}
```

```json
{
  "id": "horse-1000-0",
  "kind": "horse",
  "tile": [5, 4],
  "hp": 5,
  "trust": 0,
  "tamed": false,
  "anchor_tile": null
}
```

```json
{
  "id": "snake-1000-0",
  "kind": "snake",
  "tile": [2, 2],
  "hp": 2
}
```

The exact wire shape may evolve during planning, but every entity must expose:

- stable `id`
- stable `kind`
- stable `tile`
- current behavioral state required by observation and tests

### 4.3 State storage

`WorldStateRecord` gains:

```python
fauna: list = field(default_factory=list)
```

Existing stores must load as `fauna = []` by default. The implementation must not manually rewrite canonical `world-sim/data` or unrelated runtime files to add fauna.

Fauna state persists through the existing world-state save path used by `first_pair_runtime`.

## 5. Runtime Integration

`FirstPairRuntime.wildlife_tick()` remains the wild tick.

Add a sibling:

```python
def fauna_tick(self, heartbeat_number: int) -> None:
```

and call it in the same heartbeat lifecycle where `wildlife_tick()` is currently called.

Fauna tick responsibilities:

1. Resolve weather/time deterministically from `survival`
2. Advance cow/horse/snake movement
3. Advance cow milk readiness and tamed-anchor behavior
4. Move snakes only while active
5. Apply snake bites to adjacent unsheltered agents outside fire safety
6. Persist through the normal end-of-heartbeat world-state save

### 5.1 RNG separation

Use a distinct deterministic seed from wildlife’s seed, e.g.:

```python
rng = random.Random(
    heartbeat_number * 31 +
    (hash(self._pair_id) % 100000)
)
```

This avoids coupling fauna randomness to wolf/deer randomness.

## 6. Spawn Rules

The first fauna population must stay low.

| Species | Max alive per pair | Spawn window | Initial conditions |
|---|---:|---|---|
| Cow | 1 | Day, non-storm/non-blizzard | At least `FAUNA_MIN_SPAWN_DISTANCE = 4` tiles from both agents and outside fire radius |
| Horse | 1 | Day, non-storm/non-blizzard | Same as cow |
| Snake | 2 | Warm/active conditions | At least `FAUNA_MIN_SPAWN_DISTANCE = 4` tiles from agents, not on sheltered tiles, not inside fire radius |

Rules:

- No cow, horse, or snake spawns adjacent to an agent.
- No fauna spawns on a sheltered tile as its initial location.
- Snakes do not spawn while dormant.
- Existing live entities never re-spawn beyond the max alive count.
- Candidate tiles are bounded around the pair’s current agents, not across the whole planet.
- Exact tile selection is deterministic from the fauna RNG.

## 7. Animal Behavior

### 7.1 Cow

Untamed cow:

- Drifts slowly, at most one tile per few heartbeats.
- Does not flee every time an agent approaches.
- Becomes milk-ready only after taming.

Tamed cow:

- No longer flees.
- Sets `anchor_tile` to the tile where taming completes.
- Remains bounded near `anchor_tile`, within `TAMED_ANCHOR_RADIUS = 3`.
- Grazes in place rather than drifting into wilderness.

Milk readiness:

- After taming, a cow becomes milk-ready every `MILK_READY_HEARTBEATS = 144`.
- Milking sets the cow back to not ready and records `milk_ready_at_hb`.

### 7.2 Horse

Untamed horse:

- Wary.
- If any agent is within `HORSE_FLEE_RADIUS = 2` and `trust == 0`, the horse moves one tile away.
- Does not flee once `trust > 0`.
- Drifts slowly like other fauna.

Tamed horse:

- No longer flees.
- Sets `anchor_tile` to the tile where taming completes.
- Remains bounded near `anchor_tile`, within `TAMED_ANCHOR_RADIUS = 3`.
- Grants no movement, speed, reach, or load effect in Phase 1.

### 7.3 Snake

Snakes are ambient danger, not livestock.

- Move only while snake-active.
- Do not enter shelter tiles.
- Do not approach within `SNAKE_FIRE_SAFETY_RADIUS = 2` of an active fire.
- Bite adjacent unsheltered agents outside fire safety for `SNAKE_BITE_DAMAGE = 5.0` vitality.
- Bite damage uses the existing vitality/collapse rules.
- Striking a snake with no tool requires two strikes.
- Striking a snake with a tool of at least `2.0` damage multiplier kills it in one strike.
- A killed snake drops `1` meat directly into the attacker’s inventory.

### 7.4 Weather effects on fauna

Fauna behavior uses the existing weather system. Phase 10JN must not redesign weather.

- Snakes are active only when weather is not rain/storm/blizzard and effective temperature is at least `SNAKE_ACTIVE_TEMP = 50.0`.
- Snakes are dormant in rain/storm/blizzard, at night, or when cold.
- Cows and horses do not newly spawn in rain/storm/blizzard.
- Existing fauna continue normal behavior unless a weather-specific rule says otherwise.

## 8. Observation & Cognition Grounding

### 8.1 Observation

The runtime must expose fauna alongside wildlife. Do not remove or rename existing wildlife observation fields.

Suggested shape:

```json
{
  "wildlife": {
    "nearby": [
      {"kind": "wolf", "id": "wolf-1000-0", "distance": 3}
    ],
    "howling": false
  },
  "fauna": {
    "nearby": [
      {
        "kind": "cow",
        "id": "cow-1000-0",
        "distance": 1,
        "trust": 40,
        "tamed": false,
        "milk_ready": false
      }
    ]
  }
}
```

`observation["wildlife"]` must preserve the existing exact shape:

```python
{
  "nearby": list[dict],
  "howling": bool
}
```

`observation["fauna"]` is a sibling observation key, not nested inside wildlife:

```python
{
  "nearby": list[dict]
}
```

Fauna must not be inserted into `observation["wildlife"]["nearby"]` in a way that changes existing wildlife semantics.

Rules:

- Entity IDs must be visible.
- Tamed/untamed state must be visible for cow and horse.
- Milk readiness must be visible for cow.
- Snake proximity must be visible without leaking hidden true-map locations.
- Distance uses the existing sight rules; do not reveal unseen animals.

### 8.2 Prompt facts

The cognition prompt must include factual, non-strategic grounding:

- “A cow is nearby; it is untamed.”
- “A cow is nearby; it is tamed and milk is ready.”
- “A horse is nearby; it is wary.”
- “A horse is nearby; it is tamed.”
- “A snake is nearby; it is dangerous.”
- Current accepted animal foods.
- `milk` hunger satisfaction.

The prompt must not tell the agent which animal to choose, where to go, or what goal to adopt.

## 9. Action Contracts

Phase 10JN must register both new actions in the cognition contract so model outputs validate before runtime execution.

Add to `_VALID_ACTIONS`:

```python
"offer_food",
"milk_animal",
```

Add exact schemas to `_ACTION_SCHEMAS`:

```python
"offer_food": frozenset({"action_type", "target_id", "resource_kind", "reason"}),
"milk_animal": frozenset({"action_type", "target_id", "reason"}),
```

These schema entries prevent valid animal interactions from being rejected as `invalid_action_type` while still failing closed if required fields are missing.

### 9.1 `offer_food`

Required fields:

```json
{
  "action_type": "offer_food",
  "target_id": "cow-1000-0",
  "resource_kind": "wild_berries"
}
```

Accepted animal foods:

| Resource | Trust increase |
|---|---:|
| `wild_berries` | 15 |
| `edible_roots` | 18 |
| `wild_apples` | 20 |
| `wild_grain` | 16 |
| `fiber_plants` | 8 |

Trust thresholds:

| Animal | Trust threshold |
|---|---:|
| Cow | 60 |
| Horse | 70 |

Preconditions:

- Target must exist.
- Target must be adjacent.
- Target must be cow or horse.
- Target must not already be tamed.
- `resource_kind` must be in the accepted table.
- Agent must hold at least one unit.
- Bool, float, string-number, zero, negative, or malformed amounts are rejected fail-closed.
- A snake target is rejected with a clear reason; snakes are not tamable in Phase 1.

Effects:

- Consume exactly one unit.
- Increase trust by the table value.
- When trust reaches its threshold:
  - set `tamed = true`
  - set `anchor_tile` to the agent’s current tile
  - clear the transient wary state
- The outcome must include:
  - resolved target ID
  - target kind
  - food consumed
  - trust before/after or current state
  - whether taming completed
  - relevant rejection reason on failure

Example success:

```json
{
  "status": "success",
  "target_id": "horse-1000-0",
  "target_kind": "horse",
  "resource_kind": "wild_apples",
  "trust": 70,
  "tamed": true,
  "detail": "The horse accepts the wild_apples and trusts you now."
}
```

### 9.1.1 Animal/inventory transaction requirement

`offer_food` changes both inventory and fauna state. Preflight validation alone is not enough.

Phase 10JN must implement a recoverable animal interaction transaction:

1. Before mutation, append a durable interaction intent with a unique `event_id`, target ID, agent, food kind, and intended trust delta.
2. Apply the inventory delta through the validated inventory batch writer.
3. Apply the fauna trust/taming change to world state.
4. On recovery, replay only incomplete interactions idempotently using `event_id`.
5. If recovery cannot determine whether inventory was consumed, the interaction fails closed and does not silently duplicate food or trust.

The existing `modify_inventory_batch` mechanism is necessary but not sufficient, because it only makes the inventory file mutation atomic, not the cross-file animal-state transaction.

### 9.2 `milk_animal`

Required fields:

```json
{
  "action_type": "milk_animal",
  "target_id": "cow-1000-0"
}
```

Preconditions:

- Target must exist.
- Target must be adjacent.
- Target must be cow.
- Cow must be tamed.
- Cow must have `milk_ready = true`.

Effects:

- Add exactly one `milk`.
- Set `milk_ready = false`.
- Set `milk_ready_at_hb = current heartbeat`.
- Report success with target ID, milk produced, and readiness state.

Phase 1 milk is container-free: no pot, bucket, or clay pot is required.

`milk` is edible and must be added to `survival.EAT_SATISFACTION`. Suggested Phase 1 value:

```python
"milk": 28.0
```

Milk must also appear in prompt food grounding with its satisfaction value.

### 9.3 Snake strike

Extend existing attack handling so:

- Wolf/deer attacks continue exactly as before.
- Snakes can be struck when adjacent.
- Cow/horse are not attackable in Phase 1. Attempting to attack them must reject with a fact-based reason, e.g. “This animal is not hostile.”
- Snake strike outcome reports:
  - target ID
  - damage
  - killed
  - meat dropped
  - whether the snake remains

## 10. Migration & Compatibility

Existing live stores may have `world_state.json` without a `fauna` field. Phase 10JN must:

- Load old records as `fauna = []`.
- Not reinterpret existing wildlife, inventories, or known maps.
- Initialize new fauna only through the runtime tick.
- Preserve existing wolves/deer behavior.
- Preserve viewer payload compatibility by placing fauna in its own top-level observation field.

No manual canonical mutation is authorized by this spec.

## 11. Testing Requirements

Phase 10JN must start with failing tests and keep the following green before live use.

### 11.1 Pure fauna tests

- Cow spawn respects max count, distance, day/weather rules, and determinism.
- Horse spawn respects max count, distance, day/weather rules, and determinism.
- Snake spawn respects max count, distance, shelter/fire rules, and dormancy.
- Snake movement avoids shelters and fire radius.
- Snake bite only occurs while active, adjacent, unsheltered, and outside fire safety.
- Snake bite applies exactly one 5.0 vitality loss.
- Cow milk readiness advances on the specified interval only after taming.
- Horse flee behavior changes when trust changes.
- Tamed cow/horse remain within anchor radius.

### 11.2 Runtime interaction tests

- Observation exposes animal ID, kind, distance, trust, tamed, and milk readiness.
- `offer_food` succeeds with each accepted food.
- `offer_food` rejects non-diet food before inventory mutation.
- `offer_food` rejects non-adjacent targets.
- `offer_food` rejects snakes.
- `offer_food` rejects already tamed animals.
- Taming threshold produces exactly one tamed state transition.
- `milk_animal` succeeds only for ready tamed cows.
- Milk cooldown prevents immediate re-milking.
- Snake strike and drop outcomes are correct.
- Existing wolves, deer, bees, crafting, smelting, survival, and runtime regression suites remain green.

### 11.3 Transaction/recovery tests

- `offer_food` intent + inventory + fauna update produces exactly one trust increase.
- Recovery after a simulated crash between intent and inventory mutation does not duplicate or lose food/trust.
- Recovery after a simulated crash between inventory and world-state mutation recovers deterministically or fails closed without duplication.
- `milk_animal` cannot duplicate milk after recovery.

## 12. Suggested Phase 10JN Constants

Final values may be adjusted during implementation planning, but Phase 1 should start with:

```python
FAUNA_MIN_SPAWN_DISTANCE = 4
COW_MAX_ALIVE = 1
HORSE_MAX_ALIVE = 1
SNAKE_MAX_ALIVE = 2

COW_TRUST_THRESHOLD = 60
HORSE_TRUST_THRESHOLD = 70
HORSE_FLEE_RADIUS = 2
TAMED_ANCHOR_RADIUS = 3

MILK_READY_HEARTBEATS = 144

SNAKE_BITE_DAMAGE = 5.0
SNAKE_HP = 2
SNAKE_FIRE_SAFETY_RADIUS = 2
SNAKE_ACTIVE_TEMP = 50.0
```

## 13. Boundaries For This Spec Phase

This document is specification and implementation planning only. Phase 10JN is not started and not authorized.

No implementation, code edit, test edit, live heartbeat, daemon, scheduler, network provider, Docker, VPS, or canonical store change is authorized by this spec.
