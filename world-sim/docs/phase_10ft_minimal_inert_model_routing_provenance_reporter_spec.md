# Phase 10FT - Minimal Inert Model Routing Provenance Reporter

10FT implements the single candidate named by 10FR. It is the first
governance/provenance branch after the proof-chain closure at 10FN. It is a pure
read-only, in-process, caller-driven reporter over one caller-supplied exact
routing/provenance policy artifact dictionary.

10FT does not verify 10FN or any ledger artifact. It never accepts a ledger or
configuration path, opens or scans a file, calls a backend, provider, model, or
agent surface, mutates configuration, or promotes report data into runtime or
world state. Gate-7 remains closed.

## Baseline and model

- Baseline: `570aea3 docs: record 10FS metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10FT test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 238 passed.
- Optional 10FN proof-chain regression: 184 passed.

## Public API

```python
create_minimal_inert_model_routing_provenance_report(
    routing_provenance_artifact: dict | None,
) -> dict

export_minimal_inert_model_routing_provenance_report(
    provenance_report: dict,
) -> str
```

The reporter accepts exactly one caller-supplied policy dictionary. It has no
path parameter, no default production path, and no routing/provider/model
handle. Missing, non-dictionary, subclassed, malformed, inconsistent, or
tampered input fails closed into the same sanitized `invalid_report` output.

## Source artifact envelope

10FT requires exactly these 32 fields:

- `policy_schema_version`
- `policy_revision`
- `policy_type`
- `policy_scope`
- `policy_decision_id`
- `artifact_class`
- `artifact_family`
- `authorized_lane`
- `authority_id`
- `authority_basis`
- `provider_id`
- `provider_name`
- `pinned_model_id`
- `pinned_model_revision`
- `model_pinned`
- `provider_pinned`
- `route_locked`
- `allowed_action`
- `forbidden_boundaries`
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `provider_call_allowed`
- `model_invocation_allowed`
- `config_mutation_allowed`
- `agent_launch_allowed`
- `world_sim_data_accessed`
- `gate7_activity_allowed`
- `claim_boundary`
- `errors`

Required identity and type rules:

- `policy_schema_version == "10FT.POLICY.1"`;
- `policy_revision` is the exact built-in integer `1`;
- `policy_type == "minimal_inert_model_routing_provenance_policy"`;
- `policy_scope == "model_routing_provenance_policy_only"`;
- `policy_decision_id` is `10FT-POLICY-` followed by 32 lowercase hexadecimal
  characters and must equal the independently recomputed policy decision ID;
- `allowed_action == "produce_artifact"`;
- `claim_boundary` is exact;
- dictionary, list, string, and integer subclasses are rejected;
- all strings are exact built-in strings;
- `model_pinned`, `provider_pinned`, and `route_locked` are exactly `True`;
- every execution/provider/model/config/agent/world/gate flag is exactly
  `False` (integer `0` is rejected);
- `errors` is an exact built-in empty list.

Safe provenance metadata is ASCII-only, 1-128 characters, limited to letters,
digits, `-`, `_`, `.`, and `:`, and must begin and end with an alphanumeric
character. Parent traversal, known credential-shaped prefixes, normalized
sensitive fragments, raw-config markers, and equality-signal/value markers are
rejected.
Identifiers have these syntax-only prefixes:

- `authorized_lane`: `lane:`
- `authority_id`: `authority:`
- `provider_id`: `provider:`
- `pinned_model_id`: `model:`

The lane and authority IDs are opaque syntax-checked external identifiers. 10FT
does not reproduce or recompute them. The provider identity is internally
consistent only when `provider_id == "provider:" + provider_name`.

## Exact forbidden boundaries

`forbidden_boundaries` is an exact built-in list containing these exact built-in
strings in this deterministic order:

1. `agent_launch`
2. `config_mutation`
3. `filesystem_scan`
4. `gate7_activity`
5. `model_invocation`
6. `provider_call`
7. `runtime_execution`
8. `world_sim_data_access`

Missing, extra, duplicated, reordered, unknown, or subclassed entries fail
closed. The list and `errors` are detached immediately after the caller
validation.

## Source policy decision ID

The source policy decision ID commits to all 31 source fields except
`policy_decision_id` itself. The complete safe policy material is serialized
with sorted keys, compact separators, and `ensure_ascii=False`, encoded as
UTF-8, and hashed with SHA-256. The required identifier is `10FT-POLICY-` plus
the first 32 lowercase hexadecimal characters.

This recomputation validates only the internal integrity of the supplied policy
artifact. It does not invoke a provider/model, authenticate an operator, or
recompute external lane/authority identities.

## Output envelope

10FT returns exactly these 28 safe fields:

- `ok`
- `provenance_report_schema_version = "10FT.1"`
- `provenance_report_type = "minimal_inert_model_routing_provenance_report"`
- `provenance_report_scope = "model_routing_provenance_report_only"`
- `provenance_report_decision_id`
- `source_policy_schema_version`
- `source_policy_revision`
- `source_policy_decision_id`
- `artifact_class`
- `artifact_family`
- `authorized_lane`
- `authority_id`
- `authority_basis`
- `provider_id`
- `provider_name`
- `pinned_model_id`
- `pinned_model_revision`
- `forbidden_boundaries`
- `provenance_report_status`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The output contains only the safe source schema/revision/decision identity,
artifact class/family, authorized lane, authority identity/basis, pinned
provider/model identity, exact forbidden-boundary list, 10FT status metadata,
all-False gate status, exact claim boundary, and 10FT-owned generic errors.

## Status semantics

A valid intact policy artifact produces:

- `ok=True`;
- `provenance_report_status="verified_provenance"`;
- the sanitized safe provenance metadata;
- `errors=[]`.

Invalid or tampered input produces:

- `ok=False`;
- `provenance_report_status="invalid_report"`;
- empty source strings, `source_policy_revision=0`, and an empty
  `forbidden_boundaries` list;
- `errors=["routing_provenance_artifact is not a valid 10FT routing provenance
  policy"]`.

Raw source errors and source details are never propagated on failure.

## 10FT report decision ID and export

The 10FT report decision ID commits to all 27 output fields except
`provenance_report_decision_id` itself. The canonical/hash procedure matches the
source policy procedure, with prefix `10FT-`.

The strict exporter snapshots an exact plain dictionary, immediately detaches
the two caller-owned lists, validates exact shape, strict built-in types,
status/source consistency, safe metadata, exact forbidden boundaries, all-False
gate flags, generic error mapping, and the complete 10FT report decision ID,
then emits deterministic sorted JSON. Malformed or tainted reports raise
`ValueError`.

## Data not emitted

10FT never emits:

- source policy type, scope, lock booleans, allowed action, or source gate
  fields;
- explicit sensitive/credential fields, known credential-shaped values, or raw
  provider/model payloads;
- raw configuration, configuration paths, file paths, or ledger paths;
- ledger records, record hashes, or raw hashes;
- raw source errors;
- `equality_signal_value` or `equality_signal_type`;
- runtime state;
- movement, map lookup, route execution, event, NPC, social, or timing fields.

## Forbidden behavior

10FT does not:

- import or call 10FN or any proof-chain phase;
- import or call 10CP or any backend module;
- invoke a model, call a provider, launch an agent, or mutate configuration;
- accept a ledger/config path or use a default production path;
- open, read, list, inspect, scan, glob, or walk any file or directory;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import filesystem, process, network, provider, model, agent, or runtime
  clients;
- promote results into runtime or world state;
- create movement, map, route execution, event, NPC, social, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

Imports are limited to `__future__`, `hashlib`, `json`, and `typing`. All
runtime/world/gate flags remain False. Gate-7 is closed by absence. 10CP remains
the sole writer.

## Trust boundary

10FT structurally and semantically validates one caller-supplied policy
artifact, including its exact 32-field envelope and complete policy decision
ID. It reports internal policy integrity and safe provenance metadata. It does
not authenticate the real-world provenance of a fabricated-but-self-consistent
policy, independently authorize a lane/model/provider, or execute routing.
Callers remain responsible for supplying an artifact produced under the named
authority.

Lane, authority, provider, and model identities are deliberately opaque
syntax-checked identifiers. 10FT rejects explicit sensitive fields and guarded
known credential/path/equality markers, but it cannot infer whether a caller has
misused an otherwise syntax-valid opaque identifier to encode undisclosed
sensitive material. The caller remains responsible for that semantic boundary;
10FT is not a credential-discovery or authentication system.

## Tests and checks

- Initial TDD RED: missing 10FT module collection error.
- 10FT targeted suite from repo root: 238 passed.
- Optional 10FN targeted regression: 184 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports, no backend/proof-chain/writer calls,
  no file/process/network/provider/model/agent/config/runtime calls, no
  forbidden config paths, immediate list detachment, and snapshot-before-key
  validation.
- CI pure-test list includes the 10FT test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10FT implements only the 10FR-authorized governance/provenance reporter. It
does not extend or reopen the proof chain closed at 10FN. It adds no ledger or
configuration path, read/write surface, backend/provider/model/agent call,
runtime execution, or gate-7 work. 10CP remains the sole writer. Gate-7 remains
closed. 10FU will sync 10FT metadata only after the implementation commit is
pushed; 10FV may audit the pushed boundary afterward.
