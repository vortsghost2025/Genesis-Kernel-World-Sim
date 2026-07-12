# Phase 10DX - Minimal Inert Ledger Read-Back Verifier

10DX implements the single candidate named by 10DV. It is a pure read-only,
in-process, caller-driven verifier for one explicit existing 10CP NDJSON
ledger file. It does not call 10CP, mutate or repair a ledger, scan a
directory, or promote ledger contents into runtime or world state.

Gate-7 remains closed.

## Baseline and model

- Baseline: `fa9ce4f Phase 10DW: sync 10DV metadata`.
- Implementation model: GPT-5.6 Sol/Luna.
- TDD: the 10DX test module failed collection with `ModuleNotFoundError`
  before the implementation module existed. Subsequent boundary-review tests
  were observed failing before each hardening change.

## Public API

```python
verify_minimal_inert_ledger_readback(
    ledger_path=None,
    *,
    max_records=None,
)

export_minimal_inert_ledger_readback_result(result)
```

`ledger_path=None` is a missing-path sentinel, not a default production path.
The verifier opens only one caller-supplied path and only in binary read mode.
It never selects the 10CN production ledger path itself.

`max_records` is optional. When supplied, it must be a strictly positive
integer (not a boolean). It is a fail-closed ceiling: encountering record
`max_records + 1` rejects the verification rather than silently verifying a
prefix. `max_records=None` verifies the complete explicit file.

## Path and read boundary

10DX:

- rejects a missing path;
- rejects a nonexistent path;
- rejects a directory path;
- normalizes `os.PathLike` input before inspection;
- rejects UNC/network paths before `Path` construction or filesystem access;
- opens exactly the explicit normalized path once with mode `rb`;
- does not resolve a default, inspect a parent, list, glob, walk, or scan;
- does not contain the 10CN production path literal;
- does not import or call 10CP or any other backend module;
- does not write, append, overwrite, truncate, delete, rename, repair, create
  directories, or otherwise mutate the file.

Tests write only temporary ledgers under `tmp_path`. No production
`world-sim/data` file is accessed by tests.

## Append-only line format

The ledger must contain at least one record. An empty file is invalid.

Each record must be exactly one UTF-8 JSON object terminated by one LF byte.
The verifier rejects:

- a non-newline-terminated final record;
- CRLF line endings;
- blank lines;
- malformed JSON;
- non-object JSON;
- duplicate object keys;
- invalid UTF-8;
- excessively nested JSON that exceeds parser limits.

These conditions set `append_only_line_format_valid` to `False` and fail
closed. Record-schema or record-hash errors reject the record while preserving
the distinction that its NDJSON line framing was valid.

## Exact 10CP record contract

Each record must have exactly these ten fields and no others:

- `ledger_schema_version`
- `source_adapter_schema_version`
- `adapter_decision_id`
- `source_decision_id`
- `source_consumer_scope`
- `source_signal_seen`
- `recognized_signal_type`
- `planned_action`
- `recorded_at_utc`
- `record_hash`

Required values and types:

- `ledger_schema_version == "10CP.1"`;
- `source_adapter_schema_version == "10CJ.1"`;
- `source_consumer_scope == "record_public_equality_signal_only"`;
- `source_signal_seen is True` (integer `1` is rejected);
- `planned_action == "log_only"`;
- adapter decision ID, source decision ID, recorded time, and record hash are
  nonempty UTF-8 strings;
- `recognized_signal_type` is one of:
  - `snapshot_id_equality`
  - `snapshot_hash_equality`
  - `current_tile_id_equality`
  - `route_intent_id_equality`
  - `known_tile_ids_set_equality`
  - `route_destination_tile_id_equality`

The record hash must exactly match the 10CP rule:

1. remove `record_hash`;
2. serialize canonical JSON with `sort_keys=True`, compact separators, and
   `ensure_ascii=False`;
