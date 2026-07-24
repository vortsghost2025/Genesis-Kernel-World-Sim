# Documentation Correction & Phase Pointer Synchronization Runbook

## Purpose

This runbook defines the standard procedure for:

1. **Documentation corrections** — fixing typos, clarifying prose, updating cross-references, or correcting metadata in `world-sim/docs/` markdown files (including `phase_index.md`).
2. **Phase pointer synchronization** — advancing the "current phase" pointer in tooling and documentation after a phase is pushed to `origin/master`.

The runbook is **read-only for tooling**; it does not grant authority to modify implementation code, tests, backend, frontend, runtime, or data.

---

## 1. Scope & Authority

| Action | Allowed | Requires Explicit Authorization |
|--------|---------|--------------------------------|
| Edit `world-sim/docs/*.md` for typo/prose/format fixes | ✅ | — |
| Update cross-references in `phase_index.md` | ✅ | — |
| Edit `phase_index.md` Status/Purpose/Commit/Runtime/Notes cells | ❌ | Sean explicit approval |
| Change `phase_index.md` Phase ordering or add rows | ❌ | Sean explicit approval |
| Modify `verify_repo_state.ps1` | ❌ | Sean explicit approval |
| Modify `sync_phase_index_sha.ps1` | ❌ | Sean explicit approval |
| Modify AGENTS.md | ❌ | Sean explicit approval |
| Modify README.md | ❌ | Sean explicit approval |
| Create new markdown files in `world-sim/docs/` | ❌ | Sean explicit approval |
| Run `-Apply` against live `phase_index.md` | ❌ | Sean explicit approval |
| Start W3 or 10II | ❌ | Sean explicit approval |

**Boundary reminder**: This runbook covers documentation-only corrections. Any change to the phase index's structural rows (Phase, Status, Commit SHA) is a *phase metadata* operation and follows the phase sync protocol (Section 5), not this runbook.

---

## 2. Preconditions

Before any documentation correction:

1. **Repository state is GREEN**:
   ```powershell
   git status -sb
   git rev-parse HEAD
   git rev-parse origin/master
   git ls-remote origin refs/heads/master
   pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 -ExpectedSha <current-head-sha>
   ```
   All must report clean tree, branch `master`, triple-SHA alignment, and verifier GREEN.

2. **Working tree is clean** — no unstaged, staged, or untracked files except the intended correction.

3. **Current HEAD matches origin/master** — no local commits ahead.

4. **No W2B, W3, or 10II work in progress** — this runbook is for documentation corrections only.

---

## 3. Documentation Correction Workflow

### 3.1 Identify the Correction

- Locate the target file(s) in `world-sim/docs/`.
- Confirm the change is **prose, formatting, cross-reference, or metadata clarification only**.
- Document the exact change (old text → new text) in a scratch note.

### 3.2 Apply the Correction

```powershell
# Example: fix a typo in phase_index.md
# 1. Read the file
$path = 'S:\Genesis Kernel World Sim\world-sim\docs\phase_index.md'
$content = [IO.File]::ReadAllText($path, [Text.UTF8Encoding]::new($false))

# 2. Make the targeted replacement (exact string match)
$old = 'exmaple'
$new = 'example'
if ($content -notmatch [regex]::Escape($old)) { throw "Old text not found" }
$content = $content.Replace($old, $new)

# 3. Write with LF-only, no BOM
[IO.File]::WriteAllText($path, $content, [Text.UTF8Encoding]::new($false))

# 4. Verify no CRLF/BOM introduced
$bytes = [IO.File]::ReadAllBytes($path)
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { throw "BOM introduced" }
for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
    if ($bytes[$i] -eq 0x0D -and $bytes[$i+1] -eq 0x0A) { throw "CRLF introduced at $i" }
}
```

### 3.3 Verify the Correction

```powershell
# Run repo verifier (no -Path; we trust the verifier to scan changes)
pwsh -NoProfile -File world-sim/scripts/verify_repo_state.ps1 -ExpectedSha <current-head-sha>

# Confirm diff is exactly the intended change
git diff -- world-sim/docs/phase_index.md
git diff --check
```

### 3.4 Stop Before Commit

**Do not commit or push.** Documentation corrections in this phase are **spec/audit only**. The commit/push decision belongs to Sean.

Record the exact change for the handoff:
- File(s) changed
- Exact diff
- Verifier output (GREEN)

---

## 4. Phase Pointer Synchronization (Post-Push)

This section applies **only after a phase has been pushed to `origin/master`** and the real pushed SHA is known.

### 4.1 When to Run

- A phase implementation commit has been pushed to `origin/master`.
- The public `phase_index.md` still shows the old short SHA or "Pushed / CI pending" status.
- Sean authorizes the metadata sync.

### 4.2 Procedure

