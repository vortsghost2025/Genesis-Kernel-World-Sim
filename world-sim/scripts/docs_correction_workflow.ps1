#requires -Version 7.0

<#
.SYNOPSIS
    W4 Documentation-Correction Workflow Coordinator

.DESCRIPTION
    Resumable six-action orchestration wrapper around verify_repo_state.ps1 and
    sync_phase_index_sha.ps1. Actions: InspectDocs, CommitDocs, SyncDryRun,
    SyncApply, CommitIndex, FinalVerify.

    Confirmation tokens (exact case-sensitive, supplied by internal provider):
      CONTENT-REVIEWED  (CommitDocs)
      STAGE             (CommitDocs / CommitIndex)
      COMMIT            (CommitDocs / CommitIndex)
      APPLY             (SyncApply)
      PUSH              (CommitDocs / CommitIndex)

.PARAMETER Action
    One of: InspectDocs, CommitDocs, SyncDryRun, SyncApply, CommitIndex, FinalVerify

.PARAMETER Path
    One or more exact authorized repository paths.

.PARAMETER ExpectedSha
    Lowercase 40-character hexadecimal SHA required for every non-SelfTest action.

.PARAMETER CommitMessage
    Explicit commit message required for CommitDocs and CommitIndex.

.PARAMETER PhaseId
    Phase identifier for SyncDryRun, SyncApply.

.PARAMETER OldShortSha
    Current 7-char SHA for SyncDryRun, SyncApply.

.PARAMETER NewFullSha
    New 40-char full SHA for SyncDryRun, SyncApply.

.PARAMETER PushMode
    Manual (default) or Prompted.

.PARAMETER Remote
    Git remote name. Default: origin

.PARAMETER Branch
    Git branch name. Default: master

.PARAMETER SelfTest
    Switch to run the built-in 24-assertion behavioural SelfTest.

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action InspectDocs -Path world-sim/docs/workflow_infrastructure_w3_pilot_report.md -ExpectedSha 6b13b5372d054947587afa4a8630256d02c31563

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitDocs -Path world-sim/docs/workflow_infrastructure_w3_pilot_report.md -CommitMessage "docs: correct W3 pilot report labels" -ExpectedSha 6b13b5372d054947587afa4a8630256d02c31563 -PushMode Manual

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -Action SyncDryRun -PhaseId W3 -OldShortSha abcdef1 -NewFullSha 1234567890123456789012345678901234567890 -ExpectedSha 6b13b5372d054947587afa4a8630256d02c31563

.EXAMPLE
    .\world-sim\scripts\docs_correction_workflow.ps1 -SelfTest
#>

[CmdletBinding()]
param(
    [ValidateSet(
        'InspectDocs',
        'CommitDocs',
        'SyncDryRun',
        'SyncApply',
        'CommitIndex',
        'FinalVerify'
    )]
    [string]$Action = 'InspectDocs',

    [string[]]$Path,
    [string]$ExpectedSha,
    [string]$CommitMessage,
    [string]$PhaseId,
    [string]$OldShortSha,
    [string]$NewFullSha,

    [ValidateSet('Manual', 'Prompted')]
    [string]$PushMode = 'Manual',

    [string]$Remote = 'origin',
    [string]$Branch = 'master',
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

$script:ExitCodeGreen = 0
$script:ExitCodeRed = 2

$script:AcceptedTokens = @(
    'CONTENT-REVIEWED',
    'STAGE',
    'COMMIT',
    'APPLY',
    'PUSH'
)

$script:RequiredCheckpoints = @(
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
    'FINAL_VERIFY_COMPLETE'
)

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

function Write-StepHeader {
    param([string]$Name)
    Write-Host ""
    Write-Host "=== STEP: $Name ===" -ForegroundColor Cyan
}

function Write-Checkpoint {
    param([string]$Name)
    Write-Host "[CHECKPOINT] $Name" -ForegroundColor Yellow
}

function Get-RepoRoot {
    try {
        $root = & git rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($root)) {
            return $null
        }
        return $root
    } catch {
        return $null
    }
}

function Get-HeadSha {
    param([string]$RepoRoot)
    Push-Location -LiteralPath $RepoRoot
    try {
        $sha = (& git rev-parse HEAD) | Select-Object -First 1
        return $sha
    } finally {
        Pop-Location
    }
}

function Get-RemoteTrackingSha {
    param([string]$RepoRoot, [string]$Remote, [string]$Branch)
    Push-Location -LiteralPath $RepoRoot
    try {
        $ref = "$Remote/$Branch"
        $sha = (& git rev-parse $ref 2>&1) | Select-Object -First 1
        if ($LASTEXITCODE -ne 0) { return $null }
        return $sha
    } finally {
        Pop-Location
    }
}

function Get-LsRemoteSha {
    param([string]$RepoRoot, [string]$Remote, [string]$Branch)
    Push-Location -LiteralPath $RepoRoot
    try {
        $output = & git ls-remote $Remote "refs/heads/$Branch" 2>&1
        if ($LASTEXITCODE -ne 0) { return $null }
        $lines = @($output | Where-Object { $_ -match '^[0-9a-f]{40}\s' })
        if ($lines.Count -ne 1) { return $null }
        return ($lines[0] -split '\s')[0]
    } finally {
        Pop-Location
    }
}

function Get-PorcelainSummary {
    param([string]$RepoRoot)
    Push-Location -LiteralPath $RepoRoot
    try {
        $output = & git status --porcelain=v1 2>&1
        $lines = [System.Collections.Generic.List[string]]::new()
        foreach ($line in $output) {
            if (-not [string]::IsNullOrWhiteSpace($line)) {
                $lines.Add($line)
            }
        }
        return $lines.ToArray()
    } finally {
        Pop-Location
    }
}

function Get-UnstagedPaths {
    param([string]$RepoRoot)
    $summary = Get-PorcelainSummary -RepoRoot $RepoRoot
    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $summary) {
        $status = $line.Substring(0, 2)
        if ($status -notmatch '^[ MADRCU?][ MADRCU?]$') { continue }
        if ($status[0] -eq ' ' -and $status[1] -ne ' ') {
            $path = $line.Substring(3).Trim()
            if ($path -and $path -notlike '-> *') {
                $paths.Add($path)
            }
        }
    }
    return ,$paths.ToArray()
}

function Get-StagedPaths {
    param([string]$RepoRoot)
    $summary = Get-PorcelainSummary -RepoRoot $RepoRoot
    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $summary) {
        $status = $line.Substring(0, 2)
        if ($status -notmatch '^[ MADRCU?][ MADRCU?]$') { continue }
        if ($status[0] -ne ' ' -and $status[1] -eq ' ') {
            $path = $line.Substring(3).Trim()
            if ($path -and $path -notlike '-> *') {
                $paths.Add($path)
            }
        }
    }
    return ,$paths.ToArray()
}

function Test-LowerHex40 {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    if ($Value.Length -ne 40) { return $false }
    return ($Value -match '^[0-9a-f]{40}$')
}