3. compute the lowercase SHA-256 hexadecimal digest of the UTF-8 bytes.

Forbidden or structurally invalid records return before canonical hashing, so
forbidden/nested values cannot influence errors or the verifier decision ID.

## Forbidden record fields

10DX rejects these fields without reading, logging, exporting, hashing, or
reflecting their values:

- `equality_signal_value`
- `equality_signal_type`
- `agent_id`
- `tile`
- `route`
- `path`
- `destination`
- `timing`
- `co_presence`
- `awareness`
- `relationship`
- `interaction`
- `movement`
- `map_lookup`
- `emit_event`
- `create_event`
- `npc_behavior`
- `daemon_output`
- `scheduler_output`
- `network_output`

Errors contain line numbers and generic reasons only. They contain no raw
record values or ledger path.

## Output envelope

10DX returns exactly these safe status fields:

- `ok`
- `verifier_schema_version = "10DX.1"`
- `verifier_type = "minimal_inert_ledger_readback_result"`
- `verifier_scope = "inert_ledger_readback_only"`
- `verifier_decision_id`
- `ledger_path_supplied`
- `ledger_file_seen`
- `records_seen`
- `records_valid`
- `invalid_record_count`
- `verified_record_hashes`
- `recognized_signal_types_seen`
- `append_only_line_format_valid`
- `executed = False`
- `runtime_allowed = False`
- `daemon_allowed = False`
- `scheduler_allowed = False`
- `network_allowed = False`
- `world_sim_data_accessed = False`
- `gate7_activity_allowed = False`
- `claim_boundary`
- `errors`

The decision ID hashes only this safe verification status and excludes the
ledger path and record values. Verified hashes retain ledger order. Signal
types are unique and sorted. The exporter requires the exact 10DX shape,
strict status types, known signal types, valid hashes, all-False gate fields,
and a matching decision ID before deterministic JSON serialization.

## Forbidden behavior

10DX does not:

- call the 10CP writer or any backend function;
- use a default production ledger path;
- scan `world-sim/data` or any directory;
- write or repair any ledger;
- read or emit `equality_signal_value`;
- promote ledger contents into runtime or world state;
- create movement, map, route, event, NPC, co-presence, awareness,
  relationship, interaction, or timing behavior;
- start runtime, daemon, scheduler, network, provider, launcher, container,
  or Docker behavior.

All runtime/world/gate flags remain False. Gate-7 is closed by absence.

## Tests and checks

- Initial TDD RED: missing 10DX module collection error.
- Iterative RED/GREEN boundary coverage: non-object framing, forbidden-value
  independence, UNC and disguised `PathLike` rejection, strict exporter
  validation, invalid nested values, and fail-closed parser/path exceptions.
- 10DX targeted suite from repo root: 93 passed.
- 10CP + 10DR + 10DX bounded regression from `world-sim`: 207 passed.
- Compile checks pass for the implementation and test modules.
- Static tests prove one `explicit_path.open("rb")`, no backend/10CP import or
  call, no production path literal, and no mutation/scanning/runtime APIs.
- CI pure-test list includes the 10DX test module.

Full pytest is intentionally not run because legacy canonical/world mutation
tests are outside the authorized bounded test set.

## Residual provenance limitation

10DX verifies the exact ten fields persisted by 10CP. It cannot reconstruct or
assert upstream adapter fields that 10CP does not persist. In particular,
legacy direct 10CP acceptance behavior for a non-persisted adapter `ok` value
cannot be inferred from a ledger record. The authorized 10DR path validates
its 10CJ/10DL `ok` values with strict boolean identity before calling 10CP.
Changing legacy 10CP input validation is outside 10DX's allowed files and is
not represented as a read-back guarantee.

## Scope boundary

10DX implements only the 10DV-authorized read-back verifier. It adds no batch
orchestrator, local-sim bridge, write path, repair path, or runtime execution.
10CP remains the only writer. Gate-7 remains closed.
