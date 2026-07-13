# Phase 10ED - Minimal Inert Ledger Summary Reporter

10ED implements the single candidate named by 10EB. It is a pure read-only,
in-process, caller-driven reporter over one caller-supplied 10DX verification
result dictionary. It never accepts a ledger path, opens or scans a file,
calls 10DX or 10CP, or promotes summary data into runtime or world state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `417599f docs: correct 10EC metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10ED test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Review hardening RED: 10 focused tests failed before exact built-in type,
  snapshot, UTF-8, provenance, and exporter protections were added.
- Final review RED: one detach-before-validate regression failed before caller
  lists were copied ahead of all content validation.

## Public API

```python
create_minimal_inert_ledger_summary_report(
    verification_result: dict | None,
) -> dict

export_minimal_inert_ledger_summary_report(report: dict) -> str
```

The reporter accepts only one caller-supplied 10DX result dictionary. It has no
path parameter and no default production path. Missing, non-dictionary,
subclassed, malformed, or inconsistent input fails closed into the same
sanitized `invalid_source` report.

## Source boundary

10ED requires the exact 22-field 10DX output envelope:

- `ok`
- `verifier_schema_version`
- `verifier_type`
- `verifier_scope`
- `verifier_decision_id`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hashes`
- `recognized_signal_types_seen`
- `append_only_line_format_valid`
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

- `verifier_schema_version == "10DX.1"`;
- `verifier_type == "minimal_inert_ledger_readback_result"`;
- `verifier_scope == "inert_ledger_readback_only"`;
- `verifier_decision_id` is `10DX-` followed by 32 lowercase hexadecimal
  characters;
- the 10DX claim boundary is exact;
- `ok`, `ledger_path_supplied`, `ledger_file_seen`, and
  `append_only_line_format_valid` are exact built-in booleans;
- `records_seen`, `records_valid`, and `invalid_record_count` are exact
  non-negative built-in integers (booleans and subclasses are rejected);
- `verified_record_hashes` is an exact built-in list of 64-character lowercase
  hexadecimal built-in strings;
- `recognized_signal_types_seen` is an exact built-in sorted unique list of
  known inert signal strings;
- all gate flags are strictly `False`;
- `errors` is an exact built-in list of nonempty UTF-8-safe built-in strings.

The source aggregate must also be internally realizable:

- `records_valid + invalid_record_count == records_seen`;
- the number of verified hashes equals `records_valid`;
- a seen file requires a supplied path;
- seen records require a seen file;
- valid append-only framing requires a seen file;
- no valid records means no recognized signal types;
- valid records require at least one recognized signal type, and the unique
  signal-type count cannot exceed `records_valid`;
- source `ok` must match the exact 10DX success conditions.

10ED copies the exact built-in dictionary and its list fields before using
them. Dictionary, list, string, and integer subclasses are rejected, preventing
caller overrides and post-validation serialization changes.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10ED returns exactly these 28 safe aggregate fields:

- `ok`
- `reporter_schema_version = "10ED.1"`
- `reporter_type = "minimal_inert_ledger_summary_report"`
- `reporter_scope = "inert_ledger_summary_only"`
- `reporter_decision_id`
- `source_verifier_schema_version`
- `source_verifier_decision_id`
- `source_ok`
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
- `summary_status`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

Summary statuses:

- `verified`: the source is a valid successful 10DX result; reporter `ok=True`
  and reporter errors are empty.
- `verification_failed`: the source is a valid failed 10DX result; reporter
  `ok=False`, `source_error_count` is retained, and the reporter emits only the
  generic error `source 10DX verification did not pass`.
- `invalid_source`: input shape, type, identity, gate, encoding, or aggregate
  consistency validation failed; all source aggregate fields are sanitized to
  empty/zero/False values and one generic reporter error is emitted.

The 10ED decision ID is derived only from the safe aggregate report material.
It never hashes raw verified record hashes or raw source errors. The strict
exporter validates exact shape, types, aggregate consistency, status/error
mapping, all-False gate flags, and the reporter decision ID, then serializes a
fresh validated plain-dictionary snapshot as deterministic sorted JSON.

## Data not emitted

10ED never emits:

- `verified_record_hashes` or any raw record hash;
- source `errors` or any raw source error text;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or `equality_signal_type`;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only the verified hash count, safe known signal-type names/count, source error
count, and safe source status/identity fields are retained.

## Forbidden behavior

10ED does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10CP writer;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import `pathlib`, `os`, backend modules, network modules, or subprocess APIs;
- promote summary results into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Trust boundary

10ED structurally and semantically validates a caller-supplied 10DX result. It
does not call or re-run 10DX and does not recompute the 10DX decision ID from
raw hashes/errors, because 10EB explicitly forbids re-verification and hashing.
The source verifier decision ID is retained as an explicitly required safe
status field and is checked for the exact 10DX syntax. Therefore, 10ED is a
summary reporter, not an authentication boundary for arbitrary fabricated
dictionaries. Callers remain responsible for supplying the result produced by
10DX.

## Tests and checks

- Initial TDD RED: missing 10ED module collection error.
- Review-hardening RED: 10 failures covering caller-controlled subclasses,
  malformed Unicode, impossible source provenance, and exporter subclass
  serialization.
- 10ED targeted suite from repo root: 123 passed.
- 10DX + 10ED bounded suite from `world-sim`: 216 passed.
- Optional 10CP + 10DR + 10DX + 10ED bounded regression from `world-sim`:
  330 passed.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/10DX/10CP import or call, no file access or mutation,
  no scanning, and no runtime APIs.
- CI pure-test list includes the 10ED test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10ED implements only the 10EB-authorized summary reporter. It adds no ledger
read or write path, verification call, batch reporter, local-sim bridge,
runtime execution, or gate-7 work. 10CP remains the only writer. Gate-7 remains
closed.
