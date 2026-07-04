# Phase 10AY — Shared Public Snapshot Hash Equality Contract

## Status

Planned.  No implementation until the operator approves the scope.

## Purpose

Phase 10AY formalizes whether two agents' known-map snapshots have
identical content fingerprints.  Two agents may share public
observation of tiles (10AT), reference the same public anchor (10AU),
reference the same public event (10AV), publicly route toward the same
destination tile (10AW), cite the same territory ref (10AX), *and* have
identical known-map snapshots, without either agent having private
knowledge of the other.

Snapshot hash data is present in the 10AS agent bundles' `snapshot_hash`
fields.  No caller-supplied override is needed; 10AY reads the bundle
fields directly.  If a bundle lacks `snapshot_hash`, the contract still
builds with empty/False hash fields.

10AY is the last simple public-surface comparison before time/window
logic.  It does not infer how the agents acquired identical knowledge,
whether they communicated, coordinated, or have any kind of
relationship.

## Consumption contract

10AY consumes a Phase 10AS two-agent public merge artifact.

Snapshot hash data comes from the agent bundles' `snapshot_hash` fields.
No caller-supplied arguments are needed.  If a bundle lacks
`snapshot_hash` or the field is empty, that side is treated as having
no known hash.

10AY **must not**:

- import or call any 10AS, 10AR, 10AQ, 10AP, or any earlier phase
  creator function;
- write to any ledger;
- call any projector, route planner, or movement helper;
- spawn processes, open sockets, read environment, read filesystem
  state other than a single caller-supplied JSON file path;
- touch `world-sim/data`.

10AY imports exactly one helper from the public sanitizer
(`sanitize_public_mapping`) — the same helper 10AR, 10AS, 10AT, 10AU,
10AV, 10AW, and 10AX already import — and nothing else from the
upstream stack.

## Allowed and forbidden claims

### 10AY may say

> "Both agents' known-map snapshots have identical content hashes."

> "Both agents' public known-map snapshots are byte-for-byte equal."
> (a public-surface match; no claim of shared private knowledge,
> communication, or awareness)

> "Both agents declare the same snapshot hash."
> (a public-surface match; no claim of how they acquired identical
> knowledge)

### 10AY may not say

> "The agents have the same knowledge."

> "The agents communicated or shared information."

> "The agents coordinated their exploration."

> "The agents are aware of each other."

> "The agents are or were co-present, nearby, or in the same
> location."

> "The agents' identical snapshots imply they have a relationship."

Any claim that promotes a shared snapshot hash into a private
relationship, shared memory, communication, awareness, trust,
cooperation, conflict, temporal overlap, coordination, or joint-planning
claim is forbidden.  The contract's `claim_scope` is
`shared_snapshot_hash_equality_only`; that scope name exists precisely
to make this narrowness visible in the artifact itself.

## Output schema

A 10AY contract is a JSON-serializable dict with these top-level fields:

| field                                   | type                  | notes |
|-----------------------------------------|-----------------------|-------|
| `ok`                                    | `bool`                | `True` only when the input 10AS merge validates and the contract was built successfully |
| `contract_schema_version`               | `str`                 | `"10AY.1"` |
| `contract_type`                         | `str`                 | `"shared_snapshot_hash_equality_contract"` |
| `contract_id`                           | `str \| None`          | `"10AY-" + sha256[:32]` of the canonical contract material; `None` on failure |
| `source_phase`                          | `str`                 | `"10AS"` |
| `source_merge_id`                       | `str \| None`         | the `merge_id` from the input 10AS merge |
| `source_merge_hash`                     | `str \| None`         | sha256 over the canonical sanitized 10AS merge (provenance fingerprint) |
| `source_merge_schema_version`           | `str \| None`         | the `merge_schema_version` from the input 10AS merge |
| `agent_a_id`                            | `str \| None`         | sanitized `agent_a.agent_id` |
| `agent_b_id`                            | `str \| None`         | sanitized `agent_b.agent_id` |
| `shared_known_tile_ids`                 | `list[str]`           | sorted unique intersection of the two agents' `known_tile_ids` (lifted from the 10AS merge) |
| `shared_known_tile_count`               | `int`                 | `len(shared_known_tile_ids)` |
| `same_current_tile`                     | `bool`                | public-surface match: both agents' published `current_tile_id` are equal (no co-presence claim) |
| `shared_current_tile_id`                | `str \| None`         | the matching `current_tile_id` if `same_current_tile`, else `None` |
| `agent_a_snapshot_hash`                 | `str \| None`         | sanitized `snapshot_hash` from agent_a's bundle |
| `agent_b_snapshot_hash`                 | `str \| None`         | sanitized `snapshot_hash` from agent_b's bundle |
| `agent_a_snapshot_id`                   | `str \| None`         | sanitized `snapshot_id` from agent_a's bundle |
| `agent_b_snapshot_id`                   | `str \| None`         | sanitized `snapshot_id` from agent_b's bundle |
| `same_snapshot_hash`                    | `bool`                | `True` only when both agents have a non-empty `snapshot_hash` and they are equal |
| `shared_snapshot_hash`                  | `str \| None`         | the matching snapshot hash when `same_snapshot_hash` is `True`; otherwise `None` |
| `claim_scope`                           | `str`                 | `"shared_snapshot_hash_equality_only"` |
| `errors`                                | `list[str]`           | empty on success; safe human-readable error strings on failure |

