# Phase 10AX — Shared Public Territory Ref Contract

## Status

Planned.  No implementation until the operator approves the scope.

## Purpose

Phase 10AX formalizes which public territory references two agents have
each declared in their already-public surfaces.  Two agents may share
public observation of a tile (10AT), reference the same public anchor
(10AU), reference the same public event (10AV), publicly route toward
the same destination tile (10AW), *and* both publicly declare the same
territory reference, without either agent having private knowledge of
the other.

Territory reference data is not present in the 10AS agent bundles.  The
caller supplies it directly as optional arguments — no 10AS update is
required.

10AX is the next rung in the public-observation contract stack.  It does
not infer shared private knowledge, co-presence, awareness, trust,
cooperation, conflict, communication, temporal overlap, coordination,
planning, proximity, or any kind of relationship.

## Consumption contract

10AX consumes a Phase 10AS two-agent public merge artifact.

Territory reference data comes from one of two paths:

1. **Caller-supplied (primary):** optional `agent_a_territory_ref` and
   `agent_b_territory_ref` arguments to the creator function.  These are
   treated as known public declarations for that side when the sanitized
   territory ref is non-empty.  This path exists because territory refs
   are not stored in the 10AS agent bundles.
2. **Bundle field (future):** if a future 10AS update adds
   `territory_ref` to the agent bundles, 10AX will read them as a
   fallback when caller-supplied overrides are absent.

10AX **must not**:

- import or call any 10AS, 10AR, 10AQ, 10AP, or any earlier phase
  creator function;
- write to any ledger;
- call any projector, route planner, or movement helper;
- spawn processes, open sockets, read environment, read filesystem
  state other than a single caller-supplied JSON file path;
- touch `world-sim/data`.

10AX imports exactly one helper from the public sanitizer
(`sanitize_public_mapping`) — the same helper 10AR, 10AS, 10AT, 10AU,
10AV, and 10AW already import — and nothing else from the upstream stack.

## Allowed and forbidden claims

### 10AX may say

> "Both agents publicly cite territory ref T."

> "Both agents' public surfaces reference the same territory ref T."
> (a public-surface match; no claim of shared private knowledge,
> coordination, or awareness)

> "Both agents declare the same public territory ref."
> (a public-surface match; no claim of proximity, co-presence,
> travel timing, or relationship)

### 10AX may not say

> "The agents are in the same territory."

> "The agents are aware of each other's territory refs."

> "The agents are coordinating or planning jointly."

> "The agents are or were co-present, nearby, or in the same location."

> "The agents' shared territory ref implies they have a relationship."

Any claim that promotes a shared public territory ref into a private
relationship, shared memory, co-presence, awareness, trust, cooperation,
conflict, temporal overlap, coordination, or joint-planning claim is
forbidden.  The contract's `claim_scope` is
`shared_territory_refs_only`; that scope name exists precisely to make
this narrowness visible in the artifact itself.

## Output schema

A 10AX contract is a JSON-serializable dict with these top-level fields:

| field                                   | type                  | notes |
|-----------------------------------------|-----------------------|-------|
| `ok`                                    | `bool`                | `True` only when the input 10AS merge validates and the contract was built successfully |
| `contract_schema_version`               | `str`                 | `"10AX.1"` |
| `contract_type`                         | `str`                 | `"shared_territory_ref_contract"` |
| `contract_id`                           | `str \| None`          | `"10AX-" + sha256[:32]` of the canonical contract material; `None` on failure |
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
| `agent_a_territory_ref`                 | `str \| None`         | sanitized territory ref from agent_a's caller-supplied override or bundle field |
| `agent_b_territory_ref`                 | `str \| None`         | sanitized territory ref from agent_b's caller-supplied override or bundle field |
| `same_territory_ref`                    | `bool`                | `True` only when both agents have a non-empty territory ref and they are equal |
| `shared_territory_ref`                  | `str \| None`         | the matching territory ref when `same_territory_ref` is `True`; otherwise `None` |
| `agent_a_only_territory_ref`            | `str \| None`         | agent_a's territory ref when only agent_a has a non-empty one; otherwise `None` |
| `agent_b_only_territory_ref`            | `str \| None`         | agent_b's territory ref when only agent_b has a non-empty one; otherwise `None` |
| `claim_scope`                           | `str`                 | `"shared_territory_refs_only"` |
| `errors`                                | `list[str]`           | empty on success; safe human-readable error strings on failure |

### `contract_id` material

`contract_id` is computed as

```
contract_id = "10AX-" + sha256(canonical_json(contract_material))[:32]
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
    "agent_a_territory_ref":         <str | "">,
    "agent_b_territory_ref":         <str | "">,
    "same_territory_ref":            <bool>,
    "shared_territory_ref":          <str | "">,
    "agent_a_only_territory_ref":    <str | "">,
    "agent_b_only_territory_ref":    <str | "">,
    "claim_scope":                   "shared_territory_refs_only",
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
   before 10AX will accept them (same discipline 10AS uses for
   `snapshot_type`).
5. `merge["agent_a"]` and `merge["agent_b"]` are dicts.
6. `agent_a["agent_id"]` and `agent_b["agent_id"]` are non-empty
   strings.
7. `agent_a["agent_id"]` and `agent_b["agent_id"]` are distinct.  A
   shared-public-territory-ref contract is between two distinct agents;
   same-agent input is `ok=False` with `"agent_a_id and agent_b_id must
   be distinct"`.
