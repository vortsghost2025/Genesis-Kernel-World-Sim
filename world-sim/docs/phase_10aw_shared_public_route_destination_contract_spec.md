# Phase 10AW — Shared Public Route Destination Contract

## Status

Planned.  No implementation until the operator approves the scope.

## Purpose

Phase 10AW formalizes which public route destinations two agents have
each declared in their already-public surfaces.  Two agents may share
public observation of a tile (10AT), reference the same public anchor
(10AU), reference the same public event (10AV), *and* both
publicly declare a route toward the same destination tile, without either
agent having private knowledge of the other.

Route destination data comes from the 10AS agent bundles when present.
If the bundles do not carry `route_destination_tile_id`, the caller may
supply them directly as optional arguments — no 10AS update is required.

10AW is the next rung in the public-observation contract stack.  It does
not infer travel direction, travel timing, route path, co-presence,
proximity, coordination, planning, awareness, or any kind of relationship.

## Consumption contract

10AW consumes a Phase 10AS two-agent public merge artifact.

Route destination data comes from one of two paths:

1. **Bundle field (preferred):** `agent_a.route_destination_tile_id`,
   `agent_a.route_destination_known`, `agent_b.route_destination_tile_id`,
   and `agent_b.route_destination_known` in the sanitized 10AS agent
   bundles.  When present, they are used directly.
2. **Caller-supplied (fallback):** optional `agent_a_route_destination`
   and `agent_b_route_destination` arguments to the creator function.
   These override the bundle fields when provided.  This path exists so
   10AW can be implemented and tested without a 10AS update.

10AW **must not**:

- import or call any 10AS, 10AR, 10AQ, 10AP, or any earlier phase
  creator function;
- write to any ledger;
- call any projector, route planner, or movement helper;
- spawn processes, open sockets, read environment, read filesystem
  state other than a single caller-supplied JSON file path;
- touch `world-sim/data`.

10AW imports exactly one helper from the public sanitizer
(`sanitize_public_mapping`) — the same helper 10AR, 10AS, 10AT, 10AU,
and 10AV already import — and nothing else from the upstream stack.

## Allowed and forbidden claims

### 10AW may say

> "Both agents publicly route toward destination tile D."

> "Both agents declare the same public route destination tile D."
> (a public-surface match; no claim of shared private knowledge,
> coordination, or awareness)

> "Both agents' route destinations are known and equal."
> (a public-surface match; no claim of travel timing, path,
> co-presence, or relationship)

### 10AW may not say

> "The agents are traveling together."

> "The agents are aware of each other's routes."

> "The agents are coordinating or planning jointly."

> "The agents are moving at the same time."

> "The agents are or were co-present, nearby, or in the same location."

> "The agents' shared route destination implies they have a relationship."

Any claim that promotes a shared public route destination into a private
relationship, shared memory, co-presence, awareness, trust, cooperation,
conflict, temporal overlap, coordination, or joint-planning claim is
forbidden.  The contract's `claim_scope` is
`shared_public_route_destination_only`; that scope name exists precisely
to make this narrowness visible in the artifact itself.

## Output schema

A 10AW contract is a JSON-serializable dict with these top-level fields:

| field                                   | type                  | notes |
|-----------------------------------------|-----------------------|-------|
| `ok`                                    | `bool`                | `True` only when the input 10AS merge validates and the contract was built successfully |
| `contract_schema_version`               | `str`                 | `"10AW.1"` |
| `contract_type`                         | `str`                 | `"shared_public_route_destination_contract"` |
| `contract_id`                           | `str \| None`          | `"10AW-" + sha256[:32]` of the canonical contract material; `None` on failure |
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
| `agent_a_route_destination_tile_id`     | `str \| None`         | sanitized `route_destination_tile_id` from agent_a's bundle or caller-supplied override |
| `agent_b_route_destination_tile_id`     | `str \| None`         | sanitized `route_destination_tile_id` from agent_b's bundle or caller-supplied override |
| `agent_a_route_destination_known`       | `bool`                | sanitized `route_destination_known` from agent_a's bundle or caller-supplied override |
| `agent_b_route_destination_known`       | `bool`                | sanitized `route_destination_known` from agent_b's bundle or caller-supplied override |
| `both_route_destination_known`          | `bool`                | `True` only when both agents' `route_destination_known` flags are `True` |
| `shared_route_destination_tile_id`      | `str \| None`         | the matching destination tile id when `both_route_destination_known` is `True` and both destination tile ids are equal; otherwise `None` |
| `claim_scope`                           | `str`                 | `"shared_public_route_destination_only"` |
| `errors`                                | `list[str]`           | empty on success; safe human-readable error strings on failure |

