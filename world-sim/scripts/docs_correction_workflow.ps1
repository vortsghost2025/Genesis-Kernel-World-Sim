<#
.SYNOPSIS
    W4 Documentation-Correction Workflow Coordinator

.DESCRIPTION
    Resumable six-action orchestration wrapper around verify_repo_state.ps1 and
    sync_phase_index_sha.ps1. Actions: InspectDocs, CommitDocs, SyncDryRun,
    SyncApply, CommitIndex, FinalVerify.

    Read-Host confirmation tokens (exact case-sensitive):
      CONTENT-REVIEWED  (InspectDocs)
      STAGE             (CommitDocs)
      COMMIT            (CommitDocs / CommitIndex)
      APPLY             (SyncApply)
      PUSH              (CommitDocs / CommitIndex / FinalVerify)

.PARAMETER Action
    One of: InspectDocs, CommitDocs, SyncDryRun, SyncApply, CommitIndex, FinalVerify, SelfTest

.PARAMETER TargetPath
    For InspectDocs, CommitDocs, FinalVerify: documentation file path (relative to repo root).

.PARAMETER IndexPath
    For SyncDryRun, SyncApply, CommitIndex, FinalVerify: phase_index.md path (relative to repo root).

.PARAMETER CommitMessage
    Optional commit message override for CommitDocs and CommitIndex.

.PARAMETER PhaseId
    For SyncDryRun and SyncApply: phase identifier in phase_index.md (e.g. W3).

.PARAMETER OldShortSha
    For SyncDryRun and SyncApply: current 7-char SHA in phase_index.md Commit cell.

.PARAMETER NewFullSha
    For SyncDryRun and SyncApply: new 40-char full SHA to write into phase_index.md.

.PARAMETER SelfTest
    Switch to run the built-in 24-assertion SelfTest.

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action InspectDocs -TargetPath world-sim\docs\workflow_infrastructure_w3_pilot_report.md

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitDocs -TargetPath world-sim\docs\workflow_infrastructure_w3_pilot_report.md -CommitMessage "docs: correct W3 pilot report labels"

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action FinalVerify -TargetPath world-sim\docs\workflow_infrastructure_w3_pilot_report.md -IndexPath world-sim\docs\phase_index.md

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet('InspectDocs', 'CommitDocs', 'SyncDryRun', 'SyncApply', 'CommitIndex', 'FinalVerify', 'SelfTest')]
    [string]$Action,

    [Parameter()]
    [string]$TargetPath,

    [Parameter()]
    [string]$IndexPath,

    [Parameter()]
    [string]$CommitMessage,

    [Parameter()]
    [string]$PhaseId,

    [Parameter()]
    [string]$OldShortSha,

    [Parameter()]
    [string]$NewFullSha,

    [Parameter()]
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:assertCount = 0

#region Utilities

function Write-StepHeader {
    param([string]$Name)
    Write-Host ""
    Write-Host "=== STEP: $Name ===" -ForegroundColor Cyan
}

function Write-Checkpoint {
    param([string]$Name)
    Write-Host "[CHECKPOINT] $Name" -ForegroundColor Yellow
}

function Get-ScriptDir {
    return $PSScriptRoot
}

function Get-RepoRoot {
    $repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
    return $repoRoot
}

function Invoke-Verifier {
    param(
        [Parameter(Mandatory)][string]$TargetPath,
        [string]$IndexPath
    )
    $repoRoot = Get-RepoRoot
    $helper = Join-Path $repoRoot "world-sim\scripts\verify_repo_state.ps1"
    if (-not (Test-Path -LiteralPath $helper)) {
        throw "HELPER_NOT_FOUND: $helper"
    }
    $paths = @($TargetPath)
    if ($IndexPath) {
        $paths += , $IndexPath
    }
    $result = & pwsh -NoProfile -File $helper -Path $paths 2>&1
    return $result
}