### `contract_id` material

`contract_id` is computed as

```
contract_id = "10AY-" + sha256(canonical_json(contract_material))[:32]
```

where `canonical_json` uses `sort_keys=True`, compact separators, and
`ensure_ascii=False`, and `contract_material` is exactly:

```python
{
    "source_merge_id":               <10AS merge_id> or "",
    "agent_a_id":                    <str>,
    "agent_b_id":                    <str>,
    "shared_known_tile_ids":         <sorted list[str]>,
    "same_current_tile":             <bool>,
    "shared_current_tile_id":        <str | "">,
    "agent_a_snapshot_hash":         <str | "">,
    "agent_b_snapshot_hash":         <str | "">,
    "agent_a_snapshot_id":           <str | "">,
    "agent_b_snapshot_id":           <str | "">,
    "same_snapshot_hash":            <bool>,
    "shared_snapshot_hash":          <str | "">,
    "claim_scope":                   "shared_snapshot_hash_equality_only",
}
```

The contract material contains only contract-level public fields.
Raw 10AS bundle internals (public state details, tick values) are
deliberately excluded from the hash input so the contract id remains
stable across repeated calls with the same inputs.

## Validation rules

In order:

1. `merge` is a `dict`.  Otherwise `ok=False` with `"merge must be a
   dict"`.
2. `merge["ok"]` is `True`.  Otherwise `ok=False` with `"merge ok
   flag is not True"`.
3. `merge["merge_type"] == "two_agent_public_merge"`.  Otherwise
   `ok=False`.
4. `merge["merge_schema_version"] == "10AS.1"`.  Otherwise `ok=False`.
   Future 10AS schema bumps must be explicitly allow-listed here
   before 10AY will accept them (same discipline 10AS uses for
   `snapshot_type`).
5. `merge["agent_a"]` and `merge["agent_b"]` are dicts.
6. `agent_a["agent_id"]` and `agent_b["agent_id"]` are non-empty
   strings.
7. `agent_a["agent_id"]` and `agent_b["agent_id"]` are distinct.  A
   shared-public-snapshot-hash-equality contract is between two
   distinct agents; same-agent input is `ok=False` with
   `"agent_a_id and agent_b_id must be distinct"`.
8. `merge["shared_known_tile_ids"]` is a list.  Tile ids that are
   not strings or are empty are dropped before the contract is built.
9. `merge["same_current_tile"]` is a `bool`.
10. Snapshot hash fields are read directly from the sanitized agent
    bundles: `snapshot_hash` and `snapshot_id`.  If a field is missing
    or not of the expected type, it is treated as `None` / empty
    string — the contract still builds with `ok=True` and safe empty
    hash fields.
11. After sanitization, `agent_a["current_tile_id"]` and
    `agent_b["current_tile_id"]` are read for the
    `shared_current_tile_id` derivation.
12. If `same_current_tile` is `True` but the sanitized bundle
    `current_tile_id` values differ, `ok=False` with `"same_current_tile
    is True but agent current_tile_ids differ"` — the same
    internal-consistency guard 10AT, 10AU, 10AV, 10AW, and 10AX use.

If any rule fails, the contract is returned with `ok=False`,
`contract_id=None`, and a non-empty `errors` list.  The function
never raises; it always returns a dict.

## Purity and side effects

The module is pure:

- No filesystem writes.
- No network.
- No environment reads.
- No process spawning.
- No mutation of caller-owned inputs.  All inputs are deep-copied
  before any read.  Only `copy.deepcopy`, `hashlib.sha256`,
  `json.dumps/loads`, `pathlib.Path` for the file helper, and
  `sanitize_public_mapping` from `world_event_sanitizer` are used.

## Public functions

```python
create_shared_snapshot_hash_equality_contract(merge: dict) -> dict
```

Create a deterministic sanitized shared-snapshot-hash-equality contract
from an already-built 10AS two-agent public merge artifact.  Snapshot
hash data is read from the agent bundles' `snapshot_hash` and
`snapshot_id` fields.  Returns a contract dict.  Never raises.

```python
export_shared_snapshot_hash_equality_contract(contract: dict) -> str
```

