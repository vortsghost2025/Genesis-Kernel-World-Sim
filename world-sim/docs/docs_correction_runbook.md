# Documentation Correction & Phase Pointer Synchronization Runbook

## Purpose

This runbook defines the standard procedure for:

1. **Documentation corrections** — fixing typos, clarifying prose, updating
   cross-references, or correcting metadata in authorized
   `world-sim/docs/` markdown files.
2. **Phase-index Commit-cell pointer synchronization** — updating a phase
   row's Commit cell to reference the Commit A correction commit that
   belongs to that phase.

The runbook is **read-only for tooling**; it does not grant authority to
modify implementation code, tests, backend, frontend, runtime, or data.

---

## 1. Scope & Authority

| Action | Allowed | Requires Explicit Authorization |
|--------|---------|--------------------------------|
| Edit an explicitly authorized `world-sim/docs/*.md` file | ✅ | Sean before edit begins |
| Stage, commit, and push that correction | ✅ after passing all checks | — |
| Synchronise the commit SHA in an existing phase row | ✅ after Commit A is pushed | Sean before dry-run |
| Edit `verify_repo_state.ps1` | ❌ | Sean |
| Edit `sync_phase_index_sha.ps1` | ❌ | Sean |
| Edit `AGENTS.md` | ❌ | Sean |
| Edit `README.md` | ❌ | Sean |
| Start W3, 10II, or any implementation phase | ❌ | Sean |
| Force-push, amend, rebase, reset, or rewrite public history | ❌ | Never |
| Modify backend, runtime, provider, container, data, or first-pair files | ❌ | Never |

---

## 2. Non-Negotiable Boundaries

- **Gate-7 remains closed** — 10CP is the sole world-state/ledger writer.
- **FIRST_PAIR_CREATION_AUTHORIZED = False** — no first-pair creation.
- **10HD is named-only** — no 10HD work has begun.
- **No force push** — never use `--force`, `--force-with-lease`, or any
  rewrite of public history.
- **Never amend Commit A** after its SHA has been referenced or pushed.
- **No-op creates no pointer commit** — if dry-run or Apply produces no
  diff, there is nothing to commit.

---

## 3. Required Tools and Paths

- **Shell**: PowerShell 7 only (`pwsh -NoProfile`)
- **Repository root**: `S:\Genesis Kernel World Sim`
- **Phase index**: `world-sim/docs/phase_index.md` (relative to repo root)
- **Verify helper**: `world-sim/scripts/verify_repo_state.ps1`
- **Sync helper**: `world-sim/scripts/sync_phase_index_sha.ps1`

---

## 4. Exit Codes and GREEN/RED Meaning

| Helper | GREEN Meaning | RED Meaning |
|--------|---------------|-------------|
| `verify_repo_state.ps1` | All checks pass; state is correct | At least one check failed |
| `sync_phase_index_sha.ps1` | Validation passed; operation is safe | Validation failed; do not proceed |

Both helpers exit 0 for GREEN and 2 for RED.

---

## 5. Before Touching a File

```powershell
Set-Location 'S:\Genesis Kernel World Sim'

git status -sb
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master

pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha c5b6f366fbfab02a1574f9e5affb73d63bcecba5

pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -SelfTest
```

**STOP unless all of the following are true:**

> - branch is `master`
> - tree is clean
> - local HEAD, origin/master, and git ls-remote are identical
> - verifier is **GREEN**
> - helper self-test exits 0 and prints `SELF-TEST PASSED` exactly once

If any check fails:

> - **STOP**
> - **Preserve evidence** — copy the failing command and output
> - **Do not merge, rebase, reset, revert, restore, stash, clean, or
>   force-push**
> - **Return to Sean for direction**

---

## 6. Documentation-Correction Commit Procedure

This procedure produces **Commit A** — the approved documentation correction.

### Step 1: Confirm Authorization

- Sean has explicitly named the exact file path and the nature of the change.
- The file is in `world-sim/docs/` and is not a phase-index row operation.

### Step 2: Confirm Starting State

Run the checks from Section 5 (Before Touching a File). All must pass.

### Step 3: Run Starting Verifier

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD>
```

Must be GREEN.

### Step 4: Edit Exactly the Authorized Document

Make the targeted edit. Use exact-string replacement when possible. Do not
modify any other file.

### Step 5: Verify Byte Integrity

```powershell
$bytes = [IO.File]::ReadAllBytes('world-sim/docs/<file>')

