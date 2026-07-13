# Phase 10EV - Minimal Inert Ledger Status Digest Verifier

10EV implements the single candidate named by 10ET. It is a pure read-only,
in-process, caller-driven verifier over one caller-supplied exact 10EP digest
dictionary. It never accepts a ledger path, opens or scans a file, calls 10DX,
10ED, 10EJ, 10EP, or 10CP, or promotes verification data into runtime or world
state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `3019927 docs: record 10EU metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10EV test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 174 passed.

## Public API

```python
verify_minimal_inert_ledger_status_digest_report(
    digest_report: dict | None,
) -> dict

export_minimal_inert_ledger_status_digest_verification_report(
    verification_report: dict,
) -> str
```

The verifier accepts exactly one caller-supplied 10EP digest dictionary. It has
no path parameter and no default production path. Missing, non-dictionary,
subclassed, malformed, inconsistent, or tampered input fails closed into the
same sanitized `invalid_digest` verification report.

## Source boundary

10EV requires the exact 31-field 10EP output envelope:

- `ok`
- `digest_schema_version`
- `digest_type`
- `digest_scope`
- `digest_decision_id`
- `source_bundle_schema_version`
- `source_bundle_decision_id`
- `source_bundle_status`
- `source_ok`
- `source_summary_status`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hash_count`
- `recognized_signal_types_seen`
- `recognized_signal_type_count`
- `append_only_line_format_valid`
- `source_error_count`
- `digest_status`
- `digest_text`
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `world_sim_data_accessed`
- `gate7_activity_allowed`
- `claim_boundary`
- `errors`

Required identity and type rules:

- `digest_schema_version == "10EP.1"`;
- `digest_type == "minimal_inert_ledger_status_digest_report"`;
- `digest_scope == "inert_ledger_status_digest_only"`;
- `digest_decision_id` is `10EP-` followed by 32 lowercase hexadecimal
  characters and must equal the independently recomputed 10EP decision ID;
- the 10EP claim boundary is exact;
- all booleans are exact built-in booleans;
- all counts are exact non-negative built-in integers;
- `recognized_signal_types_seen` is an exact built-in sorted unique list of
  known inert built-in strings and its length equals
  `recognized_signal_type_count`;
- all gate flags are strictly `False`;
- `digest_text` exactly matches the 10EP deterministic format;
- `errors` is an exact built-in list with the exact 10EP error mapping for the
  selected digest status;
- dictionary, list, string, and integer subclasses are rejected.

10EV copies caller-owned list fields before content validation. It checks the
source 10EJ `source_bundle_decision_id` for exact `10EJ-` plus 32 lowercase
hexadecimal syntax only and deliberately does **not** recompute it. Recomputing
that identifier would duplicate 10EJ bundle logic and require forbidden source
lineage fields. The source 10EJ identifier remains an opaque safe status ID.

## 10EP decision-ID verification

10EV independently reconstructs the exact 10EP decision material:

- `digest_schema_version`
- `digest_scope`
- `source_bundle_schema_version`
- `source_bundle_decision_id`
- `source_bundle_status`
- `source_ok`
- `source_summary_status`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hash_count`
- `recognized_signal_types_seen`
- `recognized_signal_type_count`
- `append_only_line_format_valid`
- `source_error_count`
- `digest_status`
- `digest_text`
- `errors`

The material is serialized with sorted keys, compact separators, and
`ensure_ascii=False`, encoded as UTF-8, and hashed with SHA-256. The required
identifier is `10EP-` plus the first 32 lowercase hexadecimal characters. No
ledger record, record hash, 10DX ID, 10ED ID, or 10EJ ID is recomputed.

## Valid 10EP statuses

10EV accepts all three exact 10EP statuses when their complete envelopes are
internally valid and their 10EP decision IDs match:

- `verified_digest`: exact valid `verified_bundle`, source and digest
  `ok=True`, exact verified aggregates, exact digest text, and no 10EP errors;
- `non_verified_digest`: exact valid `verification_failed_bundle`,
  `invalid_10dx_source`, `invalid_10ed_source`, or `mismatched_sources`, digest
  `ok=False`, exact aggregate sanitization/status, exact digest text, and the
  one generic 10EP non-verified error;
- `invalid_10ej_source`: exact fully sanitized source aggregate, digest
  `ok=False`, exact invalid-source digest text, and the one generic 10EP
  invalid-source error.

A valid 10EP digest with any of these statuses produces a successful 10EV
integrity result. 10EV `ok` reports whether the supplied digest artifact is
intact; it does not promote the underlying 10EP source-success boolean.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10EV returns exactly these 35 safe aggregate fields:

- `ok`
- `verifier_schema_version = "10EV.1"`
- `verifier_type = "minimal_inert_ledger_status_digest_verifier"`
- `verifier_scope = "inert_ledger_status_digest_verification_only"`
- `verifier_decision_id`
- `source_digest_schema_version`
- `source_digest_decision_id`
- `source_digest_status`
- `source_digest_ok`
- `source_bundle_schema_version`
- `source_bundle_decision_id`
- `source_bundle_status`
- `source_ok`
- `source_summary_status`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hash_count`
- `recognized_signal_types_seen`
- `recognized_signal_type_count`
- `append_only_line_format_valid`
- `source_error_count`
- `digest_text_valid`
- `verification_status`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