### `contract_id` material

`contract_id` is computed as

```
contract_id = "10AW-" + sha256(canonical_json(contract_material))[:32]
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
    "agent_a_route_destination_tile_id": <str | "">,
    "agent_b_route_destination_tile_id": <str | "">,
    "agent_a_route_destination_known":   <bool>,
    "agent_b_route_destination_known":   <bool>,
    "both_route_destination_known":      <bool>,
    "shared_route_destination_tile_id":  <str | "">,
    "claim_scope":                   "shared_public_route_destination_only",
}
```

The contract material contains only contract-level public fields.
Raw 10AS bundle internals (hashes, snapshot ids, tick values) are
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
   before 10AW will accept them (same discipline 10AS uses for
   `snapshot_type`).
5. `merge["agent_a"]` and `merge["agent_b"]` are dicts.
6. `agent_a["agent_id"]` and `agent_b["agent_id"]` are non-empty
   strings.
7. `agent_a["agent_id"]` and `agent_b["agent_id"]` are distinct.  A
   shared-public-route-destination contract is between two distinct
   agents; same-agent input is `ok=False` with `"agent_a_id and
   agent_b_id must be distinct"`.
8. `merge["shared_known_tile_ids"]` is a list.  Tile ids that are
   not strings or are empty are dropped before the contract is built.
9. `merge["same_current_tile"]` is a `bool`.
10. Route destination fields are resolved as follows: if the caller
     passes `agent_a_route_destination` or `agent_b_route_destination`
     arguments, those values are used directly (after sanitization).
     Caller-supplied destination overrides are treated as known public
     declarations for that side when the sanitized destination is
     non-empty.  Otherwise the agent bundle's `route_destination_tile_id`
     and `route_destination_known` fields are read.  If a field is missing
     or not of the expected type, it is treated as `None` / `False`
     — the contract still builds with `ok=True` and safe empty
     destination fields.
11. After sanitization, `agent_a["current_tile_id"]` and
    `agent_b["current_tile_id"]` are read for the
    `shared_current_tile_id` derivation.
