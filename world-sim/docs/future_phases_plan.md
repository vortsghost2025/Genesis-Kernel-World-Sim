# Future Phases Plan

Roadmap of planned phases after 10O/10P. Each phase is tagged with its prerequisites so agents and operators can identify what is safe to run and when.

---

## Legend

| Label | Meaning |
|-------|---------|
| **CI** | CI must be passing (green) before this phase can be verified |
| **RUNTIME** | Requires live shell access to the canonical runtime host as verified by the operator |
| **DOCS** | Documentation only — safe to write on any machine without infrastructure |
| **PURE** | Code-only — safe to write on any machine; tests use tempdirs only |
| **GATE** | Requires operator approval before execution; not for automated agents |

---

## Phase Status Summary

| Phase | Status | Prerequisites | Type |
|-------|--------|---------------|------|
| 10O | Pushed / CI pending | GitHub billing lock must clear before Done | DOCS |
| 10P | Blocked | GitHub billing clearance | CI verification |
| 10Q | Draft | None | DOCS |
| 10R | Planned | 10Q complete | DOCS |
| 10S | Planned | 10P green, 10R complete | PURE |
| 10T | Planned | 10S complete | PURE |
| 10U | Planned | 10T complete | PURE |
| — | Planned | 10U complete | RUNTIME + GATE |

---

## Detailed Phase Descriptions

### 10P — CI Verification (blocked)

**Purpose:** Verify that the pure 10K/10L test suite passes in GitHub Actions.

**Status:** Blocked on GitHub billing/account lock. Workflow YAML is correct — GitHub parsed and accepted it, but the runner never started.

**Trigger:** When billing lock clears, run:
```
gh run rerun 28424128344
```
or trigger a new push/PR. If green, update 10O status to Done in `phase_index.md` and optionally add a CI badge to `README.md`.

**Constraints:**
- No CI YAML edits (already correct)
- No code changes
- No test changes

---

### 10Q — Future Phases Plan (current)

**Purpose:** This document. Establish a shared roadmap so all agents and the operator align on what comes next and what each phase requires.

**Type:** DOCS
**Prerequisites:** None
**Files affected:** `world-sim/docs/future_phases_plan.md`

---

### 10R — Runtime Wiring Architecture

**Purpose:** Design document mapping how the pure ledger (`world_event_ledger.py`) and candidate mapper (`world_event_candidate_mapper.py`) will connect into the daemon's action-execution path. Covers data flow, new module definitions, sequence diagrams, and test prerequisites — without writing any runtime code.

**Type:** DOCS
**Prerequisites:** 10Q complete
**Files affected:** `world-sim/docs/runtime_wiring_architecture.md`

**Expected contents:**
- Data flow diagram (ASCII or Mermaid)
- New module specifications (`world_event_processor.py`, `world_event_store.py`, etc.)
- How candidates become committed events
- How the daemon invokes the pipeline
- What pure tests must exist before runtime wiring
- Safety gates: what prevents accidental ledger corruption

**Explicitly out of scope:**
- No daemon edits
- No data writes
- No Docker or provider configs
- No secrets or credentials

---

### 10S — Pure Event Verification Module

**Purpose:** Implement a pure `world_event_verifier.py` that validates a candidate event against the current ledger state before the daemon commits it. Catches contradictions, duplicate timestamps, and boundary violations before they reach the append-only ledger.

**Type:** PURE
**Prerequisites:** 10P green (CI passing), 10R complete (design agreed)
**Files affected:** `world-sim/backend/world/world_event_verifier.py`, plus test file

**Constraints:**
- No runtime dependencies
- Tempdir-only tests
- No daemon or provider calls
- Must pass CI before merging

---

### 10T — Pure Event Aggregation Module

**Purpose:** Implement a pure `world_event_aggregator.py` that produces summaries and derived state from the event ledger (e.g., recent event count by category, agent activity windows, world-state deltas over time). Useful for dashboards and decision support without hitting the live sim.

**Type:** PURE
**Prerequisites:** 10P green, 10R complete
**Files affected:** `world-sim/backend/world/world_event_aggregator.py`, plus test file

---

### 10U — Pure Event Export Module

**Purpose:** Implement a pure `world_event_exporter.py` that serializes ledger events to portable formats (JSON, JSONL, CSV) for offline analysis, debugging, and audit trails. Read-only — never modifies the ledger.

**Type:** PURE
**Prerequisites:** 10P green, 10R complete
**Files affected:** `world-sim/backend/world/world_event_exporter.py`, plus test file

---

### Runtime Wiring Phase (unnumbered)

**Purpose:** Connect the pure pipeline (ledger → verifier → aggregator → exporter) into the daemon's action-execution path. This is the first phase that touches live simulation state.

**Type:** RUNTIME + GATE
**Prerequisites:** All pure phases (10S–10U) complete and passing CI, design from 10R reviewed and approved, operator present on canonical runtime host

**Constraints:**
- Must not run from CI
- Must not run from an unverified environment
- Operator must review daemon diff before execution
- Operator must verify data directory state before and after
- First run must use a test isolation mode (separate event store path)

---

## Dependency Map

```
10O (docs) ──> 10P (CI verify) ──> 10S (verifier) ──+
                   ^                                  │
                   │                                  │
10Q (docs) ──> 10R (architecture) ────────────────────+──> Runtime Wiring
                                                        │
                                                  10T (aggregator) ──+
                                                  10U (exporter) ─────+
```

---

## Always-Safe Operations

Regardless of billing or phase status, the following are always safe:

- Reading `world-sim/docs/` files
- Reading `world-sim/backend/world/` modules (they are pure with no runtime deps)
- Running the explicit 10K/10L test suite (7 files, tempdirs only)
- Writing to `world-sim/docs/` (documentation only)
- Drafting documentation or specs for pure module phases

## Never-Safe Without Explicit Authorization

- Running `pytest tests/` (broad) unless a specific phase authorizes it
- Editing daemon, provider, tick, or scheduler files
- Reading or writing `world-sim/data/`
- Starting or stopping Docker containers
- Executing remote shell commands on the canonical runtime host
- Accessing provider APIs or models