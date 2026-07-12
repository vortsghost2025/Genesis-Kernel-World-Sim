# Phase 10CJ - Pure Dry-Run Consumer Adapter Harness

First pure dry-run adapter seam after the 10CH runtime-readiness boundary
audit. 10CJ is the sibling module to 10BT: 10BT is a pure consumer;
10CJ is a pure adapter that consumes already-built 10BT consumer
*decision* objects and emits an inert dry-run adapter *decision* object.

This phase performs **no runtime wiring**. It does not add runtime hooks,
daemon or periodic-job jobs, event emitters, movement logic, map lookup,
route planning or execution, NPC behavior, awareness, relationship,
interaction, co-presence, proximity, timing, or coordination logic. It
does not read or write `world-sim/data`. It does not authorize any live
runtime connection.

---

## What 10CJ is

A new module, `local_runtime_adapter_dry_run_harness.py`, that:

- uses only stdlib imports;
- does not import world-sim runtime modules;
- does not import background-service / periodic-job / network / provider /
  launcher / container runtime modules;
- does not import or read `world-sim/data`;
- does not import any equality contract creator;
- does not call the 10BT consumer creator;
- accepts an already-built 10BT decision dict as input;
- emits a deterministic dry-run adapter decision object;
- never executes anything.

---

## Allowlisted readable input fields (only these five)

- `ok`
- `decision_id`
- `consumer_scope`
- `equality_signal_type`
- `equality_signal_present`

The adapter **never reads `equality_signal_value`**. It does not read,
copy, transform, log, or expose the signal value. The signal value is an
opaque public identifier; 10CJ treats it as absent.

### Forbidden readable input fields

`equality_signal_value`, `source_merge_hash`, `source_contract_id`,
`source_contract_type`, `source_claim_scope`,
`source_contract_schema_version`, any agent field, any tile field except as
an opaque signal-type string, any route / path / destination value, any
timing field, and anything not explicitly allowlisted.

---

## Behavior

- Input is not a dict -> `ok` False, `errors` non-empty,
  `planned_action` `"none"`, `executed` False.
- Input `ok` is not True -> `ok` False, `errors` non-empty,
  `planned_action` `"none"`, `executed` False.
- `consumer_scope` is not `"record_public_equality_signal_only"` ->
  `ok` False, `errors` non-empty, `planned_action` `"none"`,
  `executed` False.
- `equality_signal_present` is not True -> `ok` True,
  `source_signal_seen` False, `planned_action` `"none"`,
  `executed` False.
- `equality_signal_present` is True and `equality_signal_type` is one of
  the six known consumer signals -> `ok` True, `source_signal_seen`
  True, `recognized_signal_type` set to the signal type,
  `planned_action` `"log_only"`, `executed` False.
- Unknown signal type (present but not in the six known signals) -> `ok`
  True, `recognized_signal_type` None, `planned_action` `"none"`,
  `executed` False.

### Known signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

---

## Output envelope

A deterministic dict with a fixed schema:

- `ok`
- `adapter_schema_version` = `"10CJ.1"`
- `adapter_type` = `"runtime_adapter_dry_run_decision"`
- `adapter_scope` = `"dry_run_only"`
- `adapter_decision_id`
- `source_decision_id`
- `source_consumer_scope`
- `source_signal_seen`
- `recognized_signal_type`
- `planned_action`
- `executed` = False
- `runtime_allowed` = False
- `daemon_allowed` = False
- `scheduler_allowed` = False
- `network_allowed` = False
- `world_sim_data_accessed` = False
- `claim_boundary`
- `errors`

`planned_action` can only be `"none"` or `"log_only"`. The `"log_only"`
action is an in-memory record intent only and is never performed. The
following `planned_action` values are forbidden and never produced:
`"move"`, `"route"`, `"schedule"`, `"emit_event"`, `"write"`,
`"daemon"`, `"network"`, `"map_lookup"`, `"npc_behavior"`,
`"relationship"`, `"awareness"`, `"co_presence"`, `"timing"`.

