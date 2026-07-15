# Phase 10GR - Minimal Inert Model Routing Authorization Report Status Verification Verifier Status Verification Verifier Status Reporter

10GR implements the single candidate named by 10GP. It is a pure read-only,
in-process, caller-driven meta-verifier/status reporter over one caller-supplied
exact 34-field 10GL.1 authorization status verification report dictionary.

10GR verifies whether that supplied verification report is structurally intact,
whether its own 10GL decision ID recomputes correctly, and whether its status is
`verified_authorized_status` or `verified_not_authorized_status`. It does not
call 10GL, re-verify 10GF, re-authorize 10FZ, verify 10FT or 10FN, execute
routing, read a ledger, invoke a model, call a provider, launch an agent, mutate
configuration, read or write a file, or promote report data into runtime/world
state. Gate-7 remains closed.

## Baseline and model

- Baseline: `f2139a9 docs: record 10GQ metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10GR test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 362 passed.
- Optional 10GL verifier regression: 307 passed.
- Optional 10GF status-reporter regression: 298 passed.
- Optional 10FZ authorization-report regression: 337 passed.
- Optional 10FT provenance regression: 238 passed.
- Optional 10FN proof-chain regression: 184 passed.

## Public API

```python
create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report(
    verification_report: dict | None,
) -> dict

