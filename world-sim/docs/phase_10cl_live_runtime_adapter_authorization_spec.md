# Phase 10CL - Live Runtime Adapter Authorization Spec

Docs-only / approval-gate phase. 10CL decides exactly what a future
live (write-path) adapter may touch, **before** any runtime code is
written. It authorizes nothing by itself; it defines the contract a
later approved phase (10CM+) would implement.

10CL is the 10CH gate-1 "separate runtime adapter spec" made
explicit and the gate-10 "operator approval" checkpoint made durable.
It is not an implementation phase. It adds no module, no test, no CI
entry, no runtime hook, no daemon/periodic-job job, no world-sim/data
access, and no movement/map-lookup/route logic.

---

## Authority boundary

- 10CL **does not** authorize runtime wiring.
- 10CL **does not** create a live adapter.
- 10CL **does not** modify 10CJ (the existing dry-run seam).
- 10CL **does** publish the allowlist, denylist, and gating
  conditions a future live adapter must satisfy.
- A future live adapter (10CM or later) requires:
  - this spec approved by the operator,
  - the 10CH gates 6 and 7 separately satisfied by a dedicated
    phase (world-sim/data access and background-service/periodic-job/
    network action each need their own reviewed authorization),
  - a distinct implementation + test phase,
  - operator approval before commit.

---

## What a future live adapter MAY read

A future live adapter must consume **10CJ dry-run adapter decisions**,
not raw 10BT consumer decisions. It may read only the 10CJ output
fields:

- `ok`
- `adapter_schema_version`
- `adapter_type`
- `adapter_scope`
- `adapter_decision_id`
- `source_decision_id`
- `source_consumer_scope`
- `source_signal_seen`
- `recognized_signal_type`
- `planned_action`
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `world_sim_data_accessed`

It must:

- **not** read 10BT directly;
- **not** read `equality_signal_value`;
- **not** read `equality_signal_type` directly from 10BT;
- use `recognized_signal_type` from 10CJ only;
- only consider records where `planned_action == "log_only"`;
- reject or ignore anything where `executed` is not False;
- reject or ignore anything where any gate flag is not False.

The signal value stays an opaque public identifier — never a command,
never a presence claim. A live adapter sees only what 10CJ chooses
to expose.

---

## What a future live adapter MAY do (the only permitted write)

The single authorized write path is an **append-only, verified log
entry** derived from a recognized 10CJ dry-run decision:

- consume a 10CJ decision where `planned_action == "log_only"`;
- append one verified record to a caller-supplied, explicitly
  authorized ledger location;
- the record carries only the inert adapter fields
  (`adapter_decision_id`, `source_decision_id`,
  `recognized_signal_type`, `adapter_schema_version`, `adapter_type`,
  `adapter_scope`);
- the record carries **no** equality value, no route, no tile,
  no destination, no timing, no co-presence, no awareness, no
  relationship.

That is the complete authorized surface. Everything else is forbidden.

---

## What a future live adapter MUST NOT do (denylist)

- movement execution;
- map lookup / reconstruction;
- route planning or route execution;
- scheduling;
- daemon / background-service action;
- network action;
- event creation / emission beyond the authorized log entry;
- NPC awareness, relationship, interaction, co-presence, proximity,
  timing, or coordination;
- any `world-sim/data` access not explicitly authorized by a
  dedicated, separately-reviewed phase;
- promote `equality_signal_value` into any runtime state.

The `claim_boundary` from 10BT/10CJ ("no co-presence, no
awareness, no relationship, no timing inference") remains binding on
any live adapter.

---

## Required gating before any live adapter phase (10CH mapping)

| 10CH gate | Status after 10CL |
|---|---|
| 1. separate runtime adapter spec | **satisfied** (this spec) |
| 2. read-only dry-run adapter first | **satisfied** (10CJ) |
| 3. explicit allowlist of readable fields | **satisfied** (above) |
| 4. explicit denylist of forbidden surfaces | **satisfied** (above) |
| 5. no direct use of `equality_signal_value` | **satisfied** (10CJ + above) |
| 6. no `world-sim/data` read/write until authorized | **NOT yet** — needs dedicated phase |
| 7. no daemon/scheduler/network until authorized | **NOT yet** — needs dedicated phase |
| 8. tests proving 10BT flags stay False | **satisfied** (existing) |
| 9. tests proving adapter is dry-run/read-only first | **satisfied** (10CJ) |
| 10. operator approval before any non-doc phase | **pending** — 10CL is the approval artifact; a later implementation phase still needs its own go |

Gates 6 and 7 remain explicitly out of scope for 10CL and for any
dry-run work. They are hard prerequisites for 10CM+.

---

## Files

- New spec only: `world-sim/docs/phase_10cl_live_runtime_adapter_authorization_spec.md`
- No module, no test, no `pure-tests.yml` change, no README/phase_index
  change required by 10CL itself (index/sync handled in a later
  metadata phase once approved).

## Conclusion

10CL is the authorization contract for a future live adapter. It
narrows the readable surface, defines the single permitted write (an
inert verified log entry), and enumerates the denylist. It does
**not** implement runtime; it only makes the boundary explicit and
approvable. Live wiring remains blocked until gates 6 and 7 are
satisfied by their own dedicated phases and the operator approves the
implementation phase.