Verification statuses:

- `digest_intact`: the exact 10EP envelope, status mapping, digest text, and
  independently recomputed 10EP decision ID are valid. 10EV `ok=True`,
  `digest_text_valid=True`, and errors are empty for every valid 10EP status.
- `invalid_digest`: invalid or tampered input. All source aggregate fields are
  sanitized to empty/zero/False values, `digest_text_valid=False`, 10EV
  `ok=False`, and the only error is
  `digest_report is not a valid 10EP digest`.

10EV never emits the supplied 10EP `digest_text` or `errors`. It emits only the
boolean `digest_text_valid` and the allowed safe source aggregates.

## 10EV decision ID and export

The 10EV decision ID hashes these safe verification fields:

- `verifier_schema_version`
- `verifier_scope`
- `source_digest_schema_version`
- `source_digest_decision_id`
- `source_digest_status`
- `source_digest_ok`
- `source_bundle_schema_version`
- `source_bundle_decision_id`
- `source_bundle_status`
- `source_ok`
- `source_summary_status`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hash_count`
- `recognized_signal_types_seen`
- `recognized_signal_type_count`
- `append_only_line_format_valid`
- `source_error_count`
- `digest_text_valid`
- `verification_status`
- `errors`

The canonical/hash procedure matches the 10EP procedure, with prefix `10EV-`.
The decision material excludes `verifier_decision_id` itself. The strict
exporter validates exact shape, strict built-in types, status/source aggregate
consistency, all-False gate flags, generic error mapping, and the 10EV decision
ID before serializing a fresh plain-dictionary snapshot as deterministic sorted
JSON.

## Data not emitted

10EV never emits:

- `digest_text`;
- `source_verifier_decision_id` or `source_reporter_decision_id`;
- `verified_record_hashes` or any raw hash value;
- raw 10DX, 10ED, 10EJ, or 10EP errors;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or an `equality_signal_type` field;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only safe digest/bundle IDs, statuses, counts, known signal-type names/count,
source error count, source summary status, digest-text validity, and all-False
gate status are retained for intact digests.

## Forbidden behavior

10EV does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10ED summary reporter;
- import or call the 10EJ bundle reporter;
- import or call the 10EP digest reporter;
- import or call the 10CP writer;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import `pathlib`, `os`, backend modules, network modules, or subprocess APIs;
- promote verification results into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Trust boundary

10EV structurally and semantically validates one caller-supplied 10EP digest,
including its exact deterministic text and decision ID. It does not call 10EP,
re-run 10EJ, or recompute the opaque source 10EJ decision ID. Therefore 10EV
attests to the internal integrity of a 10EP digest artifact, not the provenance
of an arbitrary fabricated-but-self-consistent 10EP/10EJ dictionary. Callers
remain responsible for supplying a digest produced by the authorized 10EP
function.

## Tests and checks

- Initial TDD RED: missing 10EV module collection error.
- 10EV targeted suite from repo root: 174 passed.
- 10EP + 10EV bounded suite from `world-sim`: 297 passed.
- Optional 10EJ + 10EP + 10EV bounded regression from `world-sim`: 472 passed.
- Optional 10DX + 10ED + 10EJ + 10EP + 10EV bounded regression from
  `world-sim`: 688 passed.
- Optional 10CP + 10DR + 10DX + 10ED + 10EJ + 10EP + 10EV bounded regression
  from `world-sim`: 802 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/10DX/10ED/10EJ/10EP/10CP import or call, no file access
  or mutation, no scanning, and no runtime APIs.
- CI pure-test list includes the 10EV test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10EV implements only the 10ET-authorized status digest verifier. It adds no
ledger path, read or write surface, verification/summary/bundle/digest call,
batch verifier, local-sim bridge, runtime execution, or gate-7 work. 10CP
remains the only writer. Gate-7 remains closed.
