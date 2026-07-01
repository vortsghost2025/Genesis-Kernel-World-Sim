# Phase 10S: Runtime Wiring Architecture

Architecture for connecting pure event-sourcing modules into live daemon ticks while preserving the habitat principles defined in 10R.

---

## 1. Purpose

The pure modules (10K ledger, 10L candidate mapper) are deliberately isolated from runtime. They work against isolated files, produce deterministic output, and have no knowledge of the daemon, tick loop, scheduler, or live sim state.

This document describes **how those modules eventually wire into the daemon's action-execution path** — without compromising append-only safety, claim scopes, phase gates, or public/private boundaries.

The wiring is not implemented here. This is the architecture that an implementation phase will follow.

---

## 2. Non-Goals

- Writing runtime code or daemon edits
- Defining scheduler, provider, or model interfaces
- Specifying data directory layout or storage backends
- Designing agent-to-agent communication protocols
- Resolving agent identity, authentication, or authorization
- Defining the tick loop or action-selection algorithm
- Addressing network, container, or deployment topology
- Handling secrets, credentials, or private configuration

These are out of scope for 10S. A future runtime implementation phase will address them, informed by this architecture.

---

## 3. Inputs from Existing Pure Modules

### 3.1 World Event Ledger (10K)

The ledger provides the canonical event store. Its public interface is:

| Function | Input | Output | Side Effects |
|----------|-------|--------|-------------|
| `validate_event(event)` | A candidate event dict | `(bool, list[str])` — valid flag + error messages | None |
| `append_event(event, ledger_path)` | A validated event + path | `None` or raises | Writes one JSONL line |
| `read_events(ledger_path, offset, limit)` | Path + optional range | `list[dict]` — event records | None |

The ledger enforces schema, evidence categories, claim scopes, before/after refs for mutations, and hidden-water/animal-guidance boundaries.

### 3.2 Candidate Event Mapper (10L)

The mapper translates raw agent action results into candidate event dicts. Its public interface:

| Function | Input | Output | Side Effects |
|----------|-------|--------|-------------|
| `map_result_to_candidate(...)` | Action type, result dict, agent state | `dict` — candidate event or `None` | Returns dicts only, never writes files |

The mapper validates agent state against the runtime boundary rules (rejects unsafe gathers and private paths) but does not check against ledger history — that is the verifier's job.

### 3.3 Event Verifier (future pure module)

A planned pure module that checks a candidate against the current ledger state:

- Duplicate detection (same tick + agent + action type already recorded)
- Contradiction detection (new event contradicts an existing world_event)
- Sequence validation (before/after refs point to existing events)
- Boundary enforcement (event does not violate forbidden-inference rules across evidence)

This module does not exist yet. The architecture below shows where it fits.

---

## 4. Runtime Boundary Model

The runtime wiring operates across a strict boundary:

```
┌──────────────────────────────────────────────────┐
│                  DAEMON / TICK                    │
│  (live sim state, agent objects, scheduler)      │
│                                                   │
│  ┌─────────────┐    ┌────────────────────────┐   │
│  │ Tick Action  │───>│ Candidate Event        │   │
│  │ Execution    │    │ Mapper (10L, pure)     │   │
│  └─────────────┘    └───────────┬────────────┘   │
│                                 │                 │
│                                 ▼                 │
│  ┌──────────────────────────────────────────┐    │
│  │         VERIFICATION GATE                 │    │
│  │  (future pure module)                    │    │
│  │  - checks against ledger                 │    │
│  │  - rejects contradictions                │    │
│  │  - operator overridable via evidence     │    │
│  └──────────────────┬───────────────────────┘    │
│                     │                             │
│                     ▼                             │
│  ┌──────────────────────────────────────────┐    │
│  │         WORLD EVENT LEDGER (10K)          │    │
│  │  append-only, schema-enforced, JSONL     │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         EVENT AGGREGATOR (future)         │    │
│  │  derived state, summaries, windows      │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         EVENT EXPORTER (future)           │    │
│  │  JSON/JSONL/CSV for offline audit       │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  ═══════════════════ PUBLIC / PRIVATE ═══════════ │
│                                                   │
│  ┌──────────────────────────────────────────┐    │
│  │         DAEMON PRIVATE STATE              │    │
│  │  (tick counter, agent sockets, config)   │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

Key constraint: **the ledger, verifier, aggregator, and exporter never read daemon private state.** They receive only what the daemon passes through the candidate mapper. The public/private boundary is enforced by the mapper's runtime boundary checks (from 10N).

---

## 5. Tick-to-Candidate Flow

```
1. Tick loop calls action_fn(agent, world)
2. action_fn returns result dict: {observation, items, location, message, ...}
3. Daemon calls map_result_to_candidate(action_type, result, agent_state)
4. Mapper returns candidate dict or None (if result cannot become an event)
5. If candidate is None, daemon logs and continues — no event recorded
6. If candidate is valid, daemon holds it for verification
```

At step 6, the candidate is **not yet committed**. It exists only in memory. The next section describes how it becomes a permanent event.

---

## 6. Candidate-to-Ledger Flow

```
1. Daemon passes candidate to verifier module
2. Verifier checks candidate against current ledger state:
   a. Schema validity (reuses 10K validate_event)
   b. Duplicate tick/agent/action check
   c. Contradiction check against recent world_events
   d. Reference integrity (before/after event IDs exist)
   e. Forbidden-inference check across combined evidence
3. Verifier returns: {accepted: bool, reasons: list[str], severity: str}
4. If accepted:
   a. Daemon calls append_event(candidate, ledger_path)
   b. Append writes one JSONL line
   c. Append completes or raises — the daemon uses `read_events` afterward to obtain readback verification