# UTF-8 no BOM
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
  throw 'BOM detected'
}

# LF only
for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
  if ($bytes[$i] -eq 0x0D -and $bytes[$i+1] -eq 0x0A) { throw "CRLF at byte $i" }
}

# Exactly one final LF
if ($bytes[-1] -ne 0x0A) { throw 'Missing final LF' }
if ($bytes.Length -gt 1 -and $bytes[-2] -eq 0x0A) { throw 'More than one final LF' }
```

### Step 6: Check Status and Diff

```powershell
git status --short
git diff -- world-sim/docs/<file>
git diff --check
```

### Step 7: Run Dirty-State Verifier with Explicit Path

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD> `
  -AllowDirty `
  -Path world-sim/docs/<file>
```

Must be GREEN. This checks the changed file for CRLF, BOM, credential-shaped
patterns, and whitespace issues.

### Step 8: Review the Complete Diff

Confirm every changed line is intentional.

### Step 9: Redacted Credential-Shaped Scan

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD> `
  -AllowDirty `
  -Path world-sim/docs/<file> `
  -SkipCrlfCheck `
  -SkipDiffCheck
```

Review the output. Never print raw credential values. The scan keyword-matches
credential-shaped patterns and surfaces NOTICE-level lines.

### Step 10: Stage Exactly the Authorized File

```powershell
git add world-sim/docs/<file>
```

Never use `git add .` or `git add -A`.

### Step 11: Verify Staged Content

```powershell
git diff --cached --check
git diff --cached --name-only
git diff --cached --numstat
git diff --cached -- world-sim/docs/<file>
```

The staged file list must contain exactly the one authorized file.

### Step 12: Commit with the Authorized Message

```powershell
git commit -m '<authorized commit message>'
```

### Step 13: Push Non-Force Immediately

```powershell
git push origin master
```

### Step 14: Fetch and Triple-Verify

```powershell
git fetch origin master
git status -sb
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master
```

Require triple-SHA alignment and clean tree.

### Step 15: Run Clean-State Verifier

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <NEW_40_HEX>
```

Must be GREEN.

### Step 16: Confirm Helper Integrity

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -SelfTest

pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -SelfTest
```

Both must print self-test passed.

---

At this point, **Commit A** exists. It is the pushed documentation correction.
Do not amend it.

---

## 7. Decide Whether Phase-Index Synchronisation Is Required

**Pointer synchronization is required only when ALL of the following are
true:**

- The corrected document belongs to a named existing phase (has a row in
  `phase_index.md`)
- Exactly one current phase row matches the `PhaseId`
- That row's `Commit` cell currently points to the superseded SHA
- The new documentation correction commit is the authorized replacement
  pointer

**Do NOT synchronize for:**

- Workflow infrastructure such as W1, W2A, or W2B
- Unrelated documentation that does not belong to any existing phase
- An already-correct pointer (Commit cell already matches)
- A phase with no authorized row in the index
- An attempt to create or start a new phase

If pointer synchronization is not required, stop here. No Commit B is needed.

---

## 8. Two-Commit Protocol

```
Commit A — Approved documentation correction (prose, format, cross-ref)
           Push first. Never amend after SHA is stable.

Commit B — Phase-index Commit-cell pointer synchronization
           Only if the corrected document belongs to a named phase and the
           Commit cell must be updated. Created only when Apply produces a
           real diff.
```

**Rules:**

- Commit A must be pushed and triple-aligned before any dry-run for Commit B.
- Commit A's full SHA must be stable before dry-run.
- Never amend Commit A after its SHA has been referenced.
- Commit B changes only `world-sim/docs/phase_index.md`.
- No-op dry-run or no-op Apply creates no Commit B.

---

## 9. Pointer-Decision Record and Dry-Run

### Record

Before the dry-run, record:

- **PhaseId**: the exact phase ID (e.g., `10FH`)
- **OldShortSha**: the current 7-char SHA in the Commit cell
- **NewFullSha**: the full 40-char SHA of Commit A
- **NewShortSha**: first 7 characters of NewFullSha
- **Reason**: why the phase pointer must change
- **Approval**: Sean has explicitly approved the proposed BEFORE/AFTER row

### Dry-Run

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId '<PhaseId>' `
  -OldShortSha '<OldShortSha>' `
  -NewFullSha '<NewFullSha>'
```

**Review the helper's actual output:**

