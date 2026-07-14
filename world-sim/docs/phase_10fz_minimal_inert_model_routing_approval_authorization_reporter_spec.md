# Phase 10FZ - Minimal Inert Model Routing Approval Authorization Reporter

10FZ implements the single candidate named by 10FX. It is the first
approval/execution-authorization governance layer after the provenance branch
closed at 10FW. It is a pure read-only, in-process, caller-driven reporter over
two caller-supplied dictionaries:

1. one exact 10FT.1 verified provenance report; and
2. one exact 10FZ approval/authorization artifact.

10FZ reports whether the supplied provenance has matching operator
authorization. It does not execute routing, verify 10FN, reopen either closed
branch, invoke a model, call a provider, launch an agent, mutate configuration,
read or write a file, or promote report data into runtime/world state. Gate-7
remains closed.

## Baseline and model

- Baseline: `85dbb71 docs: record 10FY metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10FZ test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 337 passed.
- Optional 10FT provenance regression: 238 passed.
- Optional 10FN proof-chain regression: 184 passed.

## Public API

```python
create_minimal_inert_model_routing_approval_authorization_report(
    provenance_report: dict | None,
    approval_authorization_artifact: dict | None,
) -> dict

export_minimal_inert_model_routing_approval_authorization_report(
    authorization_report: dict,
) -> str
```

The reporter accepts exactly two caller-supplied dictionaries. It has no path,
provider, model, config, agent, runtime, or backend handle. Missing, non-dict,
subclassed, malformed, inconsistent, or tampered structure fails closed into
the same sanitized `invalid_report` output.

## Input 1: exact 10FT.1 provenance envelope

10FZ independently requires exactly these 28 fields:

- `ok`
- `provenance_report_schema_version`
- `provenance_report_type`
- `provenance_report_scope`
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
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `world_sim_data_accessed`
- `gate7_activity_allowed`
- `claim_boundary`
- `errors`

Required provenance rules:

- exact built-in dict/list/string/integer/boolean types only;
- `ok is True`;
- `provenance_report_schema_version == "10FT.1"`;
- `provenance_report_type ==
  "minimal_inert_model_routing_provenance_report"`;
- `provenance_report_scope == "model_routing_provenance_report_only"`;
- `source_policy_schema_version == "10FT.POLICY.1"`;
- `source_policy_revision` is the exact built-in integer `1`;
- `provenance_report_status == "verified_provenance"`;
- `provenance_report_decision_id` has exact `10FT-` plus 32 lowercase
  hexadecimal syntax;
- `source_policy_decision_id` has exact `10FT-POLICY-` plus 32 lowercase
  hexadecimal syntax;
- safe artifact/lane/authority/provider/model metadata and exact required
  prefixes;
- `provider_id == "provider:" + provider_name`;
- exact deterministic forbidden-boundary list;
- all seven output gate flags exactly `False` (`0` is rejected);
- exact 10FT report claim boundary; and
- `errors` is an exact built-in empty list.

10FZ snapshots the exact plain dictionary before key/type validation and
immediately detaches both caller-owned lists before content validation. It does
not import or call 10FT. It deliberately treats both 10FT decision IDs as
opaque syntax-checked identifiers and does not recompute either identifier.

## Input 2: exact approval artifact envelope

10FZ requires exactly these 35 fields:

- `approval_schema_version`
- `approval_revision`
- `approval_type`
- `approval_scope`
- `approval_decision_id`
- `approval_status`
- `approval_authority_id`
- `approval_authority_basis`
- `approver_lane`
- `approved_action`
- `approved_artifact_class`
- `approved_artifact_family`
- `approved_authorized_lane`
- `approved_authority_id`
- `approved_authority_basis`
- `approved_provider_id`
- `approved_provider_name`
- `approved_pinned_model_id`
- `approved_pinned_model_revision`
- `referenced_provenance_report_decision_id`
- `referenced_source_policy_decision_id`
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

Required approval rules:

- exact built-in dict/list/string/integer/boolean types only;
- `approval_schema_version == "10FZ.APPROVAL.1"`;
- `approval_revision` is the exact built-in integer `1`;
- `approval_type ==
  "minimal_inert_model_routing_approval_authorization_artifact"`;
- `approval_scope == "model_routing_approval_authorization_only"`;
- `approval_status` is exactly `operator_approved` or `operator_denied`;
- `approval_decision_id` has exact `10FZ-APPROVAL-` plus 32 lowercase
  hexadecimal syntax and equals the independently recomputed identifier;
- `approval_authority_id` has the `approval-authority:` prefix;
- `approver_lane` and `approved_authorized_lane` have the `lane:` prefix;
- `approved_authority_id` has the `authority:` prefix;
- `approved_provider_id` has the `provider:` prefix and equals
  `"provider:" + approved_provider_name`;
- `approved_pinned_model_id` has the `model:` prefix;
- `approved_action == "authorize_routing_execution"`;
- both referenced 10FT identifiers have exact syntax but are not recomputed;
- exact deterministic forbidden-boundary list;
- all eleven execution/provider/model/config/agent/world/gate flags exactly
  `False`;
- exact approval claim boundary; and
- `errors` is an exact built-in empty list.

The approval authority, approver lane, approved lane/authority, and referenced
10FT identifiers are opaque syntax-checked external identities. 10FZ does not
recompute or authenticate them.

## Exact forbidden boundaries

Both valid inputs and every valid 10FZ output carry this exact built-in list of
exact built-in strings in deterministic order:

1. `agent_launch`
2. `config_mutation`
3. `filesystem_scan`
4. `gate7_activity`
5. `model_invocation`
6. `provider_call`
7. `runtime_execution`
8. `world_sim_data_access`

Missing, extra, duplicated, reordered, unknown, or subclassed entries fail
closed.

## Approval decision ID

The approval decision ID commits to all 34 approval fields except
`approval_decision_id` itself. The complete safe material is serialized with
sorted keys, compact separators, and `ensure_ascii=False`, encoded as UTF-8,
and hashed with SHA-256. The required identifier is `10FZ-APPROVAL-` plus the
first 32 lowercase hexadecimal characters.

This validates only the approval artifact's internal integrity. It does not
authenticate an operator, call a provider, invoke a model, or grant execution.

## Approval/provenance matching

An internally valid `operator_approved` artifact authorizes only when all of
these approval fields exactly match the supplied provenance report:

- referenced provenance and source-policy decision IDs;
- artifact class and family;
- authorized lane;
- authority ID and basis;
- provider ID and name;
- pinned model ID and revision; and
- exact forbidden boundaries.

An internally valid denial or internally valid approved-but-mismatched artifact
is a valid governance result, not malformed input. It produces
`not_authorized/ok=True`. Structural/type/identity/hash taint produces
`invalid_report/ok=False`.

## Exact 10FZ.1 output envelope

10FZ returns exactly these 35 safe fields:

- `ok`
- `authorization_report_schema_version = "10FZ.1"`
- `authorization_report_type =
  "minimal_inert_model_routing_approval_authorization_report"`
- `authorization_report_scope =
  "model_routing_approval_authorization_report_only"`
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
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The compact output deliberately omits the approver lane, approved mirror
fields, source gate flags, raw source errors, and every execution payload. The
approval decision ID commits to the full approval artifact, while the 10FZ
decision ID commits to the compact report.

## Status semantics

Valid provenance plus an internally valid matching approval produces:

- `ok=True`;
- `authorization_report_status="authorized"`;
- `approval_status="operator_approved"`; and
- `errors=[]`.

Valid provenance plus an internally valid denial produces:

- `ok=True`;
- `authorization_report_status="not_authorized"`;
- `approval_status="operator_denied"`; and
- `errors=[]`.

Valid provenance plus an internally valid approved-but-mismatched artifact
produces:

- `ok=True`;
- `authorization_report_status="not_authorized"`;
- `approval_status="operator_approved"`; and
- `errors=[]`.

Malformed or tampered input produces:

- `ok=False`;
- `authorization_report_status="invalid_report"`;
- empty source/approval strings, `approval_revision=0`, and an empty boundary
  list; and
- one generic 10FZ-owned error with no raw source detail.

## 10FZ report decision ID and exporter

The 10FZ report decision ID commits to all 34 output fields except
`authorization_report_decision_id` itself. It uses the same canonical SHA-256
procedure with prefix `10FZ-`.

The strict exporter snapshots an exact plain dictionary, immediately detaches
both lists, validates exact shape, strict built-in types, status/source
consistency, safe metadata, opaque identifier syntax, exact boundaries,
all-False gate flags, generic error mapping, and the complete 10FZ report
decision ID, then emits deterministic sorted JSON. Malformed or tainted reports
raise `ValueError`.

Because approved mirror fields are intentionally omitted, the exporter can
verify that `authorized` requires `operator_approved`, but cannot reconstruct
which source field caused an `operator_approved/not_authorized` mismatch. The
source approval decision ID commits to those omitted fields. This exporter is
an integrity guard over a caller-supplied report, not an authentication system.

## Data not emitted

10FZ never emits:

- approver lane or approved mirror fields beyond the safe approved action;
- source provider/model/config/agent gate fields;
- explicit credential fields, raw provider/model payloads, or raw config;
- configuration, file, ledger, or production paths;
- ledger records, record hashes, or raw hashes;
- raw source errors;
- `equality_signal_value` or `equality_signal_type`;
- runtime state; or
- movement, map, route execution, event, NPC, social, or timing fields.

## Forbidden behavior

10FZ does not:

- import or call 10FT, 10FN, 10CP, or any prior/backend phase;
- recompute 10FT or proof-chain decision IDs;
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

10FZ structurally validates two caller-supplied artifacts, including exact
envelopes and the complete approval decision ID. It reports internal
authorization consistency. It does not authenticate a real-world operator,
independently attest the 10FT provenance, grant execution, or execute routing.

10FT decision IDs, lane IDs, authority IDs, and external approval identities
remain opaque syntax-checked identifiers. Known credential/path/equality
markers and generic compacted token markers are rejected, but 10FZ cannot infer
whether a caller encoded undisclosed sensitive semantics in otherwise safe
opaque text. Decision IDs are unkeyed integrity hashes, not signatures. The
caller remains responsible for authentic source custody.

## Tests and checks

- Initial TDD RED: missing 10FZ module collection error.
- 10FZ targeted suite from repo root: 337 passed.
- Optional 10FT targeted regression: 238 passed.
- Optional 10FN targeted regression: 184 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports; no backend/prior-phase/writer calls;
  no file/process/network/provider/model/agent/config/runtime calls or aliases;
  no forbidden config paths or raw sensitive markers; immediate list
  detachment; and snapshot-before-key validation.
- A real 10FT producer artifact interoperates with 10FZ without production
  import/call or 10FT decision-ID recomputation.
- CI pure-test list includes the 10FZ test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10FZ implements only the 10FX-authorized approval-authorization reporter. It
does not extend or reopen the proof chain closed at 10FN or the provenance
branch closed at 10FW. It adds no file/config path, read/write surface,
backend/provider/model/agent call, runtime execution, or gate-7 work. 10CP
remains the sole writer. Gate-7 remains closed. After 10FZ is pushed, 10GA will
sync its metadata.
