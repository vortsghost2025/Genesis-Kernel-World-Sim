# Phase 10AT — Shared Public Observation Contract

## Status

Planned phase.  Builds on Phase 10AS.  Not yet implemented in the
runtime; this document defines the scope contract before any code,
tests, daemon, scheduler, provider, Docker, runtime, network, or live
data enter the system.

## Purpose

Phase 10AT formalizes how two agents can produce a **shared public
observation contract** from their already-public surfaces, without
ever inferring private knowledge or co-presence.

A 10AT contract is a thin *contract artifact* derived from a successful
10AS two-agent public merge.  It does not call any 10AS creator; it
only reads an already-built 10AS merge and emits a deterministic,
sanitized, hash-stable contract that records which public observations
the two agents demonstrably share, and nothing more.

## Consumption contract

10AT **consumes 10AS only**.

10AT **must not**:

- import or call any 10AS, 10AR, 10AQ, 10AP, or any earlier phase
  creator function;
- write to any ledger;
- call any projector, route planner, or movement helper;
- spawn processes, open sockets, read environment, read filesystem
  state other than a single caller-supplied JSON file path;
- touch `world-sim/data`.

10AT imports exactly one helper from the public sanitizer
(`sanitize_public_mapping`) — the same helper 10AR and 10AS already
import — and nothing else from the upstream stack.

## Allowed and forbidden claims

### 10AT may say

> "These two agents share public observation of tiles X / Y / Z."

> "Their two published public surfaces report the same current public
> tile T (a public-surface match; no claim of co-presence)."

> "Both agents have each published an `intent_only` route intent toward
> the same destination tile D."

### 10AT may not say

> "The agents are / were co-present."

> "The agents met each other, became aware of each other, or know each
> other privately."

> "The agents trust, cooperate, conflict, communicate, exchange
> memory, share private state, perceive each other, or traveled
> together."

> "Same-current-tile implies the agents can see, hear, speak to, or
> act on each other."

`same_current_tile` is a *public-surface match* — a fact derivable
purely from each agent's already-public 10AP projection and 10AQ
snapshot.  10AT never promotes a public-surface match into a private
co-presence, awareness, communication, trust, cooperation, or
relationship claim.  The contract's `claim_scope` is
`shared_public_only`; that scope name exists precisely to make this
narrowness visible in the artifact itself.

## Output schema

A 10AT contract is a JSON-serializable dict with these top-level fields:

| field                                   | type                  | notes |
|-----------------------------------------|-----------------------|-------|
| `ok`                                    | `bool`                | `True` only when the input 10AS merge validates and the contract was built successfully |
| `contract_schema_version`               | `str`                 | `"10AT.1"` |
| `contract_type`                         | `str`                 | `"shared_public_observation_contract"` |
| `contract_id`                           | `str \| None`          | `"10AT-" + sha256[:32]` of the canonical contract material; `None` on failure |
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
| `both_have_route_intent`                | `bool`                | both agent bundles carry a non-empty `route_intent_id` |
| `both_route_to_same_destination`        | `bool`                | `True` only when both bundles have a route intent **and** both `route_destination_tile_id` are equal and non-empty |
| `shared_route_destination_tile_id`      | `str \| None`         | the shared destination tile id when `both_route_to_same_destination`, else `None` |
| `agent_a_route_destination_tile_id`     | `str \| None`         | sanitized `agent_a.route_destination_tile_id`, or `None` |
| `agent_b_route_destination_tile_id`     | `str \| None`         | sanitized `agent_b.route_destination_tile_id`, or `None` |
| `claim_scope`                           | `str`                 | `"shared_public_only"` |
| `errors`                                | `list[str]`           | empty on success; safe human-readable error strings on failure |

### `contract_id` material

`contract_id` is computed as

```
contract_id = "10AT-" + sha256(canonical_json(contract_material))[:32]
```

where `canonical_json` uses `sort_keys=True`, compact separators, and
`ensure_ascii=False`, and `contract_material` is exactly:

```python
{
    "source_merge_id":       <10AS merge_id> or "",
    "agent_a_id":            <str>,
    "agent_b_id":            <str>,
    "shared_known_tile_ids": <sorted list[str]>,
    "same_current_tile":     <bool>,
    "shared_current_tile_id": <str | "">,
    "both_have_route_intent":  <bool>,
    "both_route_to_same_destination": <bool>,
    "shared_route_destination_tile_id": <str | "">,
    "claim_scope":           "shared_public_only",
}
```

The contract material contains only contract-level public fields.  Raw
10AS bundle internals (hashes, snapshot ids, snapshot hashes) are
deliberately excluded from the hash input so the contract id remains
stable across 10AS input-ordering changes and across repeated calls
with the same inputs.

## Validation rules

In order:

1. `merge` is a `dict`.  Otherwise `ok=False` with `"merge must be a
   dict"`.
2. `merge["ok"]` is `True`.  Otherwise `ok=False` with `"merge ok flag
   is not True"`.
3. `merge["merge_type"] == "two_agent_public_merge"`.  Otherwise
   `ok=False`.
4. `merge["merge_schema_version"] == "10AS.1"`.  Otherwise `ok=False`.
   Future 10AS schema bumps must be explicitly allow-listed here
   before 10AT will accept them (same discipline 10AS uses for
   `snapshot_type`).
5. `merge["agent_a"]` and `merge["agent_b"]` are dicts.
6. `agent_a["agent_id"]` and `agent_b["agent_id"]` are non-empty
   strings.
