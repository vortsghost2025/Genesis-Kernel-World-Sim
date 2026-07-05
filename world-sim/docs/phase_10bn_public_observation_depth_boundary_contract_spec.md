# Phase 10BN — Public Observation Depth Boundary Contract

## Status

10BN is a **docs-only boundary contract**:

- not an equality contract
- not a comparison surface
- not an observation-count inference
- not a temporal / co-presence / same-event inference
- not a runtime-wiring change

---

## Boundary Contract Envelope

### Inputs

- A valid 10AS merge artifact (mandatory).
- Caller-supplied `agent_a_depth_token` (string or None).
- Caller-supplied `agent_b_depth_token` (string or None).

### Locked depth-token enum (no open string surface)

- `spot`
- `detailed`
- `broad`
- `scan`
- `survey`
- `None`

### Sanitization rules per token

- non-string → `None`
- empty string → `None`
- string containing `[REDACTED` → `None`
- any sanitized string **not** in the locked enum → reject the contract (no half-built result)
- allowed enum values pass through unchanged

### Identity source (from the valid 10AS merge)

- `agent_a_id = merge["agent_a"]["agent_id"]`
- `agent_b_id = merge["agent_b"]["agent_id"]`
- missing / empty / non-string agent id on either side → `ok=False`
- identical agent ids (after sanitization) → `ok=False`
- no caller-supplied agent ids
- no root-only identity fallback

### Output schema (mandatory fields, in order)

```
ok
contract_schema_version
contract_type
contract_id
source_phase
source_merge_id
source_merge_hash
source_merge_schema_version
agent_a_id
agent_b_id
public_depth_token_a
public_depth_token_b
claim_scope
errors
```

### Envelope rules

- `ok=True` ⇒ `errors=[]`, both depth tokens are sanitized (allowed enum or `None`).
- `ok=False` ⇒ `errors=[...]` listing every rejection reason. Tokens may be `None` on rejection.
- No `accepted` boolean on top of `ok`.
- No equality boolean.
- No `same_depth_token`.
- No `shared_depth_token`.
- No depth score, ranking, ordering, or stronger/weaker inference.

### Claim scope

```
claim_scope = "shared_public_observation_depth_only"
```

This name encodes the boundary: depth is documented as a public declaration surface only and may not promote into a comparison, equivalence, or social claim.

---

## Contract ID Material

`contract_id` is derived from sha256 of canonical material:

- `contract_schema_version`
- `claim_scope`
- `source_merge_id`
- `source_merge_hash`
- `agent_a_id`
- `agent_b_id`
- `public_depth_token_a` (sanitized)
- `public_depth_token_b` (sanitized)

Output format:

```
"10BN-" + sha256(canonical_material)[:32]
```

Rules:
- Source merge anchored (no token-only contract_id).
- A/B orientation preserved (no sort).
- Sanitized tokens only.
- Both branches deterministically equivalent on the same inputs.

---

## May-Say / May-Not-Say

### 10BN may say

- "Agent A's public observation depth token is `<token>`."
- "Agent B's public observation depth token is `<token>`."
- "Agent A's token was rejected: <error>." (rejection path only)
- "Agent B's token was rejected: <error>." (rejection path only)

### 10BN may NOT say

- "Agent A observed more deeply than Agent B." (ranking inference)
- "Agent B observed less deeply than Agent A." (weaker inference)
- "Both agents observed at the same depth." (equality inference)
- "These two agents share the same observation depth surface." (shared inference)
- "Agent A has more private observation data than Agent B." (private-knowledge transfer)
- "Agent B missed something Agent A saw." (hidden-map leakage)
- "Agent A has a deeper observation experience than Agent B." (experience inference)
- Any claim that promotes the depth surface into trust, cooperation, conflict, awareness, co-presence, timing, or relationship inference.

---

## Forbidden Inferences

10BN does not infer any of:

- observation rank, order, or magnitude
- observation-count equality or inequality
- observation-event overlap or coincidence
- temporal overlap, active-at-same-time, or co-presence
- meeting, awareness, communication, interaction, or proximity
- route, path, destination, timing, window, or plan inference
- relationship, trust, cooperation, or conflict inference

---

## Out-of-Scope List

10BN is explicitly out of scope for:

- any 10AP / 10AQ / 10AR direct inputs (10AS merge is the only surface)
- any parent-body rehashing of the 10AS merge
- any full route-intent revalidation
- any true-map lookup, pathfinding, or movement
- any ledger write, candidate event mapping, or verifier inference
- any runtime, daemon, scheduler, provider, Docker, or network activity
- any `world-sim/data` access
- any meeting, awareness, co-presence, or relationship justification
- any distance, ETA, or timing-window inference
- any plan inference
- any depth score, ranking, ordering, or shared-depth reconstruction

---

## Forbidden in 10BN

10BN itself is docs-only. The following are strictly forbidden under any pretext:

- No equality implementation (incl. depth inequality, depth equality, same-depth, shared-depth).
- No new test files.
- No `world-sim/backend/world/*.py` additions or modifications.
- No ledger, mapper, verifier, exporter, or sanitizer changes.
- No docker, daemon, scheduler, or provisioner activity.
- No network access or network-related changes.
- No `world-sim/data` reads or writes.
- No edits to catalog, secrets, credentials, or configuration files.
- No runtime wiring implementation; no first heartbeat; no pilot reactivation.
- No force pushes, no `--no-verify`, no hook bypass, no amend.
- No partial-depth contracts (must be full or rejected).
- No expanding the depth-token enum.

---

## Future-Rung Note

If a future rung proposes anything on top of the 10BN enumeration (e.g., same-depth equality, depth ranking, depth calendarization), it must satisfy the 10BM readiness gate and additionally declare:

- what new dimension the rung introduces beyond the depth surface,
- why it does not relitigate a 10AS bundle scalar,
- why it does not promote observation depth into a comparison or social claim.
