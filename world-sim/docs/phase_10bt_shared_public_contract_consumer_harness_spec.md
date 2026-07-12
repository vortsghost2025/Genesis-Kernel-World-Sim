# Phase 10BT — First Shared Public Contract Consumer Harness

## Status

10BT is the **first consumer harness** in the shared-public ladder. It consumes already-built shared-public equality contract artifacts (such as a 10BP snapshot_id equality contract) and emits a sanitized "consumer decision" object describing what a downstream runtime consumer would do, without ever performing any runtime action.

10BT is **pure**: no daemon, no scheduler, no provider, no Docker, no network, no live data, no `world-sim/data` access. The only I/O happens in `consume_shared_public_contract_file`, which only reads JSON from a caller-supplied path.

10BT is **not** an equality contract. It does not create equality claims. It does not compare two agents' surfaces. It does not see two agents' public bundles directly. It accepts a contract artifact and emits a decision.

---

## Allowed Evidence Sources

10BT may only rely on:

- `README.md`
- `world-sim/docs/phase_index.md`
- `world-sim/docs/phase_10br_post_10bp_public_surface_coverage_audit_spec.md`
- `world-sim/docs/phase_10bp_shared_public_snapshot_id_equality_contract_spec.md`
- `world-sim/backend/world/local_shared_public_snapshot_id_equality_contract.py` (read-only)
- `world-sim/backend/world/local_two_agent_public_merge.py` (read-only at test time only — fixture)
- `world-sim/backend/world/world_event_sanitizer.py` (read-only; only allowed upstream import)
- `.github/workflows/pure-tests.yml`

10BT does **not** import or call any phase creator (10AP, 10AQ, 10AR, 10AS, 10AT, 10AU, 10AV, 10AW, 10AX, 10AY, 10AZ, 10BA, 10BB, 10BC, 10BD, 10BE, 10BF, 10BG, 10BH, 10BI, 10BJ, 10BK, 10BL, 10BP). Tests may use 10AS/10BP **fixtures**, but the module itself must be safe in isolation.

---

## Baseline Commits

| Commit | Subject |
|---|---|
| `32302e2` | docs: add 10BR post-10BP public surface coverage audit |

10BT is built on the closed public-surface ladder at `6ba6622` (10BP) plus the closures and audits at `57ee9a3` (10BQ) and `32302e2` (10BR).

---

## Public Function Signatures

```python
def create_shared_public_contract_consumer_decision(contract: dict) -> dict
def export_shared_public_contract_consumer_decision(decision: dict) -> str
def consume_shared_public_contract_file(contract_json_path: Path | str) -> dict
```

Field naming follows the existing ladder convention (snake_case JSON keys, schema-versioned output, hash-prefixed identity).

---

## Required Output Fields (21 total)

The decision envelope has the full expected shape on every code path:

1. `ok` — bool, True if contract passed validation, else False
2. `decision_schema_version` — `"10BT.1"` (hard-coded)
3. `decision_type` — `"shared_public_contract_consumer_decision"` (hard-coded)
4. `decision_id` — `"10BT-" + sha256(canonical_material)[:32]` on success; None on failure
5. `source_contract_id` — from `contract["contract_id"]`; None if missing
6. `source_contract_type` — from `contract["contract_type"]`; None if missing
7. `source_contract_schema_version` — from `contract["contract_schema_version"]`; None if missing
8. `source_claim_scope` — from `contract["claim_scope"]`; None if missing
9. `source_merge_hash` — from `contract["source_merge_hash"]`; None if missing
10. `consumer_scope` — `"record_public_equality_signal_only"` (hard-coded)
11. `contract_seen` — True if contract was structurally valid enough to inspect; otherwise False
12. `contract_ok` — echo of `contract["ok"]`; False if contract not accepted
13. `equality_signal_present` — bool, depends on contract_type
14. `equality_signal_type` — string, `"snapshot_id_equality"` for 10BP; `"unknown_contract_type"` otherwise
15. `equality_signal_value` — string or None, depends on contract_type
16. `runtime_allowed` — **always False**
17. `daemon_allowed` — **always False**
18. `scheduler_allowed` — **always False**
19. `network_allowed` — **always False**
20. `claim_boundary` — fixed string, see below
21. `errors` — list of error strings (empty on success)