`executed` is hard-coded False. The five gate flags
(`runtime_allowed`, `daemon_allowed`, `scheduler_allowed`,
`network_allowed`, `world_sim_data_accessed`) are hard-coded False with no
code path that can flip them to True.

---

## Relationship to the 10CH gates

10CJ satisfies 10CH gates 1-5 and 8-9:

1. A separate runtime adapter module exists (10CJ), distinct from 10BT.
2. The first adapter implementation is dry-run / no-write by construction.
3. An explicit allowlist of readable decision fields is published.
4. An explicit denylist of forbidden inference surfaces is enforced.
5. `equality_signal_value` is never read or used for movement /
   co-presence.
8. The 10BT runtime flags remain False on every path (existing tests
   keep passing).
9. Tests prove 10CJ is dry-run / read-only first, with a failing test
   if a write path were introduced (the forbidden `planned_action`
   values can never be produced).

Gates 6, 7, and 10 remain explicitly out of scope:

- No `world-sim/data` reads or writes are performed (gate 6).
- No background-service / periodic-job / network action is performed
  (gate 7).
- This phase does not authorize runtime wiring; a future live adapter
  requires a separate phase and operator approval (gate 10).

---

## Files

- New module: `world-sim/backend/world/local_runtime_adapter_dry_run_harness.py`
- New tests: `world-sim/tests/test_phase10cj_runtime_adapter_dry_run_harness.py`
- CI: `world-sim/tests/test_phase10cj_runtime_adapter_dry_run_harness.py`
  added to `pure-tests.yml`.

## Tests

- Non-dict input -> `ok` False, `planned_action` `"none"`,
  `executed` False.
- Non-ok 10BT decision -> `ok` False, `planned_action` `"none"`,
  `executed` False.
- Wrong `consumer_scope` -> `ok` False, `planned_action` `"none"`,
  `executed` False.
- `equality_signal_present` False -> `ok` True,
  `planned_action` `"none"`, `executed` False.
- Each of the six known signal types with `equality_signal_present` True ->
  `planned_action` `"log_only"`, `executed` False.
- Unknown signal type -> `planned_action` `"none"`, `executed` False.
- Output envelope is deterministic and stable.
- All runtime gate flags are always False.
- No output includes `equality_signal_value`.
- No output includes route / path / destination / tile value keys,
  co-presence, awareness, relationship, timing, movement, map lookup,
  event emission, background-service, periodic-job, network, or NPC
  behavior keys.
- Module source discipline: an AST-based test forbids imports of
  `socket`, `requests`, `urllib`, `http`, `subprocess`, `os`; forbids
  calls named `emit_event`, `create_event`, `map_lookup`; forbids
  `open(...)` filesystem access and any `world-sim/data` path. The test
  allows the mandated inert output flag names `daemon_allowed` and
  `scheduler_allowed` because those are hard-coded False outputs, not
  background-service or periodic-job behavior. The discipline test
  forbids behavior / imports / APIs — not the required inert flag names.
- Module source does not read `equality_signal_value` from the input
  decision (AST check on the `create_runtime_adapter_dry_run_decision`
  parameter for `decision.get("equality_signal_value")` or
  `decision["equality_signal_value"]`). The docstring may mention the
  field name without failing the test.
- Existing 10BT consumer tests still pass, proving the consumer is
  unchanged and its runtime flags stay False.

## Source discipline note

The source discipline tests allow the required inert field names
`daemon_allowed` and `scheduler_allowed` because those fields are
mandated hard-coded False outputs. The tests forbid behavior, imports,
and APIs — not the required inert flag names.

## Conclusion

The adapter seam now exists as a provably inert dry-run layer. 10CJ
confirms the consumer->adapter boundary can be crossed without touching
runtime. It does **not** authorize runtime wiring.
