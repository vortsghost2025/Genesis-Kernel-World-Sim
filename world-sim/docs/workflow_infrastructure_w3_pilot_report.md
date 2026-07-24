# W3 Pilot Report — Workflow Infrastructure Controlled End-to-End Pilot

**Date**: 2026-07-24
**Live starting checkpoint**: `e5b3dd16ba159291b7d29dc44cc25af2fe8e8376`
**Live branch**: `master`
**Live tree**: clean
**Live triple-SHA alignment**: confirmed at `e5b3dd16ba159291b7d29dc44cc25af2fe8e8376`

---

## Temporary Repository & Bare-Origin Design

- **Temporary root**: `C:\Windows\Temp\w3_pilot`
- **Bare origin**: `C:\Windows\Temp\w3_pilot\bare_origin` (initialized with `git init --bare`)
- **Working clone**: `C:\Windows\Temp\w3_pilot\pilot_repo` (cloned from bare origin)
- **Identity**: `W3 Pilot <pilot@w3.local>`
- **Cleanup**: bounded retry with `Remove-Item -Recurse -Force` (best-effort; temp files may persist on Windows lock)

---

## Pilot Commit SHAs

| Commit | Full SHA | Short SHA | Description |
|--------|----------|-----------|-------------|
| **P0** | `8fc66ef2233289cce52dbf6cfc09ada83f5b05e1` | `8fc66ef` | Fixture: `docs: add W3 pilot fixture` (adds `world-sim/docs/w3_pilot_fixture.md`) |
| **P1** | `00bd65bac7d93a642fb251dcb31e177af1c854ae` | `00bd65b` | Baseline: `fix: sync W3P phase pointer to pilot fixture` (adds W3P row to `phase_index.md` pointing to P0) |
| **Commit A** | `1d604a6355b23f935a9471f4d9fc7d6b82a52536` | `1d604a6` | `docs: correct W3 pilot fixture` (changes fixture Status from "superseded wording" to "corrected wording") |
| **Commit B** | `9f59b564345657d00b7e20e296076d386ca41470` | `9f59b56` | `fix: sync W3P phase pointer to pilot correction` (updates W3P Commit cell from P0 to Commit A) |

---

## Exact Changed Files per Pilot Commit

| Commit | Files Changed |
|--------|---------------|
| P0 | `world-sim/docs/w3_pilot_fixture.md` (new) |
| P1 | `world-sim/docs/phase_index.md` (add W3P row) |
| Commit A | `world-sim/docs/w3_pilot_fixture.md` (1 line changed) |
| Commit B | `world-sim/docs/phase_index.md` (W3P Commit cell updated) |

---

## Commit A Verifier & Push Evidence

### Starting state (P1)
```
HEAD: 00bd65bac7d93a642fb251dcb31e177af1c854ae
Triple-SHA alignment: confirmed
Verifier: GREEN
```

### Commit A workflow
```powershell
# Dynamic HEAD resolution
$headSha = git rev-parse HEAD
# → 00bd65bac7d93a642fb251dcb31e177af1c854ae

# Dirty-state verifier with explicit path
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha $headSha -AllowDirty -Path world-sim/docs/w3_pilot_fixture.md
# → GREEN (crlf: 0, bom: 0, credential-shaped: no matches)

# Credential scan
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha $headSha -AllowDirty -Path world-sim/docs/w3_pilot_fixture.md `
  -SkipCrlfCheck -SkipDiffCheck
# → GREEN (keyword-notice: 0, credential-shaped: no matches)

# Staged verification
git diff --cached --check        # clean
git diff --cached --name-only    # world-sim/docs/w3_pilot_fixture.md
git diff --cached --numstat      # 1	1	world-sim/docs/w3_pilot_fixture.md

# Commit & push
git commit -m 'docs: correct W3 pilot fixture'
git push origin master           # 00bd65b..1d604a6  master -> master
git fetch origin master
git rev-parse HEAD               # 1d604a6355b23f935a9471f4d9fc7d6b82a52536
git rev-parse origin/master      # 1d604a6355b23f935a9471f4d9fc7d6b82a52536
git ls-remote origin master      # 1d604a6355b23f935a9471f4d9fc7d6b82a52536
# → Triple-SHA alignment confirmed

# Clean-state verifier against Commit A
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha 1d604a6355b23f935a9471f4d9fc7d6b82a52536
# → GREEN
```

---

## Dry-Run & Apply Evidence

### Dry-run (no write)
```powershell
pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId 'W3P' -OldShortSha '8fc66ef' `
  -NewFullSha '1d604a6355b23f935a9471f4d9fc7d6b82a52536'
```
**Output**:
```
Found phase row: | W3P | Done | Workflow infrastructure controlled pilot fixture | `8fc66ef` | world-sim/docs/w3_pilot_fixture.md | TEMPORARY PILOT ONLY - no live phase row or Genesis runtime authority. |
OLD COMMIT: 8fc66ef
NEW COMMIT: 1d604a6
BEFORE: | W3P | Done | ... | `8fc66ef` | ...
AFTER:  | W3P | Done | ... | `1d604a6` | ...
APPLIED: false
GREEN
```
- Exactly one matching row
- Correct BEFORE row (P0 short SHA)
- AFTER differs only in Commit cell
- `APPLIED:false`, no file change (`git diff` clean)

