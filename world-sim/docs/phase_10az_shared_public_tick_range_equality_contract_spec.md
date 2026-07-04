# Phase 10AZ — Shared Public Tick-Range Equality Contract

## Scope Contract

10AZ is a pure public tick-range equality contract over a valid 10AS merge artifact.

10AZ consumes a 10AS two-agent public merge for provenance and agent identity only. Tick ranges (`first_tick`, `last_tick`) are supplied as optional caller arguments; 10AZ does not read them from 10AS bundles. 10AZ emits a deterministic, sanitized contract that compares the supplied tick ranges mechanically.

10AZ may say:

- "Agent A's public tick range is [X, Y]."
- "Agent B's public tick range is [X, Y]."
- "Both agents declare the same first tick." (public-surface equality only)
- "Both agents declare the same last tick." (public-surface equality only)
- "Both agents declare identical public tick ranges." (public-surface equality only)

10AZ may not say:

- "The agents' tick ranges overlap." (temporal overlap inference)
- "The agents were active at the same time." (co-presence inference)
- "The agents could have met or interacted." (meeting/interaction inference)
- "The agents' activity periods coincide." (temporal relationship inference)
- Anything about awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference.
- "The agents share a temporal window." (window inference)

## Allowed Comparisons

10AZ compares only caller-supplied tick fields:

- `agent_a_first_tick` vs `agent_b_first_tick` → `same_first_tick` (True only when both non-None and equal)
- `agent_a_last_tick` vs `agent_b_last_tick` → `same_last_tick` (True only when both non-None and equal)
- `agent_a_first_tick` and `agent_a_last_tick` as a pair vs `agent_b_first_tick` and `agent_b_last_tick` as a pair → `same_tick_range` (True only when both pairs are non-None and identical)
- `agent_a_first_tick`, `agent_a_last_tick`, `agent_b_first_tick`, `agent_b_last_tick` always propagated as individual fields (None when not supplied)

When caller-supplied tick fields are missing or None, the contract builds with `ok=True`, tick fields set to None, and all equality booleans set to False.

## Forbidden

- No temporal overlap calculation
- No co-presence inference
- No awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference
- No 10AP/10AQ/10AR direct inputs
- No parent-body rehashing
- No full route-intent revalidation
- No true map lookup, pathfinding, movement, ledger write
- No runtime, daemon, provider, Docker, network, `world-sim/data` access
- No meeting inference

## Contract Schema

```json
{
  "ok": true,
  "contract_schema_version": "10AZ.1",
  "contract_type": "shared_public_tick_range_equality_contract",
  "contract_id": "10AZ-<sha256[:32]>",
  "claim_scope": "shared_tick_range_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_first_tick": 1,
  "agent_a_last_tick": 10,
  "agent_b_first_tick": 1,
  "agent_b_last_tick": 10,
  "same_first_tick": true,
  "same_last_tick": true,
  "same_tick_range": true,
  "errors": []
}
```

## Public Functions

- `create_shared_tick_range_equality_contract(merge, *, agent_a_first_tick=None, agent_a_last_tick=None, agent_b_first_tick=None, agent_b_last_tick=None)` — build contract from a valid 10AS merge dict plus optional caller-supplied tick fields
- `export_shared_tick_range_equality_contract(contract)` — deterministic sanitized JSON string
- `contract_tick_range_equality_file(merge_json_path, *, agent_a_first_tick=None, agent_a_last_tick=None, agent_b_first_tick=None, agent_b_last_tick=None)` — read merge JSON from path, build contract with optional caller-supplied tick fields, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:
- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_first_tick`, `agent_a_last_tick`, `agent_b_first_tick`, `agent_b_last_tick`
- `same_first_tick`, `same_last_tick`, `same_tick_range`

The material block is hashed via sha256; `contract_id = "10AZ-" + hash[:32]`.

## Sanitization

- All string values pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output path
- `agent_a_first_tick`, `agent_a_last_tick`, `agent_b_first_tick`, `agent_b_last_tick` are integers; no sanitization needed for integers

## Test Plan

1. Happy path: both agents declare identical tick ranges → `same_tick_range` is True
2. Different `first_tick` → `same_first_tick` is False
3. Different `last_tick` → `same_last_tick` is False
4. Same `first_tick` and `last_tick` but different agents → `same_tick_range` is True
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when any compared tick value changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: `first_tick`/`last_tick` not int
11. `same_tick_range` internal consistency guard: `same_first_tick` and `same_last_tick` must both be True for `same_tick_range` to be True
12. Private markers redacted in exported JSON
13. Graceful handling of missing `first_tick`/`last_tick` (None or missing keys)
14. Stable JSON export / round-trip
15. `contract_tick_range_equality_file` reads and builds from path
16. All three public functions exercised
17. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
18. Module does not call upstream creators
19. Happy path contains no forbidden tokens (overlap, co-presence, temporal, etc.)
20. Boundary: `first_tick` > `last_tick` is allowed (public declaration, not validated)
21. Boundary: negative tick values are allowed (public declaration, not validated)

Target: 25 tests.

## Regression Target

10AI → 10AZ: expected 550+ passed.

## Next Phase Boundary

After 10AZ, the next phase (10BA?) may introduce explicit shared-window or temporal-bounded comparisons, but 10AZ deliberately stops at mechanical tick-range equality to avoid temporal overlap / co-presence inference.
