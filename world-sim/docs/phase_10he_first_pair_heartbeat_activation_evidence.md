# First Pair Heartbeat Activation Evidence — Tick 0

Untracked working-tree audit evidence. Records the first canonical observe-only
Adam/Eve heartbeat execution. No persistence, no state, no commit, no push.

- **operator_authorization_timestamp**: `2026-08-24T03:50:14Z` (the provenance
  / operator authorization timestamp for the source artifacts and this
  activation invocation)
- **heartbeat_execution_timestamp**: `NOT_CAPTURED` (the exact wall-clock time
  of heartbeat execution was not recorded; not invented or backdated)
- **model used**: `deepseek-ai/deepseek-v4-flash-0731` under the explicit
  operator model-policy override (Sean)

## Operator proof

- **operator-proof commit**: `8dc714f3a66975eb2543ca780f59e35d9af02e93`
- **provenance source**: `world-sim/docs/first_pair_identity_spec.md`
- **source SHA-256**: `360e1c916afa9bc1e1d792e90ebb0b46afe7bec07f7a7db8e80d85aa2fceaac4`

## Provenance commitments

- **Adam provenance commitment**: `691e3c72e1318e7724c2625c03b7b7c2b04ede5f4da9eca9c252732d631238aa`
- **Eve provenance commitment**: `3df3c9d905d99a7bc930ad1c61dcab27364d24e581f70a7603da5a9f8a1bef3c`

## Rollback anchor (pre-persistence absent state)

- **rollback_anchor_id**: `genesis.first_pair.absent_state.tick0.20260824`
- **habitat_id**: `genesis-first-habitat`
- **claim_scope**: `operator_proof`
- **absent-state commitment**: `21272020352a0788dc7aae39f098d8a3b9fb1388a8998d05d1038c1a4498d6c7`
  (derived by `first_pair_absent_state_commitment()` only because the canonical
  persistence authority is actually empty).
- **rollback_anchor_id is an invocation-level caller-supplied safe identifier
  under 10IH; it is NOT promoted to a globally canonical Genesis identifier.**

## Birth candidate

- **birth_candidate_id**: `10IC-4e0d3a239718211f2099fbc1c97829b5`
- **pair_id**: `genesis-first-pair`
- **Adam agent_id**: `genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d`
- **Eve agent_id**: `genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211`

## Heartbeats — tick 0

### Adam
- **proof**: PASS — `ok=true`, `status=verified_observation_only`, `heartbeat_verified=true`
- **heartbeat_proof_id**: `10IC-HB-a58a01ca307b0125df0f93a76b0ff168`
- **tick**: `0` · action `observe` · claim_scope `observed` · canonical_agent_ref `east_adam`
- **observation**: `{"current_tile_id":"public-start-adam","visible_tile_ids":["public-start-adam"],"summary":"Canonical Adam observe-only first step at tick zero on the public starting tile."}`

### Eve
- **proof**: PASS — `ok=true`, `status=verified_observation_only`, `heartbeat_verified=true`
- **heartbeat_proof_id**: `10IC-HB-e562126b8f63f9824fc1f118fe9dc4a4`
- **tick**: `0` · action `observe` · claim_scope `observed` · canonical_agent_ref `east_eve`
- **observation**: `{"current_tile_id":"public-start-eve","visible_tile_ids":["public-start-eve"],"summary":"Canonical Eve observe-only first step at tick zero on the public starting tile."}`

Both results: `runtime_executed=false, runtime_entity_created=false, persisted=false,
memory_written=false, ledger_written=false, write_attempted=false,
model_called=false, provider_called=false, network_called=false`,
plus all runtime/daemon/scheduler/network/gate7 flags `false`.

## Persistence manifest

- **before** (canonical `.runtime/first-pair/`): EMPTY
- **after** (canonical `.runtime/first-pair/`): EMPTY
- **authoritative persistence entries**: `0`

## Tests

- 10IN focused: 8 passed
- absent-state focused: 10 passed
- 10IC suite: 75 passed
- Combined: 93 passed

## Authorization / gate state

- **FIRST_PAIR_CREATION_AUTHORIZED**: `False`
- **Gate-7**: CLOSED
- **Pushed**: NO
- **Committed** (this artifact): NO — untracked working-tree evidence only.

## Durable observation state

- **FIRST_PAIR_CANONICAL_OBSERVATION_COMPLETED**: `YES` — the canonical
  Adam and Eve observe-only heartbeats at tick 0 completed and verified.
- This records a completed observation verification. It does **not** assert
  `FIRST_PAIR_OBSERVATION_ACTIVE`: the heartbeat is inert (zero-write,
  `runtime_executed=false`), so no ongoing active First-Pair runtime exists
  unless a later authorized source establishes one.