7. `agent_a["agent_id"]` and `agent_b["agent_id"]` are distinct.  A
   shared-public-observation contract is between two distinct agents;
   same-agent input is `ok=False` with `"agent_a_id and agent_b_id
   must be distinct"`.
8. `merge["shared_known_tile_ids"]` is a list.  Tile ids that are not
   strings or are empty are dropped before the contract is built.
9. `merge["same_current_tile"]` is a `bool`.
10. `merge["both_have_route_intent"]` is a `bool`.
11. After sanitization, `agent_a["current_tile_id"]` and
    `agent_b["current_tile_id"]` are read for the
    `shared_current_tile_id` derivation.
12. Bundle route-destination fields are read only from the sanitized
    bundles; raw route-intent objects are never copied into the
    contract.

If any rule fails, the contract is returned with `ok=False`,
`contract_id=None`, the `source_merge_id` copied where determinable,
and a non-empty `errors` list.  All failures are safe: the function
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
create_shared_public_observation_contract(merge: dict) -> dict
```

Create a deterministic sanitized shared-public-observation contract
from an already-built 10AS two-agent public merge artifact.  Returns a
contract dict.  Never raises.

```python
export_shared_public_observation_contract(contract: dict) -> str
```

Export a contract as stable sorted sanitized JSON text.  The contract
is sanitized via `sanitize_public_mapping` before serialization.

```python
contract_shared_observation_file(merge_json_path: Path | str) -> dict
```

Read an exported 10AS merge JSON artifact from a caller-supplied path
and create a shared-public-observation contract.  File loading is
JSON-only; the path must refer to a single JSON file.  No other I/O.

## Test plan

`world-sim/tests/test_phase10at_shared_public_observation_contract.py`
must cover, in tempdir-only fashion:

1. Happy path: a real 10AS merge (built via the 10AS creator) produces
   `ok=True`, `contract_schema_version == "10AT.1"`, `contract_type`
   correct, `contract_id` starting with `"10AT-"`, `claim_scope ==
   "shared_public_only"`, empty `errors`.
2. Output has exactly the required top-level fields; no forbidden
   fields leak (`co_presence`, `met`, `trust`, `cooperation`,
   `conflict`, `awareness`, `communication`, `relationship`,
   `private_*`, `shared_private_*`).
3. `shared_known_tile_ids` is the sorted intersection lifted from the
   10AS merge, and `shared_known_tile_count` matches.
4. `same_current_tile` is `True` only when both agents' public
   `current_tile_id` match; `shared_current_tile_id` is the matching
   tile or `None`.  No co-presence claim is inferable.
5. `both_have_route_intent` mirrors the 10AS merge flag.
6. `both_route_to_same_destination` is `True` only when both bundles
   have a route intent **and** both `route_destination_tile_id` are
   non-empty and equal; `shared_route_destination_tile_id` is the
   shared destination or `None`.
7. Per-agent route-destination fields are copied from the sanitized
   bundles, never from raw route intent objects.
8. `contract_id` is stable across repeated calls with identical input
   (determinism).
9. `contract_id` changes when any contract-material field changes
   (collision resistance sanity).
10. Input mutation guard: after `create_shared_public_observation_contract`
    returns, the caller's `merge` dict is unchanged (deep-copy).
11. Non-dict `merge` → `ok=False` with safe error.
12. `merge["ok"] is False` → `ok=False` with `"merge ok flag is not
    True"`.
13. Wrong `merge_type` → `ok=False`.
14. Wrong `merge_schema_version` → `ok=False`.
15. Missing / non-dict `agent_a` or `agent_b` → `ok=False`.
16. Empty `agent_a_id` or `agent_b_id` → `ok=False`.
17. Same `agent_a_id` and `agent_b_id` → `ok=False` with distinct-agent
    error.
18. `shared_known_tile_ids` not a list → `ok=False`.
19. `same_current_tile` not a bool → `ok=False`.
20. `both_have_route_intent` not a bool → `ok=False`.
21. Private markers planted in the merge (filesystem paths, secret
    labels, loopback IPs, agent-trace markers, slash-skill refs) are
    redacted in the contract output **and** in
    `export_shared_public_observation_contract` output.
22. `contract_shared_observation_file` successfully reads an exported
    10AS merge JSON from a tempdir path and builds a contract.
23. Saturation: `create_shared_public_observation_contract`,
    `export_shared_public_observation_contract`, and
    `contract_shared_observation_file` are all exercised at least once.
24. Boundary scan: the 10AT module file itself contains no forbidden
    imports (`local_two_agent_public_merge`, `local_public_state_projector`,
    `local_known_map_snapshot_export`, `local_route_intent_contract`,
    `world_event_ledger`, `subprocess`, `socket`, `requests`, `os.environ`,
    `pathlib`'s `glob`, `walk`, `rglob`, `iterdir`) beyond what the
    approved import allow-list permits.

All tests are tempdir-only.  No test writes to `world-sim/data`, no
test connects to a provider, runs a daemon, or requires Docker.

## Out of scope for 10AT

- Multi-agent (>2) shared observation.
- Inferring whether the agents are aware of each other.
- Inferring whether the agents met, will meet, or could meet.
- Building any kind of joint plan, joint route, joint memory, or joint
  ledger.
- Mutating any 10AS, 10AR, 10AQ, or 10AP artifact.
- Producing a ledger event.
- Anything that would require a daemon, scheduler, provider, Docker,
  or network.

## Forward compatibility

A future phase that wants to surface shared-private-state claims, or
to assert co-presence as a first-class event, must do so under a new
phase number with its own scope contract.  10AT explicitly bans all
such inferences and encodes that ban in its `claim_scope` name.
