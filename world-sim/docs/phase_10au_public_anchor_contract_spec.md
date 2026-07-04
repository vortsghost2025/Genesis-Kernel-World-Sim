# Phase 10AU — Public Anchor / Reference Sharing Contract

## Status

Planned.  No implementation until the operator approves the scope.

## Purpose

Phase 10AU formalizes which public landmarks, event refs, or
territory refs two agents have each cited in their already-public
surfaces.  Two agents may share public observation of a tile (10AT)
*and* both reference the same public anchor or reference on that
tile, without either agent having private knowledge of the other.

Anchor identifiers are read from the 10AS agent bundles when present.
If the bundles do not carry `public_anchor_ids`, the caller may supply
them directly as optional arguments — no 10AS update is required.

10AU is the first rung beyond 10AT in the public-observation contract
stack.  It does not plan routes, does not infer adjacency, does not
claim the agents can navigate to each other, and does not promote a
shared public anchor into a private relationship, trust, cooperation,
conflict, awareness, or co-presence claim.

## Consumption contract

10AU consumes a Phase 10AS two-agent public merge artifact.

Anchor identifiers come from one of two paths:

1. **Bundle field (preferred):** `agent_a.public_anchor_ids` and
   `agent_b.public_anchor_ids` in the sanitized 10AS agent bundles.
   When present and list-shaped, they are used directly.
2. **Caller-supplied (fallback):** optional `agent_a_anchor_ids` and
   `agent_b_anchor_ids` arguments to the creator function.  These
   override the bundle fields when provided.  This path exists so
   10AU can be implemented and tested without a 10AS update.

10AU **must not**:

- import or call any 10AS, 10AR, 10AQ, 10AP, or any earlier phase
  creator function;
- write to any ledger;
- call any projector, route planner, or movement helper;
- spawn processes, open sockets, read environment, read filesystem
  state other than a single caller-supplied JSON file path;
- touch `world-sim/data`.

10AU imports exactly one helper from the public sanitizer
(`sanitize_public_mapping`) — the same helper 10AR, 10AS, and 10AT
already import — and nothing else from the upstream stack.

## Allowed and forbidden claims

### 10AU may say

> "These two agents share public anchor / reference IDs X / Y / Z."

> "Both agents cite the same public territory ref T." (a
> public-surface match; no claim of shared private knowledge)

> "Both agents' public surfaces reference the same event ID E."
> (a public-surface match; no claim of shared memory, communication,
> or awareness)

### 10AU may not say

> "The agents share private state about these anchors."

> "The agents trust each other's anchor choices."

> "The agents are aware of each other because they cite the same
> anchor."

> "The agents can navigate to each other via shared anchors."

> "The agents' shared anchors imply they met, communicated,
> cooperate, conflict, or have a relationship."

Any claim that promotes a shared public anchor into a private
relationship, shared memory, co-presence, awareness, trust,
cooperation, conflict, or navigation claim is forbidden.  The
contract's `claim_scope` is `shared_public_anchors_only`; that scope
name exists precisely to make this narrowness visible in the artifact
itself.

## Output schema

A 10AU contract is a JSON-serializable dict with these top-level
fields:

| field                                   | type                  | notes |
|-----------------------------------------|-----------------------|-------|
| `ok`                                    | `bool`                | `True` only when the input 10AS merge validates and the contract was built successfully |
| `contract_schema_version`               | `str`                 | `"10AU.1"` |
| `contract_type`                         | `str`                 | `"shared_public_anchor_contract"` |
| `contract_id`                           | `str \| None`          | `"10AU-" + sha256[:32]` of the canonical contract material; `None` on failure |
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
| `shared_public_anchor_ids`              | `list[str]`           | sorted unique intersection of the two agents' `public_anchor_ids` (from bundle fields or caller-supplied overrides; empty list when neither side provides anchors) |
| `shared_public_anchor_count`            | `int`                 | `len(shared_public_anchor_ids)` |
| `agent_a_only_anchor_ids`               | `list[str]`           | sorted set difference: anchors in agent_a's bundle or caller-supplied list, but not agent_b's |
| `agent_b_only_anchor_ids`               | `list[str]`           | sorted set difference: anchors in agent_b's bundle or caller-supplied list, but not agent_a's |
| `claim_scope`                           | `str`                 | `"shared_public_anchors_only"` |
| `errors`                                | `list[str]`           | empty on success; safe human-readable error strings on failure |

### `contract_id` material

`contract_id` is computed as

```
contract_id = "10AU-" + sha256(canonical_json(contract_material))[:32]
```

where `canonical_json` uses `sort_keys=True`, compact separators, and
`ensure_ascii=False`, and `contract_material` is exactly:

```python
{
    "source_merge_id":           <10AS merge_id> or "",
    "agent_a_id":                <str>,
    "agent_b_id":                <str>,
    "shared_known_tile_ids":     <sorted list[str]>,
    "same_current_tile":         <bool>,
    "shared_current_tile_id":    <str | "">,
    "shared_public_anchor_ids":  <sorted list[str]>,
    "claim_scope":               "shared_public_anchors_only",
}
```

The contract material contains only contract-level public fields.
Raw 10AS bundle internals (hashes, snapshot ids) are deliberately
excluded from the hash input so the contract id remains stable
across repeated calls with the same inputs.

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
   before 10AU will accept them (same discipline 10AS uses for
   `snapshot_type`).
5. `merge["agent_a"]` and `merge["agent_b"]` are dicts.
6. `agent_a["agent_id"]` and `agent_b["agent_id"]` are non-empty
   strings.
