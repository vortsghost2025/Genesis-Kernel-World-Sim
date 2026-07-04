# Phase 10BB — Shared Public State Hash Equality Contract

## Scope Contract

10BB is a pure public state-hash equality contract over a valid 10AS merge artifact.

10BB consumes a 10AS two-agent public merge for provenance and agent identity only. Public state hashes are supplied as optional caller arguments; 10BB does not read them from 10AS bundles. Caller-supplied public state hashes are sanitized through `sanitize_public_mapping` first; empty strings and non-string items are then dropped. 10BB emits a deterministic, sanitized contract that compares the supplied public state hash strings mechanically.

Public state hashes are opaque sha256-derived strings (e.g., `"sha256-abc123..."`). They are fingerprint metadata, not state content. Comparing public state hash strings does not imply temporal overlap, co-presence, awareness, or any kind of relationship.

10BB may say:

- "Agent A's public state hash is X."
- "Agent B's public state hash is Y."
- "Both agents declare the same public state hash string." (public-surface equality only)

10BB may not say:

- Any claim that hash equality proves identical public-state contents. (state inference)
- "The agents were active at the same time." (co-presence inference)
- "The agents could have met or interacted." (meeting/interaction inference)
- "The agents have a temporal window in common." (window inference)
- "The agents' public state hashes imply a relationship." (relationship inference)
- Anything about awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference.

## Allowed Comparisons

10BB compares only caller-supplied public state hash fields:

- `agent_a_public_state_hash` vs `agent_b_public_state_hash` → `same_public_state_hash` (True only when both non-None, non-empty, and equal)
- `shared_public_state_hash` — populated only when `same_public_state_hash` is True

Public state hashes are treated as opaque strings. No parsing of hash content is performed. No semantic interpretation of the hashed state is performed.

## Forbidden

- No "same state" claim — only "same public_state_hash string"
- No temporal overlap calculation
- No co-presence inference
- No awareness, communication, cooperation, conflict, relationship, trust, proximity, distance, ETA, or route inference
- No hash content parsing or semantic interpretation
- No ordering or sequence inference from hashes
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
  "contract_schema_version": "10BB.1",
  "contract_type": "shared_public_state_hash_equality_contract",
  "contract_id": "10BB-<sha256[:32]>",
  "claim_scope": "shared_public_state_hash_equality_only",
  "source_phase": "10AS",
  "source_merge_id": "...",
  "source_merge_hash": "...",
  "source_merge_schema_version": "10AS.1",
  "agent_a_id": "...",
  "agent_b_id": "...",
  "agent_a_public_state_hash": "sha256-...",
  "agent_b_public_state_hash": "sha256-...",
  "same_public_state_hash": true,
  "shared_public_state_hash": "sha256-...",
  "errors": []
}
```

## Public Functions

- `create_shared_public_state_hash_equality_contract(merge, *, agent_a_public_state_hash=None, agent_b_public_state_hash=None)` — build contract from a valid 10AS merge dict plus optional caller-supplied public state hash strings
- `export_shared_public_state_hash_equality_contract(contract)` — deterministic sanitized JSON string
- `contract_public_state_hash_equality_file(merge_json_path, *, agent_a_public_state_hash=None, agent_b_public_state_hash=None)` — read merge JSON from path, build contract with optional caller-supplied public state hash strings, return result dict

## Determinism

`contract_id` is derived from a canonical material block containing:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id` (preserved in A/B orientation, not sorted)
- `agent_b_id` (preserved in A/B orientation, not sorted)
- `agent_a_public_state_hash`
- `agent_b_public_state_hash`
- `same_public_state_hash`
- `shared_public_state_hash`

The material block is hashed via sha256; `contract_id = "10BB-" + hash[:32]`.

## Sanitization

- Caller-supplied public state hashes are sanitized through `sanitize_public_mapping` first
- After sanitization, empty strings and non-string items are dropped from each agent's hash field
- Redacted sanitizer output participates in comparison if non-empty
- All string values in the final contract pass through `sanitize_public_mapping` before output
- Private markers (paths, credentials, IPs, runtime markers, agent trace markers) must never appear in any output path

## Missing / None Handling

- Missing or `None` caller-supplied public state hash fields produce a contract with `ok=True`, hash fields set to `None`, and all equality booleans set to `False`
- Empty string hash fields are treated as missing

## Test Plan

1. Happy path: both agents declare identical public state hash strings → `same_public_state_hash` is True
2. Different public state hash strings → `same_public_state_hash` is False, `shared_public_state_hash` populated appropriately
3. One side missing hash, other side present → `same_public_state_hash` is False
4. Both sides missing hashes → `same_public_state_hash` is False, all hash fields empty/None
5. Output has exactly required top-level fields; no forbidden fields
6. `contract_id` deterministic across repeated calls
7. `contract_id` changes when any public state hash changes
8. Input mutation guard (deep copy before reading)
9. Structural failures: non-dict, `ok=False`, wrong `merge_type`, wrong `merge_schema_version`, missing `agent_a`/`agent_b`, empty agent ids, same agent ids
10. Type validation failures: hash fields not strings
11. Private markers redacted in exported JSON
12. Graceful handling of missing/None hash fields
13. Stable JSON export / round-trip
14. `contract_public_state_hash_equality_file` reads and builds from path
15. All three public functions exercised
16. Module has no forbidden imports (no 10AP/10AQ/10AR creators, no world-sim/data)
17. Module does not call upstream creators
18. Happy path contains no forbidden tokens (same state, temporal, co-presence, etc.)
19. Boundary: empty string and non-string hash fields are dropped after sanitization
20. Boundary: special characters preserved in hash strings only when sanitizer does not redact them; redacted forms participate in comparison
21. `contract_id` preserves A/B agent orientation (not sorted)
22. Sanitization redacts path/IP markers from hash strings; redacted forms participate in comparison

Target: 22 tests.

## Regression Target

Run full 10AI → 10BB regression; record observed count.

## Next Phase Boundary

After 10BB, the next phase may introduce additional singular-field equality contracts over other 10AS-exposed metadata, but 10BB deliberately stops at mechanical public-state-hash string equality to avoid temporal overlap / co-presence / state inference.

## Relationship to Prior Phases

- 10AY compares snapshot hashes (10AQ layer) as caller-supplied optional kwargs
- 10AZ compares tick ranges (first_tick, last_tick) as caller-supplied optional kwargs
- 10BA compares tick label sets as caller-supplied optional kwargs
- 10BB compares public state hash strings (10AP layer) as caller-supplied optional kwargs
- All consume 10AS for provenance and agent identity only
- None infer temporal overlap, co-presence, awareness, or any kind of relationship
- Together they provide orthogonal mechanical comparisons over public metadata without crossing into forbidden inference
