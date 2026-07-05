# Phase 10BJ - Shared Public Current Tile ID Equality Contract

## Scope Contract

10BJ is a pure public current-tile-id equality contract over a valid 10AS merge artifact.

10BJ consumes a valid 10AS merge and reads only the two scalar bundle fields:

- `merge["agent_a"]["current_tile_id"]`
- `merge["agent_b"]["current_tile_id"]`

10BJ narrows the 10AS `same_current_tile` concept into a dedicated scalar equality contract. It does not use caller-supplied current-tile overrides. It emits a deterministic, sanitized contract that compares the agents' public `current_tile_id` values mechanically.

`current_tile_id` is an opaque public tile identifier. It is an identifier, not a temporal claim, not a claim about physical co-presence, not a route claim, and not a claim about what the tile means. Comparing current tile IDs does not imply same place at same time, meeting, interaction, proximity, awareness, communication, cooperation, conflict, trust, or relationship.

10BJ may say:

- "Agent A's public current_tile_id is X."
- "Agent B's public current_tile_id is Y."
- "Both agents report the same public current_tile_id value." (public-surface equality only)

10BJ may not say:

- "Both agents are in the same place at the same time." (co-presence inference)
- "Both agents met." (meeting inference)
- "Both agents interacted." (interaction inference)
- "Both agents are near each other." (proximity inference)
- "Both agents are aware of each other." (awareness inference)
- "Both agents have the same route/path/destination/timing." (route inference)
- "Both agents have a relationship, trust, cooperation, or conflict." (relationship inference)

## Allowed Comparisons

10BJ compares only sanitized scalar current-tile IDs read from the 10AS agent bundles:

- `agent_a_current_tile_id` vs `agent_b_current_tile_id` -> `same_current_tile_id` (True only when both are non-None and equal)
- `shared_current_tile_id` - populated only when `same_current_tile_id` is True

`current_tile_id` values are treated as opaque strings. No semantic interpretation of the ID is performed.

## Forbidden

- No caller-supplied current-tile-id kwargs
- No claim that equal IDs prove same place at same time - only "same public current_tile_id value"
- No co-presence inference
- No meeting inference
- No interaction inference
- No proximity or distance inference
- No awareness, communication, cooperation, conflict, relationship, trust, route, path, destination, ETA, or timing/window inference
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
  "contract_schema_version": "10BJ.1",
  "contract_type": "shared_public_current_tile_id_equality_contract",
  "contract_id": "10BJ-<sha256[:32]>",
  "claim_scope": "shared_public_current_tile_id_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_current_tile_id": "tile_alpha",
  "agent_b_current_tile_id": "tile_alpha",
  "same_current_tile_id": true,
  "shared_current_tile_id": "tile_alpha",
  "errors": []
}
```

## Public Functions

- `create_shared_current_tile_id_equality_contract(merge)` - build contract from a valid 10AS merge dict; reads current tile IDs from agent bundles
- `export_shared_current_tile_id_equality_contract(contract)` - deterministic sanitized JSON string
- `contract_current_tile_id_equality_file(merge_json_path)` - read merge JSON from path, build contract, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_current_tile_id`
- `agent_b_current_tile_id`
- `same_current_tile_id`
- `shared_current_tile_id`

The material block is hashed via sha256; `contract_id = "10BJ-" + hash[:32]`.

## Sanitization

- `current_tile_id` values are strings sanitized via `sanitize_public_mapping`; non-string or empty-after-sanitize values become `None`
- Any sanitized value containing `[REDACTED` becomes `None` to prevent sanitizer-collapse false equality
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output

## Missing / None Handling

- Missing, non-string, or empty-after-sanitize bundle `current_tile_id` values are treated as `None`
- When either ID is `None`, `same_current_tile_id` is False and `shared_current_tile_id` is None

## Test Plan

1. Happy path: both bundle current tile IDs equal -> `same_current_tile_id` is True
2. Different bundle current tile IDs -> `same_current_tile_id` is False
3. One bundle current tile ID missing/None -> `same_current_tile_id` is False
4. Both bundle current tile IDs missing/None -> `same_current_tile_id` is False
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when current tile ID changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: `current_tile_id` not a string or empty after sanitize
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None current tile IDs
13. Stable JSON export / round-trip
14. `contract_current_tile_id_equality_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (co-presence, meeting, proximity, route, relationship inference, etc.)
19. Boundary: private-marker-like current tile ID is sanitized/redacted and never leaks
20. Boundary: empty string current tile ID treated as None
21. `contract_id` preserves A/B agent orientation (not sorted)
22. Scalar-only: no list fields in output
23. Scalar-only: current tile IDs not present beyond id fields

Target: 23 tests.

## Regression Target

Run full 10AI -> 10BJ regression; record observed count.

## Boundary Invariant

10BJ may only say:
- same public current_tile_id value

10BJ may NOT say:
- same place at same time
- co-present
- met
- interacted
- near
- aware
- same route/path/destination/timing
- relationship, trust, cooperation, or conflict

## Relationship to Prior Phases

- 10AS exposes `agent_a.current_tile_id`, `agent_b.current_tile_id`, and root `same_current_tile` in the public merge.
- 10AT through 10AY reused `same_current_tile` / `shared_current_tile_id` as contextual fields while focusing on other contracts.
- 10BJ is the dedicated scalar equality contract for the two public bundle `current_tile_id` values.
- 10BJ does not compare route destinations, route intents, anchors, event refs, territory refs, snapshots, tick ranges, counts, event IDs, or merge IDs.
- 10BJ does not infer temporal overlap, co-presence, awareness, proximity, or any kind of relationship.