- `Found phase row` — confirm the correct row was matched
- `OLD COMMIT` — must match OldShortSha
- `NEW COMMIT` — must match NewShortSha
- `BEFORE` — the existing row
- `AFTER` — the proposed updated row
- `APPLIED:false` — dry-run did not write
- `GREEN` — validation passed

**Confirm no file change:**

```powershell
git diff -- world-sim/docs/phase_index.md
```

Must show no diff.

---

## 10. Authorized Phase-Index Apply

Apply may occur only when:

- Commit A is already pushed and triple-aligned
- Dry-run was GREEN
- BEFORE and AFTER rows are approved by Sean
- Tree is clean
- Pointer change is explicitly authorized by Sean

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId '<PhaseId>' `
  -OldShortSha '<OldShortSha>' `
  -NewFullSha '<NewFullSha>' `
  -Apply
```

Verify:

- Only `world-sim/docs/phase_index.md` changed
- Exactly one row changed
- Only its Commit cell changed
- All other rows and prose unchanged
- Byte integrity correct
- `git diff --check` clean

Run dirty-state verifier:

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD> `
  -AllowDirty `
  -Path world-sim/docs/phase_index.md
```

Must be GREEN.

---

The helper only edits the file. It never stages, commits, fetches, or pushes.
No-op Apply (when old and new SHA are the same) still enforces safety but
creates no diff and no commit.

---

## 11. Pointer-Sync Commit Procedure

### Stage Exactly the Phase Index

```powershell
git add world-sim/docs/phase_index.md
```

### Verify Staged Content

```powershell
git diff --cached --check
git diff --cached --name-only
git diff --cached --numstat
git diff --cached -- world-sim/docs/phase_index.md
```

The staged file list must contain exactly `world-sim/docs/phase_index.md`.

### Commit with Authorized Message

```powershell
git commit -m 'fix: sync phase_index.md <PhaseId> commit to <NewShortSha>'
```

### Push Non-Force Immediately

```powershell
git push origin master
```

### Fetch and Triple-Verify

```powershell
git fetch origin master
git status -sb
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master
```

Require triple-SHA alignment and clean tree.

### Run Clean-State Verifier

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <NEW_40_HEX>
```

Must be GREEN.

---

## 12. Final Verification (After Any Commit)

Run after every commit and push:

```powershell
# Repository state
git status -sb
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master

# Verifier
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <NEW_40_HEX>

# Helper integrity
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -SelfTest
```

Confirm:

- Triple-SHA alignment
- Clean tree
- Verifier GREEN
- Helper self-test PASSED
- `phase_index.md` byte-identical to HEAD (unless Commit B was created)
- Both helpers, `AGENTS.md`, and `README.md` unchanged (unless explicitly
  authorized)

---

## 13. Abort and Recovery Cases

For every case below:

> - **STOP**
> - **Preserve evidence** — copy the failing command and its output
> - **Do not merge, rebase, reset, revert, restore, stash, clean, or
>   force-push**
> - **Return to Sean for direction**

| Scenario | Stop Signal |
|----------|-------------|
| Dirty tree before starting | `git status -sb` shows staged/unstaged/untracked |
| Wrong branch | `git rev-parse --abbrev-ref HEAD` is not `master` |
| SHA divergence | HEAD, origin/master, or ls-remote differ |
| Missing origin | `git rev-parse origin/master` fails |
| Unexpected untracked/changed paths | `git status --short` shows unexpected files |
| Verifier RED | `FINAL STATE: RED` |
| Helper self-test RED | Not `SELF-TEST PASSED` |
| Zero or multiple phase matches | `sync_phase_index_sha.ps1` reports zero/duplicate |
| Wrong OldShortSha | OLD COMMIT does not match expected |
| Malformed phase row | Helper exits RED on row parsing |
| Path outside repository | `sync_phase_index_sha.ps1` ST24 |
| Preflight drift | Drift check fails (ST36a) |
| Apply RED | Apply exits non-zero or shows RED |
| Unexpected extra diff | More rows changed than expected |
| Rejected push (remote advanced) | `git push` fails with non-fast-forward |
| Credential-shaped material | Verifier NOTICE with actual credential pattern |

---

## 14. Evidence Checklist

After every complete run:

- Starting state checks (Section 5 output)
- Commit A full SHA and message
- Non-force push output
- Commit B full SHA and message (if created)
- Final triple-SHA alignment
- Clean tree confirmation
- Verifier GREEN output
- Helper self-test PASSED
- Changed file list and numstat
- Proof exactly one final LF
- Byte-integrity results (UTF-8 no BOM, LF-only, no NUL)
- Credential-shaped scan result
- Policy corrections made (if runbook was the target)
- Confirmation `phase_index.md` unchanged (unless Commit B was created)
- Confirmation helpers, AGENTS.md, README.md unchanged
- Confirmation W3 and 10II not started
- Gate-7 still closed
- 10CP sole writer
- 10HD named-only
- FIRST_PAIR_CREATION_AUTHORIZED = False

---

## 15. Fully Worked 10IH No-Op Example

This example demonstrates a no-op dry-run against the existing 10IH phase
row. It does not change `phase_index.md`.

### Context

- **PhaseId**: `10IH`
- **OldShortSha**: `f3317e1`
- **NewFullSha**: `f3317e106a8c59d39498a1e4cd708e134ff1f389`
- **NewShortSha**: `f3317e1` (same as OldShortSha)
- This is a **no-op**: old and new SHA are identical

### Command

```powershell
Set-Location 'S:\Genesis Kernel World Sim'

pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId '10IH' `
  -OldShortSha 'f3317e1' `
  -NewFullSha 'f3317e106a8c59d39498a1e4cd708e134ff1f389'
```

### Expected Output

```
Found phase row: | 10IH | Sub/Active | (long purpose) | `f3317e1` | Low | (notes) |
OLD COMMIT: f3317e1
NEW COMMIT: f3317e1
BEFORE: | 10IH | Sub/Active | (purpose) | `f3317e1` | Low | (notes) |
AFTER:  | 10IH | Sub/Active | (purpose) | `f3317e1` | Low | (notes) |
APPLIED: false
GREEN
```

### Verification

```powershell
git diff -- world-sim/docs/phase_index.md
```

Must show no diff — `phase_index.md` stays unchanged.

### Rules

- Do not add `-Apply`
- Do not commit anything
- This is a no-op; it creates no Commit B

---

## 16. Copy-Paste PowerShell Reference

### Check Starting State

```powershell
Set-Location 'S:\Genesis Kernel World Sim'

git status -sb
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master

pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha c5b6f366fbfab02a1574f9e5affb73d63bcecba5

pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -SelfTest
```

### Verify Dirty Work

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD> `
  -AllowDirty `
  -Path world-sim/docs/<file>
```

### Verify Clean State

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <NEW_40_HEX>
```

### Sync Dry-Run

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId '<PhaseId>' `
  -OldShortSha '<OldShortSha>' `
  -NewFullSha '<NewFullSha>'
```

### Sync Apply (authorized only)

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/sync_phase_index_sha.ps1 `
  -PhaseId '<PhaseId>' `
  -OldShortSha '<OldShortSha>' `
  -NewFullSha '<NewFullSha>' `
  -Apply
```

### Stage, Commit, Push

```powershell
git add world-sim/docs/<file>
git diff --cached --check
git diff --cached --name-only
git diff --cached --numstat
git diff --cached -- world-sim/docs/<file>
git commit -m '<message>'
git push origin master

git fetch origin master
git status -sb
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master
```

### Credential-Shaped Scan

```powershell
pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha <CURRENT_40_HEX_HEAD> `
  -AllowDirty `
  -Path world-sim/docs/<file> `
  -SkipCrlfCheck `
  -SkipDiffCheck
```

### Helper Self-Tests

```powershell
pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 -SelfTest
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 -SelfTest
```

### Byte Integrity Check

```powershell
$bytes = [IO.File]::ReadAllBytes('world-sim/docs/<file>')

# UTF-8 no BOM
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
  throw 'BOM detected'
}

# LF only
for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
  if ($bytes[$i] -eq 0x0D -and $bytes[$i+1] -eq 0x0A) { throw "CRLF at byte $i" }
}

# Exactly one final LF
if ($bytes[-1] -ne 0x0A) { throw 'Missing final LF' }
if ($bytes.Length -gt 1 -and $bytes[-2] -eq 0x0A) { throw 'More than one final LF' }
```

---

## 17. Version

Runbook created: 2026-07-24
Correction commit: corrects the initial W2B runbook (base commit
`c5b6f366fbfab02a1574f9e5affb73d63bcecba5`)

This runbook is Commit A of the correction. No pointer synchronization is
needed for W2B (workflow infrastructure — see Section 7).
