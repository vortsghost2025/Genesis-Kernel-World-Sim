# Phase 10EJ - Minimal Inert Ledger Status Bundle Reporter

10EJ implements the single candidate named by 10EH. It is a pure read-only,
in-process, caller-driven reporter over one caller-supplied 10DX verification
result dictionary and one caller-supplied 10ED summary report dictionary. It
never accepts a ledger path, opens or scans a file, calls 10DX, 10ED, or 10CP,
or promotes bundle data into runtime or world state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `c3ae756 docs: record 10EI metadata hash`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD initial RED: the 10EJ test module failed collection with
  `ModuleNotFoundError` before the implementation module existed.
- Review-hardening RED: one focused test failed before the exporter bound the
  supplied 10ED reporter decision ID to the safe aggregate bundle fields.
- Final targeted GREEN: 175 passed.

## Public API

```python
create_minimal_inert_ledger_status_bundle_report(
    verification_result: dict | None,
    summary_report: dict | None,
) -> dict

export_minimal_inert_ledger_status_bundle_report(bundle: dict) -> str
```

The reporter accepts exactly two caller-supplied dictionaries. It has no path
parameter and no default production path. Missing, non-dictionary, subclassed,
malformed, or inconsistent inputs fail closed into sanitized status bundles.
10DX validation runs first, so an invalid 10DX source takes precedence when
both inputs are invalid.

## 10DX source boundary

10EJ requires the exact 22-field 10DX output envelope:

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

The identity, strict built-in type, all-False gate, known signal type, UTF-8
error, count/hash, and aggregate provenance rules match the 10ED source
boundary. Dictionary, list, string, and integer subclasses are rejected.
Caller-owned lists are copied before their contents are validated.

10EJ checks `verifier_decision_id` for exact `10DX-` plus 32 lowercase
hexadecimal syntax. It does not recompute that ID because doing so would hash
raw 10DX verified record hashes and errors, which are explicitly outside the
10EJ safe aggregate boundary.

## 10ED source boundary

10EJ requires the exact 28-field 10ED output envelope:

- `ok`
- `reporter_schema_version`
- `reporter_type`
- `reporter_scope`
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
- `executed`
- `runtime_allowed`
- `daemon_allowed`
- `scheduler_allowed`
- `network_allowed`
- `world_sim_data_accessed`
- `gate7_activity_allowed`
- `claim_boundary`
- `errors`

10EJ validates exact 10ED identity, strict built-in types, all-False gates,
known sorted unique signal types, aggregate provenance, status/error mapping,
and the 10ED reporter decision ID derived from safe aggregate fields. It accepts
only the three 10ED statuses (`verified`, `verification_failed`, and the fully
sanitized `invalid_source`) with their exact generic errors.

The strict 10EJ exporter independently recomputes the source 10ED reporter
decision ID from the safe bundle fields. A syntactically valid forged 10ED ID
therefore cannot be made exportable merely by recomputing the 10EJ bundle ID.

## Cross-source boundary

After both inputs independently validate, 10EJ requires all 13 authorized
cross-checks:

1. 10ED `source_verifier_decision_id` equals 10DX `verifier_decision_id`.
2. 10ED `source_verifier_schema_version` equals 10DX
   `verifier_schema_version`.
3. 10ED `source_ok` equals 10DX `ok` with strict boolean identity.
4. `ledger_path_supplied` matches.
5. `ledger_file_seen` matches.
6. `records_seen` matches.
7. `records_valid` matches.
8. `invalid_record_count` matches.
9. 10ED `verified_record_hash_count` equals the length of the 10DX verified
   hash list.
10. `recognized_signal_types_seen` matches exactly.
11. 10ED `recognized_signal_type_count` equals the length of the 10DX signal
    type list.
12. `append_only_line_format_valid` matches with strict boolean identity.
13. 10ED `source_error_count` equals the length of the 10DX error list.

