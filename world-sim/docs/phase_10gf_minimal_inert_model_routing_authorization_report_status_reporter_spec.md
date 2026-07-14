# Phase 10GF - Minimal Inert Model Routing Authorization Report Status Reporter

10GF implements the single candidate named by 10GD. It is a pure read-only,
in-process, caller-driven status reporter over one caller-supplied exact 35-field
10FZ.1 authorization report dictionary.

10GF reports whether that supplied authorization report is structurally intact
and whether its status is `authorized` or `not_authorized`. It does not execute
routing, re-authorize approval, recursively verify approval, verify 10FN, read a
ledger, invoke a model, call a provider, launch an agent, mutate configuration,
read or write a file, or promote report data into runtime/world state. Gate-7
remains closed.

## Baseline and model

- Baseline: `a569dee docs: record 10GE metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10GF test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 298 passed.
- Optional 10FZ authorization-report regression: 337 passed.
- Optional 10FT provenance regression: 238 passed.
- Optional 10FN proof-chain regression: 184 passed.

## Public API

```python
create_minimal_inert_model_routing_authorization_report_status_report(
    authorization_report: dict | None,
) -> dict

export_minimal_inert_model_routing_authorization_report_status_report(
    status_report: dict,
) -> str
```

The reporter accepts exactly one caller-supplied dictionary. It has no path,
provider, model, config, agent, runtime, or backend handle. Missing, non-dict,
subclassed, malformed, inconsistent, or tampered structure fails closed into
the same sanitized `invalid_report` output.

## Exact 10FZ.1 input envelope

10GF independently requires exactly these 35 fields:

- `ok`
- `authorization_report_schema_version`
- `authorization_report_type`
- `authorization_report_scope`
- `authorization_report_decision_id`
- `source_provenance_schema_version`
- `source_provenance_decision_id`
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
- `approval_schema_version`
- `approval_revision`
- `approval_decision_id`
- `approval_status`
- `approval_authority_id`
- `approval_authority_basis`
- `approved_action`
- `forbidden_boundaries`
- `authorization_report_status`
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `world_sim_data_accessed`
- `gate7_activity_allowed`
- `claim_boundary`
- `errors`

Required source rules:

- exact built-in dict/list/string/integer/boolean types only;
- `ok is True`;
- `authorization_report_schema_version == "10FZ.1"`;
- `authorization_report_type ==
  "minimal_inert_model_routing_approval_authorization_report"`;
- `authorization_report_scope ==
  "model_routing_approval_authorization_report_only"`;
- `authorization_report_decision_id` has exact `10FZ-` plus 32 lowercase
  hexadecimal syntax and equals the independently recomputed identifier;
- `source_provenance_schema_version == "10FT.1"`;
- `source_provenance_decision_id` has exact `10FT-` plus 32 lowercase
  hexadecimal syntax;
- `source_policy_decision_id` has exact `10FT-POLICY-` plus 32 lowercase
  hexadecimal syntax;
- `approval_schema_version == "10FZ.APPROVAL.1"`;
- `approval_revision` is the exact built-in integer `1`;
- `approval_decision_id` has exact `10FZ-APPROVAL-` plus 32 lowercase
  hexadecimal syntax;
- `approval_status` is exactly `operator_approved` or `operator_denied`;
- `approved_action == "authorize_routing_execution"`;
- `authorization_report_status` is exactly `authorized` or `not_authorized`;
- `authorized` requires `operator_approved`, while `not_authorized` permits an
  internally valid denial or approved-but-mismatched 10FZ result;
- safe artifact/lane/authority/provider/model metadata and exact required
  prefixes;
- `provider_id == "provider:" + provider_name`;
- exact deterministic forbidden-boundary list;
- all seven output gate flags exactly `False` (`0` is rejected);
- exact 10FZ report claim boundary; and
- `errors` is an exact built-in empty list.

10GF snapshots the exact plain dictionary before key/type validation and
immediately detaches both caller-owned lists before content validation. It does
not import or call 10FZ. It deliberately treats source provenance, source
policy, approval, lane, authority, provider, and model identities as opaque
syntax-checked identifiers and does not recompute them.

## Exact forbidden boundaries

Every valid 10FZ input carries this exact built-in list of exact built-in
strings in deterministic order:

1. `agent_launch`
2. `config_mutation`
3. `filesystem_scan`
4. `gate7_activity`
5. `model_invocation`
6. `provider_call`
7. `runtime_execution`
8. `world_sim_data_access`

Missing, extra, duplicated, reordered, unknown, or subclassed entries fail
closed. The list is validated but is not re-emitted by the compact 10GF report.

## Source 10FZ decision ID

The supplied 10FZ authorization decision ID commits to all 34 input fields
except `authorization_report_decision_id` itself. 10GF independently serializes
that complete material with sorted keys, compact separators, and
`ensure_ascii=False`, encodes it as UTF-8, and hashes it with SHA-256. The
required identifier is `10FZ-` plus the first 32 lowercase hexadecimal
characters.

This validates only the supplied report's internal integrity. It does not
recompute the 10FZ approval decision ID, authenticate an operator, call a
provider, invoke a model, grant execution, or re-authorize routing.

## Exact 10GF.1 output envelope

10GF returns exactly these 30 safe fields:

- `ok`
- `authorization_status_report_schema_version = "10GF.1"`
- `authorization_status_report_type =
  "minimal_inert_model_routing_authorization_report_status_report"`
- `authorization_status_report_scope =
  "model_routing_authorization_report_status_only"`
- `authorization_status_report_decision_id`
- `source_authorization_schema_version`
- `source_authorization_decision_id`
- `source_authorization_status`
- `source_authorization_ok`
- `source_provenance_decision_id`
- `source_policy_decision_id`
- `approval_decision_id`
- `approval_status`
- `artifact_class`
- `artifact_family`
- `authorized_lane`
- `provider_id`
- `provider_name`
- `pinned_model_id`
- `pinned_model_revision`
- `authorization_status_report_status`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The output deliberately omits source authorization type/scope, source
provenance schema version, authority details, approval schema/revision/authority
details, approved action, forbidden boundaries, source errors, and every
execution payload. It carries only the exact safe status metadata explicitly
authorized by the 10GF contract.

## Status semantics

An exact valid source with `authorization_report_status="authorized"` produces:

- `ok=True`;
- `source_authorization_ok=True`;
- `source_authorization_status="authorized"`;
- `authorization_status_report_status="authorized_status"`;
- `approval_status="operator_approved"`; and
- `errors=[]`.

An exact valid source with
`authorization_report_status="not_authorized"` produces:

- `ok=True`;
- `source_authorization_ok=True`;
- `source_authorization_status="not_authorized"`;
- `authorization_status_report_status="not_authorized_status"`;
- `approval_status` preserved as `operator_denied` or `operator_approved`; and
- `errors=[]`.

Malformed or tampered input produces:

- `ok=False`;
- `source_authorization_ok=False`;
- `authorization_status_report_status="invalid_report"`;
- every source string empty; and
- one generic 10GF-owned error with no raw source detail.

## 10GF decision ID and exporter

The 10GF decision ID commits to all 29 output fields except
`authorization_status_report_decision_id` itself. It uses the same canonical
SHA-256 procedure with prefix `10GF-`.

The strict exporter snapshots an exact plain dictionary, immediately detaches
the caller-owned error list, validates exact shape, strict built-in types,
status/source consistency, safe metadata, opaque identifier syntax, all-False
gate flags, generic error mapping, neutral invalid-report fields, and the
complete 10GF decision ID, then emits deterministic sorted JSON. Malformed or
tainted reports raise `ValueError`.

The exporter cannot reconstruct the omitted 10FZ fields and therefore does not
recompute the source 10FZ decision ID. The creator already performs that
complete 34-field check before producing 10GF. The exporter validates the
source ID's exact syntax and the 10GF decision ID that commits to it. This is an
integrity guard, not an authentication system.

## Data not emitted

10GF never emits:

- source authorization type/scope or source provenance schema version;
- source authority or approval-authority details;
- approved action or forbidden-boundary list;
- explicit credential fields, raw provider/model payloads, or raw config;
- configuration, file, ledger, or production paths;
- ledger records, record hashes, or raw hash fields;
- raw source errors;
- `equality_signal_value` or `equality_signal_type`;
- runtime state; or
- movement, map, route execution, event, NPC, social, or timing fields.

## Forbidden behavior

10GF does not:

- import or call 10FZ, 10FT, 10FN, 10CP, or any prior/backend phase;
- recompute 10FZ approval, 10FT, 10FN, or proof-chain decision IDs;
- invoke a model, call a provider, launch an agent, or mutate configuration;
- accept a file, ledger, config, or production path;
- open, read, list, inspect, scan, glob, or walk any file or directory;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import filesystem, process, network, provider, model, agent, config, or
  runtime clients;
- promote results into runtime or world state;
- create movement, map, route execution, event, NPC, social, or timing behavior;
  or
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

Imports are limited to `__future__`, `hashlib`, `json`, and `typing`. All
runtime/world/gate flags remain False. Gate-7 is closed by absence. 10CP remains
the sole writer.

## Trust boundary

10GF structurally validates one caller-supplied 10FZ.1 artifact, including its
exact envelope and complete authorization report decision ID. It reports the
artifact's compact authorization status. It does not authenticate a real-world
operator, independently attest the source provenance or approval, grant
execution, or execute routing.

Source provenance, policy, approval, lane, authority, provider, and model
identities remain opaque syntax-checked contract values. Known credential,
path, equality, and generic compacted sensitive markers are rejected, but 10GF
cannot infer whether a caller encoded undisclosed semantics in otherwise safe
opaque text. Decision IDs are unkeyed integrity hashes, not signatures. The
caller remains responsible for authentic source custody.

## Tests and checks

- Initial TDD RED: missing 10GF module collection error.
- 10GF targeted suite from repo root: 298 passed.
- Optional 10FZ targeted regression: 337 passed.
- Optional 10FT targeted regression: 238 passed.
- Optional 10FN targeted regression: 184 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports; no backend/prior-phase/writer calls;
  no file/process/network/provider/model/agent/config/runtime calls or aliases;
  no direct public-input assignment/deletion; no forbidden config paths or raw
  sensitive markers; immediate list detachment; and snapshot-before-key
  validation.
- A real 10FZ producer artifact interoperates with 10GF without production
  import/call or source approval decision-ID recomputation.
- CI pure-test list includes the 10GF test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10GF implements only the 10GD-authorized authorization-report status reporter.
It does not extend or reopen the proof chain closed at 10FN, the provenance
branch closed at 10FW, or the approval-authorization branch closed at 10GC. It
adds no file/config path, read/write surface, backend/provider/model/agent call,
runtime execution, or gate-7 work. 10CP remains the sole writer. Gate-7 remains
closed. After 10GF is pushed, 10GG will sync its metadata.