This consistent envelope means downstream consumers may rely on a stable field set without special-casing failure paths.

---

## Required Contract Inputs

The decision accepts a contract only when all five required fields are present and valid:

| Field | Required type |
|---|---|
| `ok` | strictly `True` |
| `contract_id` | non-empty string |
| `contract_type` | non-empty string |
| `claim_scope` | non-empty string |
| `source_merge_hash` | non-empty string |

If any required field is missing or invalid:

- `ok = False`
- `decision_id = None`
- `contract_seen = False`
- `contract_ok = False`
- `equality_signal_present = False`
- `equality_signal_type = "unknown_contract_type"`
- `equality_signal_value = None`
- All four runtime flags are still **False**
- `errors` populated with the reasons

---

## 10BP-Specific Equality Signal Extraction

When `contract_type == "shared_public_snapshot_id_equality_contract"`:

- `equality_signal_type = "snapshot_id_equality"`
- `equality_signal_present = bool(contract["same_snapshot_id"])`
- `equality_signal_value = contract["shared_snapshot_id"]` when `same_snapshot_id` is True
- `equality_signal_value = None` otherwise (including when `contract["shared_snapshot_id"]` is non-string, empty after sanitize, or redacted)

The equality signal value is sanitized through the public egress sanitizer before being copied into the decision. Private strings in 10BP's `shared_snapshot_id` field never appear in the export.

---

## Unknown Contract Types

When `contract_type` is a non-empty string but not yet wired up:

- `ok = True` (the contract is structurally valid)
- `contract_seen = True`, `contract_ok = True`
- `equality_signal_present = False`
- `equality_signal_type = "unknown_contract_type"`
- `equality_signal_value = None`
- `consumer_scope` remains `"record_public_equality_signal_only"`
- All four runtime flags remain **False**

The harness remains open to future contracts (10BK, 10BL, 10BG, 10BH, 10BI, and others) without modification; the consumer simply records the contract type "unknown" until an explicit future rung teaches the consumer how to extract a signal from it.

### Currently Recognised Contract Vocabulary

The consumer harness has explicit signal-extraction branches for:

| Contract type string | Signal type | Source field | Signal value source |
|---|---|---|---|
| `shared_public_snapshot_id_equality_contract` (10BP) | `"snapshot_id_equality"` | `contract["same_snapshot_id"]` | `contract["shared_snapshot_id"]` (sanitized) when present-true, else `None` |
| `shared_snapshot_hash_equality_contract` (10AY) | `"snapshot_hash_equality"` | `contract["same_snapshot_hash"]` | `contract["shared_snapshot_hash"]` (sanitized) when present-true, else `None` |
| `shared_public_current_tile_id_equality_contract` (10BJ) | `"current_tile_id_equality"` | `contract["same_current_tile_id"]` | `contract["shared_current_tile_id"]` (sanitized) when present-true, else `None` |
| `shared_public_route_intent_id_equality_contract` (10BK) | `"route_intent_id_equality"` | `contract["same_route_intent_id"]` | `contract["shared_route_intent_id"]` (sanitized) when present-true, else `None` |
| `shared_public_known_tile_ids_set_equality_contract` (10BL) | `"known_tile_ids_set_equality"` | `contract["same_known_tile_ids"]` | `contract["shared_known_tile_ids"]` (sanitized list of strings) when present-true and non-empty, else `None` |

Adding a new recognised contract is a small extension to `_extract_equality_signal` in the 10BT module only; the public-facing decision envelope (21 fields), `consumer_scope`, `claim_boundary`, `decision_schema_version`, and the hard-coded runtime/daemon/scheduler/network block do **not** change between recognitions.

### 10BJ-Specific Boundary (Hard)

A same current_tile_id equality signal is a **public equality signal only**. It MUST NOT, and DOES NOT, imply:

- co-presence
- same time
- same observation
- proximity
- awareness
- interaction
- relationship
- meeting
- collision
- shared visit
- shared journey
- having navigated to each other
- being "together"

The 10BT envelope must never expose any of those keys, tokens, or phrases at the public surface. The `claim_boundary` field names a configurable fixed list of these forbidden concepts (co-presence, awareness, relationship, timing) so that a downstream consumer reading the export may verify the boundary is intact. The 10BX test suite explicitly scans the exported decision JSON for the forbidden keys, tokens, and phrases; any future regression that re-introduces them will fail the test.

