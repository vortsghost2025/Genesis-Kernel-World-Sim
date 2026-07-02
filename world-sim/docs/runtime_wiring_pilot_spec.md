# Phase 10X: Runtime Wiring Pilot Spec

Docs-only architecture contract for the first heartbeat.

---

## 1. Purpose

Phase 10X defines the smallest future runtime bridge that proves the event
architecture can breathe once.

This phase does not implement the bridge. It defines the contract for one
narrow path:

```text
one action output
-> one candidate event
-> one verifier result
-> one ledger append
-> one sanitized/exportable projection
```

The purpose is closure, not scale.

Action output is not truth.
Candidate event is not accepted history.
Verifier gates acceptance.
Ledger append creates durable history.
Sanitizer/export creates public-safe visibility.
Memory may later reference events but does not become truth automatically.

## 2. Non-goals

Phase 10X does not do any of the following:

- rewrite daemon logic
- redesign the scheduler
- integrate external services
- add live runtime wiring
- add population, economy, factions, or broader civilization systems
- define long-horizon autonomy loops
- change the event schema
- change claim-scope rules
- serialize raw action output directly

## 3. First heartbeat definition

The first heartbeat is a five-step contract for a single action:

1. A runtime action produces one minimal action envelope.
2. One mapper function turns that envelope into one candidate event.
3. The verifier returns one acceptance result for that candidate.
4. If accepted, the ledger appends exactly one durable event.
5. A sanitizer-safe event or projection becomes exportable for public egress.

Anything outside that narrow contract is out of scope for 10X.

## 4. Minimal input action shape

For the first heartbeat, the runtime side only needs a minimal envelope that is
compatible with the existing observe mapper path.

Required top-level fields:

| Field | Type | Purpose |
|---|---|---|
| `actor_id` | string | Acting agent identifier |
| `action_type` | string | Must be `observe` for the first heartbeat |
| `action_text` | string | Human-readable observation text passed to the mapper |
| `result` | dict | Mapper input payload |
| `tick` | integer or null | Tick value if available |
| `timestamp_utc` | string or null | Timestamp if available |

For the first heartbeat, `result` only needs these fields:

| Field | Type | Purpose |
|---|---|---|
| `territory_ref` | string | Observation territory reference |
| `evidence_used` | list of dict | Evidence entries passed through to the mapper |

Each `evidence_used` entry must already follow the existing evidence shape used
by the mapper and ledger:

- must be a dict
- must include `category`
- should include `ref` or `reference`

The first heartbeat does not require a larger runtime envelope than this.

## 5. Candidate event mapping step

Phase 10Y should start with the existing observe mapper only:

- `candidate_from_observe_result(actor_id, action_text, result, *, tick=None, timestamp_utc=None)`

The 10X contract does not introduce a new generic mapper API.

For the first heartbeat:

1. runtime code constructs the minimal input action envelope
2. runtime code calls `candidate_from_observe_result(...)`
3. the mapper returns one candidate event dict

That candidate event must remain within the current event field surface:

- `event_id`
- `schema_version`
- `tick`
- `timestamp_utc`
- `actor_id`
- `lens`
- `territory_ref`
- `action_type`
- `summary`
- `evidence_refs`
- `claim_scope`
- `before_ref`
- `after_ref`
- `affected_agents`
- `artifacts_created_or_changed`
- `relationship_delta`
- `consequence`
- `verification_status`

The first heartbeat does not add fields beyond that surface.

## 6. Verification step

Verification uses the existing pure verifier contract:

- load current ledger history with `read_events(ledger_path)`
- call `verify_candidate_event(candidate, existing_events)`

The verifier returns:

- `accepted`
- `errors`
- `warnings`

The candidate remains in-memory only until verification finishes.

If `accepted` is false, the first heartbeat stops there and no durable history
is created.

## 7. Ledger append gate

Only an accepted candidate may cross the ledger append gate.

The append gate uses the existing ledger helper:

- `append_event(ledger_path, candidate)`

This gate matters because ledger append is the moment when candidate state
becomes durable history.

The pilot contract should treat append success as the durable-history boundary:

- before append success: candidate only
- after append success: accepted world history

For 10Y proof purposes, a readback check with `read_events(ledger_path)` is
part of the contract, because the harness must prove that exactly one event was
persisted.

## 8. Sanitizer/export step

After a successful append, the event may move to a public-safe visibility step.

That step has two parts:

1. apply the 10W sanitizer rules to the appended event or to a projection built
   from the appended event
2. pass the sanitized event or sanitized projection to `export_events(...)`

10X does not require a final sanitizer implementation yet. It only requires
that the runtime bridge preserve this order:

```text
accepted ledger event
-> sanitizer-safe event or projection
-> exporter output
-> public egress
```

The sanitizer/export step does not decide truth and does not affect whether the
ledger append already happened. It only governs public-safe visibility.

## 9. Reject paths

The first heartbeat must document four reject paths:

1. **Mapper no-output path**
   - the mapper returns `None`
   - result: no candidate event, no verifier call, no append

2. **Verifier reject path**
   - `verify_candidate_event(...)` returns `accepted = false`
   - result: no append and no public export step

3. **Ledger append failure path**
   - `append_event(...)` does not complete successfully or raises
   - result: no durable history is accepted unless readback confirms exactly one appended event

4. **Sanitizer reject path**
   - the accepted ledger event cannot be exposed through the public-safe export path
   - result: durable history may still exist, but no public exportable projection is released

These reject paths must stay explicit in 10Y so failure handling is observable
without widening the project scope.

## 10. Minimal supported first actions

Required for the first proof:

- `observe`

Not required for the first proof, but reasonable next extensions after 10Y:

- `rest`
- `whisper`
- `goal`
- `help`

Deferred until later because they introduce mutating-world concerns or more
complex state transitions:

- `gather`
- `move_local`
- `create_artifact`
- `modify_artifact`
- `repair`

The first heartbeat should prove one non-mutating action before any mutating
world-change primitive is wired.

## 11. Tempdir-only proof plan for 10Y

Phase 10Y should prove this contract with an isolated temporary-directory
harness.

The proof plan is:

1. create an isolated temporary ledger location
2. build one mock `observe` action envelope using the minimal shape from 10X
3. call `candidate_from_observe_result(...)`
4. load existing history with `read_events(...)`
5. call `verify_candidate_event(...)`
6. if accepted, call `append_event(...)`
7. read back the ledger with `read_events(...)`
8. build a sanitizer-safe event or projection
9. pass that event or projection to `export_events(...)`
10. assert that the pipeline produced:
    - one candidate event
    - one accepted verifier result
    - one appended ledger event
    - one sanitized/exportable projection

10Y should remain tempdir-only and should not require daemon edits, live ticks,
or any external service wiring.

## 12. Open questions

- Should the first public exportable projection use the full sanitized event or a smaller projection subset?
- Should 10Y prove readback by comparing event count only, or by matching the appended `event_id` as well?
- Should the first harness require both `tick` and `timestamp_utc`, or allow one to be null as long as the other is present?
- Which immediate post-10Y extension should come first: `rest`, `whisper`, `goal`, or `help`?
- Should the sanitizer step operate on the full appended event first, even if later exports use smaller projections?

---

This specification is intentionally narrow. It exists to define the first
heartbeat contract cleanly so that 10Y can prove it in isolation before any
larger living-world loop is attempted.