Export a contract as stable sorted sanitized JSON text.  The contract
is sanitized via `sanitize_public_mapping` before serialization.

```python
contract_snapshot_hash_equality_file(merge_json_path: Path | str) -> dict
```

Read an exported 10AS merge JSON artifact from a caller-supplied path
and create a shared-snapshot-hash-equality contract.  File loading is
JSON-only; the path must refer to a single JSON file containing a 10AS
merge artifact.

## Test plan

`world-sim/tests/test_phase10ay_shared_public_snapshot_hash_equality_contract.py`
must cover:

1. Happy path: a real 10AS merge with both bundles carrying equal
   `snapshot_hash` produces `ok=True`, `contract_schema_version ==
   "10AY.1"`, `contract_type` correct, `contract_id` starting with
   `"10AY-"`, `claim_scope ==
   "shared_snapshot_hash_equality_only"`, empty `errors`,
   `same_snapshot_hash == True`, `shared_snapshot_hash` populated.
2. Different snapshot hashes: when bundles carry different
   `snapshot_hash` values, `same_snapshot_hash == False` and
   `shared_snapshot_hash` is `None`.
3. Output has exactly the required top-level fields; no forbidden
   fields leak (`co_presence`, `met`, `trust`, `cooperation`,
   `conflict`, `awareness`, `communication`, `relationship`,
   `private_*`, `shared_private_*`, `tick_window`, `active_at_same_time`,
   `temporal_overlap`, `route_path`, `travel_timing`, `eta`).
4. `same_current_tile` and `shared_current_tile_id` are lifted from
   the 10AS merge and correctly propagated.
5. `shared_known_tile_ids` and `shared_known_tile_count` are lifted
   from the 10AS merge.
6. `agent_a_snapshot_hash` and `agent_b_snapshot_hash` are read from
   bundles and correctly propagated.
7. `agent_a_snapshot_id` and `agent_b_snapshot_id` are read from
   bundles and correctly propagated.
8. `contract_id` is deterministic across repeated calls with
   identical input.
9. `contract_id` changes when any contract-material field changes
    (including snapshot hash fields).
10. Input mutation guard: caller's `merge` dict is unchanged after the
    call.
11. Non-dict / ok=False / wrong merge_type / wrong merge_schema_version
    / missing agent_a or agent_b / empty agent ids / same agent ids
    → `ok=False` with safe errors.
12. `shared_known_tile_ids` not a list / `same_current_tile` not a
    bool → `ok=False`.
13. `same_current_tile` True but bundle current tiles differ →
    `ok=False` (internal-consistency guard).
14. Private markers planted in the merge (paths, secrets, IPs, agent
    traces, slash-skill refs) are redacted in the contract output
    and in the exported JSON text.
15. Graceful handling of missing `snapshot_hash`: when a 10AS merge
    without bundle-level `snapshot_hash` fields is passed, the
    contract builds with empty/None hash fields and `ok=True`.
16. `export_shared_snapshot_hash_equality_contract` produces stable
    sorted JSON; round-trips through `json.loads`.
17. `contract_snapshot_hash_equality_file` reads an exported 10AS
    merge JSON from a tempdir path and builds a contract.
18. Saturation: all three public functions exercised at least once.
19. Boundary scan: the 10AY module contains no forbidden imports (no
      10AS/10AR/10AQ/10AP creators, no ledger writers, no projectors,
      no network/process/runtime tools, no `world-sim/data`).
20. Module source does not call `create_two_agent_public_merge(` or
      any other upstream creator.
21. Boundary smoke: the full happy-path contract text carries no
      relationship, trust, cooperation, conflict, awareness,
      co-presence, communication, temporal, travel-timing, path, or
      coordination tokens.

All tests are tempdir-only.  No test writes to `world-sim/data`, no
test connects to a provider, runs a daemon, or requires Docker.

## Out of scope for 10AY

- Inferring why two agents have identical snapshots.
- Inferring whether agents communicated, coordinated, or explored
  together.
- Inferring whether agents are or were co-present or nearby.
- Inferring travel timing, ETA, or temporal window overlap.
- Building any kind of joint plan, joint route, joint memory, or
  joint ledger.
- Multi-agent (>2) snapshot hash comparison.
- Mutating any 10AS, 10AR, 10AQ, or 10AP artifact.
- Producing a ledger event.
- Reading the hidden true map or any agent's private observation
  result.
- Anything that would require a daemon, scheduler, provider, Docker,
  or network.

## Forward compatibility

A future phase (10AZ or later) may extend this stack to temporal
window overlap, territory proximity, or multi-agent snapshot
comparison under its own scope contract.  10AY explicitly bans all
communication, coordination, and relationship inferences and encodes
that ban in its `claim_scope` name.