### 10BK-Specific Boundary (Hard)

A same route_intent_id equality signal is a **public equality signal only**. It records that two agents' public route-intent contracts self-reported the same `intent_id`. It MUST NOT, and DOES NOT, imply:

- co-presence
- co-journey / shared journey
- same time
- same observation
- proximity
- awareness
- interaction
- relationship
- meeting
- collision
- coordination
- cooperation
- shared visit
- having navigated to each other
- being "together"
- any route path, travel timing, or ETA inference

The 10BT envelope must never expose any of those keys, tokens, or phrases at the public surface. The 10BZ test suite explicitly scans the exported decision JSON for the forbidden keys (including `co_journey`, `coordination`, `shared_visit`, `shared_journey`, `proximity`, `route_path`, `travel_timing`, `eta`); any future regression that re-introduces them will fail the test.

### 10BL-Specific Boundary (Hard — set value)

A same known_tile_ids **set** equality signal is a **public equality signal only**. It records that two agents' public bundle `known_tile_ids` sets were mechanically identical (same opaque identifiers, order-independent). It MUST NOT, and DOES NOT, imply:

- same observation depth
- same knowledge depth
- same route path
- same travel history
- same memory
- same map
- same experience
- same time
- co-presence
- awareness
- interaction
- relationship
- meeting
- collision
- coordination
- cooperation
- shared visit
- having navigated to each other
- being "together"
- any route path, travel timing, or ETA inference

The equality signal **value** is a sanitized, sorted list of opaque tile identifiers. It is not a map, not a path, not a reconstruction, not a depth measure, and not a memory claim. The 10BT envelope must never expose any of the forbidden keys, tokens, or phrases at the public surface. The 10CB test suite explicitly scans the exported decision JSON for the forbidden keys (including `same_observation_depth`, `same_knowledge_depth`, `same_path`, `same_route`, `same_travel`, `same_travel_history`, `same_memory`, `same_map`, `same_experience`, `route_path`, `travel_timing`, `eta`); any future regression that re-introduces them will fail the test.

---

## Hard-Coded Runtime Safety Block

```python
"runtime_allowed": False,
"daemon_allowed": False,
"scheduler_allowed": False,
"network_allowed": False,
```

These flags are unconditionally False. There is no code path in this module that can flip them to True. They are emitted in the same envelope shape on the happy path, on the unknown-contract-type path, on the missing-fields path, and on the non-dict input path.

---

## Claim Boundary (Hard-Coded)

```
public equality signal only; no runtime action, no co-presence,
no awareness, no relationship, no timing inference
```

The claim boundary is fixed. It is one of the few places where `co-presence`, `awareness`, `relationship`, and `timing` may appear in the export — they appear only as **forbidden concepts**, not as asserted facts. Other decision fields never carry these tokens.

---

## Canonical Material for decision_id

```python
decision_material = {
    "decision_schema_version": "10BT.1",
    "consumer_scope": "record_public_equality_signal_only",
    "source_contract_id": source_contract_id,
    "source_contract_type": source_contract_type,
    "source_claim_scope": source_claim_scope,
    "source_merge_hash": source_merge_hash,
    "equality_signal_present": equality_signal_present,
    "equality_signal_type": equality_signal_type,
    "equality_signal_value": equality_signal_value,
}
decision_id = "10BT-" + sha256(canonical_json(decision_material))[:32]
```

`canonical_json` uses sorted keys, `(",", ":")` separators, no whitespace, UTF-8 preservation. Deterministic across runs. Different source contracts yield different `decision_id`s; identical source contracts yield identical `decision_id`s.

---

## Module Import Discipline (Hard Boundaries)

Module imports (exactly these, no others):

```python
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from backend.world.world_event_sanitizer import sanitize_public_mapping
```

Module must **not** import:

- Any daemon, runtime, scheduler, network, Docker, provider, launcher, requests, urllib, asyncio, socket, threading, or subprocess module
- Any phase creator from prior phases (10AP, 10AQ, 10AR, 10AS, 10AT, 10AU, 10AV, 10AW, 10AX, 10AY, 10AZ, 10BA, 10BB, 10BC, 10BD, 10BE, 10BF, 10BG, 10BH, 10BI, 10BJ, 10BK, 10BL, 10BP)
- Anything from `world-sim/data`

