# Phase 10CV - Minimal Gate-7-Free Dry-Run Adapter Implementation

10CV implements the 10CT gate-7-free dry-run adapter contract as a
pure, in-process, caller-driven transform. It consumes one already-built
10CJ dry-run adapter decision and emits one deterministic inert decision
object in memory.

10CV has no side effects. Gate-7 remains closed.

---

## 1. Input boundary

10CV consumes already-built 10CJ decisions only. It validates the 10CJ
schema, type, scope, planned action, execution state, gate flags, signal
presence, and recognized inert signal type.

10CV:

- does not read raw 10BT decisions;
- does not import or call 10BT;
- does not read `equality_signal_value`;
- does not read `equality_signal_type` from 10BT;
- does not read source contract values;
- does not read agent, tile, route, path, destination, timing,
  co-presence, awareness, relationship, interaction, movement, map,
  event, or NPC fields.

---

## 2. Required accepted input

An input is accepted only when:

- it is a dict;
- `ok == True`;
- `adapter_schema_version == "10CJ.1"`;
- `adapter_type == "runtime_adapter_dry_run_decision"`;
- `adapter_scope == "dry_run_only"`;
- `planned_action == "log_only"`;
- `executed == False`;
- `runtime_allowed == False`;
- `daemon_allowed == False`;
- `scheduler_allowed == False`;
- `network_allowed == False`;
- `world_sim_data_accessed == False`;
- `source_signal_seen == True`;
- `recognized_signal_type` is one of the six known inert signal types.

The six known inert signal types are:

- `snapshot_id_equality`;
- `snapshot_hash_equality`;
- `current_tile_id_equality`;
- `route_intent_id_equality`;
- `known_tile_ids_set_equality`;
- `route_destination_tile_id_equality`.

Malformed, gate-True, non-log-only, unseen, or unknown-signal input fails
closed with `candidate_action == "none"`.

---

## 3. Output boundary

The output is a deterministic `10CV.1`
`gate7_free_dry_run_adapter_decision` with scope
`gate7_free_dry_run_only`.

For accepted input:

- `planned_action == "log_only"`;
- `candidate_action == "eligible_for_inert_ledger_log"`.

For rejected input:

- `planned_action == "none"`;
- `candidate_action == "none"`;
- `errors` explains the rejected fields.

On every path:

- `executed == False`;
- `runtime_allowed == False`;
- `daemon_allowed == False`;
- `scheduler_allowed == False`;
- `network_allowed == False`;
- `world_sim_data_accessed == False`;
- `gate7_activity_allowed == False`;
- `ledger_write_attempted == False`.

The decision ID is deterministic: `10CV-` plus the first 32 hexadecimal
characters of a SHA-256 hash over canonical inert decision material.
Export uses stable, sorted JSON.

---

## 4. No-side-effect guarantee

10CV:

- does not call 10CP;
- does not import the 10CP writer;
- does not write a ledger;
- does not create, read, or write production ledger files;
- does not touch `world-sim/data`;
- does not open files or scan directories;
- starts no daemon or background service;
- creates no scheduler, periodic job, or tick driver;
- opens no network connection;
- calls no provider, model, launcher, Docker, or container surface;
- performs no movement, map lookup, route execution, event emission,
  NPC behavior, co-presence, awareness, relationship, interaction,
  timing, or coordination.

`eligible_for_inert_ledger_log` is only an inert candidate label. It is
not a ledger write and does not call the separately implemented 10CP
writer.

---

## 5. Tests

The 10CV tests prove:

- strict accepted-input validation and fail-closed behavior;
- all six known inert signal types produce only the inert candidate
  label;
- unknown and unseen signals produce no candidate action;
- the output has the exact inert envelope and no forbidden value fields;
- all execution, gate-7, world-data, and ledger-attempt flags stay False;
- deterministic JSON export and deterministic decision IDs;
- AST-level import and call discipline;
- no file, scanning, 10BT, or 10CP calls.

Verification:

- 10CV targeted tests: 29 passed;
- 10CJ + 10CP + 10CV combined tests: 83 passed.

---

## 6. Conclusion

10CV implements only the 10CT gate-7-free dry-run adapter contract. It
emits an inert in-memory decision and performs no action. Gate-7 remains
closed: no daemon, scheduler, network, provider, launcher, Docker, or
container behavior is authorized or implemented.

## Files

- `world-sim/backend/world/local_gate7_free_dry_run_adapter.py`
- `world-sim/tests/test_phase10cv_gate7_free_dry_run_adapter.py`
- `world-sim/docs/phase_10cv_gate7_free_dry_run_adapter_spec.md`
- `README.md`
- `world-sim/docs/phase_index.md`
- `.github/workflows/pure-tests.yml` (explicit test path only)
