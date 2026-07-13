# Phase 10FB - Minimal Inert Ledger Status Digest Verification Reporter

10FB implements the single candidate named by 10EZ. It is a pure read-only,
in-process, caller-driven reporter over one caller-supplied exact 10EV
verification report dictionary. It never accepts a ledger path, opens or scans
a file, calls 10DX, 10ED, 10EJ, 10EP, 10EV, or 10CP, or promotes report data
into runtime or world state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `4a93706 docs: record 10FA metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10FB test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 185 passed.

## Public API

```python
create_minimal_inert_ledger_status_digest_verification_report(
    verification_report: dict | None,
) -> dict

export_minimal_inert_ledger_status_digest_verification_report(
    digest_report: dict,
) -> str
```

The reporter accepts exactly one caller-supplied 10EV verification dictionary.
It has no path parameter and no default production path. Missing,
non-dictionary, subclassed, malformed, inconsistent, or tampered input fails
closed into the same sanitized `invalid_10ev_source` digest report.

## Source boundary

10FB requires the exact 35-field 10EV output envelope:

- `ok`
- `verifier_schema_version`
- `verifier_type`
- `verifier_scope`
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

- `verifier_schema_version == "10EV.1"`;
- `verifier_type == "minimal_inert_ledger_status_digest_verifier"`;
- `verifier_scope == "inert_ledger_status_digest_verification_only"`;
- `verifier_decision_id` is `10EV-` followed by 32 lowercase hexadecimal
  characters and must equal the independently recomputed 10EV decision ID;
- the 10EV claim boundary is exact;
- all booleans are exact built-in booleans;
- all counts are exact non-negative built-in integers;
- `recognized_signal_types_seen` is an exact built-in sorted unique list of
  known inert built-in strings and its length equals
  `recognized_signal_type_count`;
- all gate flags are strictly `False`;
- `errors` is an exact built-in list with the exact 10EV error mapping for the
  selected verification status;
- dictionary, list, string, and integer subclasses are rejected.

10FB copies caller-owned list fields before content validation. For
`digest_intact`, it checks the source 10EP `source_digest_decision_id` for exact
`10EP-` plus 32 lowercase hexadecimal syntax only and deliberately does **not**
recompute it. Recomputing that identifier would duplicate 10EP logic and
require forbidden source digest text. For the valid, fully sanitized
`invalid_digest` status, the source 10EP identifier is correctly empty under
the 10EV contract.

## 10EV decision-ID verification

10FB independently reconstructs the exact 10EV decision material:

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

The material is serialized with sorted keys, compact separators, and
`ensure_ascii=False`, encoded as UTF-8, and hashed with SHA-256. The required
identifier is `10EV-` plus the first 32 lowercase hexadecimal characters. No
ledger record, record hash, 10DX ID, 10ED ID, 10EJ ID, or 10EP ID is recomputed.

## Valid 10EV statuses

10FB accepts both exact 10EV statuses when their complete envelopes are
internally valid and their 10EV decision IDs match:

- `digest_intact`: exact valid 10EV source over any valid `verified_digest`,
  `non_verified_digest`, or `invalid_10ej_source` 10EP status; 10EV `ok=True`,
  `digest_text_valid=True`, and errors are empty;
- `invalid_digest`: exact fully sanitized source aggregate, 10EV `ok=False`,
  `digest_text_valid=False`, and the one generic 10EV invalid-digest error.

10FB maps these statuses as follows:

- valid `digest_intact` -> `ok=True`,
  `verification_digest_status="verified_verification_digest"`, no errors;
- valid `invalid_digest` -> `ok=False`,
  `verification_digest_status="non_verified_verification_digest"`, and only
  `source 10EV verification did not report digest_intact`;
- invalid or tampered source -> `ok=False`,
  `verification_digest_status="invalid_10ev_source"`, fully sanitized source
  aggregates, and only
  `verification_report is not a valid 10EV verification report`.

The source 10EV error text is never propagated.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10FB returns exactly these 40 safe aggregate fields:

- `ok`
- `verification_digest_schema_version = "10FB.1"`
- `verification_digest_type = "minimal_inert_ledger_status_digest_verification_report"`
- `verification_digest_scope = "inert_ledger_status_digest_verification_report_only"`
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
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The required `source_verifier_decision_id` is the immediate validated 10EV
identifier. 10FB emits no verifier or reporter decision IDs from older source
phases. The 10EP and 10EJ identifiers remain safe opaque source status IDs.

## Deterministic digest text

`verification_digest_text` summarizes only safe status, boolean, count, and
all-False gate aggregates. It includes no IDs, source error text, path, record,
raw hash, signal-type value, digest text, agent, tile, route, destination,
timing, social, event, or NPC fields. Invalid input produces the same
deterministic sanitized text from empty/zero/False source aggregates.

## 10FB decision ID and export

The 10FB decision ID hashes these safe report fields:

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

The canonical/hash procedure matches the 10EV procedure, with prefix `10FB-`.
The material excludes `verification_digest_decision_id` itself. The strict
exporter validates exact shape, strict built-in types, status/source aggregate
consistency, reconstructed 10EV integrity, deterministic digest text,
all-False gate flags, generic error mapping, and the 10FB decision ID before
serializing a fresh plain-dictionary snapshot as deterministic sorted JSON.

## Data not emitted

10FB never emits:

- the supplied 10EP `digest_text`;
- verifier or reporter decision IDs from older source phases;
- `verified_record_hashes` or any raw hash value;
- raw 10DX, 10ED, 10EJ, 10EP, or 10EV errors;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or an `equality_signal_type` field;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only safe immediate/source IDs, statuses, counts, known signal-type
names/count, source error count, source summary status, digest-text validity,
the sanitized deterministic 10FB text, and all-False gate status are retained
for valid sources.

## Forbidden behavior

10FB does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10ED summary reporter;
- import or call the 10EJ bundle reporter;
- import or call the 10EP digest reporter;
- import or call the 10EV digest verifier;
- import or call the 10CP writer;
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

10FB structurally and semantically validates one caller-supplied 10EV report,
including its exact decision ID. It does not call 10EV, re-run 10EP, or
recompute the opaque source 10EP decision ID. Therefore 10FB attests to the
internal integrity and status of a 10EV artifact, not the provenance of an
arbitrary fabricated-but-self-consistent 10EV/10EP dictionary. Callers remain
responsible for supplying a report produced by the authorized 10EV function.

## Tests and checks

- Initial TDD RED: missing 10FB module collection error.
- 10FB targeted suite from repo root: 185 passed.
- 10EV + 10FB bounded suite from `world-sim`: 359 passed.
- Optional 10EP + 10EV + 10FB bounded regression from `world-sim`: 482 passed.
- Optional 10EJ + 10EP + 10EV + 10FB bounded regression from `world-sim`: 657
  passed.
- Optional 10DX + 10ED + 10EJ + 10EP + 10EV + 10FB bounded regression from
  `world-sim`: 873 passed.
- Optional 10CP + 10DR + 10DX + 10ED + 10EJ + 10EP + 10EV + 10FB bounded
  regression from `world-sim`: 987 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/10DX/10ED/10EJ/10EP/10EV/10CP import or call, no file
  access or mutation, no scanning, and no runtime APIs.
- CI pure-test list includes the 10FB test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10FB implements only the 10EZ-authorized verification reporter. It adds no
ledger path, read or write surface, verifier/reporter/writer call, batch
reporter, local-sim bridge, runtime execution, or gate-7 work. 10CP remains the
only writer. Gate-7 remains closed.