Tests verify these via Python `ast` parsing of the module source — comments and docstrings are stripped before checks, so a token merely mentioned in a docstring cannot accidentally clear an import-discipline test.

---

## Behaviour Boundaries (What 10BT Will Never Do)

- Never infer same map, same observation, same knowledge, same snapshot, same event, same sequence, same route, same place, same timing, same active-at-same-time, same tick window, co-presence, awareness, communication, cooperation, conflict, trust, intimacy, relationship, proximity, distance, ETA.
- Never write to a ledger, never record an event, never update public state.
- Never call into a daemon, scheduler, provider, launcher, movement helper, route helper, map helper, or any runtime subsystem.
- Never perform HTTP, RPC, socket, subprocess, threading, or any other side-effect-laden action.
- Never raise an exception for invalid input. Always returns `ok: False` with structured errors.
- Never lift the runtime_allowed / daemon_allowed / scheduler_allowed / network_allowed flags from False.
- Never accept an equality contract whose `ok` is not `True`. (A contract that doesn't self-report `True` cannot be promoted by 10BT into anything.)

---

## Relation to 10BP, 10BN, 10BO, 10BR

- **10BP (shared_public_snapshot_id_equality_contract)** is the first equality contract 10BT can consume. 10BT is contract-agnostic in shape (any structurally-valid contract passes the 5-field check) and has explicit signal-extraction branches for 10BP (`snapshot_id_equality`), 10AY (`snapshot_hash_equality`), 10BJ (`current_tile_id_equality`), 10BK (`route_intent_id_equality`), and 10BL (`known_tile_ids_set_equality`). Other contract types get `unknown_contract_type`.
- **10BN / 10BO** closed the depth surface (no depth equality, rank, order, calendar, shared-depth reconstruction, or enum expansion). 10BT does not reopen any depth surface and does not extract a "depth equality signal."
- **10BR** documented that the public-surface ladder is closed at 10BP and recommended no standalone next-rung candidate except possibly a post-ladder runtime-wiring readiness phase. 10BT is precisely that next step: it does not add new equality rungs and does not wire to live runtime; it prepares the consumer side. 10BT does **not** name or commit to 10BS or any later rung; it only points at the operator decision.

---

## Tests Required

1. Happy path consumes a valid 10BP same-snapshot-id contract (signal present, type correct, source fields all populated).
2. Different snapshot_id contract produces `equality_signal_present = False`.
3. Unknown but structurally-valid contract type is accepted with `equality_signal_type = "unknown_contract_type"`.
4. Invalid non-dict input returns `ok = False` with a clear error.
5. Missing required contract fields return `ok = False` with specific errors and full envelope shape (decision_id=None, contract_seen=False, contract_ok=False, runtime flags False).
6. Output envelope shape is consistent across all four failure paths (None, non-dict string, `{}`, ok=False contract).
7. Input contract is not mutated.
8. decision_id is deterministic.
9. decision_id changes when source_contract_id changes.
10. Exported JSON is stable (re-export is identical strings).
11. File helper works with tempdir JSON file only; never writes elsewhere.
12. Private/redacted strings do not leak into the export.
13. Forbidden inference words are absent from output keys; the single allowed home is `claim_boundary`, where they appear as **forbidden concepts**.
14. `runtime_allowed` / `daemon_allowed` / `scheduler_allowed` / `network_allowed` are always False on every path (happy, unknown, invalid, bad_type).
15. Module source does not import daemon/runtime/scheduler/network/Docker/provider code.
16. Module source does not call any upstream contract creator.
17. All public functions are exercised.

---

## No Implementation Beyond This Spec

10BT declares that the following are strictly forbidden:

- Adding new equality contracts.
- Adding a co-presence, awareness, communication, or relationship rung.
- Opening the depth surface in any direction.
- Wiring into a daemon, scheduler, provider, launcher, runtime, network, or live subscriber.
- Changing public-surface ladder by adding new fields to the 10AS bundle.
- Caching state across calls. Each call is independent.
- Touching `world-sim/data`.
- Force pushes, `--no-verify`, amend, hook bypass.

10BT may be logged in `phase_index.md` and added to the README ladder, plus added to `pure-tests.yml` at the line right after 10BP's entry. Nothing more.