5. If rejected:
   a. Daemon records rejection in a separate rejection log
   b. Agent may receive a notice (future feature)
   c. Operator can review and override via evidence
```

**Critical safety property:** The ledger write is the **last** step. The daemon does not modify agent state, world state, or tick counters based on an event until after the ledger confirms the append. This prevents state corruption from partial writes.

---

## 7. Provenance and Claim Scope Preservation

Every event that enters the ledger carries its claim scope from the candidate mapper. The wiring must preserve this chain:

```
Raw perception
    │
    ▼
Agent interpretation ──> claim_scope: "memory"
    │
    ▼
Speech exchange ──> claim_scope: "speech"
    │
    ▼
Candidate mapper ──> claim_scope: preserved
    │
    ▼
Ledger ──> claim_scope: recorded as-is
```

The wiring does **not** upgrade claim scopes. An agent's "hypothesis" does not become a "world_event" through the wiring — it remains a hypothesis. The wiring layer must not invent new claim scopes. Runtime audit details that do not fit existing claim scopes require a future schema phase before they can enter the ledger.

---

## 8. Phase Gates Before Runtime Mutation

No runtime wiring change reaches the daemon without passing through phase gates:

| Gate | What It Protects | Trigger |
|------|------------------|---------|
| **Pure module CI** | All pure modules pass their tempdir-only tests | Automated CI run |
| **Operator review** | Daemon diff is read and approved by the operator | Manual git diff review |
| **Test isolation run** | First runtime run uses a separate event store path, not the live sim path | Operator command |
| **Readback verification** | After test run, operator reads back the isolated ledger and verifies contents | Operator reads ledger file |
| **Boundary scan** | No private paths, hostnames, or credentials leaked into ledger | Automated grep scan |
| **Phase status update** | Phase index updated to reflect runtime wiring as active | Operator commit |

These gates are not optional. If any gate fails, the wiring reverts to the previous state.

---

## 9. Public/Private Boundary Rules

The following are **never** passed to any pure module:

- Machine hostnames, IPs, or network identifiers
- Container names, IDs, or orchestration labels
- Filesystem paths outside the designated event store directory
- Provider API keys, model names, or endpoint URLs
- SSH keys, tokens, or session credentials
- Operator account names or UIDs
- Docker image tags or container configs

The candidate mapper (10L) already enforces a subset of these. The wiring layer must add an additional filter before any data touches the verifier or ledger. This is called the **egress sanitizer** — a minimal pass that strips or rejects any payload field not in the allowed event schema.

---

## 10. Failure Modes

| Failure | Effect | Recovery |
|---------|--------|----------|
| Ledger file write fails mid-line | Partial line — corruption risk | Pre-write checksum, retry once, then operator alert |
| Verifier hangs or crashes | Tick proceeds without event recording | Timeout guard — candidate is dropped, not queued indefinitely |
| Duplicate event written | Ledger has two entries for same tick+agent+action | Compensating mutation/rejection marker with evidence; never silent removal |
| Claim scope mismatch | Event stored with wrong provenance | Operator edits claim scope via mutation event (before/after refs) |
| Private data leaks into candidate | Egress sanitizer catches it | Candidate rejected, operator notified, source inspected |
| Verifier disagrees with operator intent | Event rejected but operator wants it recorded | Operator records an explicit override through the same validated append path, with `operator_proof` evidence |

All failure modes are **recoverable** — the append-only ledger means nothing is overwritten. Recovery always adds new evidence rather than modifying history.

---

## 11. Open Questions

- Should the verifier run synchronously within the tick or asynchronously on a short-delayed queue?
- What is the maximum acceptable delay between tick execution and event commitment?
- Should rejected candidates ever retry automatically, or always require operator review?
- How does the system handle ledger rotation — splitting one large JSONL into multiple files?
- Should the egress sanitizer be a standalone pure module or part of the candidate mapper?
- How does the aggregator handle gaps from rejected candidates without misleading summaries?
- What does the runtime wiring test harness look like when there is no live sim to test against?

---

## 12. Future Implementation Prerequisites

Before runtime wiring can be implemented, the following must exist and pass CI:

1. **10T — Event Verifier (pure module)** — validates candidates against ledger state
2. **10U — Event Aggregator (pure module)** — produces derived state from ledger (needed by verifier for context)
3. **10V — Event Exporter (pure module)** — read-only serialization for audit trails
4. **10P — CI green** — confirms all pure modules pass in GitHub Actions
5. **10W — Egress Sanitizer Spec** — defines what private data the sanitizer must catch (may be folded into 10V or stand alone)

These phases are renumbered from the original plan to account for 10R (habitat principles) and 10S (this document) taking the earlier slots.

---

## Appendix: Dependency Chain (Revised)

```
10O (CI docs) ──> 10P (CI verify) ──> 10T (verifier) ──+
                    ^                                     │
                    │                                     │
10Q (roadmap) ──> 10R (habitat principles) ──────────────+──> 10T (verifier)
                       │                                       │
                       ▼                                       ▼
                   10S (wiring arch) ─────────────────> 10U (aggregator)
                                                              │
                                                              ▼
                                                          10V (exporter)
                                                              │
                                                              ▼
                                                   Runtime Wiring (gated)
```

The runtime wiring phase itself remains unnumbered and gated — it requires operator presence on the canonical runtime host and cannot execute from CI or an unverified environment.

---

*This document is not a specification. It is an architecture sketch — enough to guide implementation without dictating every detail. The verifier, aggregator, and exporter phases will each produce more detailed designs before code is written.*