function Test-PathAuthorized {
    param(
        [string]$Candidate,
        [string[]]$Authorized
    )
    foreach ($auth in $Authorized) {
        $candidateNorm = ($Candidate -replace '\\', '/').TrimStart('./')
        $authNorm = ($auth -replace '\\', '/').TrimStart('./')
        if ($candidateNorm -eq $authNorm) { return $true }
        if ($candidateNorm.StartsWith($authNorm + '/', [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Invoke-Verifier {
    param(
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [string[]]$Path,
        [switch]$AllowDirty
    )
    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return $script:ExitCodeRed
    }
    $helper = Join-Path $PSScriptRoot 'verify_repo_state.ps1'
    if (-not (Test-Path -LiteralPath $helper)) {
        Write-Host "ERROR: Helper not found: $helper" -ForegroundColor Red
        return $script:ExitCodeRed
    }
    $allowDirtyArg = if ($AllowDirty) { '-AllowDirty' } else { '' }
    # Serialize Path array to Base64 JSON to preserve array structure across process boundary
    $pathJson = ''
    if ($Path.Count -gt 0) {
        $pathJson = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes(($Path | ConvertTo-Json -Compress)))
    }
    $argList = @('-NoProfile','-File',$helper,'-ExpectedSha',$ExpectedSha,'-Remote',$Remote,'-Branch',$Branch)
    if ($pathJson) {
        $argList += '-PathJson'
        $argList += $pathJson
    }
    if ($AllowDirty) { $argList += '-AllowDirty' }
    & pwsh @argList 2>&1 | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    return $exitCode
}

function Invoke-SyncHelper {
    param(
        [string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha,
        [switch]$Apply
    )
    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return $script:ExitCodeRed
    }
    $helper = Join-Path $PSScriptRoot 'sync_phase_index_sha.ps1'
    if (-not (Test-Path -LiteralPath $helper)) {
        Write-Host "ERROR: Helper not found: $helper" -ForegroundColor Red
        return $script:ExitCodeRed
    }
    $argList = @('-NoProfile','-File',$helper,'-IndexPath',$IndexPath,'-PhaseId',$PhaseId,'-OldShortSha',$OldShortSha,'-NewFullSha',$NewFullSha)
    if ($Apply) { $argList += '-Apply' }
    & pwsh @argList 2>&1 | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    return $exitCode
}

function Invoke-RepoStateGate {
    param(
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [string[]]$AuthorizedDirtyPaths
    )
    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $null; RemoteTracking = $null; LsRemote = $null; Porcelain = @() }
    }

    $currentBranch = (& git rev-parse --abbrev-ref HEAD) | Select-Object -First 1
    if ($currentBranch -ne $Branch) {
        Write-Host "ERROR: Branch mismatch: expected $Branch, found $currentBranch" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $null; RemoteTracking = $null; LsRemote = $null; Porcelain = @() }
    }

    $localHead = (& git rev-parse HEAD) | Select-Object -First 1
    $remoteTracking = Get-RemoteTrackingSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
    $lsRemote = Get-LsRemoteSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
    $porcelain = Get-PorcelainSummary -RepoRoot $repoRoot

    Write-Host "Local HEAD:    $localHead"
    Write-Host "Tracking SHA:  $remoteTracking"
    Write-Host "Ls-remote SHA: $lsRemote"

    if (-not (Test-LowerHex40 -Value $ExpectedSha)) {
        Write-Host "ERROR: ExpectedSha is not a valid 40-char lowercase hex SHA" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }

    if ($localHead.ToLowerInvariant() -ne $ExpectedSha.ToLowerInvariant()) {
        Write-Host "ERROR: Local HEAD does not match ExpectedSha" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }

    if (-not $remoteTracking) {
        Write-Host "ERROR: Remote tracking ref $Remote/$Branch not found" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }
    if ($remoteTracking.ToLowerInvariant() -ne $ExpectedSha.ToLowerInvariant()) {
        Write-Host "ERROR: Remote tracking SHA does not match ExpectedSha" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }

    if (-not $lsRemote) {
        Write-Host "ERROR: ls-remote returned no unique master row" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }
    if ($lsRemote.ToLowerInvariant() -ne $ExpectedSha.ToLowerInvariant()) {
        Write-Host "ERROR: ls-remote SHA does not match ExpectedSha" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }

    $unauthorized = @()
    foreach ($p in $porcelain) {
        $filePath = $p.Substring(3).Trim()
        if ($filePath -like '-> *') {
            $filePath = ($filePath -split ' -> ', 2)[-1]
        }
        if ($AuthorizedDirtyPaths -and $AuthorizedDirtyPaths.Count -gt 0) {
            if (-not (Test-PathAuthorized -Candidate $filePath -Authorized $AuthorizedDirtyPaths)) {
                $unauthorized += $filePath
            }
        } else {
            $unauthorized += $filePath
        }
    }

    if ($unauthorized.Count -gt 0) {
        Write-Host "ERROR: Unauthorized dirty paths: $($unauthorized -join ', ')" -ForegroundColor Red
        return [PSCustomObject]@{ ExitCode = $script:ExitCodeRed; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
    }

    return [PSCustomObject]@{ ExitCode = $script:ExitCodeGreen; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelain }
}

function New-ActionResult {
    param(
        [int]$ExitCode,
        [string]$Action,
        [string]$Checkpoint,
        [string]$CompletedStep,
        [string]$ResumeCommand
    )
    return [PSCustomObject]@{
        ExitCode      = $ExitCode
        Action        = $Action
        Checkpoint    = $Checkpoint
        CompletedStep = $CompletedStep
        ResumeCommand = $ResumeCommand
    }
}

function Write-FailureReport {
    param(
        [string]$CompletedStep,
        [string]$CurrentHead,
        [string]$TrackingSha,
        [string]$LsRemoteSha,
        [string[]]$StagedPaths,
        [string[]]$UnstagedPaths,
        [string]$Checkpoint,
        [string]$ResumeCommand,
        [string]$ManualFallback
    )
    Write-Host ""
    Write-Host "=== FAILURE REPORT ===" -ForegroundColor Red
    Write-Host "CompletedStep: $CompletedStep"
    Write-Host "CurrentHead:   $CurrentHead"
    Write-Host "TrackingSha:   $TrackingSha"
    Write-Host "LsRemoteSha:   $LsRemoteSha"
    Write-Host "StagedPaths:   $($StagedPaths -join ', ')"
    Write-Host "UnstagedPaths: $($UnstagedPaths -join ', ')"
    Write-Host "Checkpoint:    $Checkpoint"
    Write-Host "ResumeCommand: $ResumeCommand"
    Write-Host "ManualFallback: $ManualFallback"
}

# ---------------------------------------------------------------------------
# Action Handlers
# ---------------------------------------------------------------------------

function Action-InspectDocs {
    param(
        [string[]]$Path,
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "InspectDocs"

    if (-not $Path -or $Path.Count -eq 0) {
        Write-Host "ERROR: -Path is required for InspectDocs." -ForegroundColor Red
        $repoRoot = Get-RepoRoot
        $head = if ($repoRoot) { Get-HeadSha -RepoRoot $repoRoot } else { 'unavailable' }
        $tracking = if ($repoRoot) { Get-RemoteTrackingSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch } else { 'unavailable' }
        $lsr = if ($repoRoot) { Get-LsRemoteSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch } else { 'unavailable' }
        $staged = if ($repoRoot) { Get-StagedPaths -RepoRoot $repoRoot } else { @() }
        $unstaged = if ($repoRoot) { Get-UnstagedPaths -RepoRoot $repoRoot } else { @() }
        Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $head -TrackingSha $tracking -LsRemoteSha $lsr -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_INSPECT' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'InspectDocs' -Checkpoint 'FAILED_INSPECT' -CompletedStep 'InspectDocs' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'InspectDocs' -Checkpoint 'FAILED_INSPECT' -CompletedStep 'InspectDocs' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths $Path
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_INSPECT' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'InspectDocs' -Checkpoint 'FAILED_INSPECT' -CompletedStep 'InspectDocs' -ResumeCommand ''
    }

    $verifyExit = Invoke-Verifier -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -Path $Path -AllowDirty
    if ($verifyExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_INSPECT' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'InspectDocs' -Checkpoint 'FAILED_INSPECT' -CompletedStep 'InspectDocs' -ResumeCommand ''
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $diffCheck = & git diff --check 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: git diff --check reported issues" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_INSPECT' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'InspectDocs' -Checkpoint 'FAILED_INSPECT' -CompletedStep 'InspectDocs' -ResumeCommand ''
        }

        $unstagedList = @(Get-UnstagedPaths -RepoRoot $repoRoot)
        $stagedList = @(Get-StagedPaths -RepoRoot $repoRoot)

        Write-Host "Unstaged paths:"
        if ($unstagedList.Count -eq 0) {
            Write-Host "  (none)"
        } else {
            foreach ($p in $unstagedList) { Write-Host "  $p" }
        }
        Write-Host "Staged paths:"
        if ($stagedList.Count -eq 0) {
            Write-Host "  (none)"
        } else {
            foreach ($p in $stagedList) { Write-Host "  $p" }
        }

        Write-Host ""
        Write-Host "Numstat:"
        $numstat = & git diff --numstat 2>&1
        $numstat | ForEach-Object { Write-Host "  $_" }

        Write-Host ""
        Write-Host "MECHANICAL CHECKS ONLY — CONTENT REVIEW NOT VERIFIED."
        Write-Checkpoint -Name "INSPECT_COMPLETE"

        $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitDocs -Path $($Path -join ',') -ExpectedSha $ExpectedSha -CommitMessage '<message>'"
        Write-Host ""
        Write-Host "Resume with: $resume"

        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'InspectDocs' -Checkpoint 'INSPECT_COMPLETE' -CompletedStep 'InspectDocs' -ResumeCommand $resume
    } finally {
        Pop-Location
    }
}

function Action-CommitDocs {
    param(
        [string[]]$Path,
        [string]$ExpectedSha,
        [string]$CommitMessage,
        [string]$PushMode,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "CommitDocs"

    if (-not $Path -or $Path.Count -eq 0) {
        Write-Host "ERROR: -Path is required for CommitDocs." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
    }

    if (-not $CommitMessage) {
        Write-Host "ERROR: -CommitMessage is required for CommitDocs." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths $Path
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_DOCS' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
    }

    $inspectResult = Action-InspectDocs -Path $Path -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
    if ($inspectResult.ExitCode -ne $script:ExitCodeGreen) {
        return $inspectResult
    }

    $confirm1 = & $ConfirmProvider -PromptText "Confirm content review. Enter CONTENT-REVIEWED to proceed."
    if ($confirm1 -ne 'CONTENT-REVIEWED') {
        Write-Host "Content review not confirmed. Halting." -ForegroundColor Red
        Write-Checkpoint -Name "CONTENT_REVIEW_NOT_CONFIRMED"
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'CONTENT_REVIEW_NOT_CONFIRMED' -ResumeCommand $inspectResult.ResumeCommand -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'CONTENT_REVIEW_NOT_CONFIRMED' -CompletedStep 'InspectDocs' -ResumeCommand $inspectResult.ResumeCommand
    }

    $confirm2 = & $ConfirmProvider -PromptText "Stage exact paths? Enter STAGE to confirm."
    if ($confirm2 -ne 'STAGE') {
        Write-Host "Staging declined. Halting." -ForegroundColor Red
        Write-Checkpoint -Name "STAGE_DECLINED"
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'InspectDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'STAGE_DECLINED' -ResumeCommand $inspectResult.ResumeCommand -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'STAGE_DECLINED' -CompletedStep 'InspectDocs' -ResumeCommand $inspectResult.ResumeCommand
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $existingStaged = Get-StagedPaths -RepoRoot $repoRoot
        if ($existingStaged.Count -gt 0) {
            Write-Host "ERROR: Unauthorized paths already staged: $($existingStaged -join ', ')" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'STAGE_DECLINED' -ResumeCommand $inspectResult.ResumeCommand -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'STAGE_DECLINED' -CompletedStep 'CommitDocs' -ResumeCommand $inspectResult.ResumeCommand
        }

        $dirtyUnstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        $authorizedDirty = @()
        $unauthorizedDirty = @()
        foreach ($p in $dirtyUnstaged) {
            if (Test-PathAuthorized -Candidate $p -Authorized $Path) {
                $authorizedDirty += $p
            } else {
                $unauthorizedDirty += $p
            }
        }
        if ($authorizedDirty.Count -ne $Path.Count -or $unauthorizedDirty.Count -gt 0) {
            Write-Host "ERROR: Dirty paths do not match exactly." -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'STAGE_DECLINED' -ResumeCommand $inspectResult.ResumeCommand -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'STAGE_DECLINED' -CompletedStep 'CommitDocs' -ResumeCommand $inspectResult.ResumeCommand
        }

        $pathArgs = @()
        foreach ($p in $Path) { $pathArgs += $p }
        & git add -- $pathArgs 2>&1 | Out-Null

        $stagedAfter = Get-StagedPaths -RepoRoot $repoRoot
        $unstagedAfter = Get-UnstagedPaths -RepoRoot $repoRoot

        $diffCheck = & git diff --cached --check 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: git diff --cached --check reported issues" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_DOCS' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
        }

        $expectedSet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($p in $Path) { $null = $expectedSet.Add($p) }
        $actualSet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($p in $stagedAfter) { $null = $actualSet.Add($p) }

        if ($expectedSet.Count -ne $actualSet.Count -or -not $expectedSet.SetEquals($actualSet)) {
            Write-Host "ERROR: Staged paths do not match exactly." -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_DOCS' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
        }

        Write-Host "Numstat (cached):"
        $numstat = & git diff --cached --numstat 2>&1
        $numstat | ForEach-Object { Write-Host "  $_" }

        $confirm3 = & $ConfirmProvider -PromptText "Commit staged changes? Enter COMMIT to confirm."
        if ($confirm3 -ne 'COMMIT') {
            Write-Host "Commit declined. Changes remain staged." -ForegroundColor Red
            Write-Checkpoint -Name "COMMIT_DECLINED"
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitDocs -Path $($Path -join ',') -ExpectedSha $ExpectedSha -CommitMessage '$CommitMessage'"
            Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'COMMIT_DECLINED' -ResumeCommand $resume -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'COMMIT_DECLINED' -CompletedStep 'CommitDocs' -ResumeCommand $resume
        }

        & git commit -m $CommitMessage 2>&1 | Out-Null
        $commitSha = (& git rev-parse HEAD) | Select-Object -First 1
        Write-Host "Committed: $commitSha" -ForegroundColor Green
        Write-Checkpoint -Name "DOCS_STAGED_COMMIT_PENDING"

        if ($PushMode -eq 'Prompted') {
            $confirm4 = & $ConfirmProvider -PromptText "Push to remote? Enter PUSH to confirm."
            if ($confirm4 -eq 'PUSH') {
                & git push $Remote $Branch 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "ERROR: Push failed" -ForegroundColor Red
                    $staged = Get-StagedPaths -RepoRoot $repoRoot
                    $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                    Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_DOCS' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                    return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
                }
                & git fetch $Remote $Branch 2>&1 | Out-Null
                $newHead = (& git rev-parse HEAD) | Select-Object -First 1
                $newTracking = Get-RemoteTrackingSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
                $newLsRemote = Get-LsRemoteSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
                if ($newHead -ne $newTracking -or $newHead -ne $newLsRemote) {
                    Write-Host "ERROR: Post-push alignment failed" -ForegroundColor Red
                    $staged = Get-StagedPaths -RepoRoot $repoRoot
                    $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                    Write-FailureReport -CompletedStep 'CommitDocs' -CurrentHead $newHead -TrackingSha $newTracking -LsRemoteSha $newLsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_DOCS' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                    return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitDocs' -Checkpoint 'FAILED_COMMIT_DOCS' -CompletedStep 'CommitDocs' -ResumeCommand ''
                }
                Write-Host "Pushed and triple-aligned." -ForegroundColor Green
                Write-Checkpoint -Name "COMMIT_A_PUSHED"
                $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action SyncDryRun -PhaseId <PhaseId> -OldShortSha <OldShortSha> -NewFullSha $commitSha -ExpectedSha $commitSha"
                return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'COMMIT_A_PUSHED' -CompletedStep 'CommitDocs' -ResumeCommand $resume
            } else {
                Write-Host "Push declined. Local commit created." -ForegroundColor Yellow
                Write-Checkpoint -Name "COMMIT_A_CREATED_PUSH_PENDING"
                $resume = "git push $Remote $Branch"
                return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'COMMIT_A_CREATED_PUSH_PENDING' -CompletedStep 'CommitDocs' -ResumeCommand $resume
            }
        } else {
            Write-Host "Manual PushMode: push not performed." -ForegroundColor Yellow
            Write-Checkpoint -Name "COMMIT_A_CREATED_PUSH_PENDING"
            $resume = "git push $Remote $Branch"
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitDocs' -Checkpoint 'COMMIT_A_CREATED_PUSH_PENDING' -CompletedStep 'CommitDocs' -ResumeCommand $resume
        }
    } finally {
        Pop-Location
    }
}