1. **Confirm the pushed SHA**:
   ```powershell
   git ls-remote origin refs/heads/master
   # Record the 40-char SHA
   ```

2. **Identify the target row** in `phase_index.md`:
   - Phase ID (e.g., `10FH`)
   - Current short SHA in Commit cell (e.g., `bbbbbbb`)
   - New short SHA = first 7 chars of pushed 40-char SHA

3. **Run the sync helper in dry-run mode** (does not write):
   ```powershell
   pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 `
       -PhaseId '10FH' `
       -OldShortSha 'bbbbbbb' `
       -NewFullSha '<40-char-pushed-sha>' `
       -IndexPath 'world-sim/docs/phase_index.md'
   ```
   Verify output shows `APPLIED:false` and `GREEN`.

4. **Run with `-Apply`** (only after Sean authorization):
   ```powershell
   pwsh -NoProfile -File world-sim/scripts/sync_phase_index_sha.ps1 `
       -PhaseId '10FH' `
       -OldShortSha 'bbbbbbb' `
       -NewFullSha '<40-char-pushed-sha>' `
       -IndexPath 'world-sim/docs/phase_index.md' `
       -Apply
   ```
   Verify output shows `APPLIED:true` and `GREEN`.

5. **Verify the result**:
   ```powershell
   git diff -- world-sim/docs/phase_index.md
   # Should show exactly the 7-char SHA replacement in the Commit cell
   ```

6. **Commit the sync** (separate commit, message format):
```
    fix: sync phase_index.md 10FH commit to <short-sha>

    Phase 10FH pushed as <full-sha>; update index pointer.
    ```

7. **Push the sync commit**:
   ```powershell
   git push origin master
   ```

8. **Record the new triple-SHA alignment**:
   ```powershell
   git rev-parse HEAD
   git rev-parse origin/master
   git ls-remote origin refs/heads/master
   ```

---

## 5. Helper Script Reference

### `sync_phase_index_sha.ps1`

| Parameter | Required | Description |
|-----------|----------|-------------|
| `-PhaseId` | Yes | Exact Phase ID from table (e.g., `10FH`) |
| `-OldShortSha` | Yes | Current 7-char SHA in Commit cell |
| `-NewFullSha` | Yes | Full 40-char SHA from `git ls-remote` |
| `-IndexPath` | No | Default: `world-sim/docs/phase_index.md` |
| `-Apply` | No | Switch: write changes; omit for dry-run |
| `-SelfTest` | No | Switch: run internal self-test suite |

**Exit codes**: 0 = GREEN, 2 = RED (validation failure)

**Output format**:
```
Found phase row: | 10FH | Done | Purpose | `bbbbbbb` | Low | Notes |
OLD COMMIT: bbbbbbb
NEW COMMIT: 1234567
APPLIED: true
GREEN
```

### `verify_repo_state.ps1`

Read-only repository health check. Key parameters:

| Parameter | Description |
|-----------|-------------|
| `-ExpectedSha` | Required: 40-char lowercase SHA to match local HEAD |
| `-Remote` | Default `origin` |
| `-Branch` | Default `master` |
| `-Path` | Explicit paths to scan for CRLF/BOM/credentials |
| `-AllTracked` | Scan all tracked files |
| `-AllowDirty` | Allow dirty tree **only** with `-Path` |
| `-SkipDiffCheck` | Skip `git diff --check` |
| `-SkipCrlfCheck` | Skip CRLF/BOM scan |
| `-SkipSecretScan` | Skip credential-shaped scan |
| `-SelfTest` | Run internal self-test |

---

## 6. Invariants to Preserve

| Invariant | Check Method |
|-----------|--------------|
| `phase_index.md` is UTF-8, no BOM, LF-only | `verify_repo_state.ps1` |
| Exactly one final LF | `verify_repo_state.ps1` |
| No CRLF in any tracked text file | `verify_repo_state.ps1` / `git diff --check` |
| Production helper SHA256 unchanged | `Get-FileHash world-sim/scripts/sync_phase_index_sha.ps1` |
| Phase index SHA256 only changes on authorized sync | `Get-FileHash world-sim/docs/phase_index.md` |
| Triple-SHA alignment (local, remote-tracking, ls-remote) | `verify_repo_state.ps1` |
| No untracked debug/temp files in repo root | `git status --short` |
| Self-test passes for both scripts | `...ps1 -SelfTest` |

---

## 7. Escalation & Handoff

If any check fails or the correction scope is unclear:

1. **Stop** — do not guess, do not force.
2. **Document** the exact failure (command, output, expected vs actual).
3. **Report** to Sean with the minimal reproducible case.
4. **Wait** for explicit direction before proceeding.

---

## 8. Version

Runbook created: 2026-07-24
Applies to: Genesis Kernel World Sim, post-W2A validation
Next review: After W2B completion