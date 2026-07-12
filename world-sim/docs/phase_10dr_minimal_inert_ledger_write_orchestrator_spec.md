# Phase 10DR - Minimal Inert Ledger Write Orchestrator

10DR implements the single candidate named by 10DP. It is a pure,
in-process, caller-driven orchestrator over already-built inert artifacts:

```
already-built 10BT decision
  -> 10CJ public dry-run adapter
  -> 10DL public integration seam (including 10CV validation)
  -> 10CP public inert ledger writer
```

10DR does not build world state or equality contracts. Gate-7 remains
closed.

## Baseline and model

- Baseline: `d7494ec Phase 10DQ: sync 10DP metadata`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD: the 10DR test module failed collection before the module existed,
  then passed after the minimal implementation.

## Public API

```python
run_minimal_inert_ledger_write_orchestration(
    consumer_decision,
    *,
    ledger_path=None,
    authorized_ledger_path=None,
    recorded_at_utc=None,
)

export_minimal_inert_ledger_write_result(result)
```

The input must be an already-built `10BT.1`
`shared_public_contract_consumer_decision`. 10DR does not call 10BT or
any equality-contract creator.

## Validation order

10DR fails closed before calling 10CP unless every boundary succeeds:

1. The 10BT envelope has the expected schema/type/scope, non-empty
   decision ID, a present known inert signal, and all source gate flags
   False.
2. No forbidden movement/map/route/event/NPC/social/timing/output field
   is present.
3. 10CJ returns the exact established 10CJ shape with matching source
   decision ID and signal provenance, `planned_action == "log_only"`,
   `executed == False`, and all five gate flags False.
4. 10DL returns that same exact 10CJ shape and preserves the 10CJ adapter
   ID, 10BT decision ID, and recognized signal type. Because 10DL
   delegates to 10CV, a successful 10DL result also proves 10CV's
   gate-7-free validation succeeded.
5. Both `ledger_path` and `authorized_ledger_path` were explicitly
   supplied by the caller.
6. 10CP accepts the result and path pair.

Malformed dependency outputs, malformed error envelopes, provenance
substitution, any gate-True value, path rejection, missing parent, or
10CP rejection produce `ok == False` without any 10DR direct write.

## Path and write boundary

10DR has no default ledger path and contains no production path literal.
The caller supplies both the candidate path and the independently selected
authorized path. 10CP remains responsible for resolving and comparing
them exactly and is the only code that opens a file.

The only permitted production authority remains the 10CN allowlist path:

```
world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson
```

Tests use one existing `tmp_path` parent as both the candidate and
authorized path. 10DR never creates a parent, scans a directory, reads a
ledger, selects a default, or wraps/reimplements the 10CP writer.

## Output envelope

10DR returns exactly these safe status fields:

- `ok`
- `orchestrator_schema_version = "10DR.1"`
- `orchestrator_type = "minimal_inert_ledger_write_orchestrator_result"`
- `orchestrator_scope = "inert_ledger_write_only"`
- `orchestrator_decision_id`
- `source_consumer_decision_id`
- `source_adapter_decision_id`
- `recognized_signal_type`
- `planned_action`
- `ledger_write_requested`
- `ledger_write_attempted`
- `ledger_record_written`
- `ledger_path_authorized`
- `ledger_record_hash`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The orchestrator decision ID hashes only safe status/provenance fields; it
does not contain a ledger path. A writer-confirmed append remains reported
as written even if the writer also returns an error, preventing unsafe
duplicate-retry assumptions while keeping `ok == False`.

## Forbidden behavior

10DR does not:

- read or emit the equality signal value;
- call 10BT or any equality-contract creator;
- import 10CV directly (10DL owns that validation seam);
- perform direct file I/O;
- create directories or choose a default path;
- scan or read `world-sim/data` or any ledger;
- overwrite, truncate, delete, rename, or rewrite files;
- start runtime, daemon, scheduler, network, provider, launcher,
  container, or Docker behavior;
- create movement, map lookup, route execution, event emission, NPC,
  co-presence, awareness, relationship, interaction, timing, or
  coordination behavior.

10CP remains the only writer. Gate-7 is closed by absence.

## Tests and checks

- Initial TDD RED: `ModuleNotFoundError` for the not-yet-created 10DR
  module.
- Boundary-review RED: 15 focused failures proved missing optional-gate,
  provenance, malformed-envelope, Unicode, and post-write status checks.
- 10DR targeted suite from repo root: 72 passed.
- 10BT + 10CJ + 10CP + 10CV + 10DL + 10DR bounded regression from
  `world-sim`: 220 passed.
- Valid inert paths append exactly one NDJSON line through 10CP.
- Default/missing/unauthorized/missing-parent paths do not write.
- Source and dependency gate/provenance violations fail before 10CP.
- The production module has no direct file/scanning APIs and imports only
  the public 10CJ, 10DL, and 10CP functions.
- Deterministic JSON export is verified.
- CI pure-test list includes the 10DR test module.

Full pytest is intentionally not run because legacy canonical/world
mutation tests are outside the authorized bounded test set.

## Scope boundary

10DR implements only the 10DP-authorized inert write orchestrator. The
append-only 10CP audit write is not runtime execution and does not open
gate-7. Runtime, daemon, scheduler, network, provider, launcher,
container, Docker, world-state, and broad wiring remain unauthorized.
