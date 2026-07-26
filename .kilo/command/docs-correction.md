---
description: Run the proven W4 documentation-correction coordinator safely with triple-SHA gates, human confirmation boundaries, exact-path staging, optional phase-pointer synchronization, and final verification.
---

# Docs Correction Command

## Purpose

Use the existing coordinator for an explicitly authorized documentation or
instruction-file correction. This command does not replace:

- `world-sim/scripts/docs_correction_workflow.ps1`
- `world-sim/docs/docs_correction_runbook.md`
- `world-sim/scripts/verify_repo_state.ps1`
- `world-sim/scripts/sync_phase_index_sha.ps1`

Do not use this command for runtime, application, provider, model, daemon,
scheduler, network, container, Docker, `world-sim/data`, 10II, or first-pair
work.

## Boundaries

- Use `pwsh -NoProfile`.
- Begin from a clean `master` branch with local HEAD, `origin/master`, and
  `git ls-remote origin refs/heads/master` aligned.
- Resolve the current full HEAD before every action requiring
  `-ExpectedSha`.
- Stop after every RED result and preserve the complete failure report.
- Do not pre-answer or bypass a `Read-Host` confirmation.
- Use `PushMode Manual` unless prompted push was explicitly authorized.
- Never force-push, amend, reset, revert, rebase, squash, stash, clean,
  `git add -A`, or `git add .`.

## Procedure

### 1. Resolve and verify the current checkpoint

```powershell
Set-Location 'S:\Genesis Kernel World Sim'
$headSha = (git rev-parse HEAD).Trim()

git status -sb
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/master
git ls-remote origin refs/heads/master

pwsh -NoProfile -File `
  world-sim/scripts/verify_repo_state.ps1 `
  -ExpectedSha $headSha
```

Require a clean tree and FINAL STATE: GREEN.

### 2. Make only the authorized edit

Change exactly the named documentation or instruction path. Do not edit
`world-sim/docs/phase_index.md` in Commit A.

For multiple paths inside PowerShell, use a real array:

```powershell
$paths = @(
  'path/one.md',
  'path/two.md'
)
```

### 3. Inspect the correction

```powershell
& '.\world-sim\scripts\docs_correction_workflow.ps1' `
  -Action InspectDocs `
  -Path $paths `
  -ExpectedSha $headSha
```

Require `INSPECT_COMPLETE`. This proves mechanical checks only.

### 4. Review the content

Read the complete diff and every changed line. Confirm that the correction
is accurate and that only the authorized paths changed.

### 5. Create Commit A

```powershell
& '.\world-sim\scripts\docs_correction_workflow.ps1' `
  -Action CommitDocs `
  -Path $paths `
  -CommitMessage '<authorized message>' `
  -ExpectedSha $headSha `
  -PushMode Manual
```

Enter the confirmation tokens only after reviewing their named boundary:

1. `CONTENT-REVIEWED`
2. `STAGE`
3. `COMMIT`

After `COMMIT_A_CREATED_PUSH_PENDING`, run only the exact ordinary push
reported by the coordinator, fetch, and resolve the new full HEAD.

### 6. Decide whether Commit B is required

Do not synchronize `phase_index.md` for workflow infrastructure, unrelated
documentation, an already-correct pointer, a missing phase row, or a new
phase.

When no pointer update is required, skip to FinalVerify.

When one existing authorized phase row must point to Commit A, run in order:

1. `SyncDryRun`.
   Review its before/after row and byte-identity proof.
2. `SyncApply`, entering exact `APPLY`.
   Confirm `phase_index.md` is the sole unstaged path and nothing is staged.
3. `CommitIndex`, entering `STAGE` and `COMMIT`.
   After `COMMIT_B_CREATED_PUSH_PENDING`, perform only the exact ordinary
   push reported by the coordinator.
4. Resolve the new full HEAD. Commit B is now the required `-ExpectedSha`;
   the phase row correctly continues to point to Commit A.

Use the actual parameters reported by the coordinator and the fallback
runbook. Do not invent a phase ID or SHA.

### 7. Final verification

```powershell
$headSha = (git rev-parse HEAD).Trim()

& '.\world-sim\scripts\docs_correction_workflow.ps1' `
  -Action FinalVerify `
  -Path $paths `
  -ExpectedSha $headSha
```

When Commit B exists, include `world-sim/docs/phase_index.md` in `$paths`.

Require:

- `FINAL_VERIFY_COMPLETE`
- `FINAL STATE: GREEN`
- clean working tree
- local HEAD = `origin/master` = `git ls-remote`
- coordinator, sync-helper, and verifier self-tests pass

## Failure Handling

On RED, STOP. Preserve the structured failure report and open:

- `world-sim/docs/docs_correction_runbook.md`

Do not auto-recover or continue to the next action.

## Standing Conditions

Gate-7 remains closed. 10CP remains sole world-state/ledger writer. 10HD
remains named-only. `FIRST_PAIR_CREATION_AUTHORIZED = False`. Workflow
infrastructure is not 10II.
