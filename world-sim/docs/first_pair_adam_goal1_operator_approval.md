# First-Pair Adam Goal 1 — Operator Approval

Docs-only operator-proof record authorizing **exactly one** canonical Adam
GoalRecord creation under the grounded single-use authorization mechanism in
`backend/world/local_single_goal_write.py` and `tests/test_single_goal_write.py`.
This record proves Sean's **repository/operator designation only**. It does
**not** claim external cryptographic identity authentication.

This document does not implement anything, does not open Gate-7, and does not
broaden creation authorization.

---

## 1. Authorization

- **operator**: `Sean`
- **claim_scope**: `operator_proof`
- **authorization_timestamp**: `2026-08-24T11:53:09Z`

## 2. Action

- **action**: `single_goal_create`

### Target

- **target_agent_id**: `genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d`
- **pair_id**: `genesis-first-pair`

### Goal

- **goal_description**: `Understand the shared starting habitat.`
- **goal_status**: `active`
- **created_heartbeat**: `0`
- **max_writes**: `1`

### Scope

Exactly one canonical Adam `GoalRecord` creation.

## 3. Explicit exclusions

NOT authorized by this operator proof:

- Eve goal creation
- a second Adam goal
- different goal text
- movement
- memory write
- relationship write
- world-state (`world_state.json`) write
- world-event ledger write
- heartbeat persistence
- runtime entity creation
- `world-sim/data` write
- 10CP ledger write
- Gate-7 opening
- broad / `FIRST_PAIR_CREATION_AUTHORIZED` creation authorization

## 4. Standing gates

- **FIRST_PAIR_CREATION_AUTHORIZED remains `False`** (governance constant, not
  code-read by the single-goal write path; this authorization is action-specific).
- **Gate-7 remains `CLOSED`**.
- **`operator_proof_ref`** (consumed at seal time) is the goal-specific
  operator-proof commit that records this doc, **not** the earlier provenance
  source-approval commit `8dc714f3a66975eb2543ca780f59e35d9af02e93`.

## 5. Boundary citation

The write path is grounded on the source-established authority boundary
verified against live source:

- `goals.json` is First-Pair **authoritative agent-state** in
  `.runtime/first-pair/` (scoped by `FirstPairPersistenceStore` as an isolated
  repository-local runtime directory that does not touch `world-sim/data`).
- `FirstPairPersistenceStore` is its legitimate persistence authority.
- 10CP is the append-only **runtime-adapter audit-ledger** writer for
  `world-sim/data/runtime_adapter_ledger/` and does **not** author this goal
  mutation.
- No world-event ledger mutation is required for goal-intent persistence.
- `provenance.jsonl` is the evidence surface used by this path
  (`single_goal_created`, `single_goal_authorization_consumed`).

## 6. Authorized writes (exhaustive)

1. Exactly one goal-specific operator-proof Git commit recording this doc.
2. Exactly one canonical Adam goal write via `write_single_goal(...)` with the
   grounded single-use authorization (sealed against the new commit SHA).

NO other write is authorized.
