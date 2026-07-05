# Phase 10BH — Shared Public First Event ID Equality Contract

## Scope Contract

10BH is a pure public first-event-id equality contract over a valid 10AS merge artifact.

10BH consumes a valid 10AS merge for provenance and agent identity only.

First event IDs are caller-supplied optional scalar kwargs:

- `agent_a_first_event_id`
- `agent_b_first_event_id`

10BH does not read `first_event_id` from 10AS bundles because 10AS bundles do not expose that field.  Caller-supplied first event IDs are validated as non-empty strings; missing, non-string, or empty-after-sanitize values are treated as `None`.  10BH emits a deterministic, sanitized contract that compares the agents' public first event IDs mechanically.

`first_event_id` is an opaque string representing the earliest event ID on an agent's public state surface. It is an identifier, not a temporal claim, not a claim about event content, and not a claim about what the event means. Comparing first event IDs does not imply temporal overlap, co-presence, awareness, or any kind of relationship.

10BH may say:

- "Agent A's public first_event_id is X."
- "Agent B's public first_event_id is Y."
- "Both agents report the same public first_event_id value." (public-surface equality only)

10BH may not say:

- "Both agents experienced the same event." (event-content inference)
- "Both agents were active at the same time." (temporal overlap inference)
- "The agents could have met or interacted." (meeting/interaction inference)
- "The agents have a temporal window in common." (window inference)
- "The agents' first event IDs imply a relationship." (relationship inference)
- Anything about awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference.

## Allowed Comparisons

10BH compares only `first_event_id` values supplied as caller kwargs:

- `agent_a_first_event_id` vs `agent_b_first_event_id` → `same_first_event_id` (True only when both are non-None and equal)
- `shared_first_event_id` — populated only when `same_first_event_id` is True

`first_event_id` values are treated as opaque strings. No semantic interpretation of the ID is performed.

## Forbidden

- No claim that equal IDs prove identical events — only "same first_event_id value"
- No temporal overlap calculation
- No co-presence inference
- No awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference
- No event-content or temporal inference
- No ordering or sequence inference from IDs
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
  "contract_schema_version": "10BH.1",
  "contract_type": "shared_public_first_event_id_equality_contract",
  "contract_id": "10BH-<sha256[:32]>",
  "claim_scope": "shared_public_first_event_id_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_first_event_id": "ev-abc123",
  "agent_b_first_event_id": "ev-abc123",
  "same_first_event_id": true,
  "shared_first_event_id": "ev-abc123",
  "errors": []
}
```

## Public Functions

- `create_shared_first_event_id_equality_contract(merge, *, agent_a_first_event_id=None, agent_b_first_event_id=None)` — build contract from a valid 10AS merge dict; accepts optional caller-supplied first event IDs
- `export_shared_first_event_id_equality_contract(contract)` — deterministic sanitized JSON string
- `contract_first_event_id_equality_file(merge_json_path, *, agent_a_first_event_id=None, agent_b_first_event_id=None)` — read merge JSON from path, build contract, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_first_event_id`
- `agent_b_first_event_id`
- `same_first_event_id`
- `shared_first_event_id`

The material block is hashed via sha256; `contract_id = "10BH-" + hash[:32]`.

## Sanitization

- `first_event_id` values are strings sanitized via `sanitize_public_mapping`; non-string or empty-after-sanitize values become `None`
- Any sanitized value containing `[REDACTED` becomes `None` to prevent sanitizer-collapse false equality
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output

## Missing / None Handling

- Missing, non-string, or empty-after-sanitize caller-supplied `first_event_id` values are treated as `None`
- When either ID is `None`, `same_first_event_id` is False and `shared_first_event_id` is None

## Test Plan

1. Happy path: both caller-supplied first event IDs equal → `same_first_event_id` is True
2. Different caller-supplied first event IDs → `same_first_event_id` is False
3. One caller-supplied first event ID missing/None → `same_first_event_id` is False
4. Both caller-supplied first event IDs missing/None → `same_first_event_id` is False
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when first event ID changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: `first_event_id` not a string or empty after sanitize
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None first event IDs
13. Stable JSON export / round-trip
14. `contract_first_event_id_equality_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (event-content inference, temporal, co-presence, etc.)
19. Boundary: private-marker-like first event ID is sanitized/redacted and never leaks
20. Boundary: empty string first event ID treated as None
21. `contract_id` preserves A/B agent orientation (not sorted)
22. Scalar-only: no list fields in output
23. Scalar-only: event IDs not present beyond id fields

Target: 23 tests.

## Regression Target

Run full 10AI → 10BH regression; record observed count.

## Boundary Invariant

10BH may only say:
- same public first_event_id value

10BH may NOT say:
- same event
- same time
- same sequence
- same interaction
- same relationship

## Relationship to Prior Phases

- 10AY compares bundle-level snapshot hash/id fields when present.
- 10AZ compares tick ranges (first_tick, last_tick) as caller-supplied optional kwargs
- 10BA compares tick label sets as caller-supplied optional kwargs
- 10BB compares public state hash strings (10AP layer) as caller-supplied optional kwargs
- 10BC compares observation_count values (10AP layer) as caller-supplied optional kwargs
- 10BD compares movement_count values (10AP layer) as caller-supplied optional kwargs
- 10BE compares accepted_event_count values (10AP layer) as caller-supplied optional kwargs
- 10BF compares ignored_event_count values (10AP layer) as caller-supplied optional kwargs
- 10BG compares last_event_id values (10AP layer) as caller-supplied optional kwargs
- 10BH compares first_event_id values (10AP layer) as caller-supplied optional kwargs
- All consume a valid 10AS merge for provenance and agent identity; phases whose compared metadata is not exposed by 10AS accept caller-supplied scalar kwargs.
- None infer temporal overlap, co-presence, awareness, or any kind of relationship
- Together they provide orthogonal mechanical comparisons over public metadata without crossing into forbidden inference
