# Phase 10CN - World-Sim Data Write-Path Authorization Spec

Docs-only authorization spec for 10CH gate #6: no `world-sim/data`
reads or writes until separately authorized by a dedicated, reviewed
phase. 10CN defines the exact future ledger write-path rules
**before** any write implementation exists.

10CN does **not** implement writes. It does **not** read
`world-sim/data`. It does **not** write `world-sim/data`. It
does **not** add runtime code, a live adapter, movement, map
lookup, route execution, daemon/scheduler/network action, event
emission, NPC behavior, co-presence, awareness, relationship,
timing, or coordination.

---

## 1. Current state

- 10CJ is dry-run / inert. It consumes 10BT decisions and
  emits an inert dry-run adapter decision; it never writes anything.
- 10CL authorizes design only. It consumes 10CJ decisions and
  defines the future live-adapter allowlist / denylist; it allows
  only a future inert append-only verified ledger entry.
- 10CH gate #6 remains blocked until this docs-only
  authorization is approved.
- 10CN still does **not** implement any write.

---

## 2. Future ledger path rule

The only candidate future write location is:

```
world-sim/data/runtime_adapter_ledger/runtime_adapter_decisions.ndjson
```

This path is only a future allowlist target. 10CN does **not**
create it. 10CN does **not** read it. 10CN does **not**
write it.

---

## 3. Future write shape

A later implementation phase may only append one NDJSON line per
accepted 10CJ decision.

### Allowed fields in a future ledger record

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

### Forbidden fields in a future ledger record

- `equality_signal_value`
- `agent_id`
- tile value
- route value
- path value
- destination value
- timing value
- co-presence
- awareness
- relationship
- interaction
- movement
- map lookup
- event emission
- NPC behavior
- daemon/scheduler/network output

---

## 4. Future acceptance rules

A later write adapter may only append if the 10CJ decision has:

- `ok == True`
- `adapter_schema_version == "10CJ.1"`
- `adapter_type == "runtime_adapter_dry_run_decision"`
- `adapter_scope == "dry_run_only"`
- `planned_action == "log_only"`
- `executed == False`
- `runtime_allowed == False`
- `daemon_allowed == False`
- `scheduler_allowed == False`
- `network_allowed == False`
- `world_sim_data_accessed == False`
- `recognized_signal_type` is one of the six known inert signal types

### Known inert signal types

- `snapshot_id_equality`
- `snapshot_hash_equality`
- `current_tile_id_equality`
- `route_intent_id_equality`
- `known_tile_ids_set_equality`
- `route_destination_tile_id_equality`

---

## 5. Future file safety rules

A later implementation must:

- open the ledger only in append mode;
- create the parent directory only if explicitly allowed by that later phase;
- never overwrite, truncate, delete, rename, or rewrite existing data;
- never scan `world-sim/data`;
- never inspect other `world-sim/data` files;
- never infer state from the ledger;
- treat the ledger as an audit artifact only, not runtime state;
- fail closed on malformed input;
- fail closed if any forbidden field is present;
- fail closed if any gate flag is True.

---

## 6. Required future tests before implementation

A later implementation phase must add tests proving:

- no write occurs unless all acceptance rules pass;
- malformed decisions do not write;
- `planned_action != "log_only"` does not write;
- `executed != False` does not write;
- any gate flag True does not write;
- `equality_signal_value` is never written;
- forbidden fields are never written;
- only append mode is used;
- no `world-sim/data` scanning occurs;
- no runtime/daemon/scheduler/network/provider/launcher/Docker imports exist.

---

## 7. Conclusion

10CN authorizes only the future path / spec boundary. 10CN does
**not** implement writes. 10CN does **not** cross gate #6 by
itself.

The next possible phase after 10CN should be:

- 10CO - sync 10CN metadata

Then, only after operator approval and the GPT-5.6 Luna/Sol
model switch:

- 10CP - Minimal Inert Ledger Adapter Implementation

## Files

- New spec only: `world-sim/docs/phase_10cn_world_sim_data_write_path_authorization_spec.md`
- No module, no test, no `pure-tests.yml` change, no runtime code.

## Tests

- None required (docs-only).
