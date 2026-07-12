# Phase 10CT - Gate-7 Minimal Dry-Run Adapter Spec

Docs-only spec for a future **gate-7-free, minimal dry-run
adapter** that consumes 10CJ dry-run decisions and emits an inert
adapter decision **without** requiring 10CH gate #7 (daemon /
scheduler / network). 10CT defines the contract **before** any such
adapter module exists.

10CT does **not** implement. It does **not** create a dry-run
adapter module. It does **not** start a daemon. It does **not**
add a scheduler or periodic job. It does **not** open a network
connection. It does **not** call a provider, launcher, or
container. It does **not** add runtime code, movement, map
lookup, route execution, event emission, NPC behavior,
co-presence, awareness, relationship, timing, or coordination.

---

## 1. Current state

- 10CJ is dry-run / inert. Consumes 10BT decisions, emits an
  inert dry-run adapter decision; never writes; all five gate flags
  are hard-coded False.
- 10CL authorizes design only for a future write-path adapter
  (allowlist / denylist); the only permitted write is an inert
  append-only 10CP ledger entry.
- 10CN authorizes the gate-6 write path (`world-sim/data`) as a
  candidate location only.
- 10CP implements the gate-6 write path as a minimal inert
  append-only ledger writer.
- 10CR defines the gate-7 (daemon / scheduler / network)
  boundary; gate-7 remains NOT authorized.
- 10CT still does **not** implement any adapter. It defines a
  dry-run adapter contract that stays entirely inside the
  already-satisfied gates (1-6, 8, 9) and does **not**
  require gate-7.

---

## 2. Future minimal dry-run adapter contract

The only candidate future adapter 10CT pre-authorizes is a
**gate-7-free, in-process, caller-driven dry-run adapter**:

- invoked synchronously by a caller that already holds a 10CJ
  dry-run decision (no daemon, no scheduler, no network to
  obtain it);
- consumes only 10CJ output fields (the 10CL allowlist);
- emits an inert adapter decision object with the same envelope
  shape as 10CJ;
- hard-codes `daemon_allowed = False`,
  `scheduler_allowed = False`, `network_allowed = False`
  (gate-7 stays closed);
- hard-codes `runtime_allowed = False` and
  `world_sim_data_accessed = False` unless the later 10CP
  ledger path is the only write and is explicitly passed;
- `executed = False`; `planned_action` only `"none"` or
  `"log_only"`;
- never starts a process, never opens a socket, never calls a
  provider / launcher / container.

This path is the gate-2 ("read-only dry-run adapter first")
fulfillment for the gate-7 surface: a dry-run adapter that
needs no daemon / scheduler / network at all.

---

## 3. Future adapter allowlist (what a later phase MAY read/emit)

A later minimal dry-run adapter phase may only:

Read (10CJ output fields, per 10CL):

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

Emit (inert adapter decision, 10CJ-shaped):

- an inert decision object with hard-coded False gate-7 flags
  (`daemon_allowed`, `scheduler_allowed`,
  `network_allowed`);
- `executed = False`;
- `planned_action` only `"none"` or `"log_only"`;
- the single permitted side effect (if
  `planned_action == "log_only"`) is the
  already-authorized append-only 10CP inert ledger entry
  passed an explicitly authorized path — no new
  `world-sim/data` access.

It must:

- **not** read 10BT directly;
- **not** read `equality_signal_value`;
- **not** read `equality_signal_type` from 10BT;
- use `recognized_signal_type` from 10CJ only;
- only consider records where `planned_action == "log_only"`;
- reject anything where `executed` is not False;
- reject anything where any gate flag is not False.

---

## 4. Future adapter denylist (what a later phase MUST NOT do)

- daemon / background-service startup or lifecycle management;
- scheduler / periodic-job / tick-driver creation;
- network connection (outbound or inbound);
- provider / model / launcher / container call or spawn;
- Docker / VPS / infrastructure provisioning;
- movement execution;
- map lookup / reconstruction;
- route planning or route execution;
- event creation / emission beyond the authorized inert 10CP
  ledger entry;
- NPC awareness, relationship, interaction, co-presence,
  proximity, timing, or coordination;
- any `world-sim/data` access beyond the already-authorized
  append-only 10CP ledger path;
- promotion of `equality_signal_value` into any runtime state.

The `claim_boundary` from 10BT / 10CJ ("no co-presence, no
awareness, no relationship, no timing inference") remains
binding.

---

## 5. Future gating for the later dry-run adapter phase (10CH mapping)

| 10CH gate | Status after 10CT |
|---|---|
| 1. separate runtime adapter spec | **satisfied** (10CL) — 10CT narrows it to gate-7-free dry-run |
| 2. read-only dry-run adapter first | **satisfied** (10CJ) — later adapter stays dry-run |
| 3. explicit allowlist of readable fields | **satisfied** (10CL) |
| 4. explicit denylist of forbidden surfaces | **satisfied** (10CL + above) |
| 5. no direct use of `equality_signal_value` | **satisfied** (10CJ + above) |
| 6. no `world-sim/data` read/write until authorized | **satisfied** (10CN spec + 10CP inert append-only writer) |
| 7. no daemon/scheduler/network until authorized | **satisfied-by-absence** — 10CT's adapter needs NONE of them; gate-7 stays NOT authorized for any other use |
| 8. tests proving 10BT flags stay False | **satisfied** (existing) |
| 9. tests proving adapter is dry-run/read-only first | **satisfied** (10CJ) |
| 10. operator approval before any non-doc phase | **pending** — 10CT is the approval artifact; the later dry-run adapter implementation phase still needs its own go |

10CT does **not** authorize gate-7. It defines a dry-run
adapter that requires no gate-7 activity at all, keeping gate-7
closed by construction.

---

## 6. Required future tests before any later dry-run adapter phase

A later minimal dry-run adapter phase must add tests proving:

- the adapter is invoked in-process / caller-driven with no daemon,
  scheduler, or network;
- no process is started, no socket opened, no
  provider / launcher / container called;
- it consumes only 10CJ output fields;
- `equality_signal_value` is never read;
- `daemon_allowed` / `scheduler_allowed` / `network_allowed`
  are hard-coded False;
- `executed` is False and `planned_action` is only
  `"none"` or `"log_only"`;
- the only permitted side effect is the already-authorized
  append-only 10CP inert ledger entry at an explicitly
  authorized path;
- no movement, map lookup, route execution, event emission,
  NPC behavior, co-presence, awareness, relationship, timing,
  or coordination occurs;
- no `world-sim/data` access occurs beyond the
  already-authorized append-only 10CP ledger path;
- all activity fails closed on malformed / forbidden /
  gate-True input.

---

## 7. Conclusion

10CT pre-authorizes only the gate-7-free, minimal dry-run
adapter contract. It does **not** implement an adapter. It does
**not** authorize gate-7 (daemon / scheduler / network)
activity. It keeps gate-7 closed by construction: the adapter it
describes needs none of daemon, scheduler, or network.

The next possible phase after 10CT should be:

- 10CU - sync 10CT metadata

Then, only after operator approval and the GPT-5.6 Luna/Sol
model switch:

- a later minimal dry-run adapter implementation phase (not yet
  numbered) - must stay gate-7-free and may only emit the
  already-authorized inert 10CP ledger entry.

## Files

- New spec only: `world-sim/docs/phase_10ct_gate_7_minimal_dry_run_adapter_spec.md`
- No module, no test, no `pure-tests.yml` change, no runtime code.

## Tests

- None required (docs-only).