function Action-SyncDryRun {
    param(
        [string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha,
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "SyncDryRun"

    if (-not $PhaseId -or -not $OldShortSha -or -not $NewFullSha) {
        Write-Host "ERROR: -PhaseId, -OldShortSha, and -NewFullSha are required for SyncDryRun." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths @()
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncDryRun' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_DRY_RUN' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    $resolvedIndex = $IndexPath
    if (-not [System.IO.Path]::IsPathRooted($resolvedIndex)) {
        $resolvedIndex = Join-Path $repoRoot $resolvedIndex
    }
    $resolvedIndex = [System.IO.Path]::GetFullPath($resolvedIndex)
    if (-not (Test-Path -LiteralPath $resolvedIndex -PathType Leaf)) {
        Write-Host "ERROR: IndexPath not found: $IndexPath" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncDryRun' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_DRY_RUN' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $beforeBytes = [System.IO.File]::ReadAllBytes($resolvedIndex)
        $beforeHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($beforeBytes)).Replace('-', '').ToLowerInvariant()
        Write-Host "Phase index before-hash: $beforeHash"
    } finally {
        Pop-Location
    }

    $syncExit = Invoke-SyncHelper -IndexPath $resolvedIndex -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha
    if ($syncExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncDryRun' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_DRY_RUN' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $afterBytes = [System.IO.File]::ReadAllBytes($resolvedIndex)
        $afterHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($afterBytes)).Replace('-', '').ToLowerInvariant()
        Write-Host "Phase index after-hash:  $afterHash"
        if ($beforeHash -ne $afterHash) {
            Write-Host "ERROR: Dry-run changed file bytes" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncDryRun' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_DRY_RUN' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncDryRun' -Checkpoint 'FAILED_SYNC_DRY_RUN' -CompletedStep 'SyncDryRun' -ResumeCommand ''
        }
        Write-Host "Byte identity proven: before-hash == after-hash"
    } finally {
        Pop-Location
    }

    Write-Host "BEFORE row: see helper output above"
    Write-Host "AFTER row:  see helper output above"
    Write-Host "OLD COMMIT: $OldShortSha"
    Write-Host "NEW COMMIT: $NewFullSha"
    Write-Host "APPLIED:false"

    if ($OldShortSha -eq ($NewFullSha.Substring(0, 7))) {
        Write-Checkpoint -Name "NO_POINTER_COMMIT_REQUIRED"
        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'SyncDryRun' -Checkpoint 'NO_POINTER_COMMIT_REQUIRED' -CompletedStep 'SyncDryRun' -ResumeCommand ''
    }

    Write-Checkpoint -Name "SYNC_DRY_RUN_COMPLETE"
    $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action SyncApply -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -ExpectedSha $ExpectedSha"
    return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'SyncDryRun' -Checkpoint 'SYNC_DRY_RUN_COMPLETE' -CompletedStep 'SyncDryRun' -ResumeCommand $resume
}

function Action-SyncApply {
    param(
        [string]$IndexPath,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha,
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "SyncApply"

    if (-not $PhaseId -or -not $OldShortSha -or -not $NewFullSha) {
        Write-Host "ERROR: -PhaseId, -OldShortSha, and -NewFullSha are required for SyncApply." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths @('world-sim/docs/phase_index.md')
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    $resolvedIndex = $IndexPath
    if (-not [System.IO.Path]::IsPathRooted($resolvedIndex)) {
        $resolvedIndex = Join-Path $repoRoot $resolvedIndex
    }
    $resolvedIndex = [System.IO.Path]::GetFullPath($resolvedIndex)
    if (-not (Test-Path -LiteralPath $resolvedIndex -PathType Leaf)) {
        Write-Host "ERROR: IndexPath not found: $IndexPath" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    $dryRunResult = Action-SyncDryRun -IndexPath $resolvedIndex -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
    if ($dryRunResult.ExitCode -ne $script:ExitCodeGreen) {
        return $dryRunResult
    }
    if ($dryRunResult.Checkpoint -eq 'NO_POINTER_COMMIT_REQUIRED') {
        return $dryRunResult
    }

    $confirm = & $ConfirmProvider -PromptText "Apply pointer update? Enter APPLY to confirm."
    if ($confirm -ne 'APPLY') {
        Write-Host "Sync apply declined. No changes made." -ForegroundColor Red
        Write-Checkpoint -Name "SYNC_APPLY_DECLINED"
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action SyncApply -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -ExpectedSha $ExpectedSha"
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'SYNC_APPLY_DECLINED' -ResumeCommand $resume -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'SyncApply' -Checkpoint 'SYNC_APPLY_DECLINED' -CompletedStep 'SyncApply' -ResumeCommand $resume
    }

    # Capture BEFORE bytes
    $beforeApplyBytes = [System.IO.File]::ReadAllBytes($resolvedIndex)

    $syncExit = Invoke-SyncHelper -IndexPath $resolvedIndex -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -Apply
    if ($syncExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    # Capture AFTER bytes and compare
    $afterApplyBytes = [System.IO.File]::ReadAllBytes($resolvedIndex)
    $diffCount = 0
    $maxLen = [Math]::Max($beforeApplyBytes.Length, $afterApplyBytes.Length)
    for ($i = 0; $i -lt $maxLen; $i++) {
        $b = if ($i -lt $beforeApplyBytes.Length) { $beforeApplyBytes[$i] } else { -1 }
        $a = if ($i -lt $afterApplyBytes.Length) { $afterApplyBytes[$i] } else { -1 }
        if ($b -ne $a) { $diffCount++ }
    }
    if ($diffCount -ne 7) {
        Write-Host "ERROR: Expected exactly 7 byte changes, found $diffCount" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    Push-Location -LiteralPath $repoRoot
    try {
        $stagedAfter = Get-StagedPaths -RepoRoot $repoRoot
        $unstagedAfter = Get-UnstagedPaths -RepoRoot $repoRoot

        if ($stagedAfter.Count -ne 0) {
            Write-Host "ERROR: Expected zero staged paths after SyncApply, found $($stagedAfter.Count)" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
        }

        $expectedRel = $resolvedIndex
        $repoRootNorm = ($repoRoot -replace '\\', '/').TrimEnd('/')
        $expectedRelNorm = ($expectedRel -replace '\\', '/')
        if ($expectedRelNorm.StartsWith($repoRootNorm + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
            $expectedRelNorm = $expectedRelNorm.Substring($repoRootNorm.Length + 1)
        }

        if ($unstagedAfter.Count -ne 1 -or $unstagedAfter[0] -ne $expectedRelNorm) {
            Write-Host "ERROR: phase_index.md is not the only unstaged path after apply." -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
        }

        $bytes = [System.IO.File]::ReadAllBytes($resolvedIndex)
        for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
            if ($bytes[$i] -eq 0x0D -and $bytes[$i + 1] -eq 0x0A) {
                Write-Host "ERROR: CRLF found after apply" -ForegroundColor Red
                $staged = Get-StagedPaths -RepoRoot $repoRoot
                $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
            }
        }
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            Write-Host "ERROR: BOM found after apply" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
        }
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            if ($bytes[$i] -eq 0x00) {
                Write-Host "ERROR: NUL byte found after apply" -ForegroundColor Red
                $staged = Get-StagedPaths -RepoRoot $repoRoot
                $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
            }
        }
        if ($bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -ne 0x0A) {
            Write-Host "ERROR: File does not end with exactly one LF after apply" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
        }
        if ($bytes.Length -ge 2 -and $bytes[$bytes.Length - 2] -eq 0x0A) {
            Write-Host "ERROR: Multiple final LFs after apply" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
        }
    } finally {
        Pop-Location
    }

    # Compute relative path for verifier
    $verifyRelPath = $resolvedIndex
    $repoRootNorm = ($repoRoot -replace '\\', '/').TrimEnd('/')
    $verifyRelNorm = ($verifyRelPath -replace '\\', '/')
    if ($verifyRelNorm.StartsWith($repoRootNorm + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
        $verifyRelNorm = $verifyRelNorm.Substring($repoRootNorm.Length + 1)
    }

    $verifyExit = Invoke-Verifier -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -Path @($verifyRelNorm) -AllowDirty
    if ($verifyExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'SyncApply' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_SYNC_APPLY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'SyncApply' -Checkpoint 'FAILED_SYNC_APPLY' -CompletedStep 'SyncApply' -ResumeCommand ''
    }

    Write-Checkpoint -Name "POINTER_APPLIED_COMMIT_B_PENDING"
    $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitIndex -ExpectedSha $ExpectedSha -CommitMessage '<message>'"
    return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'SyncApply' -Checkpoint 'POINTER_APPLIED_COMMIT_B_PENDING' -CompletedStep 'SyncApply' -ResumeCommand $resume
}

function Action-CommitIndex {
    param(
        [string]$ExpectedSha,
        [string]$CommitMessage,
        [string]$PushMode,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "CommitIndex"

    if (-not $CommitMessage) {
        Write-Host "ERROR: -CommitMessage is required for CommitIndex." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths @('world-sim/docs/phase_index.md')
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
    }

    $indexPath = 'world-sim/docs/phase_index.md'
    $fullPath = Join-Path $repoRoot $indexPath

    $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
    if ($unstaged.Count -ne 1 -or $unstaged[0] -ne $indexPath) {
        Write-Host "ERROR: phase_index.md is not the only changed path." -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
    }

    $verifyExit = Invoke-Verifier -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -Path @($indexPath) -AllowDirty
    if ($verifyExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
    }

    $confirm = & $ConfirmProvider -PromptText "Stage phase_index.md? Enter STAGE to confirm."
    if ($confirm -ne 'STAGE') {
        Write-Host "Staging declined." -ForegroundColor Red
        Write-Checkpoint -Name "STAGE_DECLINED"
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitIndex -ExpectedSha $ExpectedSha -CommitMessage '$CommitMessage'"
        Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'STAGE_DECLINED' -ResumeCommand $resume -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitIndex' -Checkpoint 'STAGE_DECLINED' -CompletedStep 'CommitIndex' -ResumeCommand $resume
    }

    Push-Location -LiteralPath $repoRoot
    try {
        & git add -- $indexPath 2>&1 | Out-Null

        $stagedAfter = Get-StagedPaths -RepoRoot $repoRoot
        $unstagedAfter = Get-UnstagedPaths -RepoRoot $repoRoot

        $diffCheck = & git diff --cached --check 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: git diff --cached --check reported issues" -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
        }

        if ($stagedAfter.Count -ne 1 -or $stagedAfter[0] -ne $indexPath) {
            Write-Host "ERROR: Staged paths do not match exactly." -ForegroundColor Red
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
        }

        Write-Host "Numstat (cached):"
        $numstat = & git diff --cached --numstat 2>&1
        $numstat | ForEach-Object { Write-Host "  $_" }

        $confirmCommit = & $ConfirmProvider -PromptText "Commit staged changes? Enter COMMIT to confirm."
        if ($confirmCommit -ne 'COMMIT') {
            Write-Host "Commit declined." -ForegroundColor Red
            Write-Checkpoint -Name "COMMIT_DECLINED"
            $staged = Get-StagedPaths -RepoRoot $repoRoot
            $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
            $resume = ".\world-sim\scripts\docs_correction_workflow.ps1 -Action CommitIndex -ExpectedSha $ExpectedSha -CommitMessage '$CommitMessage'"
            Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'COMMIT_DECLINED' -ResumeCommand $resume -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitIndex' -Checkpoint 'COMMIT_DECLINED' -CompletedStep 'CommitIndex' -ResumeCommand $resume
        }

        & git commit -m $CommitMessage 2>&1 | Out-Null
        $commitSha = (& git rev-parse HEAD) | Select-Object -First 1
        Write-Host "Committed: $commitSha" -ForegroundColor Green
        Write-Checkpoint -Name "INDEX_STAGED_COMMIT_PENDING"

        if ($PushMode -eq 'Prompted') {
            $confirmPush = & $ConfirmProvider -PromptText "Push to remote? Enter PUSH to confirm."
            if ($confirmPush -eq 'PUSH') {
                & git push $Remote $Branch 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "ERROR: Push failed" -ForegroundColor Red
                    $staged = Get-StagedPaths -RepoRoot $repoRoot
                    $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                    Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                    return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
                }
                & git fetch $Remote $Branch 2>&1 | Out-Null
                $newHead = (& git rev-parse HEAD) | Select-Object -First 1
                $newTracking = Get-RemoteTrackingSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
                $newLsRemote = Get-LsRemoteSha -RepoRoot $repoRoot -Remote $Remote -Branch $Branch
                if ($newHead -ne $newTracking -or $newHead -ne $newLsRemote) {
                    Write-Host "ERROR: Post-push alignment failed" -ForegroundColor Red
                    $staged = Get-StagedPaths -RepoRoot $repoRoot
                    $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
                    Write-FailureReport -CompletedStep 'CommitIndex' -CurrentHead $newHead -TrackingSha $newTracking -LsRemoteSha $newLsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_COMMIT_INDEX' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
                    return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'CommitIndex' -Checkpoint 'FAILED_COMMIT_INDEX' -CompletedStep 'CommitIndex' -ResumeCommand ''
                }
                Write-Host "Pushed and triple-aligned." -ForegroundColor Green
                Write-Checkpoint -Name "COMMIT_B_PUSHED"
                $resume = ''
                return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitIndex' -Checkpoint 'COMMIT_B_PUSHED' -CompletedStep 'CommitIndex' -ResumeCommand $resume
            } else {
                Write-Host "Push declined. Local commit created." -ForegroundColor Yellow
                Write-Checkpoint -Name "COMMIT_B_CREATED_PUSH_PENDING"
                $resume = "git push $Remote $Branch"
                return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitIndex' -Checkpoint 'COMMIT_B_CREATED_PUSH_PENDING' -CompletedStep 'CommitIndex' -ResumeCommand $resume
            }
        } else {
            Write-Host "Manual PushMode: push not performed." -ForegroundColor Yellow
            Write-Checkpoint -Name "COMMIT_B_CREATED_PUSH_PENDING"
            $resume = "git push $Remote $Branch"
            return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'CommitIndex' -Checkpoint 'COMMIT_B_CREATED_PUSH_PENDING' -CompletedStep 'CommitIndex' -ResumeCommand $resume
        }
    } finally {
        Pop-Location
    }
}

function Action-FinalVerify {
    param(
        [string[]]$Path,
        [string]$ExpectedSha,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    Write-StepHeader -Name "FinalVerify"

    if (-not $Path -or $Path.Count -eq 0) {
        Write-Host "ERROR: -Path is required for FinalVerify." -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $repoRoot = Get-RepoRoot
    if (-not $repoRoot) {
        Write-Host "ERROR: Not inside a Git repository" -ForegroundColor Red
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $gate = Invoke-RepoStateGate -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -AuthorizedDirtyPaths @()
    if ($gate.ExitCode -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'FinalVerify' -CurrentHead $gate.LocalHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_FINAL_VERIFY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $currentHead = $gate.LocalHead
    if (-not (Test-LowerHex40 -Value $currentHead)) {
        Write-Host "ERROR: Current HEAD is not valid lowercase hex40" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'FinalVerify' -CurrentHead $currentHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_FINAL_VERIFY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $verifyExit = Invoke-Verifier -ExpectedSha $currentHead -Remote $Remote -Branch $Branch -Path $Path
    if ($verifyExit -ne $script:ExitCodeGreen) {
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'FinalVerify' -CurrentHead $currentHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_FINAL_VERIFY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $syncHelper = Join-Path $PSScriptRoot 'sync_phase_index_sha.ps1'
    $verifyHelper = Join-Path $PSScriptRoot 'verify_repo_state.ps1'

    $syncSelfExit = & $syncHelper -SelfTest 2>&1 | Out-Null
    $syncSelfCode = $LASTEXITCODE
    if ($syncSelfCode -ne $script:ExitCodeGreen) {
        Write-Host "ERROR: sync_phase_index_sha.ps1 self-test failed" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'FinalVerify' -CurrentHead $currentHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_FINAL_VERIFY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    $verifySelfExit = & $verifyHelper -SelfTest 2>&1 | Out-Null
    $verifySelfCode = $LASTEXITCODE
    if ($verifySelfCode -ne $script:ExitCodeGreen) {
        Write-Host "ERROR: verify_repo_state.ps1 self-test failed" -ForegroundColor Red
        $staged = Get-StagedPaths -RepoRoot $repoRoot
        $unstaged = Get-UnstagedPaths -RepoRoot $repoRoot
        Write-FailureReport -CompletedStep 'FinalVerify' -CurrentHead $currentHead -TrackingSha $gate.RemoteTracking -LsRemoteSha $gate.LsRemote -StagedPaths $staged -UnstagedPaths $unstaged -Checkpoint 'FAILED_FINAL_VERIFY' -ResumeCommand '' -ManualFallback 'world-sim/docs/docs_correction_runbook.md'
        return New-ActionResult -ExitCode $script:ExitCodeRed -Action 'FinalVerify' -Checkpoint 'FAILED_FINAL_VERIFY' -CompletedStep 'FinalVerify' -ResumeCommand ''
    }

    Write-Checkpoint -Name "FINAL_VERIFY_COMPLETE"
    Write-Host "FINAL STATE: GREEN" -ForegroundColor Green
    Write-Host ""
    Write-Host "Manual fallback: world-sim/docs/docs_correction_runbook.md"
    return New-ActionResult -ExitCode $script:ExitCodeGreen -Action 'FinalVerify' -Checkpoint 'FINAL_VERIFY_COMPLETE' -CompletedStep 'FinalVerify' -ResumeCommand ''
}

# ---------------------------------------------------------------------------
# Internal Dispatcher
# ---------------------------------------------------------------------------

function Invoke-Dispatcher {
    param(
        [string]$Action,
        [string[]]$Path,
        [string]$ExpectedSha,
        [string]$CommitMessage,
        [string]$PhaseId,
        [string]$OldShortSha,
        [string]$NewFullSha,
        [string]$PushMode,
        [string]$Remote,
        [string]$Branch,
        [scriptblock]$ConfirmProvider
    )

    if (-not $ConfirmProvider) {
        $ConfirmProvider = {
            param($PromptText)
            Read-Host $PromptText
        }
    }

    switch ($Action) {
        'InspectDocs' {
            return Action-InspectDocs -Path $Path -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        'CommitDocs' {
            return Action-CommitDocs -Path $Path -ExpectedSha $ExpectedSha -CommitMessage $CommitMessage -PushMode $PushMode -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        'SyncDryRun' {
            return Action-SyncDryRun -IndexPath $Path -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        'SyncApply' {
            return Action-SyncApply -IndexPath $Path -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        'CommitIndex' {
            return Action-CommitIndex -ExpectedSha $ExpectedSha -CommitMessage $CommitMessage -PushMode $PushMode -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        'FinalVerify' {
            return Action-FinalVerify -Path $Path -ExpectedSha $ExpectedSha -Remote $Remote -Branch $Branch -ConfirmProvider $ConfirmProvider
        }
        default {
            Write-Host "Unknown action: $Action" -ForegroundColor Red
            return New-ActionResult -ExitCode $script:ExitCodeRed -Action $Action -Checkpoint 'FAILED_UNKNOWN_ACTION' -CompletedStep $Action -ResumeCommand ''
        }
    }
}

# ---------------------------------------------------------------------------
# AST Forbidden-Operation Scan
# ---------------------------------------------------------------------------

function Invoke-AstScan {
    param([string]$ScriptPath)
    $tokens = [System.Management.Automation.Language.Parser]::ParseFile($ScriptPath, [ref]$null, [ref]$null)
    $forbidden = @(
        @{ Pattern = 'force'; Cmdlets = @('push') },
        @{ Pattern = '--force'; Cmdlets = @() },
        @{ Pattern = '--amend'; Cmdlets = @('commit') },
        @{ Pattern = 'reset'; Cmdlets = @() },
        @{ Pattern = 'revert'; Cmdlets = @() },
        @{ Pattern = 'rebase'; Cmdlets = @() },
        @{ Pattern = 'squash'; Cmdlets = @() },
        @{ Pattern = 'stash'; Cmdlets = @() },
        @{ Pattern = 'clean'; Cmdlets = @() },
        @{ Pattern = '-A'; Cmdlets = @('add') },
        @{ Pattern = '.'; Cmdlets = @('add') }
    )

    $found = @()
    foreach ($ast in $tokens.Commands) {
        foreach ($cmd in $ast) {
            $cmdName = $cmd.CommandElements[0].Value
            if ($cmdName -ne 'git') { continue }
            $args = @()
            for ($i = 1; $i -lt $cmd.CommandElements.Count; $i++) {
                $args += $cmd.CommandElements[$i].Value
            }
            foreach ($fb in $forbidden) {
                if ($args -contains $fb.Pattern) {
                    if ($fb.Cmdlets.Count -eq 0 -or $args -contains $fb.Cmdlets) {
                        $found += "$cmdName $($args -join ' ')"
                    }
                }
            }
        }
    }
    return $found
}

# ---------------------------------------------------------------------------
# Self-Test
# ---------------------------------------------------------------------------

function Run-SelfTest {
    Write-Host "=== W4 SelfTest ===" -ForegroundColor Cyan

    $tempBase = [System.IO.Path]::GetTempPath()
    $tempDir = Join-Path $tempBase ("docs_correction_workflow_selftest_" + [System.Guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempDir -Force
    $script:assertCount = 0
    $script:allPassed = $true
    $script:failureMessages = @()

    function Assert-Condition {
        param(
            [string]$Name,
            [scriptblock]$Test,
            [string]$Description
        )
        $script:assertCount++
        try {
            $result = & $Test
            if ($result) {
                Write-Host "  [PASS] $Name : $Description"
            } else {
                Write-Host "  [FAIL] $Name : $Description"
                $script:allPassed = $false
                $script:failureMessages += "$Name : $Description"
            }
        } catch {
            Write-Host "  [FAIL] $Name : $Description -- exception: $($_.Exception.Message)"
            $script:allPassed = $false
            $script:failureMessages += "$Name : $Description -- exception: $($_.Exception.Message)"
        }
    }

    function New-TempGitRepo {
        param([string]$RepoDir, [bool]$WithOrigin = $true)
        $null = New-Item -ItemType Directory -Path $RepoDir -Force
        Push-Location $RepoDir
        git init 2>&1 | Out-Null
        git config user.name 'Selftest' 2>&1 | Out-Null
        git config user.email 'selftest@example.invalid' 2>&1 | Out-Null
        git branch -M master 2>&1 | Out-Null
        if ($WithOrigin) {
            $bareDir = Join-Path ([System.IO.Path]::GetDirectoryName($RepoDir)) ([System.IO.Path]::GetFileName($RepoDir) + '_bare.git')
            git init --bare $bareDir 2>&1 | Out-Null
            git remote add origin $bareDir 2>&1 | Out-Null
        }
        Pop-Location
    }

    function Push-TempRepoToOrigin {
        param([string]$RepoDir)
        Push-Location -LiteralPath $RepoDir
        try {
            git push origin master 2>&1 | Out-Null
        } finally {
            Pop-Location
        }
    }

    function Get-QueueProvider {
        param([System.Collections.Generic.Queue[string]]$Queue)
        return {
            param($PromptText)
            if ($Queue.Count -gt 0) {
                return $Queue.Dequeue()
            }
            return ''
        }.GetNewClosure()
    }

    try {
        # T01: InspectDocs performs no writes
        Write-Host "`nT01-T05: Behavioural checks in temp repos"
        $repo01 = Join-Path $tempDir 'repo01'
        New-TempGitRepo $repo01
        $doc01 = Join-Path $repo01 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc01) -Force
        [System.IO.File]::WriteAllText($doc01, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo01
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha01 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo01
        Pop-Location
        $queue01 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue01.Enqueue('IGNORE')
        $provider01 = Get-QueueProvider -Queue $queue01
        Push-Location $repo01
        $t01Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha01 -Branch master -Remote origin -ConfirmProvider $provider01
        Pop-Location
        Assert-Condition 'T01' { $t01Result.ExitCode -eq 0 } "InspectDocs performs no writes"

        # T02: malformed ExpectedSha returns RED
        Push-Location $repo01
        $t02Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/test.md' -ExpectedSha 'short' -Branch master -Remote origin -ConfirmProvider $provider01
        Pop-Location
        Assert-Condition 'T02' { $t02Result.ExitCode -eq 2 } "malformed ExpectedSha returns RED"

        # T03: incorrect ExpectedSha returns RED
        Push-Location $repo01
        $t03Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/test.md' -ExpectedSha ('0' * 40) -Branch master -Remote origin -ConfirmProvider $provider01
        Pop-Location
        Assert-Condition 'T03' { $t03Result.ExitCode -eq 2 } "incorrect ExpectedSha returns RED"

        # T04: unauthorized dirty path returns RED
        $repo04 = Join-Path $tempDir 'repo04'
        New-TempGitRepo $repo04
        $doc04 = Join-Path $repo04 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc04) -Force
        [System.IO.File]::WriteAllText($doc04, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo04
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha04 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo04
        [System.IO.File]::WriteAllText((Join-Path $repo04 'unauthorized.txt'), "dirty`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue04 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue04.Enqueue('IGNORE')
        $provider04 = Get-QueueProvider -Queue $queue04
        Push-Location $repo04
        $t04Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha04 -Branch master -Remote origin -ConfirmProvider $provider04
        Pop-Location
        Assert-Condition 'T04' { $t04Result.ExitCode -eq 2 } "unauthorized dirty path returns RED"
        Remove-Item (Join-Path $repo04 'unauthorized.txt') -Force

        # T05: multiple authorized paths work
        $repo05 = Join-Path $tempDir 'repo05'
        New-TempGitRepo $repo05
        $doc05a = Join-Path $repo05 'world-sim/docs/a.md'
        $doc05b = Join-Path $repo05 'world-sim/docs/b.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc05a) -Force
        [System.IO.File]::WriteAllText($doc05a, "# A`n", [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($doc05b, "# B`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo05
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha05 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo05
        [System.IO.File]::WriteAllText($doc05a, "# A changed`n", [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($doc05b, "# B changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue05 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue05.Enqueue('IGNORE')
        $provider05 = Get-QueueProvider -Queue $queue05
        Push-Location $repo05
        $t05Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/a.md','world-sim/docs/b.md' -ExpectedSha $sha05 -Branch master -Remote origin -ConfirmProvider $provider05
        $t05Exit = $LASTEXITCODE
        Pop-Location
        Assert-Condition 'T05' { $t05Exit -eq 0 } "multiple authorized paths work through one explicit array"

        # T06: CONTENT-REVIEWED decline leaves nothing staged
        Write-Host "`nT06-T10: CommitDocs decline/push tests"
        $repo06 = Join-Path $tempDir 'repo06'
        New-TempGitRepo $repo06
        $doc06 = Join-Path $repo06 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc06) -Force
        [System.IO.File]::WriteAllText($doc06, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo06
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha06 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo06
        [System.IO.File]::WriteAllText($doc06, "# Changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue06 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue06.Enqueue('WRONG')
        $provider06 = Get-QueueProvider -Queue $queue06
        Push-Location $repo06
        $t06Result = Invoke-Dispatcher -Action 'CommitDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha06 -CommitMessage 'test' -PushMode Manual -Branch master -Remote origin -ConfirmProvider $provider06
        Pop-Location
        Push-Location $repo06
        $staged06 = @(& git diff --cached --name-only | Where-Object { $_ })
        Pop-Location
        Assert-Condition 'T06' { $t06Result.ExitCode -eq 0 -and $staged06.Count -eq 0 } "CONTENT-REVIEWED decline leaves nothing staged"

        # T07: STAGE decline leaves nothing staged
        $repo07 = Join-Path $tempDir 'repo07'
        New-TempGitRepo $repo07
        $doc07 = Join-Path $repo07 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc07) -Force
        [System.IO.File]::WriteAllText($doc07, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo07
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha07 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo07
        [System.IO.File]::WriteAllText($doc07, "# Changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue07 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue07.Enqueue('CONTENT-REVIEWED')
        $null = $queue07.Enqueue('WRONG')
        $provider07 = Get-QueueProvider -Queue $queue07
        Push-Location $repo07
        $t07Result = Invoke-Dispatcher -Action 'CommitDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha07 -CommitMessage 'test' -PushMode Manual -Branch master -Remote origin -ConfirmProvider $provider07
        Pop-Location
        Push-Location $repo07
        $staged07 = @(& git diff --cached --name-only | Where-Object { $_ })
        Pop-Location
        Assert-Condition 'T07' { $t07Result.ExitCode -eq 0 -and $staged07.Count -eq 0 } "STAGE decline leaves nothing staged"

        # T08: COMMIT decline leaves only exact staged paths
        $repo08 = Join-Path $tempDir 'repo08'
        New-TempGitRepo $repo08
        $doc08 = Join-Path $repo08 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc08) -Force
        [System.IO.File]::WriteAllText($doc08, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo08
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha08 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo08
        [System.IO.File]::WriteAllText($doc08, "# Changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue08 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue08.Enqueue('CONTENT-REVIEWED')
        $null = $queue08.Enqueue('STAGE')
        $null = $queue08.Enqueue('WRONG')
        $provider08 = Get-QueueProvider -Queue $queue08
        Push-Location $repo08
        $t08Result = Invoke-Dispatcher -Action 'CommitDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha08 -CommitMessage 'test' -PushMode Manual -Branch master -Remote origin -ConfirmProvider $provider08
        Pop-Location
        Push-Location $repo08
        $staged08 = @(Get-StagedPaths -RepoRoot $repo08)
        Pop-Location
        Assert-Condition 'T08' { $t08Result.ExitCode -eq 0 -and $staged08.Count -eq 1 -and $staged08[0] -eq 'world-sim/docs/test.md' } "COMMIT decline leaves only exact staged paths"

        # T09: Commit A is created using exact-path staging
        $repo09 = Join-Path $tempDir 'repo09'
        New-TempGitRepo $repo09
        $doc09 = Join-Path $repo09 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc09) -Force
        [System.IO.File]::WriteAllText($doc09, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo09
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha09 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo09
        [System.IO.File]::WriteAllText($doc09, "# Changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue09 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue09.Enqueue('CONTENT-REVIEWED')
        $null = $queue09.Enqueue('STAGE')
        $null = $queue09.Enqueue('COMMIT')
        $provider09 = Get-QueueProvider -Queue $queue09
        Push-Location $repo09
        $t09Result = Invoke-Dispatcher -Action 'CommitDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha09 -CommitMessage 'test' -PushMode Manual -Branch master -Remote origin -ConfirmProvider $provider09
        Pop-Location
        Push-Location $repo09
        $head09 = (& git rev-parse HEAD) | Select-Object -First 1
        $staged09 = Get-StagedPaths -RepoRoot $repo09
        $log09 = & git log --oneline -1
        Pop-Location
        Assert-Condition 'T09' { $t09Result.ExitCode -eq 0 -and $head09 -ne $sha09 -and $staged09.Count -eq 0 -and $log09 -match 'test' } "Commit A is created using exact-path staging"

        # T10: Manual mode creates no push and prints exact push command
        Assert-Condition 'T10' { $t09Result -match 'git push origin master' } "Manual mode creates no push and prints exact push command"

        # T11: Prompted PUSH pushes Commit A and triple-aligns
        Write-Host "`nT11-T15: Sync and push tests"
        $repo11 = Join-Path $tempDir 'repo11'
        New-TempGitRepo $repo11
        $doc11 = Join-Path $repo11 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc11) -Force
        [System.IO.File]::WriteAllText($doc11, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo11
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha11 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo11
        [System.IO.File]::WriteAllText($doc11, "# Changed`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue11 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue11.Enqueue('CONTENT-REVIEWED')
        $null = $queue11.Enqueue('STAGE')
        $null = $queue11.Enqueue('COMMIT')
        $null = $queue11.Enqueue('PUSH')
        $provider11 = Get-QueueProvider -Queue $queue11
        Push-Location $repo11
        $t11Result = Invoke-Dispatcher -Action 'CommitDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha11 -CommitMessage 'test' -PushMode Prompted -Branch master -Remote origin -ConfirmProvider $provider11
        Pop-Location
        Push-Location $repo11
        $head11 = (& git rev-parse HEAD) | Select-Object -First 1
        $tracking11 = (& git rev-parse origin/master) | Select-Object -First 1
        $lsr11 = (& git ls-remote origin refs/heads/master) | Where-Object { $_ -match '^[0-9a-f]{40}' } | Select-Object -First 1
        $lsr11sha = if ($lsr11) { ($lsr11 -split '\s')[0] } else { '' }
        Pop-Location
        Assert-Condition 'T11' { $t11Result.ExitCode -eq 0 -and $head11 -eq $tracking11 -and $head11 -eq $lsr11sha } "Prompted PUSH pushes Commit A and triple-aligns"

        # T12: SyncDryRun changes zero bytes and reports APPLIED:false with relative public Path
        Write-Host "`nT12-T15: SyncDryRun and SyncApply tests"
        $repo12 = Join-Path $tempDir 'repo12'
        New-TempGitRepo $repo12
        $idx12 = Join-Path $repo12 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx12) -Force
        [System.IO.File]::WriteAllText($idx12, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo12
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha12 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo12
        Pop-Location
        $queue12 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue12.Enqueue('IGNORE')
        $provider12 = Get-QueueProvider -Queue $queue12
        $before12 = [System.IO.File]::ReadAllBytes($idx12)
        $before12Hash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($before12)).Replace('-', '').ToLowerInvariant()
        Push-Location $repo12
        $t12Result = Invoke-Dispatcher -Action 'SyncDryRun' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha 'abcdef1' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha12 -Branch master -Remote origin -ConfirmProvider $provider12
        Pop-Location
        $after12 = [System.IO.File]::ReadAllBytes($idx12)
        $after12Hash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($after12)).Replace('-', '').ToLowerInvariant()
        Assert-Condition 'T12' { $t12Result.ExitCode -eq 0 -and $before12Hash -eq $after12Hash -and $t12Result.Checkpoint -eq 'SYNC_DRY_RUN_COMPLETE' } "SyncDryRun changes zero bytes and reports APPLIED:false with relative public Path"

        # T13: APPLY decline changes zero bytes with relative public Path
        $repo13 = Join-Path $tempDir 'repo13'
        New-TempGitRepo $repo13
        $idx13 = Join-Path $repo13 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx13) -Force
        [System.IO.File]::WriteAllText($idx13, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo13
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha13 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo13
        Pop-Location
        $queue13 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue13.Enqueue('WRONG')
        $provider13 = Get-QueueProvider -Queue $queue13
        $hash13before = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData([System.IO.File]::ReadAllBytes($idx13))).Replace('-', '').ToLowerInvariant()
        Push-Location $repo13
        $t13Result = Invoke-Dispatcher -Action 'SyncApply' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha 'abcdef1' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha13 -Branch master -Remote origin -ConfirmProvider $provider13
        Pop-Location
        $hash13after = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData([System.IO.File]::ReadAllBytes($idx13))).Replace('-', '').ToLowerInvariant()
        Assert-Condition 'T13' { $t13Result.ExitCode -eq 0 -and $hash13before -eq $hash13after } "APPLY decline changes zero bytes with relative public Path"

        # T14: SyncApply changes exactly seven bytes in one Commit cell with relative public Path
        $repo14 = Join-Path $tempDir 'repo14'
        New-TempGitRepo $repo14
        $idx14 = Join-Path $repo14 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx14) -Force
        [System.IO.File]::WriteAllText($idx14, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo14
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha14 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo14
        Pop-Location
        $queue14 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue14.Enqueue('APPLY')
        $provider14 = Get-QueueProvider -Queue $queue14
        $before14 = [System.IO.File]::ReadAllBytes($idx14)
        Push-Location $repo14
        $t14Result = Invoke-Dispatcher -Action 'SyncApply' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha 'abcdef1' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha14 -Branch master -Remote origin -ConfirmProvider $provider14
        Pop-Location
        $after14 = [System.IO.File]::ReadAllBytes($idx14)
        $diff14 = 0
        for ($i = 0; $i -lt [Math]::Max($before14.Length, $after14.Length); $i++) {
            $b = if ($i -lt $before14.Length) { $before14[$i] } else { -1 }
            $a = if ($i -lt $after14.Length) { $after14[$i] } else { -1 }
            if ($b -ne $a) { $diff14++ }
        }
        Push-Location $repo14
        $staged14 = Get-StagedPaths -RepoRoot $repo14
        $unstaged14 = Get-UnstagedPaths -RepoRoot $repo14
        Pop-Location
        $rowContains1234567 = [System.IO.File]::ReadAllText($idx14, [System.Text.UTF8Encoding]::new($false)) -match '\| W4 \| Done \| Test \| `1234567` \| Low \| Notes \|'
        Assert-Condition 'T14' { $t14Result.ExitCode -eq 0 -and $t14Result.Checkpoint -eq 'POINTER_APPLIED_COMMIT_B_PENDING' -and $diff14 -eq 7 -and $staged14.Count -eq 0 -and $unstaged14.Count -eq 1 -and $unstaged14[0] -eq 'world-sim/docs/phase_index.md' -and $rowContains1234567 } "SyncApply changes exactly seven bytes in one Commit cell with relative public Path"

        # T15: no-op sync creates no Commit B
        Write-Host "`nT15-T19: CommitIndex and FinalVerify tests"
        $repo15 = Join-Path $tempDir 'repo15'
        New-TempGitRepo $repo15
        $idx15 = Join-Path $repo15 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx15) -Force
        $noopSha = 'abcdef1' + '0' * 33
        [System.IO.File]::WriteAllText($idx15, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo15
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha15 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo15
        Pop-Location
        $queue15 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue15.Enqueue('IGNORE')
        $provider15 = Get-QueueProvider -Queue $queue15
        Push-Location $repo15
        $t15Result = Invoke-Dispatcher -Action 'SyncApply' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha 'abcdef1' -NewFullSha $noopSha -ExpectedSha $sha15 -Branch master -Remote origin -ConfirmProvider $provider15
        Pop-Location
        Push-Location $repo15
        $head15 = (& git rev-parse HEAD) | Select-Object -First 1
        Pop-Location
        Assert-Condition 'T15' { $t15Result.ExitCode -eq 0 -and $head15 -eq $sha15 -and $t15Result -match 'NO_POINTER_COMMIT_REQUIRED' } "no-op sync creates no Commit B"

        # T16: CommitIndex STAGE decline stages nothing
        $repo16 = Join-Path $tempDir 'repo16'
        New-TempGitRepo $repo16
        $idx16 = Join-Path $repo16 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx16) -Force
        [System.IO.File]::WriteAllText($idx16, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "1234567" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo16
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha16 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo16
        [System.IO.File]::WriteAllText($idx16, "| W4 | Done | Test | `abcdef1` | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue16 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue16.Enqueue('WRONG')
        $provider16 = Get-QueueProvider -Queue $queue16
        Push-Location $repo16
        $t16Result = Invoke-Dispatcher -Action 'CommitIndex' -ExpectedSha $sha16 -CommitMessage 'sync' -PushMode Manual -Branch master -Remote origin -ConfirmProvider $provider16
        Pop-Location
        Push-Location $repo16
        $staged16 = Get-StagedPaths -RepoRoot $repo16
        Pop-Location
        Assert-Condition 'T16' { $t16Result.ExitCode -eq 0 -and $staged16.Count -eq 0 } "CommitIndex STAGE decline stages nothing"

        # T17: Commit B is created and pushed
        $repo17 = Join-Path $tempDir 'repo17'
        New-TempGitRepo $repo17
        $idx17 = Join-Path $repo17 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx17) -Force
        [System.IO.File]::WriteAllText($idx17, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo17
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha17 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo17
        [System.IO.File]::WriteAllText($idx17, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "1234567" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue17 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue17.Enqueue('STAGE')
        $null = $queue17.Enqueue('COMMIT')
        $null = $queue17.Enqueue('PUSH')
        $provider17 = Get-QueueProvider -Queue $queue17
        Push-Location $repo17
        $t17Result = Invoke-Dispatcher -Action 'CommitIndex' -ExpectedSha $sha17 -CommitMessage 'sync' -PushMode Prompted -Branch master -Remote origin -ConfirmProvider $provider17
        Pop-Location
        Push-Location $repo17
        $head17 = (& git rev-parse HEAD) | Select-Object -First 1
        $tracking17 = (& git rev-parse origin/master) | Select-Object -First 1
        Pop-Location
        Assert-Condition 'T17' { $t17Result.ExitCode -eq 0 -and $head17 -ne $sha17 -and $head17 -eq $tracking17 } "Commit B is created and pushed"

        # T18: after Commit B, row points to Commit A while verification uses Commit B
        $content18 = [System.IO.File]::ReadAllText($idx17, [System.Text.UTF8Encoding]::new($false))
        $rowPointsToA = $content18 -match '\| W4 \| Done \| Test \| `1234567` \| Low \| Notes \|'
        Assert-Condition 'T18' { $rowPointsToA -and $head17 -ne $sha17 } "after Commit B, row points to Commit A while verification uses Commit B"

        # T19: FinalVerify succeeds on clean triple alignment
        Write-Host "`nT19-T22: Edge case tests"
        $repo19 = Join-Path $tempDir 'repo19'
        New-TempGitRepo $repo19
        $doc19 = Join-Path $repo19 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc19) -Force
        [System.IO.File]::WriteAllText($doc19, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo19
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha19 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo19
        Pop-Location
        $queue19 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue19.Enqueue('IGNORE')
        $provider19 = Get-QueueProvider -Queue $queue19
        Push-Location $repo19
        $t19Result = Invoke-Dispatcher -Action 'FinalVerify' -Path 'world-sim/docs/test.md' -ExpectedSha $sha19 -Branch master -Remote origin -ConfirmProvider $provider19
        Pop-Location
        Assert-Condition 'T19' { $t19Result.ExitCode -eq 0 -and $t19Result -match 'FINAL_VERIFY_COMPLETE' } "FinalVerify succeeds on clean triple alignment"

        # T20: wrong OldShortSha fails safely
        $repo20 = Join-Path $tempDir 'repo20'
        New-TempGitRepo $repo20
        $idx20 = Join-Path $repo20 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx20) -Force
        [System.IO.File]::WriteAllText($idx20, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo20
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha20 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo20
        Pop-Location
        $queue20 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue20.Enqueue('IGNORE')
        $provider20 = Get-QueueProvider -Queue $queue20
        Push-Location $repo20
        $t20Result = Invoke-Dispatcher -Action 'SyncApply' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha '0000000' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha20 -Branch master -Remote origin -ConfirmProvider $provider20
        Pop-Location
        Assert-Condition 'T20' { $t20Result.ExitCode -eq 2 } "wrong OldShortSha fails safely"

        # T21: zero phase matches fail safely
        $repo21 = Join-Path $tempDir 'repo21'
        New-TempGitRepo $repo21
        $idx21 = Join-Path $repo21 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx21) -Force
        [System.IO.File]::WriteAllText($idx21, "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo21
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha21 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo21
        Pop-Location
        $queue21 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue21.Enqueue('IGNORE')
        $provider21 = Get-QueueProvider -Queue $queue21
        Push-Location $repo21
        $t21Result = Invoke-Dispatcher -Action 'SyncApply' -Path 'world-sim/docs/phase_index.md' -PhaseId 'NOPE' -OldShortSha 'abcdef1' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha21 -Branch master -Remote origin -ConfirmProvider $provider21
        Pop-Location
        Assert-Condition 'T21' { $t21Result.ExitCode -eq 2 } "zero phase matches fail safely"

        # T22: duplicate phase rows fail safely
        $repo22 = Join-Path $tempDir 'repo22'
        New-TempGitRepo $repo22
        $idx22 = Join-Path $repo22 'world-sim/docs/phase_index.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $idx22) -Force
        $content22 = "| Phase | Status | Purpose | Commit | Runtime Impact | Notes |`n|---|---|---|---|---|---|`n| W4 | Done | Test | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n| W4 | Done | Dup | " + '`' + "abcdef1" + '`' + " | Low | Notes |`n"
        [System.IO.File]::WriteAllText($idx22, $content22, [System.Text.UTF8Encoding]::new($false))
        $bytes22before = [System.IO.File]::ReadAllBytes($idx22)
        Push-Location $repo22
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha22 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo22
        $origin22before = (& git ls-remote origin master) 2>&1 | Select-Object -First 1
        Pop-Location
        $queue22 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue22.Enqueue('IGNORE')
        $provider22 = Get-QueueProvider -Queue $queue22
        Push-Location $repo22
        $t22Result = Invoke-Dispatcher -Action 'SyncDryRun' -Path 'world-sim/docs/phase_index.md' -PhaseId 'W4' -OldShortSha 'abcdef1' -NewFullSha '1234567890123456789012345678901234567890' -ExpectedSha $sha22 -Branch master -Remote origin -ConfirmProvider $provider22
        Pop-Location
        $bytes22after = [System.IO.File]::ReadAllBytes($idx22)
        $bytes22diff = 0
        for ($i = 0; $i -lt [Math]::Max($bytes22before.Length, $bytes22after.Length); $i++) {
            $b22 = if ($i -lt $bytes22before.Length) { $bytes22before[$i] } else { -1 }
            $a22 = if ($i -lt $bytes22after.Length) { $bytes22after[$i] } else { -1 }
            if ($b22 -ne $a22) { $bytes22diff++ }
        }
        Push-Location $repo22
        $staged22 = Get-StagedPaths -RepoRoot $repo22
        $commit22 = (& git rev-parse HEAD) 2>&1 | Select-Object -First 1
        $origin22after = (& git ls-remote origin master) 2>&1
        Pop-Location
        Assert-Condition 'T22' {
            $t22Result.ExitCode -eq 2 -and
            $t22Result.Checkpoint -ne $null -and
            $t22Result.Checkpoint.Length -gt 0 -and
            $bytes22diff -eq 0 -and
            $staged22.Count -eq 0 -and
            $commit22 -eq $sha22 -and
            $origin22after -eq $origin22before
        } "duplicate phase rows fail without mutation"

        # T23: public interface has no confirmation bypass and existing helpers are used
        Write-Host "`nT23-T24: Source inspection tests"
        $scriptPath23 = Join-Path $PSScriptRoot 'docs_correction_workflow.ps1'
        $source23 = [System.IO.File]::ReadAllText($scriptPath23, [System.Text.UTF8Encoding]::new($false))
        $errors23 = $null
        $tokens23 = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($source23, [ref]$tokens23, [ref]$errors23)
        # Find the top-level param block
        $paramBlock = $ast.ParamBlock
        $paramNames = @()
        if ($paramBlock) {
            foreach ($p in $paramBlock.Parameters) {
                $nameText = $p.Name.Extent.Text
                if ($nameText.StartsWith('$')) { $nameText = $nameText.Substring(1) }
                $paramNames += $nameText
            }
        }
        $expectedParams = @('Action','Path','ExpectedSha','CommitMessage','PhaseId','OldShortSha','NewFullSha','PushMode','Remote','Branch','SelfTest')
        $paramsMatch = $true
        if ($paramNames.Count -ne $expectedParams.Count) { $paramsMatch = $false }
        else {
            for ($p = 0; $p -lt $expectedParams.Count; $p++) {
                if ($paramNames[$p] -ne $expectedParams[$p]) { $paramsMatch = $false; break }
            }
        }
        $forbiddenNames = @('Force','Confirm','NoConfirm','SkipConfirm','AutoConfirm','AssumeYes','NonInteractive','TestMode','ConfirmationProvider')
        $hasForbiddenParam = $false
        foreach ($pn in $paramNames) {
            foreach ($fn in $forbiddenNames) {
                if ($pn -eq $fn) { $hasForbiddenParam = $true }
            }
        }
        # Check Action ValidateSet contains exactly the required values
        $actionParam = $null
        if ($paramBlock) {
            foreach ($p in $paramBlock.Parameters) {
                $pName = $p.Name.Extent.Text
                if ($pName.StartsWith('$')) { $pName = $pName.Substring(1) }
                if ($pName -eq 'Action') {
                    $actionParam = $p
                    break
                }
            }
        }
        $actionValidateSetOk = $false
        if ($actionParam) {
            foreach ($attr in $actionParam.Attributes) {
                if ($attr.TypeName.Name -match 'ValidateSet') {
                    if ($attr.PositionalArguments) {
                        $vals = $attr.PositionalArguments | ForEach-Object { $_.Extent.Text.Trim("'") }
                        $expectedActions = @('InspectDocs','CommitDocs','SyncDryRun','SyncApply','CommitIndex','FinalVerify')
                        $actionValidateSetOk = $true
                        if ($vals.Count -ne $expectedActions.Count) { $actionValidateSetOk = $false }
                        else {
                            for ($v = 0; $v -lt $expectedActions.Count; $v++) {
                                if ($vals[$v] -ne $expectedActions[$v]) { $actionValidateSetOk = $false; break }
                            }
                        }
                    }
                }
            }
        }
        # AST command/function-call inspection for helper filenames
        $helperInvokes = $false
        # Look for the variable-assignment pattern that proves helper delegation
        $assignments = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true)
        $foundVerifyAssign = $false
        $foundSyncAssign = $false
        foreach ($asgn in $assignments) {
            $asgnText = $asgn.Extent.Text
            if ($asgnText -match 'verify_repo_state\.ps1') { $foundVerifyAssign = $true }
            if ($asgnText -match 'sync_phase_index_sha\.ps1') { $foundSyncAssign = $true }
        }
        # Also confirm pwsh is the runner (proves out-of-process execution)
        $allCommands = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true)
        $foundPwsh = $false
        foreach ($cmd in $allCommands) {
            $cmdText = $cmd.GetCommandName()
            if ($cmdText -eq 'pwsh') { $foundPwsh = $true }
        }
        $helperInvokes = ($foundVerifyAssign -and $foundSyncAssign -and $foundPwsh)
        Assert-Condition 'T23' { $paramsMatch -and -not $hasForbiddenParam -and $actionValidateSetOk -and $helperInvokes } "exact public interface and helper delegation"

        # T24: decline/failure report contains checkpoint, Git state, and resume command
        $repo24 = Join-Path $tempDir 'repo24'
        New-TempGitRepo $repo24
        $doc24 = Join-Path $repo24 'world-sim/docs/test.md'
        $null = New-Item -ItemType Directory -Path (Split-Path $doc24) -Force
        [System.IO.File]::WriteAllText($doc24, "# Test`n", [System.Text.UTF8Encoding]::new($false))
        Push-Location $repo24
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        $sha24 = (& git rev-parse HEAD) | Select-Object -First 1
        Push-TempRepoToOrigin $repo24
        [System.IO.File]::WriteAllText((Join-Path $repo24 'unauthorized.txt'), "dirty`n", [System.Text.UTF8Encoding]::new($false))
        Pop-Location
        $queue24 = New-Object System.Collections.Generic.Queue[string]
        $null = $queue24.Enqueue('IGNORE')
        $provider24 = Get-QueueProvider -Queue $queue24
        $proofFile24 = Join-Path $tempBase ("docs_correction_workflow_proof_" + [System.Guid]::NewGuid().ToString('N') + '.txt')
        Push-Location $repo24
        $t24Result = Invoke-Dispatcher -Action 'InspectDocs' -Path 'world-sim/docs/test.md' -ExpectedSha $sha24 -Branch master -Remote origin -ConfirmProvider $provider24 6>$proofFile24
        Pop-Location
        $t24Text = [System.IO.File]::ReadAllText($proofFile24, [System.Text.UTF8Encoding]::new($false))
        $retries = 5
        while ($retries -gt 0) {
            try {
                Remove-Item $proofFile24 -Force -ErrorAction Stop
                break
            } catch {
                $retries--
                if ($retries -gt 0) { Start-Sleep -Milliseconds 100 }
            }
        }
        Assert-Condition 'T24' { $t24Result.ExitCode -eq 2 -and $t24Text -match 'Checkpoint:' -and $t24Text -match 'CurrentHead:' -and $t24Text -match 'ResumeCommand:' } "decline/failure report contains checkpoint, Git state, and resume command"
        Remove-Item (Join-Path $repo24 'unauthorized.txt') -Force

    } finally {
        try { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-Host ''
    Write-Host "Self-test completed: $script:assertCount assertions, $(if ($script:allPassed) { 'all passed' } else { "$($script:failureMessages.Count) failed" })"
    if (-not $script:allPassed) {
        foreach ($msg in $script:failureMessages) {
            Write-Host "  FAILURE: $msg"
        }
        return $script:ExitCodeRed
    }
    Write-Host 'SELF-TEST PASSED'
    return $script:ExitCodeGreen
}

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if ($SelfTest) {
    $code = Run-SelfTest
    exit $code
}

if (-not $Action) {
    Write-Host "ERROR: -Action is required. Use -SelfTest to run the SelfTest." -ForegroundColor Red
    exit 1
}

$confirmProvider = {
    param($PromptText)
    Read-Host $PromptText
}

$result = Invoke-Dispatcher -Action $Action -Path $Path -ExpectedSha $ExpectedSha -CommitMessage $CommitMessage -PhaseId $PhaseId -OldShortSha $OldShortSha -NewFullSha $NewFullSha -PushMode $PushMode -Remote $Remote -Branch $Branch -ConfirmProvider $confirmProvider

exit $result.ExitCode
