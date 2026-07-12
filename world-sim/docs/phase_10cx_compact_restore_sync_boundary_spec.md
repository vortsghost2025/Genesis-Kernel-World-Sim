# Phase 10CX - Compact Restore Sync Boundary Spec

Import Sean's cross-repo compact/restore governance boundary into Genesis **as a specification only**. No implementation, no runtime, no daemon/scheduler/network, no world-sim/data writes, no PatchRaccoon or agent-config changes. Stop before commit.

This repurposes the originally-planned 10CX (which had been scoped as a post-10CV gate-7 boundary audit) into the **Compact Restore Sync Boundary Spec**. Gate-7 remains closed; this phase does not reopen or touch it.

## Rules
- docs-only
- cheap/free model OK
- no implementation
- no runtime
- no daemon / scheduler / network
- no world-sim/data writes
- do not touch PatchRaccoon or agent configs
- gate-7 stays closed (10CH / 10CR precedent)
- stop before commit

## Purpose
Import Sean's compact/restore governance boundary into Genesis so any future Genesis compaction/restore honors:
- a pre-compact snapshot,
- a post-restore verification against that snapshot,
- a >=93% semantic/state fidelity acceptance threshold,
- quarantine of degraded/conflicted restores,
- reload of a last-known-good phenotype/fingerprint,
- and a hard rule: do not continue phase work from a degraded compact state.