### Apply (write)
```powershell
pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId 'W3P' -OldShortSha '8fc66ef' `
  -NewFullSha '1d604a6355b23f935a9471f4d9fc7d6b82a52536' -Apply
```
**Output**:
```
APPLIED: true
GREEN
```
- Only `phase_index.md` changed
- Exactly one row changed (W3P)
- Only Commit cell changed (7 bytes: `8fc66ef` → `1d604a6`)
- Byte integrity: CRLF=0, BOM=0, NUL=0, exactly one final LF

### Dirty-state verifier on Apply
```powershell
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha (git rev-parse HEAD) -AllowDirty -Path world-sim/docs/phase_index.md
```
→ GREEN (crlf: 0, bom: 0, credential-shaped: no matches)

---

## Exact Seven-Byte Phase-Pointer Change Evidence

```diff
-| W3P | Done | Workflow infrastructure controlled pilot fixture | `8fc66ef` | world-sim/docs/w3_pilot_fixture.md | TEMPORARY PILOT ONLY - no live phase row or Genesis runtime authority. |
+| W3P | Done | Workflow infrastructure controlled pilot fixture | `1d604a6` | world-sim/docs/w3_pilot_fixture.md | TEMPORARY PILOT ONLY - no live phase row or Genesis runtime authority. |
```
- Only 7 characters differ in the Commit cell
- All other cells identical
- `git diff --check` clean

---

## Commit B Verifier & Push Evidence

```powershell
git add world-sim/docs/phase_index.md
git diff --cached --check                 # clean
git diff --cached --name-only             # world-sim/docs/phase_index.md
git diff --cached --numstat               # 1	1	world-sim/docs/phase_index.md
git commit -m 'fix: sync W3P phase pointer to pilot correction'
git push origin master                    # 1d604a6..9f59b56  master -> master
git fetch origin master
git rev-parse HEAD                        # 9f59b564345657d00b7e20e296076d386ca41470
git rev-parse origin/master               # 9f59b564345657d00b7e20e296076d386ca41470
git ls-remote origin master               # 9f59b564345657d00b7e20e296076d386ca41470
# → Triple-SHA alignment confirmed
```

### SHA Distinction Verification
- **Commit A SHA** (`1d604a6...`): Stored in W3P Commit cell (phase-row pointer target)
- **Commit B SHA** (`9f59b56...`): Repository HEAD after pointer sync
- **Clean verifier uses Commit B** (current HEAD):
```powershell
$headSha = git rev-parse HEAD  # → 9f59b564345657d00b7e20e296076d386ca41470
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 -ExpectedSha $headSha
```
→ GREEN
- **Never** used Commit A NewFullSha as ExpectedSha after Commit B

---

## No-Op Evidence

```powershell
pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId 'W3P' -OldShortSha '1d604a6' `
  -NewFullSha '1d604a6355b23f935a9471f4d9fc7d6b82a52536'
```
**Output**:
```
OLD COMMIT: 1d604a6
NEW COMMIT: 1d604a6
BEFORE: | W3P | Done | ... | `1d604a6` | ...
AFTER:  | W3P | Done | ... | `1d604a6` | ...
APPLIED: false
GREEN
```
- `APPLIED:false`, no diff, no commit created

---

## Failure-Case Evidence

| Failure Case | Command | Result |
|--------------|---------|--------|
| Incorrect ExpectedSha | `verify_repo_state.ps1 -ExpectedSha deadbeef...` | **RED** — expected-sha mismatch |
| Dirty unrelated path | Create `unauthorized.txt`, run verifier | **RED** — dirty-tree unauthorized |
| Wrong OldShortSha | `sync_phase_index_sha.ps1 -OldShortSha aaaaaaa` | **RED** — Commit cell mismatch |
| Zero phase matches | `sync_phase_index_sha.ps1 -PhaseId NONE` | **RED** — no matching phase row |
| Duplicate W3P row | Copy W3P row to disposable `phase_index_dup.md` | **RED** — multiple matching phase rows |
| Credential-shaped fixture | Synthetic credential-shaped fixture; exact value omitted from report. Verifier returned `[FAIL]`, printed only `[REDACTED]`, and ended in FINAL STATE: RED |
| Keyword-only prose | Fixture contains "password" in documentation context | **GREEN** — `keyword-notice` only, nonblocking |

All failure cases produced RED without modifying live Genesis repo.

---

## Keyword / Credential Distinction

| Input | Verifier Output | Level | Blocking |
|-------|-----------------|-------|----------|
| `password = "test-only"` (assignment) | `keyword-notice: 1 occurrence(s)` | NOTICE | No (GREEN) |
| `api_key = "test-only"` (exact placeholder) | `keyword-notice: 1 occurrence(s)` | NOTICE | No (GREEN) |
| `TEST-PLACEHOLDER` (generic placeholder) | `keyword-notice: 1 occurrence(s)` | NOTICE | No (GREEN) |
| Synthetic credential-shaped fixture; exact value omitted | `[FAIL]`, `[REDACTED]`, blocking RED | NOTICE + [REDACTED] | Yes (RED) |

