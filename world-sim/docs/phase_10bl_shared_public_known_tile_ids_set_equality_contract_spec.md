# Phase 10BL - Shared Public Known Tile IDs Set Equality Contract

## Scope Contract

10BL is a pure public known-tile-id set-equality contract over a valid 10AS merge artifact.

10BL consumes a valid 10AS merge and reads only the two agent-bundle list fields:

- `merge["agent_a"]["known_tile_ids"]`
- `merge["agent_b"]["known_tile_ids"]`

10BL does not trust the 10AS root `shared_known_tile_ids`, `agent_a_only_known_tile_ids`, or `agent_b_only_known_tile_ids` fields as authority. It recomputes all set algebra from the two sanitized bundle `known_tile_ids` lists.

`known_tile_ids` are opaque public tile identifiers. They are identifiers, not map-knowledge claims, not exploration-history claims, not observation-event claims, not place-at-time claims, and not route, path, destination, timing, or plan claims. Comparing known-tile-id sets does not imply same map knowledge, same exploration history, same observation event, same place, co-presence, awareness, communication, cooperation, conflict, trust, or relationship.

10BL may say:

- "Agent A's public known_tile_ids set is X."
- "Agent B's public known_tile_ids set is Y."
- "Both agents report the same public known_tile_ids set." (public-surface set equality only)
- "These public known_tile_ids are shared between the two bundle lists." (public-surface set algebra only)

10BL may not say:

- "Both agents have the same map knowledge." (map-knowledge inference)
- "Both agents have the same exploration history." (exploration inference)
- "Both agents observed the same event." (observation-event inference)
- "Both agents are in the same place." (place inference)
- "Both agents are co-present." (co-presence inference)
- "Both agents met or interacted." (meeting/interaction inference)
- "Both agents are near or aware of each other." (proximity/awareness inference)
- "Both agents have the same route, path, destination, timing, or plan." (route inference)
- "Both agents have a relationship, trust, cooperation, or conflict." (relationship inference)

## Allowed Comparisons

10BL compares only sanitized set values read from the 10AS agent bundles:

- `agent_a_known_tile_ids` vs `agent_b_known_tile_ids` -> `same_known_tile_ids` (True only when both sanitized sets are non-empty and equal)
- `shared_known_tile_ids` - intersection of both sanitized bundle sets
- `agent_a_only_known_tile_ids` - sanitized bundle tiles in A but not B
- `agent_b_only_known_tile_ids` - sanitized bundle tiles in B but not A
- `agent_a_known_tile_count`, `agent_b_known_tile_count`, `shared_known_tile_count`, `agent_a_only_known_tile_count`, `agent_b_only_known_tile_count` - cardinalities of the output lists

`known_tile_ids` values are treated as opaque strings. No semantic interpretation, topology lookup, adjacency calculation, pathfinding, route planning, destination inference, timing inference, observation-event matching, or map-knowledge inference is performed.

## Forbidden

- No caller-supplied known-tile-id kwargs
- No trusting root `shared_known_tile_ids`, `agent_a_only_known_tile_ids`, or `agent_b_only_known_tile_ids` as authority
- No claim that equal sets prove same map knowledge - only "same public known_tile_ids set"
- No same map knowledge inference
- No same exploration history inference
- No same observation event inference
- No same place inference
- No co-presence inference
- No meeting inference
- No interaction inference
- No proximity or distance inference
- No awareness, communication, cooperation, conflict, relationship, or trust inference
- No route, path, destination, timing, ETA, or plan inference
- No event-content or temporal inference
- No ordering or sequence inference from tile IDs
- No 10AP/10AQ/10AR direct inputs
- No parent-body rehashing
- No full route-intent revalidation
- No true map lookup, topology, adjacency, pathfinding, movement, or ledger write
- No runtime, daemon, provider, Docker, network, or `world-sim/data` access

## Contract Schema

```json
{
  "ok": true,
  "contract_schema_version": "10BL.1",
  "contract_type": "shared_public_known_tile_ids_set_equality_contract",
  "contract_id": "10BL-<sha256[:32]>",
  "claim_scope": "shared_public_known_tile_ids_set_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_known_tile_ids": ["tile_alpha", "tile_beta"],
  "agent_b_known_tile_ids": ["tile_alpha", "tile_gamma"],
  "agent_a_known_tile_count": 2,
  "agent_b_known_tile_count": 2,
  "same_known_tile_ids": false,
  "shared_known_tile_ids": ["tile_alpha"],
  "shared_known_tile_count": 1,
  "agent_a_only_known_tile_ids": ["tile_beta"],
  "agent_a_only_known_tile_count": 1,
  "agent_b_only_known_tile_ids": ["tile_gamma"],
  "agent_b_only_known_tile_count": 1,
  "errors": []
}
```

