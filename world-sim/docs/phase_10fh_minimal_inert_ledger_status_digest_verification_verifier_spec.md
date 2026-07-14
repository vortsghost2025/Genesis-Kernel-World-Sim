# Phase 10FH - Minimal Inert Ledger Status Digest Verification Verifier

10FH implements the single candidate named by 10FF. It is a pure read-only,
in-process, caller-driven verifier over one caller-supplied exact 10FB
verification digest report dictionary. It never accepts a ledger path, opens
or scans a file, calls any earlier ledger reporter/verifier/writer, or promotes
report data into runtime or world state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `7be0f36 docs: record 10FG metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10FH test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 212 passed.

## Public API

```python
verify_minimal_inert_ledger_status_digest_verification_report(
    verification_digest_report: dict | None,
) -> dict

export_minimal_inert_ledger_status_digest_verification_verifier_report(
    verification_report: dict,
) -> str
```

The verifier accepts exactly one caller-supplied 10FB verification digest
report dictionary. It has no path parameter and no default production path.
Missing, non-dictionary, subclassed, malformed, inconsistent, or tampered input
fails closed into the same sanitized `invalid_digest` verification report.

## Source boundary

10FH requires the exact 40-field 10FB.1 output envelope:

- `ok`
- `verification_digest_schema_version`
- `verification_digest_type`
- `verification_digest_scope`
- `verification_digest_decision_id`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_verifier_status`
- `source_verifier_ok`
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
- `source_digest_text_valid`
- `verification_digest_status`
- `verification_digest_text`
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

- `verification_digest_schema_version == "10FB.1"`;
- `verification_digest_type ==
  "minimal_inert_ledger_status_digest_verification_report"`;
- `verification_digest_scope ==
  "inert_ledger_status_digest_verification_report_only"`;
- `verification_digest_decision_id` is `10FB-` followed by 32 lowercase
  hexadecimal characters and must equal the independently recomputed 10FB
  decision ID;
- the 10FB claim boundary is exact;
- all booleans are exact built-in booleans;
- all counts are exact non-negative built-in integers;
- `recognized_signal_types_seen` is an exact built-in sorted unique list of
  known inert built-in strings and its length equals
  `recognized_signal_type_count`;
- all gate flags are strictly `False`;
- `errors` is an exact built-in list with the exact 10FB error mapping for the
  selected source status;
- dictionary, list, string, and integer subclasses are rejected.

10FH copies caller-owned list fields before content validation. It validates
the exact deterministic 10FB `verification_digest_text`, uses that text in the
10FB decision-ID recomputation, and never emits it.

## 10FB decision-ID verification

10FH independently reconstructs the exact 10FB decision material:

