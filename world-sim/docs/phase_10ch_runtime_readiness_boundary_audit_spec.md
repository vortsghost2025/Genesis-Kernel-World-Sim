# Phase 10CH - Runtime Readiness Boundary Audit

Docs-only runtime-readiness boundary audit after 10CF.

This phase performs **no implementation**. It does not touch the 10BT
consumer module, does not add or change tests, does not modify
`pure-tests.yml`, does not create a new equality contract, and does
**not** authorize runtime wiring. It only documents the boundary
between the (now-covered, still-inert) consumer ladder and any
future runtime connection.

10CH is the deliberate "stop before runtime" checkpoint the 10CF
audit pointed at: the consumer ladder is covered, the next safe
decision is a runtime-readiness audit, and runtime wiring is still
out of scope.

---

## Current hard safety facts (verified, not changed)

The 10BT consumer harness, after 10BV / 10BX / 10BZ / 10CB /
10CD, still:

- emits only a sanitized **21-field decision object**;
- keeps `decision_schema_version` at `"10BT.1"` (hard-coded);
- keeps `consumer_scope` at `"record_public_equality_signal_only"`
  (hard-coded);
- keeps `runtime_allowed` = **False** (hard-coded);
- keeps `daemon_allowed` = **False** (hard-coded);
- keeps `scheduler_allowed` = **False** (hard-coded);
- keeps `network_allowed` = **False** (hard-coded).

There is **no code path** in the 10BT module that can flip any of
the four runtime flags to True. They are emitted in the same envelope
shape on the happy path, on unknown-contract-type, on
missing-fields, and on non-dict input.

No consumer output authorizes:

- movement execution;
- map lookup / reconstruction;
- route planning or route execution;
- scheduling;
- daemon action;
- event creation / emission;
- NPC awareness, relationship, or interaction;
- co-presence, proximity, or timing inference.

The `claim_boundary` field names co-presence / awareness /
relationship / timing as **forbidden concepts** so a downstream
reader may verify the boundary is intact. They appear in the export
only as named forbidden concepts, never as asserted facts.

---

## Required gates before any future runtime wiring

Before any phase may connect 10BT consumer outputs to runtime,
daemon, scheduler, movement, map lookup, event emission, NPC
behavior, or `world-sim/data`, the following gates must be
satisfied in order:

1. **A separate runtime adapter spec** must be written and reviewed.
   The adapter is a distinct module from 10BT; 10BT stays a
   pure read-only consumer.
2. **A separate read-only dry-run adapter** must exist before any
   write path. The first adapter implementation is dry-run / no-write
   by construction.
3. **An explicit allowlist** of the decision fields the adapter may
   read (e.g. `equality_signal_type`, `equality_signal_present`)
   must be published. Default deny: anything not allowlisted is
   unreadable by the adapter.
4. **An explicit denylist** of forbidden inference surfaces
   (co-presence, awareness, relationship, timing, path, movement,
   arrival, coordination, cooperation) must be published and
   enforced in the adapter.
5. **No direct use of `equality_signal_value`** for movement or
   co-presence. The value is an opaque public identifier (or set),
   not a command and not a presence claim.
6. **No `world-sim/data` reads or writes** until separately
   authorized by a dedicated, reviewed phase.
7. **No daemon / scheduler / network action** until separately
   authorized by a dedicated, reviewed phase.
8. **Tests proving the 10BT runtime flags remain False** on every
   path (already exist; must keep passing).
9. **Tests proving any future adapter is dry-run / read-only first**,
   with a failing test if a write path is introduced without a
   preceding dry-run gate.
10. **Operator approval** before any non-doc phase after this audit.

---

## Conclusion

The project is **ready for a future runtime-adapter design
discussion**, but **not runtime wiring**.

The consumer ladder is covered (10BP / 10AY / 10BJ / 10BK /
10BL / 10AW) and still inert. The next possible non-doc phase
must be a **pure dry-run adapter spec / harness**, not live
runtime. 10CH confirms the boundary; it does not authorize
crossing it.
