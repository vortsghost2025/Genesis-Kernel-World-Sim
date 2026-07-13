# Phase 10EP - Minimal Inert Ledger Status Digest Reporter

10EP implements the single candidate named by 10EN. It is a pure read-only,
in-process, caller-driven reporter over one caller-supplied exact 10EJ status
bundle dictionary. It never accepts a ledger path, opens or scans a file,
calls 10DX, 10ED, 10EJ, or 10CP, or promotes digest data into runtime or world
state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `5fde368 docs: record 10EO metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10EP test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Final targeted GREEN: 123 passed.

## Public API

```python
create_minimal_inert_ledger_status_digest_report(
    bundle_report: dict | None,
) -> dict

export_minimal_inert_ledger_status_digest_report(digest: dict) -> str
```

The reporter accepts exactly one caller-supplied 10EJ bundle dictionary. It
has no path parameter and no default production path. Missing,
non-dictionary, subclassed, malformed, or inconsistent input fails closed
into the same sanitized `invalid_10ej_source` digest.

## Source boundary

10EP requires the exact 31-field 10EJ output envelope:

- `ok`
- `bundle_schema_version`
- `bundle_type`
- `bundle_scope`
- `bundle_decision_id`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_reporter_schema_version`
- `source_reporter_decision_id`
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
- `bundle_status`
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

- `bundle_schema_version == "10EJ.1"`;
- `bundle_type == "minimal_inert_ledger_status_bundle_report"`;
- `bundle_scope == "inert_ledger_status_bundle_only"`;
- `bundle_decision_id` is `10EJ-` followed by 32 lowercase hexadecimal
  characters;
- the 10EJ claim boundary is exact;
- all booleans are exact built-in booleans;
- all counts are exact non-negative built-in integers;
- `recognized_signal_types_seen` is an exact built-in sorted unique list of
  known inert built-in strings and its length equals
  `recognized_signal_type_count`;
- all gate flags are strictly `False`;
- `errors` is an exact built-in list with the exact generic error mapping for
  the selected 10EJ status;
- dictionary, list, string, and integer subclasses are rejected.

10EP copies caller-owned list fields before content validation. It checks the
10EJ bundle decision ID for syntax only and deliberately does **not** recompute
it. Recomputing that ID would duplicate 10EJ bundle logic and would require
safe source lineage fields that 10EP is forbidden from emitting. The
caller-supplied ID is retained as an opaque safe status identifier.

## Valid 10EJ statuses

10EP accepts all five exact 10EJ statuses:

- `verified_bundle`: exact matched successful source aggregates, `ok=True`,
  `source_ok=True`, `source_summary_status="verified"`, and no 10EJ errors;
- `verification_failed_bundle`: exact matched failed source aggregates,
  `ok=False`, `source_ok=False`,
  `source_summary_status="verification_failed"`, and the one generic 10EJ
  error `source 10DX verification did not pass`;
- `invalid_10dx_source`: exact sanitized source aggregates and the one generic
  invalid-10DX error;
- `invalid_10ed_source`: exact sanitized source aggregates and the one generic
  invalid-10ED error;
- `mismatched_sources`: exact sanitized source aggregates and the one generic
  mismatch error.

Matched source aggregates must preserve count, file-seen, append-only, hash
count, signal count, source status, and all-False gate consistency. Invalid or
mismatched 10EJ statuses must have fully sanitized source fields. 10EP never
re-reads or re-verifies the ledger and never recomputes a 10EJ decision ID.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10EP returns exactly these 31 safe aggregate fields:

- `ok`
- `digest_schema_version = "10EP.1"`
- `digest_type = "minimal_inert_ledger_status_digest_report"`
- `digest_scope = "inert_ledger_status_digest_only"`
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
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

Digest statuses:

- `verified_digest`: valid `verified_bundle`; digest `ok=True` and errors are
  empty.
- `non_verified_digest`: any other valid 10EJ status; digest `ok=False` and
  the only digest error is `source 10EJ bundle did not report verified`.
- `invalid_10ej_source`: invalid input; all source aggregate fields are
  sanitized to empty/zero/False values and the only digest error is
  `bundle_report is not a valid 10EJ bundle`.

The 10EP decision ID hashes only safe aggregate digest material. The strict
exporter validates exact shape, strict types, source aggregate consistency,
status/error mapping, exact digest text, all-False gate flags, and the 10EP
decision ID before serializing a fresh plain-dictionary snapshot as
deterministic sorted JSON.

## Deterministic digest text

Valid 10EJ sources use exactly:

```text
10EP status digest | source_bundle=<source_bundle_decision_id> | status=<source_bundle_status> | ok=<true_or_false> | source_summary_status=<source_summary_status> | records_seen=<records_seen> | records_valid=<records_valid> | invalid_record_count=<invalid_record_count> | verified_record_hash_count=<verified_record_hash_count> | recognized_signal_type_count=<recognized_signal_type_count> | recognized_signal_types=<comma_joined_signal_types_or_none> | append_only_line_format_valid=<true_or_false> | source_error_count=<source_error_count> | gates=executed:false,runtime:false,daemon:false,scheduler:false,network:false,world_data:false,gate7:false
```

Invalid input uses exactly:

```text
10EP status digest | source_bundle= | status= | ok=false | source_summary_status= | records_seen=0 | records_valid=0 | invalid_record_count=0 | verified_record_hash_count=0 | recognized_signal_type_count=0 | recognized_signal_types=none | append_only_line_format_valid=false | source_error_count=0 | gates=executed:false,runtime:false,daemon:false,scheduler:false,network:false,world_data:false,gate7:false
```

## Data not emitted

10EP never emits:

- `source_verifier_decision_id` or `source_reporter_decision_id`;
- `verified_record_hashes` or any raw hash value;
- raw 10DX, 10ED, or 10EJ errors;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or an `equality_signal_type` field;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only the safe 10EJ decision ID, status, counts, known signal-type names/count,
source error count, source summary status, and all-False gate status are
retained.

## Forbidden behavior

10EP does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10ED summary reporter;
- import or call the 10EJ bundle reporter;
- import or call the 10CP writer;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import `pathlib`, `os`, backend modules, network modules, or subprocess APIs;
- promote digest results into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Trust boundary

10EP structurally and semantically validates a caller-supplied 10EJ bundle. It
does not call or re-run 10EJ and does not recompute the 10EJ decision ID. The
source bundle decision ID is retained as an explicitly required safe opaque
status field and is checked for exact 10EJ syntax only. Therefore 10EP is a
digest reporter, not an authentication boundary for arbitrary fabricated
dictionaries. Callers remain responsible for supplying a bundle produced by
the authorized 10EJ function.

## Tests and checks

- Initial TDD RED: missing 10EP module collection error.
- 10EP targeted suite from repo root: 123 passed.
- 10EJ + 10EP bounded suite from `world-sim`: 298 passed.
- Optional 10DX + 10ED + 10EJ + 10EP bounded regression from `world-sim`:
  514 passed.
- Optional 10CP + 10DR + 10DX + 10ED + 10EJ + 10EP bounded regression from
  `world-sim`: 628 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/10DX/10ED/10EJ/10CP import or call, no file access or
  mutation, no scanning, and no runtime APIs.
- CI pure-test list includes the 10EP test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10EP implements only the 10EN-authorized status digest reporter. It adds no
ledger path, read or write surface, verification/summary/bundle call, batch
reporter, local-sim bridge, runtime execution, or gate-7 work. 10CP remains the
only writer. Gate-7 remains closed.