8. `merge["shared_known_tile_ids"]` is a list.  Tile ids that are
   not strings or are empty are dropped before the contract is built.
9. `merge["same_current_tile"]` is a `bool`.
10. Territory ref fields are resolved as follows: if the caller passes
    `agent_a_territory_ref` or `agent_b_territory_ref` arguments, those
    values are used directly (after sanitization).  Caller-supplied
    territory refs are treated as known public declarations for that
    side when the sanitized territory ref is non-empty.  Otherwise the
    agent bundle's `territory_ref` field is read if present.  If a field
    is missing or not of the expected type, it is treated as `None`
    — the contract still builds with `ok=True` and safe empty
    territory ref fields.
11. After sanitization, `agent_a["current_tile_id"]` and
    `agent_b["current_tile_id"]` are read for the
    `shared_current_tile_id` derivation.
12. If `same_current_tile` is `True` but the sanitized bundle
    `current_tile_id` values differ, `ok=False` with `"same_current_tile
    is True but agent current_tile_ids differ"` — the same
    internal-consistency guard 10AT, 10AU, 10AV, and 10AW use.

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
create_shared_territory_ref_contract(
    merge: dict,
    agent_a_territory_ref: str | None = None,
    agent_b_territory_ref: str | None = None,
) -> dict
```

Create a deterministic sanitized shared-territory-ref contract from an
already-built 10AS two-agent public merge artifact.  Territory ref data
comes from the optional `agent_a_territory_ref` /
`agent_b_territory_ref` arguments, falling back to the agent bundles'
`territory_ref` fields if present.  Returns a contract dict.  Never
raises.

```python
export_shared_territory_ref_contract(contract: dict) -> str
```

Export a contract as stable sorted sanitized JSON text.  The contract
is sanitized via `sanitize_public_mapping` before serialization.

```python
contract_territory_ref_file(merge_json_path: Path | str) -> dict
```

Read an exported 10AS merge JSON artifact from a caller-supplied path
and create a shared-territory-ref contract.  File loading is JSON-only;
the path must refer to a single JSON file containing a 10AS merge
artifact.

## Test plan

`world-sim/tests/test_phase10ax_shared_public_territory_ref_contract.py`
must cover:

1. Happy path: a real 10AS merge with caller-supplied territory refs
    produces `ok=True`, `contract_schema_version == "10AX.1"`,
    `contract_type` correct, `contract_id` starting with `"10AX-"`,
    `claim_scope == "shared_territory_refs_only"`, empty `errors`.
2. Caller-supplied territory-ref override: when
    `agent_a_territory_ref` and `agent_b_territory_ref` are passed
    explicitly, they are used instead of any bundle fields, and the
    contract reflects the override.
3. Output has exactly the required top-level fields; no forbidden
    fields leak (`co_presence`, `met`, `trust`, `cooperation`,
    `conflict`, `awareness`, `communication`, `relationship`,
    `private_*`, `shared_private_*`, `tick_window`, `active_at_same_time`,
    `temporal_overlap`, `route_path`, `travel_timing`, `eta`).
4. `same_current_tile` and `shared_current_tile_id` are lifted from
    the 10AS merge and correctly propagated.
5. `shared_known_tile_ids` and `shared_known_tile_count` are lifted
    from the 10AS merge.
6. `same_territory_ref` and `shared_territory_ref` are correct when
    both agents have the same non-empty territory ref.
7. `agent_a_only_territory_ref` and `agent_b_only_territory_ref` are
    correct when only one agent has a territory ref.
8. `contract_id` is deterministic across repeated calls with
    identical input.
9. `contract_id` changes when any contract-material field changes
    (including territory refs).
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
15. Graceful handling of missing territory refs: when no caller-supplied
    overrides are given and no bundle `territory_ref` fields exist,
    the contract builds with empty/None territory ref fields and
    `ok=True`.
16. `export_shared_territory_ref_contract` produces stable sorted JSON;
    round-trips through `json.loads`.
17. `contract_territory_ref_file` reads an exported 10AS merge JSON from
    a tempdir path and builds a contract.
18. Saturation: all three public functions exercised at least once.
19. Boundary scan: the 10AX module contains no forbidden imports (no
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

## Out of scope for 10AX

- Territory proximity inference or distance calculations.
- Inferring whether agents are in the same physical location.
- Inferring whether agents met, will meet, or could meet.
- Inferring travel timing, ETA, or temporal window overlap.
- Building any kind of joint plan, joint route, joint memory, or
  joint ledger.
- Multi-agent (>2) territory ref comparison.
- Mutating any 10AS, 10AR, 10AQ, or 10AP artifact.
- Producing a ledger event.
- Reading the hidden true map or any agent's private observation
  result.
- Anything that would require a daemon, scheduler, provider, Docker,
  or network.

## Forward compatibility

A future phase (10AY or later) may extend this stack to snapshot hash
equality, temporal window overlap, or territory proximity under its own
scope contract.  10AX explicitly bans all proximity, timing, and
coordination inferences and encodes that ban in its `claim_scope` name.
