# Phase 10CP - Minimal Inert Ledger Adapter Implementation

10CP is the first implementation after the 10CN gate-6 write-path
authorization. It appends one verified NDJSON audit record from an
accepted, already-built 10CJ dry-run adapter decision.

This remains an inert audit boundary. It is not movement, runtime
behavior, map lookup, route execution, event emission, NPC behavior,
background-service work, periodic-job work, or network activity.

---

## Input boundary

10CP consumes 10CJ decisions only. It never imports or calls the 10CJ
creator, never imports 10BT, and never reads raw 10BT decisions.

An input is accepted only when:

- `ok == True`;
- `adapter_schema_version == "10CJ.1"`;
- `adapter_type == "runtime_adapter_dry_run_decision"`;
- `adapter_scope == "dry_run_only"`;
- `planned_action == "log_only"`;
- `executed == False`;
- `runtime_allowed == False`;
- `daemon_allowed == False`;
- `scheduler_allowed == False`;
- `network_allowed == False`;
- `world_sim_data_accessed == False`;
- `recognized_signal_type` is one of the six known inert 10CJ signal
  types;
- required source identifiers are non-empty strings;
- `source_signal_seen == True`;
- no forbidden input field is present.

10CP never reads `equality_signal_value`. Its presence as an input key
causes a fail-closed rejection without a write.

---

## Path authorization

The 10CN candidate production path remains:

```
world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson
```

The writer accepts both `ledger_path` and `authorized_ledger_path`.
It writes only when both resolve to the exact same path. The parent
directory must already exist; 10CP never creates it.

Tests use `tmp_path` as both the candidate and authorized path. Tests
never create, read, or write the production ledger.

10CP never scans `world-sim/data`, never lists directories, never
inspects other data files, and never reads the ledger before appending.

---

## Append-only write

The ledger is opened only in append mode (`"a"`) with UTF-8 encoding
and LF newline handling. One accepted decision produces exactly one
compact canonical JSON object followed by exactly one `"\n"`.

The writer never overwrites, truncates, deletes, renames, or rewrites
existing content. Existing bytes remain before the appended record.

### Ledger record fields

The record contains exactly:

- `ledger_schema_version` = `"10CP.1"`
- `source_adapter_schema_version`
- `adapter_decision_id`
- `source_decision_id`
- `source_consumer_scope`
- `source_signal_seen`
- `recognized_signal_type`
- `planned_action`
- `recorded_at_utc`
- `record_hash`

No equality value, agent field, tile/route/path/destination/timing
value, co-presence, awareness, relationship, interaction, movement,
map lookup, event-emission, NPC-behavior, or service output is written.

---

## Record hash

`record_hash` is SHA-256 over the compact canonical JSON of the record
before `record_hash` is added:

- `sort_keys=True`;
- `separators=(",", ":")`;
- UTF-8 encoding.

The same record content, including the same `recorded_at_utc`, produces
the same hash.

---

## Fail-closed result

`append_inert_ledger_record(...)` returns:

- `ok`
- `writer_schema_version` = `"10CP.1"`
- `writer_type` = `"runtime_adapter_inert_ledger_writer_result"`
- `ledger_record_written`
- `ledger_path_authorized`
- `source_adapter_decision_id`
- `record_hash`
- `bytes_appended`
- `errors`

Malformed input, forbidden fields, failed acceptance rules,
unauthorized paths, missing parents, or append errors return `ok=False`,
`ledger_record_written=False`, `bytes_appended=0`, and non-empty errors.

---

## Tests

The 10CP suite proves:

- one accepted 10CJ decision writes exactly one NDJSON line;
- the record has exactly the allowed fields and a verifiable hash;
- existing content is preserved;
- every required acceptance failure causes no write;
- every forbidden field causes no write;
- unauthorized paths and missing parents cause no write;
- the source never reads `equality_signal_value` from the decision;
- imports are stdlib-only and scanning APIs are absent;
- every file open in the module uses append mode only;
- existing 10CJ tests remain unchanged and pass.

Tests use temporary paths only. No production ledger is created during
verification.

---

## Conclusion

10CP implements only the narrow write authorized by 10CN: one inert,
append-only, verified audit record at an exact authorized path. It does
not add runtime behavior or broader runtime wiring. After 10CP, the
next phase is metadata sync only; broader runtime work requires another
explicitly approved phase.