export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report(
    meta_verification_report: dict,
) -> str
```

The meta-verifier accepts exactly one caller-supplied dictionary. It has no
path, provider, model, config, agent, runtime, or backend handle. Missing,
non-dict, subclassed, malformed, inconsistent, or tampered structure fails
closed into the same sanitized `invalid_verification_report` output.

## Exact 10GL.1 input envelope

10GR independently requires exactly these 34 fields:

- `ok`
- `authorization_status_verification_schema_version`
- `authorization_status_verification_type`
- `authorization_status_verification_scope`
- `authorization_status_verification_decision_id`
- `source_status_report_schema_version`
- `source_status_report_decision_id`
- `source_status_report_status`
- `source_status_report_ok`
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
- `authorization_status_verification_status`
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

- exact built-in dict/list/string/boolean types only;
- `ok is True`, `source_status_report_ok is True`, and
  `source_authorization_ok is True`;
- `authorization_status_verification_schema_version == "10GL.1"`;
- `authorization_status_verification_type ==
  "minimal_inert_model_routing_authorization_report_status_verification_verifier_status_report"`;
- `authorization_status_verification_scope ==
  "model_routing_authorization_report_status_verification_only"`;
- `authorization_status_verification_decision_id` has exact `10GL-` plus 32
  lowercase hexadecimal syntax and equals the independently recomputed ID;
- `source_status_report_schema_version == "10GF.1"`;
- `source_status_report_decision_id` has exact `10GF-` plus 32 lowercase
  hexadecimal syntax;
- `source_status_report_status` is exactly `authorized_status` or
  `not_authorized_status`;
- `source_authorization_schema_version == "10FZ.1"`;
- `source_authorization_decision_id` has exact `10FZ-` plus 32 lowercase
  hexadecimal syntax;
- `source_authorization_status` is exactly `authorized` or `not_authorized`;
- `source_provenance_decision_id` has exact `10FT-` plus 32 lowercase
  hexadecimal syntax;
- `source_policy_decision_id` has exact `10FT-POLICY-` plus 32 lowercase
  hexadecimal syntax;
- `approval_decision_id` has exact `10FZ-APPROVAL-` plus 32 lowercase
  hexadecimal syntax;
- `approval_status` is exactly `operator_approved` or `operator_denied`;
- `authorization_status_verification_status` is exactly
  `verified_authorized_status` or `verified_not_authorized_status`;
- `verified_authorized_status` requires source status-report status
  `authorized_status`, source authorization status `authorized`, and
  `operator_approved`;
- `verified_not_authorized_status` requires source status-report status
  `not_authorized_status`, source authorization status `not_authorized`, and
  permits `operator_denied` or `operator_approved`;
- safe artifact/lane/provider/model metadata and exact required prefixes;
- `provider_id == "provider:" + provider_name`;
- all seven gate flags exactly `False` (`0` is rejected);
- the exact 10GL verification claim boundary; and
- `errors` is an exact built-in empty list.

10GR snapshots the exact plain dictionary before key/type validation and
immediately detaches the caller-owned error list before content validation. It
does not import or call 10GL. It deliberately treats source status-report,
authorization, provenance, policy, approval, lane, provider, and model
identities as opaque syntax-checked identifiers and does not recompute them.

## Source 10GL decision ID

The supplied 10GL verification decision ID commits to all 33 input fields
except `authorization_status_verification_decision_id` itself. 10GR
independently serializes that complete material with sorted keys, compact
separators, and `ensure_ascii=False`, encodes it as UTF-8, and hashes it with
SHA-256. The required identifier is `10GL-` plus the first 32 lowercase
hexadecimal characters.

This validates only the supplied verification report's internal integrity. It
does not recompute the 10GF status-report ID, 10FZ authorization/approval IDs,
10FT, 10FN, or any proof-chain ID; authenticate an operator; call a provider;
invoke a model; grant execution; or re-authorize routing.

## Exact 10GR.1 output envelope

10GR returns exactly these 38 safe fields:

- `ok`
- `authorization_status_meta_verification_schema_version = "10GR.1"`
- `authorization_status_meta_verification_type =
  "minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report"`
- `authorization_status_meta_verification_scope =
  "model_routing_authorization_report_status_verification_verifier_status_verification_only"`
- `authorization_status_meta_verification_decision_id`
- `source_verification_schema_version`
- `source_verification_decision_id`
- `source_verification_status`
- `source_verification_ok`
- `source_status_report_schema_version`
- `source_status_report_decision_id`
- `source_status_report_status`
- `source_status_report_ok`
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
- `authorization_status_meta_verification_status`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The output carries only the safe verification/status/identity/lane/provider/
model metadata explicitly required by the 10GR operator contract. It omits the
source verification type/scope/claim boundary/errors, source raw errors,
authorization authority details, approval authority details, approved action,
forbidden boundaries, and every execution payload.

## Status semantics

An exact valid source with
`authorization_status_verification_status="verified_authorized_status"`
produces:

- `ok=True`;
- all three carried source ok fields and `source_verification_ok=True`;
- `source_verification_status="verified_authorized_status"`;
- `source_status_report_status="authorized_status"`;
- `source_authorization_status="authorized"`;
- `authorization_status_meta_verification_status=
  "verified_authorized_verification_status"`;
- `approval_status="operator_approved"`; and
- `errors=[]`.

An exact valid source with
`authorization_status_verification_status="verified_not_authorized_status"`
produces:

- `ok=True`;
- all carried source ok fields `True`;
- `source_verification_status="verified_not_authorized_status"`;
- `source_status_report_status="not_authorized_status"`;
- `source_authorization_status="not_authorized"`;
- `authorization_status_meta_verification_status=
  "verified_not_authorized_verification_status"`;
- `approval_status` preserved as `operator_denied` or `operator_approved`; and
- `errors=[]`.

Malformed or tampered input produces:

- `ok=False`;
- `source_verification_ok=False`;
- `source_status_report_ok=False`;
- `source_authorization_ok=False`;
- `authorization_status_meta_verification_status=
  "invalid_verification_report"`;
- every source string empty; and
- one generic 10GR-owned error with no raw source detail.

## 10GR decision ID and exporter

The 10GR decision ID commits to all 37 output fields except
`authorization_status_meta_verification_decision_id` itself. It uses the same
canonical SHA-256 procedure with prefix `10GR-`.

The strict exporter snapshots an exact plain dictionary, immediately detaches
the caller-owned error list, validates exact shape, strict built-in types,
meta-verification/source-status consistency, safe metadata, opaque identifier
syntax, all-False gate flags, generic error mapping, neutral invalid-report
fields, and the complete 10GR decision ID, then emits deterministic sorted JSON.
Malformed or tainted reports raise `ValueError`.

The exporter cannot reconstruct the omitted 10GL type/scope/claim-boundary/
errors fields and therefore does not recompute the source 10GL decision ID. The
creator already performs that complete 33-field check before producing 10GR.
The exporter validates the carried source ID's exact syntax and the 10GR
decision ID that commits to it. This is an integrity guard, not authentication.

## Data not emitted

10GR never emits:

- source verification type/scope/claim boundary or source raw errors;
- source authority or approval-authority details;
- approved action or forbidden-boundary list;
- explicit credential fields, raw provider/model payloads, or raw config;
- configuration, file, ledger, or production paths;
- ledger records, record hashes, or raw hash fields;
- `equality_signal_value` or `equality_signal_type`;
- runtime state; or
- movement, map, route execution, event, NPC, social, or timing fields.

Safe-text validation rejects path traversal, slash/backslash paths, Windows
drive-relative path shapes including paths hidden behind lane/provider/model
prefixes, common compacted credential/key markers, equality markers, and unsafe
prefix or character forms. Invalid input never copies source detail into output.

## Forbidden behavior

10GR does not:

- import or call 10GL, 10GF, 10FZ, 10FT, 10FN, 10CP, or any prior/backend
  phase;
- recompute 10GF, 10FZ authorization/approval, 10FT, 10FN, or proof-chain IDs;
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

10GR structurally validates one caller-supplied 10GL.1 artifact, including its
exact envelope and complete authorization status verification decision ID. It
reports the artifact's meta-verification status. It does not authenticate a
real-world operator, independently attest source status/authorization/
provenance/approval, grant execution, or execute routing.

Source status-report, authorization, provenance, policy, approval, lane,
provider, and model identities remain opaque syntax-checked contract values.
Known credential, path, equality, and compacted sensitive markers are rejected,
but 10GR cannot infer whether a caller encoded undisclosed semantics in
otherwise safe opaque text. Decision IDs are unkeyed integrity hashes, not
signatures. The caller remains responsible for authentic source custody.

## Tests and checks

- Initial TDD RED: missing 10GR module collection error.
- Initial GREEN: 343 passed.
- Review-driven prefixed-path RED: 4 expected failures for lane/model-prefixed
  drive-relative paths; suffix-safe validation fixed the defect.
- Final 10GR targeted suite from repo root: 362 passed.
- Optional 10GL targeted regression: 307 passed.
- Optional 10GF targeted regression: 298 passed.
- Optional 10FZ targeted regression: 337 passed.
- Optional 10FT targeted regression: 238 passed.
- Optional 10FN targeted regression: 184 passed.
- Compileall passes for the implementation and test modules.
- The exact requested forbidden-token/boundary scan reports no matches.
- Static tests prove exact stdlib-only imports and aliases; fixed allowlisted
  call shapes; no backend/prior-phase/writer calls; no file/process/network/
  provider/model/agent/config/runtime calls or indirect callables; no direct or
  aliased public-input mutation; no forbidden config paths or raw sensitive
  markers; immediate list detachment; and snapshot-before-key validation.
- Real 10GL producer artifacts interoperate for authorized and both valid
  not-authorized approval variants; a producer-generated invalid artifact fails
  closed without source-error leakage.
- Two independent bounded reviews found no remaining implementation defects.
- CI pure-test list includes the 10GR test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10GR implements only the 10GP-authorized meta-verifier. It does not extend or
reopen the proof chain closed at 10FN, the provenance branch closed at 10FW, the
approval-authorization branch closed at 10GC, the status-report branch closed at
10GI, or the status-verification branch closed at 10GO. It adds no file/config
path, read/write surface, backend/provider/model/agent call, runtime execution,
or gate-7 work. 10CP remains the sole writer. Gate-7 remains closed.