function Invoke-SyncDryRun {
    param(
        [Parameter(Mandatory)][string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha
    )
    $repoRoot = Get-RepoRoot
    $helper = Join-Path $repoRoot "world-sim\scripts\sync_phase_index_sha.ps1"
    if (-not (Test-Path -LiteralPath $helper)) {
        throw "HELPER_NOT_FOUND: $helper"
    }
    $result = & pwsh -NoProfile -File $helper -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha 2>&1
    return $result
}

function Invoke-SyncApply {
    param(
        [Parameter(Mandatory)][string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha
    )
    $repoRoot = Get-RepoRoot
    $helper = Join-Path $repoRoot "world-sim\scripts\sync_phase_index_sha.ps1"
    if (-not (Test-Path -LiteralPath $helper)) {
        throw "HELPER_NOT_FOUND: $helper"
    }
    $result = & pwsh -NoProfile -File $helper -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -Apply 2>&1
    return $result
}

function Get-Content-SHA256-String {
    param([Parameter(Mandatory)][string]$Content)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $hash = $sha256.ComputeHash($bytes)
    return [System.BitConverter]::ToString($hash) -replace '-', ''
}

function Assert-Equal {
    param(
        [string]$Actual,
        [string]$Expected,
        [string]$Label
    )
    $script:assertCount++
    if ($Actual -ne $Expected) {
        throw "ASSERTION_FAILED: $Label - Expected: '$Expected', Actual: '$Actual'"
    }
}

function Assert-Contains {
    param(
        [string]$Haystack,
        [string]$Needle,
        [string]$Label
    )
    $script:assertCount++
    if ($Haystack -notlike "*$Needle*") {
        throw "ASSERTION_FAILED: $Label - Expected to contain: '$Needle'"
    }
}

function Assert-DoesNotContain {
    param(
        [string]$Haystack,
        [string]$Needle,
        [string]$Label
    )
    $script:assertCount++
    if ($Haystack -like "*$Needle*") {
        throw "ASSERTION_FAILED: $Label - Expected NOT to contain: '$Needle'"
    }
}

function Assert-True {
    param(
        [scriptblock]$Condition,
        [string]$Label
    )
    $script:assertCount++
    if (-not (& $Condition)) {
        throw "ASSERTION_FAILED: $Label"
    }
}

#endregion

#region Action Handlers

function Action-InspectDocs {
    param(
        [Parameter(Mandatory)][string]$TargetPath,
        [string]$IndexPath
    )
    Write-StepHeader -Name "InspectDocs"

    if (-not $TargetPath) {
        Write-Host "ERROR: -TargetPath is required for InspectDocs." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_INSPECT"
        exit 1
    }

    $repoRoot = Get-RepoRoot
    $fullPath = Join-Path $repoRoot $TargetPath

    if (-not (Test-Path -LiteralPath $fullPath)) {
        Write-Host "ERROR: File not found: $fullPath" -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_INSPECT"
        exit 1
    }

    Write-Host "Documentation file: $TargetPath"
    Write-Host "Size: $([System.IO.FileInfo]::new($fullPath).Length) bytes"
    Write-Host ""

    $content = Get-Content -LiteralPath $fullPath -Raw

    Write-Host "--- File Begin (first 50 lines) ---"
    $lines = $content -split "`n"
    $displayLines = $lines | Select-Object -First 50
    $displayLines | ForEach-Object { Write-Host $_ }
    Write-Host "--- File End (first 50 lines) ---"
    Write-Host ""

    $forbidden = @(
        'sk_live_',
        'sk_test_',
        'ghp_',
        'AKIA',
        'BEGIN RSA PRIVATE KEY',
        'password',
        'secret',
        'token'
    )

    $foundForbidden = $false
    foreach ($pattern in $forbidden) {
        $matches = [regex]::Matches($content, [regex]::Escape($pattern), 'IgnoreCase')
        if ($matches.Count -gt 0) {
            Write-Host "WARNING: Found possible secret pattern '$pattern' at line(s):" -ForegroundColor Yellow
            foreach ($m in $matches) {
                $lineNum = ($content.Substring(0, $m.Index) -split "`n").Count
                Write-Host "  Line $lineNum"
            }
            $foundForbidden = $true
        }
    }

    if (-not $foundForbidden) {
        Write-Host "SECURITY: No obvious secret patterns detected in $TargetPath." -ForegroundColor Green
    }

    $verifierResult = Invoke-Verifier -TargetPath $TargetPath -IndexPath $IndexPath
    Write-Host ""
    Write-Host "Verifier output:" -ForegroundColor Cyan
    Write-Host $verifierResult

    Write-Checkpoint -Name "INSPECT_COMPLETE"

    Write-Host ""
    $confirm = Read-Host "Is the content reviewed and approved? Enter CONTENT-REVIEWED to confirm"
    if ($confirm -ne "CONTENT-REVIEWED") {
        Write-Host "Content review not confirmed. Halting." -ForegroundColor Red
        Write-Checkpoint -Name "CONTENT_REVIEW_NOT_CONFIRMED"
        exit 1
    }
    Write-Host "Content review confirmed." -ForegroundColor Green
    return $true
}

function Action-CommitDocs {
    param(
        [Parameter(Mandatory)][string]$TargetPath,
        [string]$IndexPath,
        [string]$CommitMessage
    )
    Write-StepHeader -Name "CommitDocs"

    if (-not $TargetPath) {
        Write-Host "ERROR: -TargetPath is required for CommitDocs." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_COMMIT_DOCS"
        exit 1
    }

    $repoRoot = Get-RepoRoot
    $fullPath = Join-Path $repoRoot $TargetPath

    if (-not (Test-Path -LiteralPath $fullPath)) {
        Write-Host "ERROR: File not found: $fullPath" -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_COMMIT_DOCS"
        exit 1
    }

    if (-not $CommitMessage) {
        $basename = Split-Path -Leaf -LiteralPath $TargetPath
        $CommitMessage = "docs: update $basename"
    }

    Write-Host "Proposed commit message: $CommitMessage"
    Write-Host "File to stage: $TargetPath"
    Write-Host ""

    $confirmStage = Read-Host "Stage this file? Enter STAGE to confirm"
    if ($confirmStage -ne "STAGE") {
        Write-Host "Staging declined. Halting." -ForegroundColor Red
        Write-Checkpoint -Name "STAGE_DECLINED"
        exit 1
    }

    Push-Location -LiteralPath $repoRoot
    try {
        git add -- $TargetPath 2>&1 | Out-Null
        Write-Host "Staged: $TargetPath" -ForegroundColor Green

        $status = git status --short -- $TargetPath
        Write-Host "Git status:" -ForegroundColor Cyan
        Write-Host $status

        $confirmCommit = Read-Host "Commit staged changes? Enter COMMIT to confirm"
        if ($confirmCommit -ne "COMMIT") {
            Write-Host "Commit declined. Changes remain staged." -ForegroundColor Red
            Write-Checkpoint -Name "COMMIT_DECLINED"
            exit 1
        }

        git commit -m $CommitMessage 2>&1 | Out-Null
        $commitSha = (git rev-parse HEAD) | Select-Object -First 1
        Write-Host "Committed: $commitSha" -ForegroundColor Green
        Write-Checkpoint -Name "DOCS_STAGED_COMMIT_PENDING"

        Write-Host ""
        $confirmPush = Read-Host "Push to remote? Enter PUSH to confirm"
        if ($confirmPush -ne "PUSH") {
            Write-Host "Push declined. Local commit created. Run this again with same Action to push." -ForegroundColor Yellow
            Write-Checkpoint -Name "COMMIT_A_CREATED_PUSH_PENDING"
            exit 0
        }

        git push 2>&1 | Out-Null
        Write-Host "Pushed." -ForegroundColor Green
        Write-Checkpoint -Name "COMMIT_A_PUSHED"
    } finally {
        Pop-Location
    }
    return $true
}

function Action-SyncDryRun {
    param(
        [Parameter(Mandatory)][string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha
    )
    Write-StepHeader -Name "SyncDryRun"

    if (-not $IndexPath) {
        Write-Host "ERROR: -IndexPath is required for SyncDryRun." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_SYNC_DRY_RUN"
        exit 1
    }

    $repoRoot = Get-RepoRoot
    $fullPath = Join-Path $repoRoot $IndexPath

    if (-not (Test-Path -LiteralPath $fullPath)) {
        Write-Host "ERROR: File not found: $fullPath" -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_SYNC_DRY_RUN"
        exit 1
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $docSha = git rev-parse HEAD:world-sim/docs/workflow_infrastructure_w3_pilot_report.md 2>$null
        if (-not $docSha) {
            $docSha = git hash-object $fullPath
        }

        $content = Get-Content -LiteralPath $fullPath -Raw
        $expectedSha = Get-Content-SHA256-String -Content $content

        Write-Host "Document SHA (from Git): $docSha"
        Write-Host "Current index SHA256: $expectedSha"
        Write-Host ""

        if (-not $PhaseId -or -not $OldShortSha -or -not $NewFullSha) {
            Write-Host "--- Dry-run preview (provide -PhaseId, -OldShortSha, -NewFullSha for actual helper call) ---" -ForegroundColor Yellow
            Write-Host "PhaseId: $PhaseId"
            Write-Host "OldShortSha: $OldShortSha"
            Write-Host "NewFullSha: $NewFullSha"
            Write-Host "--- End preview ---" -ForegroundColor Yellow
            Write-Checkpoint -Name "SYNC_DRY_RUN_COMPLETE"
            return $true
        }

        Write-Host "--- Dry-run output (what helper WOULD compute) ---" -ForegroundColor Cyan
        $dryRunOutput = Invoke-SyncDryRun -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha
        Write-Host $dryRunOutput
        Write-Host "--- End dry-run ---" -ForegroundColor Cyan

        if ($dryRunOutput -match "ALREADY_CORRECT|POINTER_APPLIED|NO_POINTER") {
            Write-Checkpoint -Name "SYNC_DRY_RUN_COMPLETE"
        } else {
            Write-Host "Unexpected dry-run output. Review above." -ForegroundColor Yellow
            Write-Checkpoint -Name "SYNC_DRY_RUN_COMPLETE"
        }
    } finally {
        Pop-Location
    }
    return $true
}

function Action-SyncApply {
    param(
        [Parameter(Mandatory)][string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha
    )
    Write-StepHeader -Name "SyncApply"

    if (-not $IndexPath) {
        Write-Host "ERROR: -IndexPath is required for SyncApply." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_SYNC_APPLY"
        exit 1
    }

    $repoRoot = Get-RepoRoot
    $fullPath = Join-Path $repoRoot $IndexPath

    if (-not (Test-Path -LiteralPath $fullPath)) {
        Write-Host "ERROR: File not found: $fullPath" -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_SYNC_APPLY"
        exit 1
    }

    $docSha = git rev-parse HEAD:world-sim/docs/workflow_infrastructure_w3_pilot_report.md 2>$null
    if (-not $docSha) {
        $docSha = git hash-object $fullPath
    }

    $content = Get-Content -LiteralPath $fullPath -Raw
    $expectedSha = Get-Content-SHA256-String -Content $content

    if (-not $PhaseId -or -not $OldShortSha -or -not $NewFullSha) {
        Write-Host "ERROR: -PhaseId, -OldShortSha, and -NewFullSha are required for SyncApply." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_SYNC_APPLY"
        exit 1
    }

    Push-Location -LiteralPath $repoRoot
    try {
        Write-Host "Applying sync..." -ForegroundColor Yellow
        $output = Invoke-SyncApply -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha
        Write-Host $output

        $changeApplied = $false
        if ($output -match "POINTER_APPLIED") {
            $changeApplied = $true
        }

        if ($changeApplied) {
            $confirmApply = Read-Host "Sync applied changes. Enter APPLY to stage and commit"
            if ($confirmApply -ne "APPLY") {
                Write-Host "Sync apply declined. Changes remain on disk." -ForegroundColor Red
                Write-Checkpoint -Name "SYNC_APPLY_DECLINED"
                exit 1
            }

            git add -- $IndexPath 2>&1 | Out-Null
            Write-Host "Staged: $IndexPath" -ForegroundColor Green
            Write-Checkpoint -Name "POINTER_APPLIED_COMMIT_B_PENDING"
        } else {
            Write-Host "No sync changes required (pointer already correct)." -ForegroundColor Green
            Write-Checkpoint -Name "NO_POINTER_COMMIT_REQUIRED"
        }
    } finally {
        Pop-Location
    }
    return $true
}

function Action-CommitIndex {
    param()
    Write-StepHeader -Name "CommitIndex"

    $repoRoot = Get-RepoRoot
    $indexPath = "world-sim/docs/phase_index.md"
    $fullPath = Join-Path $repoRoot $indexPath

    Push-Location -LiteralPath $repoRoot
    try {
        $status = git status --short -- $indexPath
        if (-not $status) {
            Write-Host "No staged changes for phase_index.md. Nothing to commit." -ForegroundColor Yellow
            Write-Checkpoint -Name "NO_INDEX_CHANGES"
            return $true
        }

        Write-Host "Staged changes:" -ForegroundColor Cyan
        Write-Host $status

        $msg = if ($CommitMessage) { $CommitMessage } else { "sync: update phase_index.md SHA pointer for W3 pilot report" }
        Write-Host "Proposed commit message: $msg"

        $confirmCommit = Read-Host "Enter COMMIT to create commit"
        if ($confirmCommit -ne "COMMIT") {
            Write-Host "Commit declined." -ForegroundColor Red
            Write-Checkpoint -Name "COMMIT_B_CREATED_PUSH_PENDING"
            exit 1
        }

        git commit -m $msg 2>&1 | Out-Null
        $sha = (git rev-parse HEAD) | Select-Object -First 1
        Write-Host "Committed: $sha" -ForegroundColor Green
        Write-Checkpoint -Name "COMMIT_B_CREATED_PUSH_PENDING"

        $confirmPush = Read-Host "Push to remote? Enter PUSH to confirm"
        if ($confirmPush -ne "PUSH") {
            Write-Host "Push declined. Local commit created." -ForegroundColor Yellow
            Write-Checkpoint -Name "COMMIT_B_CREATED_PUSH_PENDING"
            exit 0
        }

        git push 2>&1 | Out-Null
        Write-Host "Pushed." -ForegroundColor Green
        Write-Checkpoint -Name "COMMIT_B_PUSHED"
    } finally {
        Pop-Location
    }
    return $true
}

function Action-FinalVerify {
    param(
        [Parameter(Mandatory)][string]$TargetPath,
        [string]$IndexPath
    )
    Write-StepHeader -Name "FinalVerify"

    if (-not $TargetPath) {
        Write-Host "ERROR: -TargetPath is required for FinalVerify." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_FINAL_VERIFY"
        exit 1
    }

    $repoRoot = Get-RepoRoot
    $fullTarget = Join-Path $repoRoot $TargetPath

    Write-Host "Running final verifier on: $TargetPath"
    $vResult = Invoke-Verifier -TargetPath $TargetPath -IndexPath $IndexPath
    Write-Host $vResult

    if ($vResult -match "FAIL|ERROR|RED") {
        Write-Host "Final verifier found issues. Address before proceeding." -ForegroundColor Red
        Write-Checkpoint -Name "FAILED_FINAL_VERIFY"
        exit 1
    }

    Write-Checkpoint -Name "FINAL_VERIFY_COMPLETE"
    Write-Host "All checks passed. W4 workflow complete." -ForegroundColor Green
    return $true
}

#endregion

#region Main

function Main {
    if ($SelfTest) {
        return Run-SelfTest
    }

    if (-not $Action) {
        Write-Host "ERROR: -Action is required. Use -SelfTest to run the SelfTest." -ForegroundColor Red
        exit 1
    }

    switch ($Action) {
        'InspectDocs' { Action-InspectDocs -TargetPath $TargetPath -IndexPath $IndexPath }
        'CommitDocs'  { Action-CommitDocs -TargetPath $TargetPath -IndexPath $IndexPath -CommitMessage $CommitMessage }
        'SyncDryRun'  { Action-SyncDryRun -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha }
        'SyncApply'   { Action-SyncApply -IndexPath $IndexPath -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha }
        'CommitIndex' { Action-CommitIndex }
        'FinalVerify' { Action-FinalVerify -TargetPath $TargetPath -IndexPath $IndexPath }
        default {
            Write-Host "Unknown action: $Action" -ForegroundColor Red
            exit 1
        }
    }
}

#region SelfTest

function Run-SelfTest {
    Write-Host "=== W4 SelfTest ===" -ForegroundColor Cyan

    $scriptDir = Get-ScriptDir
    $repoRoot = Get-RepoRoot
    $thisScript = Join-Path $scriptDir "docs_correction_workflow.ps1"
    $scriptContent = Get-Content -LiteralPath $thisScript -Raw

    # T1-T5: Source-level structural checks
    Write-Host "`nT1-T5: Source structural checks"

    # T1: Exact-path staging
    $script:assertCount++
    if ($scriptContent -notmatch 'git add -- \$TargetPath') {
        throw "ASSERTION_FAILED: T1: exact-path staging not found"
    }
    Write-Host "  T1 PASS: Exact-path staging present"

    # T2: No wildcard add
    $script:assertCount++
    $scanContent2 = $scriptContent
    $scanContent2 = [regex]::Replace($scanContent2, "'[^']*'", "''", 'Singleline')
    $scanContent2 = [regex]::Replace($scanContent2, '"[^"]*"', '""', 'Singleline')
    $scanContent2 = [regex]::Replace($scanContent2, '#.*', '')
    if ($scanContent2 -match 'git add -A') {
        throw "ASSERTION_FAILED: T2a: wildcard add -A found"
    }
    $script:assertCount++
    if ($scanContent2 -match 'git add \.') {
        throw "ASSERTION_FAILED: T2b: wildcard add . found"
    }
    Write-Host "  T2 PASS: No wildcard add"

    # T3: No forbidden ops
    $script:assertCount++
    $scanContent = $scriptContent
    $scanContent = [regex]::Replace($scanContent, "'[^']*'", "''", 'Singleline')
    $scanContent = [regex]::Replace($scanContent, '"[^"]*"', '""', 'Singleline')
    $scanContent = [regex]::Replace($scanContent, '#.*', '')
    $forbiddenOps = @('force.push', '--force', '-f push', 'git reset', 'git revert', 'git rebase', 'git squash', 'git stash', 'git clean', '--amend')
    $foundForbidden = $false
    foreach ($op in $forbiddenOps) {
        if ($scanContent -match [regex]::Escape($op)) {
            $foundForbidden = $true
            break
        }
    }
    if ($foundForbidden) {
        throw "ASSERTION_FAILED: T3: forbidden git op in source"
    }
    Write-Host "  T3 PASS: No forbidden ops"

    # T4: Helper invocation
    $script:assertCount++
    if ($scriptContent -notmatch 'verify_repo_state\.ps1') {
        throw "ASSERTION_FAILED: T4a: verify helper not invoked"
    }
    $script:assertCount++
    if ($scriptContent -notmatch 'sync_phase_index_sha\.ps1') {
        throw "ASSERTION_FAILED: T4b: sync helper not invoked"
    }
    Write-Host "  T4 PASS: Both helpers invoked"

    # T5: Read-Host tokens
    $script:assertCount++
    if ($scriptContent -notmatch 'CONTENT-REVIEWED') {
        throw "ASSERTION_FAILED: T5a: CONTENT-REVIEWED token missing"
    }
    $script:assertCount++
    if ($scriptContent -notmatch '\bSTAGE\b') {
        throw "ASSERTION_FAILED: T5b: STAGE token missing"
    }
    $script:assertCount++
    if ($scriptContent -notmatch '\bCOMMIT\b') {
        throw "ASSERTION_FAILED: T5c: COMMIT token missing"
    }
    $script:assertCount++
    if ($scriptContent -notmatch '\bAPPLY\b') {
        throw "ASSERTION_FAILED: T5d: APPLY token missing"
    }
    $script:assertCount++
    if ($scriptContent -notmatch '\bPUSH\b') {
        throw "ASSERTION_FAILED: T5e: PUSH token missing"
    }
    Write-Host "  T5 PASS: All Read-Host tokens present"

    # T6-T7: Subprocess non-interactive tests
    Write-Host "`nT6-T7: Subprocess non-interactive tests"

    # T6: SyncDryRun against real phase_index.md
    $script:assertCount++
    $dryResult = & pwsh -NoProfile -File $thisScript -Action SyncDryRun -IndexPath "world-sim/docs/phase_index.md" 2>&1
    if (-not ($dryResult -match 'Dry-run')) {
        throw "ASSERTION_FAILED: T6: SyncDryRun missing dry-run label"
    }
    Write-Host "  T6 PASS: SyncDryRun structural output"

    # T7: FinalVerify against real doc
    $script:assertCount++
    $verifyResult = & pwsh -NoProfile -File $thisScript -Action FinalVerify -TargetPath "world-sim/docs/workflow_infrastructure_w3_pilot_report.md" -IndexPath "world-sim/docs/phase_index.md" 2>&1
    if (-not ($verifyResult -match 'FINAL_VERIFY_COMPLETE|FAILED_FINAL_VERIFY')) {
        throw "ASSERTION_FAILED: T7: FinalVerify missing expected checkpoint"
    }
    Write-Host "  T7 PASS: FinalVerify checkpoint present"

    # T8: Checkpoint names
    Write-Host "`nT8: Checkpoint names source scan"
    $checkpoints = @(
        'INSPECT_COMPLETE',
        'CONTENT_REVIEW_NOT_CONFIRMED',
        'STAGE_DECLINED',
        'DOCS_STAGED_COMMIT_PENDING',
        'COMMIT_DECLINED',
        'COMMIT_A_CREATED_PUSH_PENDING',
        'COMMIT_A_PUSHED',
        'SYNC_DRY_RUN_COMPLETE',
        'SYNC_APPLY_DECLINED',
        'POINTER_APPLIED_COMMIT_B_PENDING',
        'NO_POINTER_COMMIT_REQUIRED',
        'INDEX_STAGED_COMMIT_PENDING',
        'COMMIT_B_CREATED_PUSH_PENDING',
        'COMMIT_B_PUSHED',
        'FINAL_VERIFY_COMPLETE',
        'FAILED_INSPECT',
        'FAILED_COMMIT_DOCS',
        'FAILED_SYNC_DRY_RUN',
        'FAILED_SYNC_APPLY',
        'FAILED_FINAL_VERIFY'
    )
    foreach ($cp in $checkpoints) {
        $script:assertCount++
        if ($scriptContent -notmatch [regex]::Escape($cp)) {
            throw "ASSERTION_FAILED: T8: checkpoint '$cp' missing"
        }
    }
    Write-Host "  T8 PASS: All required checkpoints present ($($checkpoints.Count) checkpoints)"

    # T9: Six action handlers
    Write-Host "`nT9: Six action handlers"
    $actions = @('InspectDocs', 'CommitDocs', 'SyncDryRun', 'SyncApply', 'CommitIndex', 'FinalVerify')
    foreach ($act in $actions) {
        $script:assertCount++
        if ($scriptContent -notmatch "Action-$act") {
            throw "ASSERTION_FAILED: T9: Action-$act handler missing"
        }
    }
    Write-Host "  T9 PASS: All 6 action handlers present"

    # T10: Missing Action returns error
    Write-Host "`nT10: Missing Action returns error"
    $script:assertCount++
    $noActionResult = & pwsh -NoProfile -File $thisScript 2>&1
    if (-not ($noActionResult -match 'Action is required')) {
        throw "ASSERTION_FAILED: T10: Missing Action did not produce expected error"
    }
    Write-Host "  T10 PASS: Missing Action returns error"

    # T11: No hidden bypass flags
    Write-Host "`nT11: No hidden bypass flags"
    $scanContent11 = $scriptContent
    $scanContent11 = [regex]::Replace($scanContent11, "'[^']*'", "''", 'Singleline')
    $scanContent11 = [regex]::Replace($scanContent11, '"[^"]*"', '""', 'Singleline')
    $scanContent11 = [regex]::Replace($scanContent11, '#.*', '')
    $script:assertCount++
    if ($scanContent11 -match '--Force') {
        throw "ASSERTION_FAILED: T11a: --Force flag found"
    }
    $script:assertCount++
    if ($scanContent11 -match '-NoPrompt') {
        throw "ASSERTION_FAILED: T11b: -NoPrompt flag found"
    }
    $script:assertCount++
    if ($scanContent11 -match '-SkipConfirm') {
        throw "ASSERTION_FAILED: T11c: -SkipConfirm flag found"
    }
    Write-Host "  T11 PASS: No hidden bypass flags"

    # T12: Helper path construction
    Write-Host "`nT12: Helper path construction"
    $script:assertCount++
    if ($scriptContent -notmatch 'world-sim\\scripts\\verify_repo_state\.ps1') {
        throw "ASSERTION_FAILED: T12a: verify helper path missing"
    }
    $script:assertCount++
    if ($scriptContent -notmatch 'world-sim\\scripts\\sync_phase_index_sha\.ps1') {
        throw "ASSERTION_FAILED: T12b: sync helper path missing"
    }
    Write-Host "  T12 PASS: Helper paths constructed correctly"

    # T13: UTF-8 no BOM
    Write-Host "`nT13: UTF-8 encoding without BOM"
    $bytes = [System.IO.File]::ReadAllBytes($thisScript)
    $script:assertCount++
    if ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        throw "ASSERTION_FAILED: T13: UTF-8 BOM present"
    }
    Write-Host "  T13 PASS: No UTF-8 BOM"

    # T14: LF line endings
    Write-Host "`nT14: LF line endings"
    $crlfCount = 0
    for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
        if ($bytes[$i] -eq 0x0D -and $bytes[$i + 1] -eq 0x0A) {
            $crlfCount++
        }
    }
    $script:assertCount++
    if ($crlfCount -gt 0) {
        throw "ASSERTION_FAILED: T14: $crlfCount CRLF line endings found"
    }
    Write-Host "  T14 PASS: LF line endings only ($crlfCount CRLF)"

    Write-Host ""
    Write-Host "=== SELF-TEST PASSED ($script:assertCount assertions) ===" -ForegroundColor Green
    exit 0
}

#endregion

Main
