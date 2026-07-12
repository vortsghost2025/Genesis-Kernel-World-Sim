# Phase 10DL - Minimal Authorized Runtime Adapter Integration Harness

10DL implements the single candidate authorized by 10DJ as a minimal,
in-process, caller-driven harness. It consumes one already-built 10CJ
dry-run decision, delegates inert validation to 10CV, and emits the
exact 10CJ decision shape expected by existing bounded consumers.

10DL has no side effects. Gate-7 remains closed.

## 1. Input boundary

`run_minimal_runtime_adapter_integration(...)` consumes an already-built
10CJ decision only. 10CV validates its schema, type, scope, planned
action, gate flags, signal presence, and recognized inert signal type.
10DL additionally requires:

- a non-empty 10CJ `adapter_decision_id`;
- a non-empty `source_decision_id`;
- `source_consumer_scope == "record_public_equality_signal_only"`.

10DL never reads or emits `equality_signal_value`. It does not import or
call 10BT, 10CP, or any equality contract creator.

## 2. Exact 10CJ-shaped output

10DL returns exactly the established 10CJ field set:

- `ok`;
- `adapter_schema_version`, `adapter_type`, `adapter_scope`;
- `adapter_decision_id`, source identifiers, and source scope;
- `source_signal_seen`, `recognized_signal_type`, `planned_action`;
- `executed` and all five inert gate flags;
- `claim_boundary` and `errors`.

It adds no integration, candidate-action, writer-status, path, or hash
fields. A valid source `adapter_decision_id` is preserved. Invalid input
without an ID receives a deterministic `10DL-` fallback ID for audit
correlation only.

On every path:

- `executed == False`;
- `runtime_allowed == False`;
- `daemon_allowed == False`;
- `scheduler_allowed == False`;
- `network_allowed == False`;
- `world_sim_data_accessed == False`;
- `planned_action` is only `none` or `log_only`.

## 3. Existing 10CP compatibility boundary

10DL does not import or invoke 10CP. A valid 10DL result remains an exact
10CJ-shaped decision and can therefore be supplied separately to the
existing 10CP writer by an explicitly authorized caller. 10CP retains
its exact-path check, existing-parent requirement, append-only open mode,
input denylist, and fail-closed validation.

This keeps the only previously authorized inert ledger path available
without adding any file or path behavior to 10DL itself.

## 4. Fail-closed behavior

10DL returns `ok == False`, `planned_action == "none"`, and performs no
side effect when:

- the 10CJ/10CV decision is invalid or gate-True;
- required 10CJ identity fields are absent or invalid;
- the signal is unseen or not one of the six known inert signal types.

## 5. Forbidden surfaces

10DL has no file APIs and imports only the existing 10CV surface plus
standard-library hashing/JSON types. It has no daemon, scheduler,
network, provider, launcher, container, Docker, movement, map, route,
event, NPC, world-runtime, writer, or equality-value behavior. No broad
runtime wiring or data expansion is introduced.

The output never contains agent, tile, route, path, destination, timing,
movement, map, event, NPC, co-presence, awareness, relationship,
interaction, daemon, scheduler, network, candidate-action, writer-status,
or equality-value fields.

## 6. Verification

- TDD RED: the original 10DL test module initially failed collection
  because the harness module did not exist.
- Identity RED: three incomplete-identity cases initially failed because
  10CV alone accepted them; 10DL now rejects them.
- Boundary review RED: the first implementation used a broader 10DL
  envelope and optional writer orchestration; exact-shape tests failed
  until the module was narrowed to the approved 10CJ contract.
- 10DL targeted suite from repo root: 16 passed.
- 10CJ + 10CP + 10CV + 10DL regression from `world-sim`: 99 passed.
- CI pure-test list includes the 10DL test module.
- A real 10CJ-generated artifact composes without field-set or identifier
  drift.

The combined root-level regression command still exposes two pre-existing
10CJ source-inspection tests that open `backend/...` relative to shell
cwd. They pass from the established `world-sim` test root and were not
changed because they are outside 10DL scope.

## 7. Files

- `world-sim/backend/world/local_minimal_runtime_adapter_integration_harness.py`
- `world-sim/tests/test_phase10dl_minimal_runtime_adapter_integration_harness.py`
- `world-sim/docs/phase_10dl_minimal_authorized_runtime_adapter_integration_harness_spec.md`
- `.github/workflows/pure-tests.yml` (explicit test path only)
- `README.md`
- `world-sim/docs/phase_index.md`

## 8. Conclusion

10DL implements only the minimal 10DJ-authorized integration seam. It is
in-process, caller-driven, exact-10CJ-shaped, and side-effect-free. The
existing 10CP path remains separately available to explicitly authorized
callers; 10DL itself performs no write. Gate-7 remains closed, and
runtime/daemon/scheduler/network remain unauthorized.