- `verification_digest_schema_version`
- `verification_digest_scope`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_verifier_status`
- `source_verifier_ok`
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
- `source_digest_text_valid`
- `verification_digest_status`
- `verification_digest_text`
- `errors`

The material is serialized with sorted keys, compact separators, and
`ensure_ascii=False`, encoded as UTF-8, and hashed with SHA-256. The required
identifier is `10FB-` plus the first 32 lowercase hexadecimal characters.

10FH recomputes no earlier source identifier. For valid source states where
they are populated:

- `source_verifier_decision_id` must have exact `10EV-` plus 32 lowercase
  hexadecimal syntax and is otherwise opaque;
- `source_digest_decision_id` must have exact `10EP-` plus 32 lowercase
  hexadecimal syntax and is otherwise opaque;
- `source_bundle_decision_id` must have exact `10EJ-` plus 32 lowercase
  hexadecimal syntax and is otherwise opaque.

The fields are empty only in the exact status-specific sanitized cases already
defined by the 10FB.1 contract. No 10EV, 10EP, 10EJ, ledger, record, or digest
content is re-run or re-hashed.

## Valid 10FB statuses

10FH accepts all three exact 10FB statuses when their complete envelopes,
deterministic text, and 10FB decision IDs are internally valid:

- `verified_verification_digest`;
- `non_verified_verification_digest`;
- `invalid_10ev_source`.

Every valid 10FB artifact produces:

- `ok=True`;
- `verification_status="digest_intact"`;
- `errors=[]`.

This includes internally valid `non_verified_verification_digest` and
`invalid_10ev_source` reports. 10FH verifies the integrity of the supplied
10FB artifact; it does not reinterpret success or failure from an earlier
phase.

Invalid or tampered input produces:

- `ok=False`;
- `verification_status="invalid_digest"`;
- all source aggregate fields empty, zero, or `False`;
- `errors=["verification_digest_report is not a valid 10FB verification
  digest report"]`.

Raw 10FB errors and the supplied 10FB verification digest text are never
propagated.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10FH returns exactly these 44 safe aggregate fields:

- `ok`
- `verifier_schema_version = "10FH.1"`
- `verifier_type =
  "minimal_inert_ledger_status_digest_verification_verifier"`
- `verifier_scope =
  "inert_ledger_status_digest_verification_verification_only"`
- `verifier_decision_id`
- `source_verification_digest_schema_version`
- `source_verification_digest_decision_id`
- `source_verification_digest_status`
- `source_verification_digest_ok`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_verifier_status`
- `source_verifier_ok`
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
- `source_digest_text_valid`
- `source_verification_digest_text_valid`
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

The required `source_verification_digest_decision_id` is the validated 10FB
identifier. The immediate safe `10EV-` source verifier ID and existing safe
`10EP-`/`10EJ-` status IDs are preserved only when the exact 10FB source status
allows them. No older verifier/reporter identifiers are added.

## 10FH decision ID and export

The 10FH decision ID hashes these safe report fields:

- `verifier_schema_version`
- `verifier_scope`
- `source_verification_digest_schema_version`
- `source_verification_digest_decision_id`
- `source_verification_digest_status`
- `source_verification_digest_ok`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_verifier_status`
- `source_verifier_ok`
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
- `source_digest_text_valid`
- `source_verification_digest_text_valid`
- `verification_status`
- `errors`

The canonical/hash procedure matches the 10FB procedure, with prefix `10FH-`.
The material excludes `verifier_decision_id` itself. The strict exporter
validates exact shape, strict built-in types, status/source aggregate
consistency, all-False gate flags, generic error mapping, and the 10FH decision
ID before serializing a fresh plain-dictionary snapshot as deterministic sorted
JSON.

## Data not emitted

10FH never emits:

- the supplied 10FB `verification_digest_text`;
- the supplied 10EP `digest_text`;
- raw source errors from any phase;
- `verified_record_hashes` or any raw hash value;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or an `equality_signal_type` field;
- `source_reporter_decision_id` or older verifier/reporter identifiers beyond
  the safe source identifiers already present in the 10FB envelope;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only safe source schema/decision/status identifiers, booleans, counts, known
signal-type names/count, source error count, text-validity booleans, and
all-False gate status are retained for valid sources.

## Forbidden behavior

10FH does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10ED summary reporter;
- import or call the 10EJ bundle reporter;
- import or call the 10EP digest reporter;
- import or call the 10EV digest verifier;
- import or call the 10FB verification reporter;
- import or call the 10CP writer;
- import any backend module;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import `pathlib`, `os`, backend modules, network modules, or subprocess APIs;
- promote report results into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Trust boundary

10FH structurally and semantically validates one caller-supplied 10FB report,
including its exact deterministic text and decision ID. It does not call 10FB,
re-run 10EV/10EP/10EJ, or recompute the opaque source identifiers. Therefore
10FH attests to the internal integrity of a 10FB artifact, not the provenance
of an arbitrary fabricated-but-self-consistent source chain. Callers remain
responsible for supplying a report produced by the authorized 10FB function.

## Tests and checks

- Initial TDD RED: missing 10FH module collection error.
- 10FH targeted suite from repo root: 212 passed.
- 10FB + 10FH bounded suite from `world-sim`: 397 passed.
- 10EV + 10FB + 10FH bounded regression: 571 passed.
- 10EP + 10EV + 10FB + 10FH bounded regression: 694 passed.
- 10EJ + 10EP + 10EV + 10FB + 10FH bounded regression: 869 passed.
- 10DX + 10ED + 10EJ + 10EP + 10EV + 10FB + 10FH bounded regression:
  1085 passed.
- 10CP + 10DR + 10DX + 10ED + 10EJ + 10EP + 10EV + 10FB + 10FH bounded
  regression: 1199 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/source-phase import or call, no file access or mutation,
  no scanning, and no runtime APIs.
- CI pure-test list includes the 10FH test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10FH implements only the 10FF-authorized verification verifier. It adds no
ledger path, read or write surface, verifier/reporter/writer call, batch
verifier, local-sim bridge, runtime execution, or gate-7 work. 10CP remains the
only writer. Gate-7 remains closed. 10FI will sync 10FH metadata only after the
implementation commit is pushed.