Any mismatch collapses to a sanitized `mismatched_sources` bundle. No values
from either source are retained in invalid or mismatched bundles.

## Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

## Output envelope

10EJ returns exactly these 31 safe aggregate fields:

- `ok`
- `bundle_schema_version = "10EJ.1"`
- `bundle_type = "minimal_inert_ledger_status_bundle_report"`
- `bundle_scope = "inert_ledger_status_bundle_only"`
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
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

Bundle statuses:

- `verified_bundle`: valid successful 10DX plus matching valid 10ED `verified`
  report; bundle `ok=True` and errors are empty.
- `verification_failed_bundle`: valid failed 10DX plus matching valid 10ED
  `verification_failed` report; bundle `ok=False`, aggregate counts are
  retained, and the only error is the generic
  `source 10DX verification did not pass`.
- `invalid_10dx_source`: invalid 10DX input; all source fields are sanitized.
- `invalid_10ed_source`: valid 10DX plus invalid 10ED input; all source fields
  are sanitized.
- `mismatched_sources`: both inputs validate independently but fail one or more
  cross-checks; all source fields are sanitized.

The 10EJ decision ID hashes only the safe aggregate bundle material. The
strict exporter validates exact shape, strict types, aggregate consistency,
status/error mapping, all-False gate flags, source 10ED lineage, and the 10EJ
decision ID before serializing a fresh plain-dictionary snapshot as
deterministic sorted JSON.

## Data not emitted

10EJ never emits:

- `verified_record_hashes` or any raw hash value;
- raw 10DX errors or raw 10ED errors;
- a ledger path, path string, record body, or raw record;
- `equality_signal_value` or `equality_signal_type`;
- agent, tile, route, destination, timing, co-presence, awareness,
  relationship, interaction, movement, map lookup, event, or NPC behavior
  fields.

Only verified hash count, safe known signal-type names/count, source error
count, safe source identities, and aggregate statuses are retained for matched
valid pairs.

## Forbidden behavior

10EJ does not:

- accept a ledger path or use a default production path;
- open, read, list, inspect, scan, glob, walk, or re-verify a ledger;
- import or call the 10DX verifier;
- import or call the 10ED summary reporter;
- import or call the 10CP writer;
- write, append, overwrite, truncate, delete, rename, repair, or create a
  directory;
- import `pathlib`, `os`, backend modules, network modules, or subprocess APIs;
- promote bundle results into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container, or
  Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Trust boundary

10EJ structurally and semantically validates both caller-supplied dictionaries,
recomputes the 10ED safe aggregate decision ID, and cross-checks the complete
authorized relationship between the inputs. It does not call 10DX or 10ED and
does not recompute the 10DX decision ID from raw hashes/errors. Therefore 10EJ
is a bundle reporter, not an authentication boundary for an attacker able to
fabricate a mutually consistent 10DX/10ED pair. Callers remain responsible for
supplying results produced by the authorized 10DX and 10ED functions.

## Tests and checks

- Initial TDD RED: missing 10EJ module collection error.
- Review-hardening RED: forged syntactically valid 10ED lineage ID was accepted
  by export before safe-field lineage recomputation was added.
- 10EJ targeted suite from repo root: 175 passed.
- 10DX + 10ED + 10EJ bounded suite from `world-sim`: 391 passed.
- Optional 10CP + 10DR + 10DX + 10ED + 10EJ bounded regression from
  `world-sim`: 505 passed.
- Static tests prove stdlib-only imports (`__future__`, `hashlib`, `json`,
  `typing`), no backend/10DX/10ED/10CP import or call, no file access or
  mutation, no scanning, and no runtime APIs.
- CI pure-test list includes the 10EJ test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Scope boundary

10EJ implements only the 10EH-authorized status bundle reporter. It adds no
ledger path, read or write surface, verification or summary call, batch
reporter, local-sim bridge, runtime execution, or gate-7 work. 10CP remains the
only writer. Gate-7 remains closed.
