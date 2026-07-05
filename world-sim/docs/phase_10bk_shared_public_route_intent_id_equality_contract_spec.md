# Phase 10BK - Shared Public Route Intent ID Equality Contract

## Scope Contract

10BK is a pure public route-intent-id equality contract over a valid 10AS merge artifact.

10BK consumes a valid 10AS merge and reads only the two scalar bundle fields:

- `merge["agent_a"]["route_intent_id"]`
- `merge["agent_b"]["route_intent_id"]`

10BK narrows the 10AS public route-intent exposure into a dedicated scalar equality contract. It does not use caller-supplied route-intent-id overrides. It emits a deterministic, sanitized contract that compares the agents' public `route_intent_id` values mechanically.

`route_intent_id` is an opaque public route-intent identifier. It is an identifier, not a route, not a path, not a destination, not a plan, and not a timing claim. Comparing route-intent IDs does not imply same route, same path, same destination, same timing, same plan, co-presence, meeting, interaction, proximity, awareness, communication, cooperation, conflict, trust, or relationship.

10BK may say:

- "Agent A's public route_intent_id is X."
- "Agent B's public route_intent_id is Y."
- "Both agents report the same public route_intent_id value." (public-surface equality only)

10BK may not say:

- "Both agents have the same route." (route inference)
- "Both agents have the same path." (path inference)
- "Both agents have the same destination." (destination inference)
- "Both agents have the same timing." (timing inference)
- "Both agents have the same plan." (plan inference)
- "Both agents are co-present." (co-presence inference)
- "Both agents met or interacted." (meeting/interaction inference)
- "Both agents are near or aware of each other." (proximity/awareness inference)
- "Both agents have a relationship, trust, cooperation, or conflict." (relationship inference)

## Allowed Comparisons

10BK compares only sanitized scalar route-intent IDs read from the 10AS agent bundles:

- `agent_a_route_intent_id` vs `agent_b_route_intent_id` -> `same_route_intent_id` (True only when both are non-None and equal)
- `shared_route_intent_id` - populated only when `same_route_intent_id` is True

`route_intent_id` values are treated as opaque strings. No semantic interpretation of the ID is performed.

## Forbidden

- No caller-supplied route-intent-id kwargs
- No claim that equal IDs prove same route - only "same public route_intent_id value"
- No route inference
- No path inference
- No destination inference
- No timing or ETA inference
- No plan inference
- No co-presence inference
- No meeting inference
- No interaction inference
- No proximity or distance inference
- No awareness, communication, cooperation, conflict, relationship, or trust inference
- No event-content or temporal inference
- No ordering or sequence inference from IDs
- No 10AP/10AQ/10AR direct inputs
- No parent-body rehashing
- No full route-intent revalidation
- No true map lookup, pathfinding, movement, ledger write
- No runtime, daemon, provider, Docker, network, `world-sim/data` access

## Contract Schema

```json
{
  "ok": true,
  "contract_schema_version": "10BK.1",
  "contract_type": "shared_public_route_intent_id_equality_contract",
  "contract_id": "10BK-<sha256[:32]>",
  "claim_scope": "shared_public_route_intent_id_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_route_intent_id": "10AR-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "agent_b_route_intent_id": "10AR-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "same_route_intent_id": true,
  "shared_route_intent_id": "10AR-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "errors": []
}
```

## Public Functions

- `create_shared_route_intent_id_equality_contract(merge)` - build contract from a valid 10AS merge dict; reads route-intent IDs from agent bundles
- `export_shared_route_intent_id_equality_contract(contract)` - deterministic sanitized JSON string
- `contract_route_intent_id_equality_file(merge_json_path)` - read merge JSON from path, build contract, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_route_intent_id`
- `agent_b_route_intent_id`
- `same_route_intent_id`
- `shared_route_intent_id`

The material block is hashed via sha256; `contract_id = "10BK-" + hash[:32]`.

## Sanitization

- `route_intent_id` values are strings sanitized via `sanitize_public_mapping`; non-string or empty-after-sanitize values become `None`
- Any sanitized value containing `[REDACTED` becomes `None` to prevent sanitizer-collapse false equality
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output

## Missing / None Handling

- Missing, non-string, or empty-after-sanitize bundle `route_intent_id` values are treated as `None`
- When either ID is `None`, `same_route_intent_id` is False and `shared_route_intent_id` is None

## Test Plan

1. Happy path: both bundle route-intent IDs equal -> `same_route_intent_id` is True
2. Different bundle route-intent IDs -> `same_route_intent_id` is False
3. One bundle route-intent ID missing/None -> `same_route_intent_id` is False
4. Both bundle route-intent IDs missing/None -> `same_route_intent_id` is False
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when route-intent ID changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: `route_intent_id` not a string or empty after sanitize
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None route-intent IDs
13. Stable JSON export / round-trip
14. `contract_route_intent_id_equality_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (route, path, destination, timing, plan, co-presence, meeting, proximity, relationship inference, etc.)
19. Boundary: private-marker-like route-intent ID is sanitized/redacted and never leaks
20. Boundary: empty string route-intent ID treated as None
21. `contract_id` preserves A/B agent orientation (not sorted)
22. Scalar-only: no list fields in output
23. Scalar-only: route-intent IDs not present beyond id fields

Target: 23 tests.

## Regression Target

Run full 10AI -> 10BK regression; record observed count.

## Boundary Invariant

10BK may only say:
- same public route_intent_id value

10BK may NOT say:
- same route
- same path
- same destination
- same timing
- same plan
- co-present
- met
- interacted
- near
- aware
- relationship, trust, cooperation, or conflict

## Relationship to Prior Phases

- 10AS exposes `agent_a.route_intent_id`, `agent_b.route_intent_id`, and root `both_have_route_intent` in the public merge.
- 10AW is the dedicated route-destination contract and compares `route_destination_tile_id` plus `route_destination_known` only.
- 10BK is the dedicated scalar equality contract for the two public bundle `route_intent_id` values.
- 10BK does not compare route destinations, current tiles, anchors, event refs, territory refs, snapshots, tick ranges, counts, event IDs, or merge IDs.
- 10BK does not infer route sameness, path sameness, destination sameness, timing sameness, plan sameness, co-presence, awareness, proximity, or any kind of relationship.