## Evidence inventory (read-only, from Sean's repos)
Three memory/state layers were inventoried:
1. `S:\continuity\` - Sean-level continuity / anchor memory. `CORE_SEAN_ANCHOR.md` is the highest-authority document (Sean ~95% vision disability -> 3900% zoom / 24pt font; principles: Inheritance over Initiation, Soul in State, Guardianship, Silence is Data, Verification First). `TRANSFER_PACKET.md` carries handoff instructions; `domains/genesis.md` anchors the Genesis domain.
2. `S:\Archivist-Agent\.compact-audit\` - live compact evidence: `PRE_COMPACT_SNAPSHOT.json` (schema 1.3), `COMPACT_RESTORE_PACKET.json` (schema 1.4; `authority.fields_authoritative` = [governance_constraints, active_checkpoints, drift_baseline, session_context]; `fields_advisory` = [working_context_resume]), `POST_COMPACT_AUDIT.json` (7-lane trust-store key_ids + governance/bootstrap/handoff hashes), `RECOVERY_TEST_RESULTS.json` (12/12 passed), `HANDOFF_HASH_LOG.jsonl` (tamper-evident sha256 handoff chain).
3. `S:\Archivist-Agent\.session-memory\session.db` - intended session/restore sink, but **empty**: tables `handoffs` / `compact_states` / `restore_points` all 0 rows. Treat as unproven; do not assume an auto-populated session restore exists.

Compact/restore mechanism evidence:
- Compact restore bridge pattern: `S:\kernel-lane\scripts\compact-restore-bridge.js` (`CompactRestoreBridge` + `REPO_MAP`, 5 CLI commands: snapshot/restore/audit/export/verify) and `S:\kernel-lane\scripts\post-compact-audit.js` (`PostCompactAudit`).
- `PRE_COMPACT_SNAPSHOT.json` - pre-compact resolved state captured before compaction.
- `COMPACT_RESTORE_PACKET.json` - the restore packet; authority field split above.
- `COMPACT_CONTEXT_HANDOFF` / `HANDOFF_HASH_LOG.jsonl` - tamper-evident handoff chain (stable `7c6b2a73...` then `a518c153...` from 2026-05-15).
- Cross-verify: `S:\self-organizing-library\scripts\sync-gate-verify.js` (derives `key_id` from trust-store PEMs; `valid_count` over 4 lanes) and `cross-lane-sync-gate.js`.
- Sync-all-lanes / sync-gate-verify: `S:\self-organizing-library\scripts\sync-all-lanes-audit.md`, `sync-all-lanes.js`.
- Archivist `context-buffer/sync-reports/*.json` - the actual post-compact **sync %** evidence: `summary.synced_targets / attempted_sync_targets / failed_sync_targets`, `lanes_all_tests_pass:4/4`, `healthy_lanes:4`, `overall_ok:true`; per-file `status` = `already_aligned` | `drift_detected` | `would_sync` with sha256 across archivist/swarmmind/kernel/library.

Phenotype / last-known-good concept:
- No literal "phenotype" file was inventoried; the concept is governance-level. `CORE_SEAN_ANCHOR.md` "Soul in State" + `COMPACT_RESTORE_PACKET.json` `authority.fields_authoritative.drift_baseline` = the last-known-good reference. Used for quarantine-reload.

Quarantine on failed restore:
- `S:\kernel-lane\lanes\kernel\inbox\archive\quarantine-20260503-2\` (nack-nack-*.json), `S:\SwarmMind\lanes\swarmmind\inbox\quarantine\` + `\blocked\`, and the WE4FREE lane-worker test suite (invalid -> quarantine; unsigned/mismatch/lane-violation -> blocked). `recovery-audit-log.json` carries `guardrails.adaptive_triggers.thresholds` (unpopulated stubs).

Thresholds:
- 80% trigger (existing code precedent): `orchestrate_compact.js` `TRIGGER_FRACTION=0.80` (128k token budget). This is an **early-compaction trigger**, not a restore acceptance threshold.
- >=93% minimum restore/sync fidelity (Sean-defined governance threshold): **derived, not literal**. The 93-100% SYNC is computed from sync report counts/booleans (`sync-all-lanes.js`, `sync-gate-verify.js`, `context-buffer/sync-reports/*.json`) - e.g. `valid_count/4` (4/4 = 100%) or aligned-files/total (a mid-drift snapshot reads ~93% = 41/44, recovering to 100% after re-sync). It is NOT stored as a literal `"93%"` string, which is why a naive `%` grep fails; the right place is the sync reports + gate verification, not each lane's `.compact-audit/` folder.

## Spec requirements (for any future Genesis compact/restore)
1. **Before compaction:** capture a `PRE_COMPACT_SNAPSHOT` of resolved state (mirror the kernel-lane bridge + Archivist `PRE_COMPACT_SNAPSHOT.json`).
2. **After restore:** verify the restored packet against the pre-compact snapshot (mirror `post-compact-audit.js` + `POST_COMPACT_AUDIT.json`).
3. **Fidelity acceptance:** restore must preserve **>=93%** semantic/state fidelity vs the pre-compact baseline.
4. **Below 93%:** mark the restore `conflicted` / `quarantined`; do not promote it.
5. **Last-known-good reload:** on quarantine, reload the last-known-good phenotype/fingerprint reference (the `drift_baseline` / `Soul in State` anchor), and route the degraded packet to quarantine (mirror kernel-lane `quarantine-*` + SwarmMind `quarantine/`/`blocked/`).
6. **No degraded continuation:** do not continue phase work from a degraded compact state.
7. **80% stays a trigger precedent:** the 80% `TRIGGER_FRACTION` remains an early-compaction signal, not the restore acceptance threshold.
8. **93% is the Genesis governance acceptance threshold** unless later repo evidence proves a higher exact value.
9. **Derived sync percentages:** sync fidelity MAY be derived from counts/booleans (e.g. `synced_targets/attempted_sync_targets`, `valid_count/4`, aligned-files/total), not literal `"%"` strings.
10. **Lightweight restore packets:** do NOT copy heavy graph / world state into restore packets. Store **hashes / references / fingerprints** instead, so a degraded restore can be quarantined and the last-known-good reloaded.
11. **Gate-7 remains closed.** This spec authorizes no daemon/scheduler/network/runtime; it is documentation of a boundary only.

## Allowed files
- this spec doc (`world-sim/docs/phase_10cx_compact_restore_sync_boundary_spec.md`)
- `README.md`
- `world-sim/docs/phase_index.md`

## Checks
- `git diff --check`
- `git diff --numstat`
- `git status -sb`
- CRLF check on touched files (no CRLF introduced; LF only)

## Output
```
PHASE: 10CX - Compact Restore Sync Boundary Spec
FILES CHANGED: world-sim/docs/phase_10cx_compact_restore_sync_boundary_spec.md (new), README.md, world-sim/docs/phase_index.md
EVIDENCE USED: continuity anchor (S:\continuity\CORE_SEAN_ANCHOR.md, TRANSFER_PACKET.md); Archivist .compact-audit (PRE_COMPACT_SNAPSHOT.json, COMPACT_RESTORE_PACKET.json schema 1.4, POST_COMPACT_AUDIT.json, HANDOFF_HASH_LOG.jsonl, RECOVERY_TEST_RESULTS.json 12/12); Archivist .session-memory/session.db (empty sink); kernel-lane compact-restore-bridge.js + post-compact-audit.js; library sync-gate-verify.js / cross-lane-sync-gate.js / sync-all-lanes-audit.md; Archivist context-buffer/sync-reports/*.json (synced_targets, lanes_all_tests_pass, overall_ok); orchestrate_compact.js TRIGGER_FRACTION=0.80; Sean >=93% derived sync fidelity threshold
CHECKS: git diff --check (no whitespace errors); git diff --numstat; git status -sb; CRLF/LF-only verified on touched files
STATUS: docs-only spec complete; working tree modified; NOT committed (stop before commit per rules)
PROPOSED COMMIT: 10CX: Compact Restore Sync Boundary Spec - import Sean compact/restore governance boundary into Genesis (pre-compact snapshot, post-restore >=93% fidelity verification, quarantine on <93%, last-known-good phenotype reload, 80% trigger precedent, gate-7 stays closed). Documentation only; no implementation, runtime, daemon/scheduler/network, or world-sim/data writes.
RISK NOTES:
- Archivist .session-memory/session.db is EMPTY (designed restore sink never populated) - do not assume auto session-restore exists; treat as unproven.
- COMPACT_RESTORE_PACKET.active_checkpoints is [] in the live packet yet the recovery test passed - authoritative field can be empty in practice; Genesis must require a non-empty last-known-good baseline before accepting a restore.
- The 93% figure is Sean-defined and DERIVED from counts/booleans, not a literal stored value; if later repo evidence shows a higher exact threshold, raise it. Do NOT treat 93% as a hard-coded constant in any future implementation.
- "Exclude heavy phenotype/graph from restore packet" must be applied as "store hashes/references/fingerprints, not full graph/world state" - NOT as "drop phenotype entirely." A phenotype/fingerprint reference is required so a degraded restore can be quarantined.
- Gate-7 remains closed; 10CX does not reopen or touch it.
```
