# Phase 10BF — Shared Public Ignored Event Count Equality Contract

## Scope Contract

10BF is a pure public ignored-event-count equality contract over a valid 10AS merge artifact.

10BF consumes a valid 10AS merge for provenance and agent identity only.

Ignored event counts are caller-supplied optional scalar kwargs:

- `agent_a_ignored_event_count`
- `agent_b_ignored_event_count`

10BF does not read `ignored_event_count` from 10AS bundles because 10AS bundles do not expose that field.  Caller-supplied ignored event counts are validated as non-negative integers; missing, non-integer, or negative values are treated as `None`.  10BF emits a deterministic, sanitized contract that compares the agents' public ignored event counts mechanically.

`ignored_event_count` is a non-negative integer representing how many events an agent ignored on its public state surface. It is a metadata counter, not a temporal claim, not a spatial claim, and not a claim about which events were ignored. Comparing ignored event counts does not imply temporal overlap, co-presence, awareness, or any kind of relationship.

10BF may say:

- "Agent A's public ignored_event_count is N."
- "Agent B's public ignored_event_count is M."
- "Both agents report the same public ignored_event_count value." (public-surface equality only)

10BF may not say:

- "Both agents ignored the same events." (event-content inference)
- "Both agents ignored events at the same time." (temporal overlap inference)
- "The agents could have met or interacted." (meeting/interaction inference)
- "The agents have a temporal window in common." (window inference)
- "The agents' ignored event counts imply a relationship." (relationship inference)
- Anything about awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference.

## Allowed Comparisons

10BF compares only `ignored_event_count` values supplied as caller kwargs:

- `agent_a_ignored_event_count` vs `agent_b_ignored_event_count` → `same_ignored_event_count` (True only when both are non-None and equal)
- `shared_ignored_event_count` — populated only when `same_ignored_event_count` is True

`ignored_event_count` values are treated as opaque integers. No semantic interpretation of the count is performed.

## Forbidden

- No claim that equal counts prove identical ignored events — only "same ignored_event_count value"
- No temporal overlap calculation
- No co-presence inference
- No awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference
- No event-content or temporal inference
- No ordering or sequence inference from counts
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
  "contract_schema_version": "10BF.1",
  "contract_type": "shared_public_ignored_event_count_equality_contract",
  "contract_id": "10BF-<sha256[:32]>",
  "claim_scope": "shared_public_ignored_event_count_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_ignored_event_count": 3,
  "agent_b_ignored_event_count": 5,
  "same_ignored_event_count": false,
  "shared_ignored_event_count": null,
  "errors": []
}
```

## Public Functions

- `create_shared_ignored_event_count_equality_contract(merge, *, agent_a_ignored_event_count=None, agent_b_ignored_event_count=None)` — build contract from a valid 10AS merge dict; accepts optional caller-supplied ignored event counts
- `export_shared_ignored_event_count_equality_contract(contract)` — deterministic sanitized JSON string
- `contract_ignored_event_count_equality_file(merge_json_path)` — read merge JSON from path, build contract, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_ignored_event_count`
- `agent_b_ignored_event_count`
- `same_ignored_event_count`
- `shared_ignored_event_count`

The material block is hashed via sha256; `contract_id = "10BF-" + hash[:32]`.

## Sanitization

- `ignored_event_count` values are integers; no string sanitization is required for the count fields themselves
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output path

## Missing / None Handling

- Missing, non-integer, or negative caller-supplied `ignored_event_count` values are treated as `None`
- When either count is `None`, `same_ignored_event_count` is False and `shared_ignored_event_count` is None

## Test Plan

1. Happy path: both caller-supplied ignored event counts equal → `same_ignored_event_count` is True
2. Different caller-supplied ignored event counts → `same_ignored_event_count` is False
3. One caller-supplied ignored event count missing/None → `same_ignored_event_count` is False
4. Both caller-supplied ignored event counts missing/None → `same_ignored_event_count` is False
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when ignored event count changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: `ignored_event_count` not an integer
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None ignored event counts
13. Stable JSON export / round-trip
14. `contract_ignored_event_count_equality_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (event-content inference, temporal, co-presence, etc.)
19. Boundary: negative ignored_event_count treated as None
20. Boundary: zero ignored_event_count handled correctly
21. `contract_id` preserves A/B agent orientation (not sorted)

Target: 21 tests.

## Regression Target

Run full 10AI → 10BF regression; record observed count.

## Next Phase Boundary

After 10BF, additional singular-field equality contracts over public-state metadata supplied as caller kwargs (e.g., `public_state_hash`, `observation_count`, `movement_count`, `accepted_event_count`, `ignored_event_count`) are safe next steps. 10BF deliberately stops at mechanical ignored-event-count equality to avoid temporal overlap / co-presence / event-content inference.

## Relationship to Prior Phases

- 10AY compares bundle-level snapshot hash/id fields when present.
- 10AZ compares tick ranges (first_tick, last_tick) as caller-supplied optional kwargs
- 10BA compares tick label sets as caller-supplied optional kwargs
- 10BB compares public state hash strings (10AP layer) as caller-supplied optional kwargs
- 10BC compares observation_count values (10AP layer) as caller-supplied optional kwargs
- 10BD compares movement_count values (10AP layer) as caller-supplied optional kwargs
- 10BE compares accepted_event_count values (10AP layer) as caller-supplied optional kwargs
- 10BF compares ignored_event_count values (10AP layer) as caller-supplied optional kwargs
- All consume a valid 10AS merge for provenance and agent identity; phases whose compared metadata is not exposed by 10AS accept caller-supplied scalar kwargs.
- None infer temporal overlap, co-presence, awareness, or any kind of relationship
- Together they provide orthogonal mechanical comparisons over public metadata without crossing into forbidden inference