7. `agent_a["agent_id"]` and `agent_b["agent_id"]` are distinct.  A
   shared-public-anchor contract is between two distinct agents;
   same-agent input is `ok=False` with `"agent_a_id and agent_b_id
   must be distinct"`.
8. `merge["shared_known_tile_ids"]` is a list.  Tile ids that are
   not strings or are empty are dropped before the contract is built.
9. `merge["same_current_tile"]` is a `bool`.
10. Anchor identifiers are resolved as follows: if the caller passes
    `agent_a_anchor_ids` or `agent_b_anchor_ids` arguments, those
    lists are used directly (after sanitization).  Otherwise the
    agent bundle's `public_anchor_ids` field is read.  If the field is
    missing or not a list, it is treated as an empty list — the
    contract still builds with `ok=True` and empty anchor fields.
11. After sanitization, `agent_a["current_tile_id"]` and
    `agent_b["current_tile_id"]` are read for the
    `shared_current_tile_id` derivation.
12. If `same_current_tile` is `True` but the sanitized bundle
    `current_tile_id` values differ, `ok=False` with `"same_current_tile
    is True but agent current_tile_ids differ"` — the same
    internal-consistency guard 10AT uses.

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
create_shared_public_anchor_contract(
    merge: dict,
    agent_a_anchor_ids: list[str] | None = None,
    agent_b_anchor_ids: list[str] | None = None,
) -> dict
```

Create a deterministic sanitized shared-public-anchor contract from
an already-built 10AS two-agent public merge artifact.  Anchor
identifiers come from the agent bundles' `public_anchor_ids` fields
unless overridden by the optional `agent_a_anchor_ids` /
`agent_b_anchor_ids` arguments.  Returns a contract dict.  Never
raises.

```python
export_shared_public_anchor_contract(contract: dict) -> str
```

Export a contract as stable sorted sanitized JSON text.  The contract
is sanitized via `sanitize_public_mapping` before serialization.

```python
contract_shared_anchor_file(merge_json_path: Path | str) -> dict
```

Read an exported 10AS merge JSON artifact from a caller-supplied path
and create a shared-public-anchor contract.  File loading is
JSON-only; the path must refer to a single JSON file containing a
10AS merge artifact.

## Test plan

`world-sim/tests/test_phase10au_shared_public_anchor_contract.py`
must cover:

1. Happy path: a real 10AS merge (built via the 10AS creator) with
    agent bundles that carry `public_anchor_ids` produces `ok=True`,
    `contract_schema_version == "10AU.1"`, `contract_type` correct,
    `contract_id` starting with `"10AU-"`, `claim_scope ==
    "shared_public_anchors_only"`, empty `errors`.
2. Caller-supplied anchor override: when `agent_a_anchor_ids` and
    `agent_b_anchor_ids` are passed explicitly, they are used instead
    of any bundle fields, and the contract reflects the override.
3. Output has exactly the required top-level fields; no forbidden
   fields leak (`co_presence`, `met`, `trust`, `cooperation`,
   `conflict`, `awareness`, `communication`, `relationship`,
   `private_*`, `shared_private_*`).
3. `shared_public_anchor_ids` is the sorted intersection of the two
   agents' `public_anchor_ids`; set-difference fields are correct.
4. `same_current_tile` and `shared_current_tile_id` are lifted from
   the 10AS merge and correctly propagated.
5. `shared_known_tile_ids` and `shared_known_tile_count` are lifted
   from the 10AS merge.
6. `contract_id` is deterministic across repeated calls with
   identical input.
7. `contract_id` changes when any contract-material field changes.
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
13. Graceful handling of missing `public_anchor_ids`: when a 10AS
    merge without bundle-level `public_anchor_ids` is passed and no
    caller-supplied overrides are given, the contract builds with
    empty anchor fields and `ok=True`.  (The caller-supplied override
    path is the preferred way to supply anchors without a 10AS update.)
14. `export_shared_public_anchor_contract` produces stable sorted
    JSON; round-trips through `json.loads`.
15. `contract_shared_anchor_file` reads an exported 10AS merge JSON
    from a tempdir path and builds a contract.
16. Saturation: all three public functions exercised at least once.
17. Boundary scan: the 10AU module contains no forbidden imports (no
    10AS/10AR/10AQ/10AP creators, no ledger writers, no projectors,
    no network/process/runtime tools, no `world-sim/data`).
18. Module source does not call `create_two_agent_public_merge(` or
    any other upstream creator.
19. Boundary smoke: the full happy-path contract text carries no
    relationship, trust, cooperation, conflict, awareness,
    co-presence, or communication tokens.

All tests are tempdir-only.  No test writes to `world-sim/data`, no
test connects to a provider, runs a daemon, or requires Docker.

## Out of scope for 10AU

- Multi-agent (>2) anchor sharing.
- Inferring whether agents are aware of each other because they cite
  the same anchor.
- Inferring whether agents met, will meet, or could meet.
- Building any kind of joint plan, joint route, joint memory, or
  joint ledger.
- Mutating any 10AS, 10AR, 10AQ, or 10AP artifact.
- Producing a ledger event.
- Reading the hidden true map or any agent's private observation
  result.
- Anything that would require a daemon, scheduler, provider, Docker,
  or network.

## Forward compatibility

A future phase that wants to surface shared-private-state claims, or
to assert co-presence as a first-class event, must do so under a new
phase number with its own scope contract.  10AU explicitly bans all
such inferences and encodes that ban in its `claim_scope` name.
