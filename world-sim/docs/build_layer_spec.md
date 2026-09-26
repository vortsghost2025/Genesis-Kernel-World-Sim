# Build Layer Spec — Persistent Belongings and Agent-Defined Construction

## Motivation

Four agents have gathered ~1,000 resources across 600 heartbeats and own
nothing. Gathered amounts live only in runtime memory
(`first_pair_runtime.py::_execute_gather`), so every restart wipes every
hoard — West Eve has "gathered" 574 times and never possessed anything that
survived the night. Meanwhile `create_public_object` makes symbolic things
(the meeting stone) with no material cost. The agents can neither accumulate
nor spend. A world cannot be built in anyone's image out of evaporating
goods.

This layer gives them two possibilities — verbs, never directions:
persistent belongings, and agent-defined construction.

## Design

### 1. Persistent inventory (`inventory.json`)

Per-store file, envelope type `inventory_record`, schema `inventory.1`:

```json
{"type": "inventory_record", "schema_version": "inventory.1",
 "data": {"east_adam": {"stone": 4}, "east_eve": {}}}
```

- `load_inventory(store) -> dict`: missing file = empty holdings (fresh
  stores behave exactly as before).
- `add_to_inventory(store, agent_ref, kind, delta) -> dict`: applies a
  signed delta, fail-closed (unknown/empty kind, non-integer delta, or a
  result below zero raises `ValueError`; nothing is written on failure).
  Atomic write via the store's existing `_atomic_write`.
- `_execute_gather` persists through this instead of the in-memory dict.
  The in-memory `_inventory` attribute is removed — one source of truth.
- Owner-bound by construction: the file is keyed by agent ref and only
  ever mutated for the acting agent.

Known limitation (out of scope): tile-side depletion is still per-heartbeat
(`_load_tile_resources` rebuilds from the read-only true map each tick), so
tiles effectively restock across heartbeats. Inventory persistence makes
*belongings* real; tile finiteness remains future work and is stated
truthfully in the gather prompt line.

### 2. Build action

`build` — the eleventh action. The agent declares WHAT to make and WHAT it
is made of; the runtime enforces cost and records existence. Meaning is the
agent's; physics is the runtime's.

Exact schema:
`{action_type, object_id, object_type, description, tile_id, materials}`
where `materials` is a non-empty dict of `{resource_kind: positive int}`.

Validation (all fail-closed, `rejected` with reason):
- Same placement rules as `create_public_object`: safe object id, unique
  object id, tile must be the agent's current tile and in allowed tiles,
  description survives `sanitize_public_text`.
- `materials`: must be a dict, non-empty, keys non-empty strings, values
  positive integers (bools rejected), at most 8 entries, total units ≤ 64
  (bounds against absurd single-tick spending).
- Affordability: every material kind must be held in at least the stated
  amount. Insufficient holdings reject the whole build — no partial builds,
  no debt.

Execution (atomic in effect: deduct-then-create, both persisted before
return; world_state save happens in the existing end-of-tick path):
- Deduct materials from the persisted inventory.
- Create a `PublicObjectRecord` with an additive `materials` field
  (default `{}` — old records load unchanged) plus `creator_agent_id`,
  tile, type, sanitized description, heartbeat.
- Outcome: `{status: success, object_id, materials_spent, remaining}`.
- Counts as a world mutation (joins the existing mutation action list).

### 3. Context injection

`AgentContext` gains `inventory: dict` (default empty). The prompt shows a
`YOUR BELONGINGS` section listing holdings (`stone x4` or `empty hands`),
placed with the runtime context block. The `build` line in the action list
states the cost rule truthfully: you can only spend what you hold.

### 4. Public show payload

Exporter adds `inventories` per pair snapshot (holdings only — no
mechanism words). Built objects already ship via `public_objects`, now
carrying their `materials`.

## Non-goals

- No recipes, no tech tree, no runtime-suggested builds. The runtime never
  proposes what to make.
- No trading/gifting between agents (a future verb if they ask for it).
- No tile depletion persistence (stated limitation above).
- No destruction verb. What is built stands until a future phase says
  otherwise.