12. If `same_current_tile` is `True` but the sanitized bundle
    `current_tile_id` values differ, `ok=False` with `"same_current_tile
    is True but agent current_tile_ids differ"` — the same
    internal-consistency guard 10AT, 10AU, and 10AV use.

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
create_shared_public_route_destination_contract(
    merge: dict,
    agent_a_route_destination: str | None = None,
    agent_b_route_destination: str | None = None,
) -> dict
```

Create a deterministic sanitized shared-public-route-destination contract
from an already-built 10AS two-agent public merge artifact.  Route
destination data comes from the agent bundles' `route_destination_tile_id`
and `route_destination_known` fields unless overridden by the optional
`agent_a_route_destination` / `agent_b_route_destination` arguments.
Returns a contract dict.  Never raises.

```python
export_shared_public_route_destination_contract(contract: dict) -> str
```

Export a contract as stable sorted sanitized JSON text.  The contract
is sanitized via `sanitize_public_mapping` before serialization.

```python
contract_shared_route_destination_file(merge_json_path: Path | str) -> dict
```

Read an exported 10AS merge JSON artifact from a caller-supplied path
and create a shared-public-route-destination contract.  File loading is
JSON-only; the path must refer to a single JSON file containing a
10AS merge artifact.

## Test plan

`world-sim/tests/test_phase10aw_shared_public_route_destination_contract.py`
must cover:

1. Happy path: a real 10AS merge (built via the 10AS creator) with
   agent bundles that carry `route_destination_tile_id` and
   `route_destination_known=True` produces `ok=True`,
   `contract_schema_version == "10AW.1"`, `contract_type` correct,
   `contract_id` starting with `"10AW-"`, `claim_scope ==
   "shared_public_route_destination_only"`, empty `errors`.
2. Caller-supplied route-destination override: when
   `agent_a_route_destination` and `agent_b_route_destination` are
   passed explicitly, they are used instead of any bundle fields, and
   the contract reflects the override.
3. Output has exactly the required top-level fields; no forbidden
   fields leak (`co_presence`, `met`, `trust`, `cooperation`,
   `conflict`, `awareness`, `communication`, `relationship`,
   `private_*`, `shared_private_*`, `tick_window`, `active_at_same_time`,
   `temporal_overlap`, `route_path`, `travel_timing`, `eta`).
4. `same_current_tile` and `shared_current_tile_id` are lifted from
   the 10AS merge and correctly propagated.
5. `shared_known_tile_ids` and `shared_known_tile_count` are lifted
   from the 10AS merge.
6. `contract_id` is deterministic across repeated calls with
   identical input.
7. `contract_id` changes when any contract-material field changes
   (including `agent_a_route_destination_tile_id` and
   `agent_b_route_destination_tile_id`).
8. Input mutation guard: caller's `merge` dict is unchanged after the
   call.
9. Non-dict / ok=False / wrong merge_type / wrong merge_schema_version
   / missing agent_a or agent_b / empty agent ids / same agent ids
   → `ok=False` with safe errors.
10. `shared_known_tile_ids` not a list / `same_current_tile` not a
    bool → `ok=False`.
11. `same_current_tile` True but bundle current tiles differ →
    `ok=False` (internal-consistency guard).
12. Private markers planted in the merge (paths, secrets, IPs, agent
    traces, slash-skill refs) are redacted in the contract output
    and in the exported JSON text.
13. Graceful handling of missing `route_destination_tile_id` or
    `route_destination_known`: when a 10AS merge without bundle-level
    route destination fields is passed and no caller-supplied
    overrides are given, the contract builds with empty/False
    destination fields and `ok=True`.
14. `export_shared_public_route_destination_contract` produces stable
    sorted JSON; round-trips through `json.loads`.
15. `contract_shared_route_destination_file` reads an exported 10AS
    merge JSON from a tempdir path and builds a contract.
16. Saturation: all three public functions exercised at least once.
17. Boundary scan: the 10AW module contains no forbidden imports (no
     10AS/10AR/10AQ/10AP creators, no ledger writers, no projectors,
     no network/process/runtime tools, no `world-sim/data`).
18. Module source does not call `create_two_agent_public_merge(` or
     any other upstream creator.
19. Boundary smoke: the full happy-path contract text carries no
     relationship, trust, cooperation, conflict, awareness,
     co-presence, communication, temporal, travel-timing, path, or
     coordination tokens.

All tests are tempdir-only.  No test writes to `world-sim/data`, no
test connects to a provider, runs a daemon, or requires Docker.

## Out of scope for 10AW

- Route path inference or step-by-step travel plans.
- Travel timing, ETA, or temporal window overlap.
- Inferring whether agents are moving at the same time.
- Inferring whether agents are or were co-present or nearby.
- Inferring whether agents met, will meet, or could meet.
- Building any kind of joint plan, joint route, joint memory, or
  joint ledger.
- Multi-agent (>2) route comparison.
- Mutating any 10AS, 10AR, 10AQ, or 10AP artifact.
- Producing a ledger event.
- Reading the hidden true map or any agent's private observation
  result.
- Anything that would require a daemon, scheduler, provider, Docker,
  or network.

## Forward compatibility

A future phase (10AX or later) may extend this stack to territory ref
comparison, snapshot hash equality, or temporal window overlap under its
own scope contract.  10AW explicitly bans all pathfinding, timing, and
coordination inferences and encodes that ban in its `claim_scope` name.