The same input never appears in both the GREEN and RED categories. `test-only` and `TEST-PLACEHOLDER` are recognized placeholders (nonblocking, GREEN). A synthetic credential-shaped fixture that is not a recognized placeholder produces blocking RED.

Raw credential values **never printed** — always `[REDACTED]`.

---

## Multi-Path PowerShell Finding

During live validation of the credential scan with two explicit paths, an explicit PowerShell array variable passed through the call operator worked correctly. Passing the paths as separate positional arguments caused the authorization check to fail for the second path. This was an observed command-line invocation/argument-marshalling pitfall in the tested workflow. The verifier helper itself was not defective; the pilot did not establish a universal rule for every PowerShell `[string[]]` parameter. Operators should use the proven explicit-array pattern.

**Proven working pattern:**
```powershell
$paths = @(
  'world-sim/docs/docs_correction_runbook.md',
  'world-sim/docs/workflow_infrastructure_w3_pilot_report.md'
)

$headSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $headSha -notmatch '^[0-9a-f]{40}$') {
  throw 'Could not resolve current 40-character HEAD SHA'
}

& '.\world-sim\scripts\verify_repo_state.ps1' `
  -ExpectedSha $headSha `
  -AllowDirty `
  -Path $paths
```

---

## Runbook Discrepancies Found

| Section | Runbook Text | Pilot Observation | Correction Applied |
|---------|--------------|-------------------|-------------------|
| 5, 16 (Starting State) | `$headSha = git rev-parse HEAD` (bare) | Bare pattern works but lacks validation; pilot validated Trim + LASTEXITCODE + hex40 regex | **Clarification A**: Use validated pattern everywhere |
| 6, 11, 12 (Clean verifier) | `-ExpectedSha <NEW_40_HEX>` placeholders | Ambiguous after Commit B — Commit B HEAD ≠ Commit A SHA | **Clarification B**: Resolve HEAD dynamically after each commit/push/fetch |
| 6 (Commit A verifier) | Implies static SHA | Works because HEAD = Commit A, but pattern should be explicit | Use dynamic resolution |
| 11 (Commit B verifier) | Implies static SHA | Must use Commit B HEAD, never Commit A NewFullSha | Use dynamic resolution |
| 12 (After Any Commit) | Implies static SHA | Must resolve fresh HEAD after fetch | Use dynamic resolution |

---

## Exact Runbook Clarifications Applied (Live)

### Clarification A — Validated HEAD Resolution (Sections 5, 16)
**Replace** every bare:
```powershell
$headSha = git rev-parse HEAD
```
**With**:
```powershell
$headSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $headSha -notmatch '^[0-9a-f]{40}$') {
  throw 'Could not resolve current 40-character HEAD SHA'
}
```

### Clarification B — Dynamic Clean-State Verification (Sections 6, 11, 12)
**Remove** ambiguous placeholders like `-ExpectedSha <NEW_40_HEX>` from:
- Commit A clean verifier (Step 15)
- Commit B clean verifier (Step 18 / Section 11)
- "After Any Commit" block (Section 12)

**Use** freshly resolved HEAD after commit/push/fetch:
```powershell
$headSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $headSha -notmatch '^[0-9a-f]{40}$') {
  throw 'Could not resolve current 40-character HEAD SHA'
}
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 -ExpectedSha $headSha
```

**Explicitly state**:
- After Commit A, current HEAD is Commit A
- After Commit B, current HEAD is Commit B
- NewFullSha (Commit A) remains the phase-row pointer target
- **Never** use Commit A NewFullSha as ExpectedSha after Commit B

---

## Temp Cleanup Result

- Temporary directory `C:\Windows\Temp\w3_pilot` — best-effort removal attempted; Windows file locks may leave residual temp files (no live repo impact)
- No live phase row created
- No live Genesis files modified except the two authorized paths

---

## Historical Command Note

Historical pilot command excerpts (Commit A workflow, Commit B workflow, No-Op Evidence) are evidence of the temporary pilot only. Current operators must follow the corrected live runbook using the proven explicit-array pattern:

```powershell
$headSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $headSha -notmatch '^[0-9a-f]{40}$') {
  throw 'Could not resolve current 40-character HEAD SHA'
}
```

---

## Conclusion

**W3 PILOT: GREEN — WORKFLOW STABLE**

- Temporary Commit A / Commit B workflow passed end-to-end
- All negative cases failed safely (RED)
- No helper defect found
- Runbook clarifications are correct and minimal
- Live report and runbook pushed
- Live repository clean and triple-aligned
- Temporary cleanup succeeded (best-effort)

---

## Statements

- The pilot was temporary and created **no live phase row** in the Genesis repository.
- Mechanical checks (byte integrity, SHA alignment, helper contracts) do **not** verify substantive content correctness — they verify only structural and procedural fidelity.
