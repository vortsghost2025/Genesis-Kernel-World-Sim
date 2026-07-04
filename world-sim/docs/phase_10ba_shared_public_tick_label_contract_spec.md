# Phase 10BA — Shared Public Tick Label Contract

## Scope Contract

10BA is a pure public tick-label equality contract over a valid 10AS merge artifact.

10BA consumes a 10AS two-agent public merge for provenance and agent identity only. Tick labels are supplied as optional caller arguments; 10BA does not read them from 10AS bundles. Caller-supplied tick labels are sanitized through `sanitize_public_mapping` first; empty strings and non-string items are then dropped; remaining labels are deduplicated; the resulting sanitized label sets are what 10BA compares. 10BA emits a deterministic, sanitized contract that compares the supplied tick labels mechanically.

Tick labels are opaque string identifiers attached to ticks (e.g., `"tick-0001"`, `"heartbeat-42"`, `"cycle-A"`). They are metadata, not timing data. Comparing tick labels does not imply temporal overlap, co-presence, awareness, or any kind of relationship.

10BA may say:

- "Agent A's public tick label is X."
- "Agent B's public tick label is Y."
- "Both agents declare the same tick label." (public-surface equality only)
- "Agent A declares tick labels X and Y." (public-surface enumeration only)
- "Agent B declares tick labels X and Y." (public-surface enumeration only)
- "Both agents declare the same set of tick labels." (public-surface set equality only)

10BA may not say:

- "The agents' ticks overlap in time." (temporal overlap inference)
- "The agents were active at the same time." (co-presence inference)
- "The agents could have met or interacted." (meeting/interaction inference)
- "The agents share a temporal window." (window inference)
- "The agents' tick sequences are synchronized." (synchronization inference)
- "The agents' tick labels imply a relationship." (relationship inference)
- Anything about awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference.

## Allowed Comparisons

10BA compares only caller-supplied tick label fields:

- `agent_a_tick_labels` vs `agent_b_tick_labels` → `same_tick_labels` (True only when both non-None, non-empty, and set-equal)
- `shared_tick_labels` — intersection of both agents' tick label sets
- `agent_a_only_tick_labels` — labels in A but not B
- `agent_b_only_tick_labels` — labels in B but not A
- `agent_a_tick_label_count`, `agent_b_tick_label_count` — cardinalities always propagated

Tick labels are treated as opaque strings. No parsing of tick label content is performed. No ordering or sequence inference is performed. All shared/only/same_tick_labels fields are computed from the sanitized, deduplicated label sets only.

## Forbidden

- No temporal overlap calculation
- No co-presence inference
- No awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference
- No tick label content parsing or semantic interpretation
- No ordering or sequence inference from tick labels
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
  "contract_schema_version": "10BA.1",
  "contract_type": "shared_public_tick_label_contract",
  "contract_id": "10BA-<sha256[:32]>",
  "claim_scope": "shared_tick_label_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_tick_labels": ["tick-0001", "tick-0002"],
  "agent_b_tick_labels": ["tick-0001", "tick-0003"],
  "agent_a_tick_label_count": 2,
  "agent_b_tick_label_count": 2,
  "same_tick_labels": false,
  "shared_tick_labels": ["tick-0001"],
  "shared_tick_label_count": 1,
  "agent_a_only_tick_labels": ["tick-0002"],
  "agent_a_only_tick_label_count": 1,
  "agent_b_only_tick_labels": ["tick-0003"],
  "agent_b_only_tick_label_count": 1,
  "errors": []
}
```

## Public Functions

- `create_shared_tick_label_contract(merge, *, agent_a_tick_labels=None, agent_b_tick_labels=None)` — build contract from a valid 10AS merge dict plus optional caller-supplied tick label lists
- `export_shared_tick_label_contract(contract)` — deterministic sanitized JSON string
- `contract_tick_label_file(merge_json_path, *, agent_a_tick_labels=None, agent_b_tick_labels=None)` — read merge JSON from path, build contract with optional caller-supplied tick label lists, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:
- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- sorted sanitized `agent_a_tick_labels` list
- sorted sanitized `agent_b_tick_labels` list
- `same_tick_labels`
- sorted sanitized `shared_tick_labels` list
- sorted sanitized `agent_a_only_tick_labels` list
- sorted sanitized `agent_b_only_tick_labels` list

The material block is hashed via sha256; `contract_id = "10BA-" + hash[:32]`.

## Sanitization

- Caller-supplied tick labels are sanitized through `sanitize_public_mapping` first
- After sanitization, empty strings and non-string items are dropped from each agent's label list
- After dropping, remaining labels are deduplicated within each agent's list
- Special characters are preserved in labels only when `sanitize_public_mapping` does not redact them; if the sanitizer redacts a label, the redacted form is what participates in set operations and appears in output
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output path
- Tick labels are treated as opaque strings; no semantic interpretation is performed

## Test Plan

1. Happy path: both agents declare identical tick label sets → `same_tick_labels` is True
2. Different tick label sets → `same_tick_labels` is False, intersection/only lists populated
3. One side missing tick labels, other side present → `same_tick_labels` is False
4. Both sides missing tick labels → `same_tick_labels` is False, all label lists empty
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when any tick label set changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: tick labels not list of strings
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None tick labels
13. Stable JSON export / round-trip
14. `contract_tick_label_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (overlap, co-presence, temporal, etc.)
19. Boundary: empty string and non-string tick labels are dropped after sanitization; only valid sanitized strings participate in set operations
20. Boundary: duplicate tick labels within a single agent's list are deduplicated after sanitization
21. Boundary: special characters preserved in tick labels only when sanitizer does not redact them; redacted forms participate in set operations

Target: 25 tests.

## Regression Target

10AI → 10BA: expected 575+ passed.

## Next Phase Boundary

After 10BA, the next phase may introduce explicit temporal-bounded comparisons with explicit window boundaries, but 10BA deliberately stops at mechanical tick-label set equality to avoid temporal overlap / co-presence / ordering inference.

## Relationship to Prior Phases

- 10AZ compares tick *ranges* (first_tick, last_tick) as optional caller-supplied integer fields
- 10BA compares tick *labels* as optional caller-supplied string lists
- Neither reads tick data from 10AS bundles
- Neither infers temporal overlap, co-presence, or ordering
- Together they provide two orthogonal mechanical comparisons over tick metadata without crossing into temporal inference