## Public Functions

- `create_shared_known_tile_ids_set_equality_contract(merge)` - build contract from a valid 10AS merge dict; reads known-tile IDs from agent bundles only
- `export_shared_known_tile_ids_set_equality_contract(contract)` - deterministic sanitized JSON string
- `contract_known_tile_ids_set_equality_file(merge_json_path)` - read merge JSON from path, build contract, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- sorted sanitized `agent_a_known_tile_ids`
- sorted sanitized `agent_b_known_tile_ids`
- `same_known_tile_ids`
- sorted sanitized `shared_known_tile_ids`
- sorted sanitized `agent_a_only_known_tile_ids`
- sorted sanitized `agent_b_only_known_tile_ids`

The material block is hashed via sha256; `contract_id = "10BL-" + hash[:32]`.

## Sanitization

- Each bundle `known_tile_ids` item is sanitized through `sanitize_public_mapping`
- Non-string, empty-after-sanitize, and `[REDACTED`-containing values are dropped
- Remaining values are deduplicated within each agent's list
- Output lists are sorted deterministically
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output

## Missing / None Handling

- Missing, `None`, or non-list bundle `known_tile_ids` values are treated as empty lists
- When both sanitized sets are empty, `same_known_tile_ids` is False
- When either sanitized set is empty, `same_known_tile_ids` is False

## Test Plan

1. Happy path: equal non-empty known-tile sets -> `same_known_tile_ids` is True
2. Different known-tile sets -> `same_known_tile_ids` is False and only lists populate
3. Partial overlap -> shared and only lists are recomputed correctly
4. Disjoint sets -> no shared tiles and both only lists populate
5. One side missing `known_tile_ids` -> empty list and `same_known_tile_ids` False
6. One side `known_tile_ids` is `None` -> empty list and `same_known_tile_ids` False
7. One side `known_tile_ids` is not a list -> empty list and `same_known_tile_ids` False
8. Both sides empty -> `same_known_tile_ids` False
9. Duplicate entries within each bundle are deduplicated
10. Order-insensitive equality still preserves deterministic sorted output
11. Private-marker entries are dropped and never appear in exported JSON
12. Root `shared_known_tile_ids` tampering is ignored
13. Root `agent_a_only_known_tile_ids` / `agent_b_only_known_tile_ids` tampering is ignored
14. Output has exactly required top-level fields; no forbidden fields
15. `contract_id` deterministic across repeated calls
16. `contract_id` changes when a bundle known-tile set changes
17. `contract_id` preserves A/B agent orientation (not sorted)
18. Input mutation guard (deep copy before reading)
19. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
20. Stable JSON export / round-trip
21. `contract_known_tile_ids_set_equality_file` reads and builds from path
22. All three public functions exercised
23. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no `world-sim/data`)
24. Module does not call upstream creators
25. Happy path contains no forbidden inference tokens
26. Boundary: non-string and empty list entries are dropped after sanitization
27. Boundary: root set algebra can contradict bundle lists without affecting the contract

Target: 27 tests.

## Regression Target

Run full 10AI -> 10BL regression; record observed count.

## Boundary Invariant

10BL may only say:

- same public known_tile_ids set

10BL may NOT say:

- same map knowledge
- same exploration history
- same observation event
- same place
- co-presence
- awareness
- route/path/destination/timing/plan
- relationship, trust, cooperation, or conflict

## Relationship to Prior Phases

- 10AS exposes `agent_a.known_tile_ids`, `agent_b.known_tile_ids`, root `shared_known_tile_ids`, root `agent_a_only_known_tile_ids`, and root `agent_b_only_known_tile_ids`.
- 10BL is the dedicated set-equality contract for the two public bundle `known_tile_ids` lists.
- 10BL recomputes all set algebra from the bundle lists and does not trust the 10AS root set-algebra fields as authority.
- 10BL does not compare current tiles, route intents, route destinations, anchors, event refs, territory refs, snapshots, tick ranges, counts, event IDs, or merge IDs.
- 10BL does not infer same map knowledge, same exploration history, same observation event, same place, co-presence, awareness, proximity, route/path/destination/timing/plan, or any kind of relationship.
