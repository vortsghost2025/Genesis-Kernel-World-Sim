#requires -Version 7.0

[CmdletBinding()]
param(
    [string] $PhaseId,
    [string] $OldShortSha,
    [string] $NewFullSha,
    [string] $IndexPath = 'world-sim/docs/phase_index.md',
    [switch] $Apply,
    [switch] $SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ExitCodeGreen = 0
$script:ExitCodeRed = 2
$script:repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..', '..', '..')).Path
if (-not $script:repoRoot) { $script:repoRoot = (Get-Location).Path }

function Write-ErrorAndExit {
    param([string]$Message)
    Write-Host "ERROR: $Message"
    exit $script:ExitCodeRed
}

function Get-FileSha256 {
    param([string]$FilePath)
    $stream = [System.IO.File]::OpenRead($FilePath)
    try {
        $hash = [System.Security.Cryptography.SHA256]::ComputeHash($stream)
        return [BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant()
    } finally { $stream.Close() }
}

function Test-IsValidHex {
    param([string]$Value, [int]$Length)
    return ($Value.Length -eq $Length) -and ($Value -match '^[0-9a-fA-F]+$')
}

function Test-InputFileIntegrity {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        Write-ErrorAndExit "IndexPath not found: $FilePath"
    }
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -eq 0x00) { Write-ErrorAndExit "NUL byte found at offset $i in $FilePath" }
    }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        Write-ErrorAndExit "UTF-8 BOM found in $FilePath"
    }
    for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
        if ($bytes[$i] -eq 0x0D -and $bytes[$i + 1] -eq 0x0A) { Write-ErrorAndExit "CRLF found at byte offset $i in $FilePath" }
    }
    if ($bytes.Length -eq 0 -or $bytes[$bytes.Length - 1] -ne 0x0A) { Write-ErrorAndExit "File does not end with exactly one LF in $FilePath" }
    if ($bytes.Length -ge 2 -and $bytes[$bytes.Length - 2] -eq 0x0A) { Write-ErrorAndExit "Multiple final LFs (trailing blank line) in $FilePath" }
}

function Parse-MarkdownRows {
    param([string]$Content)
    $rows = @()
    foreach ($line in ($Content -split "`n")) {
        if (-not $line.StartsWith('|') -or -not $line.EndsWith('|')) { continue }
        $cells = $line.Split('|')
        $logicalCells = @()
        for ($i = 1; $i -lt $cells.Count - 1; $i++) { $logicalCells += $cells[$i].Trim() }
        if ($logicalCells.Count -ne 6) { continue }
        $rows += [PSCustomObject]@{ RawLine = $line; LogicalCells = $logicalCells }
    }
    return $rows
}

function Find-PhaseRow {
    param([string]$Content, [string]$PhaseId, [string]$ExpectedOldShortSha)
    $rows = Parse-MarkdownRows -Content $Content
    $matchingRows = @()
    foreach ($row in $rows) {
        if ($row.LogicalCells[0].Trim() -eq $PhaseId) { $matchingRows += $row }
    }
    if ($matchingRows.Count -eq 0) { Write-ErrorAndExit "No matching phase row found for PhaseId '$PhaseId'" }
    if ($matchingRows.Count -gt 1) { Write-ErrorAndExit "Multiple matching phase rows found for PhaseId '$PhaseId'" }
    $commitSha = $matchingRows[0].LogicalCells[3].Trim('`').Trim()
    if ($commitSha -ne $ExpectedOldShortSha) { Write-ErrorAndExit "Commit cell '$commitSha' does not match OldShortSha '$ExpectedOldShortSha' for PhaseId '$PhaseId'" }
    return $matchingRows[0]
}

function Build-NewRow {
    param($OriginalRow, [string]$OldShortSha, [string]$NewShortSha)
    $cells = $OriginalRow.LogicalCells
    $newCells = @()
    for ($i = 0; $i -lt 6; $i++) {
        if ($i -eq 3) { $newCells += '`' + $NewShortSha + '`' } else { $newCells += $cells[$i] }
    }
    return '| ' + ($newCells -join ' | ') + ' |'
}

function Apply-Sync {
    param([string]$IndexPath, [string]$OldShortSha, [string]$NewShortSha, [string]$PhaseId)
    if (-not ($IndexPath -is [string])) { $IndexPath = $IndexPath.ToString() }
    if (-not (Test-Path -LiteralPath $IndexPath -PathType Leaf)) { Write-ErrorAndExit "IndexPath not found: $IndexPath" }
    $preflightSha = Get-FileSha256 -FilePath $IndexPath
    $content = [System.IO.File]::ReadAllText($IndexPath, [System.Text.UTF8Encoding]::new($false))
    $targetRow = Find-PhaseRow -Content $content -PhaseId $PhaseId -ExpectedOldShortSha $OldShortSha
    $newRow = Build-NewRow -OriginalRow $targetRow -OldShortSha $OldShortSha -NewShortSha $NewShortSha
    $newContent = $content.Replace($targetRow.RawLine, $newRow)
    if ($newContent -eq $content) { Write-ErrorAndExit "No change made; old and new rows are identical" }
    $beforeRows = Parse-MarkdownRows -Content $content
    $afterRows = Parse-MarkdownRows -Content $newContent
    $beforeTarget = $afterTarget = $null
    foreach ($r in $beforeRows) { if ($r.LogicalCells[0].Trim() -eq $PhaseId) { $beforeTarget = $r } }
    foreach ($r in $afterRows) { if ($r.LogicalCells[0].Trim() -eq $PhaseId) { $afterTarget = $r } }
    for ($i = 0; $i -lt 6; $i++) {
        if ($i -eq 3) { continue }
        if ($beforeTarget.LogicalCells[$i] -ne $afterTarget.LogicalCells[$i]) { Write-ErrorAndExit "Cell index $i changed unexpectedly (not Commit)" }
    }
    if ($afterTarget.LogicalCells[3].Trim('`').Trim() -ne $NewShortSha) { Write-ErrorAndExit "New Commit cell does not contain NewShortSha" }
    $newContentBytes = [System.Text.Encoding]::UTF8.GetBytes($newContent)
    for ($i = 0; $i -lt $newContentBytes.Length - 1; $i++) {
        if ($newContentBytes[$i] -eq 0x0D -and $newContentBytes[$i + 1] -eq 0x0A) { Write-ErrorAndExit "CRLF introduced during write" }
    }
    if ($newContentBytes[$newContentBytes.Length - 1] -ne 0x0A) { Write-ErrorAndExit "Written content does not end with LF" }
    if ((Get-FileSha256 -FilePath $IndexPath) -ne $preflightSha) { Write-ErrorAndExit "FilePath SHA-256 changed between preflight and write" }
    [System.IO.File]::WriteAllBytes($IndexPath, $newContentBytes)
}

function Invoke-SelfTest {
    $tempBase = [System.IO.Path]::GetTempPath()
    $tempDir = Join-Path $tempBase ("sync_phase_index_sha_selftest_" + [System.Guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempDir -Force
    $testScript = Join-Path $tempDir 'sync_phase_index_sha.ps1'
    Copy-Item -LiteralPath $PSCommandPath -Destination $testScript -Force

    $script:assertCount = 0
    $script:allPassed = $true
    $script:failures = @()

    function Assert-Pass {
        param([string]$Name, [bool]$Condition, [string]$Description)
        $script:assertCount++
        if ($Condition) { Write-Host "  [PASS] $Name : $Description" }
        else { Write-Host "  [FAIL] $Name : $Description"; $script:allPassed = $false; $script:failures += $Name }
    }

    function Ensure-Lf {
        param([string]$Content)
        if (-not $Content.EndsWith("`n")) { return $Content + "`n" }
        return $Content
    }

    function New-TempRepo {
        param([string]$RepoDir)
        $null = New-Item -ItemType Directory -Path $RepoDir -Force
        Push-Location $RepoDir
        git init 2>&1 | Out-Null
        git config user.name 'SelfTest' 2>&1 | Out-Null
        git config user.email 'selftest@example.invalid' 2>&1 | Out-Null
        git branch -M master 2>&1 | Out-Null
        Pop-Location
    }

    try {
        $NL = "`n"
        $fixture = Ensure-Lf @'
| Phase | Status | Purpose | Commit | Runtime Impact | Notes |
|---|---|---|---|---|---|
| S01 | Done | A test phase | `abcdef0` | Low | Notes here |
| S02 | Done | Another phase | `1234567` | Medium | More notes |
| S04 | Done | Exact same purpose | `abcdef0` | Low | Different notes here |
'@

        # ST01: valid dry-run
        $p = Join-Path $tempDir 'f01.md'
        [System.IO.File]::WriteAllText($p, $fixture, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $p 2>&1
        Assert-Pass 'ST01' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "valid dry-run returns GREEN and APPLIED:false"

        # ST02: valid apply with Git repo
        $r2 = Join-Path $tempDir 'repo02'
        New-TempRepo $r2
        $af = Join-Path $r2 'phase_index.md'
        [System.IO.File]::WriteAllText($af, ($fixture + "| S02b | Done | Dup phase | `abcdef0` | Low | Dup notes$NL"), [System.Text.UTF8Encoding]::new($false))
        Push-Location $r2; git add . 2>&1 | Out-Null; git commit -m 'init' 2>&1 | Out-Null; Pop-Location
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $af -Apply 2>&1
        Assert-Pass 'ST02' ($LASTEXITCODE -eq 0) "valid apply returns GREEN"
        Assert-Pass 'ST02b' ([System.IO.File]::ReadAllText($af, [System.Text.UTF8Encoding]::new($false)) -match '`1234567890123456789012345678901234567890`') "apply changed Commit to new SHA"

        # ST03: zero matches
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'NONE' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $p 2>&1
        Assert-Pass 'ST03' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "zero matches exits RED"

        # ST04: duplicate matches
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S04' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $af 2>&1
        Assert-Pass 'ST04' ($LASTEXITCODE -eq 2 -and $r -match 'Multiple matching') "duplicate matches exits RED"

        # ST05: substring not confused
        $subPath = Join-Path $tempDir 'sub.md'
        [System.IO.File]::WriteAllText($subPath, (Ensure-Lf ($fixture + "| S010 | Done | Sub | `abcdef0` | Low | Sub notes$NL")), [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $subPath 2>&1
        Assert-Pass 'ST05' ($LASTEXITCODE -eq 0) "exact phase match not confused by substring"

        # ST06: wrong old SHA
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha '0000000' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $p 2>&1
        Assert-Pass 'ST06' ($LASTEXITCODE -eq 2 -and $r -match 'does not match') "wrong old SHA exits RED"

        # ST07: malformed old SHA (6 chars)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcde' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $p 2>&1
        Assert-Pass 'ST07' ($LASTEXITCODE -eq 2) "malformed old SHA (too short) exits RED"

        # ST08: malformed full SHA
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha 'short' -IndexPath $p 2>&1
        Assert-Pass 'ST08' ($LASTEXITCODE -eq 2) "malformed full SHA exits RED"

        # ST09: malformed columns (5 cells)
        $badFix = Ensure-Lf ("| Phase | Status | Purpose | Commit | Runtime Impact |" + "$NL" + "|---|---|---|---|---|---|" + "$NL" + "| BAD1 | Done | Bad | `aaaaaaa` | Low |")
        $badPath = Join-Path $tempDir 'bad.md'
        [System.IO.File]::WriteAllText($badPath, $badFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'BAD1' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $badPath 2>&1
        Assert-Pass 'ST09' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "malformed row (5 cells) exits RED"

        # ST10: old SHA in Notes but not Commit cell
        $noteFix = Ensure-Lf "| TN | Done | Notes SHA | `bbbbbbb` | Low | prev abcdef0 was here |"
        $notePath = Join-Path $tempDir 'note.md'
        [System.IO.File]::WriteAllText($notePath, $noteFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TN' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $notePath 2>&1
        Assert-Pass 'ST10' ($LASTEXITCODE -eq 2 -and $r -match 'does not match') "old SHA in Notes but not Commit exits RED"

        # ST11: exact PhaseId match when SHA appears in another row
        $multiFix = Ensure-Lf ("| M1 | Done | Other | `abcdef0` | Low | NA" + "$NL" + "| M2 | Done | Target | `abcdef0` | Low | NA")
        $multiPath = Join-Path $tempDir 'multi.md'
        [System.IO.File]::WriteAllText($multiPath, $multiFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'M2' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $multiPath 2>&1
        Assert-Pass 'ST11' ($LASTEXITCODE -eq 0) "exact PhaseId match works when old SHA appears in another row"

        # ST12: CRLF rejection
        $crlfBytes = [System.Text.Encoding]::ASCII.GetBytes("| T12 | Done | CRLF | `aaaaaaa` | Low | Notes" + "`r`n")
        $crlfPath = Join-Path $tempDir 'crlf.md'
        [System.IO.File]::WriteAllBytes($crlfPath, $crlfBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T12' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $crlfPath 2>&1
        Assert-Pass 'ST12' ($LASTEXITCODE -eq 2 -and $r -match 'CRLF') "CRLF rejection"

        # ST13: BOM rejection
        $bomBytes = [byte[]](0xEF, 0xBB, 0xBF) + [System.Text.Encoding]::ASCII.GetBytes("| T13 | Done | BOM | `aaaaaaa` | Low | Notes$NL")
        $bomPath = Join-Path $tempDir 'bom.md'
        [System.IO.File]::WriteAllBytes($bomPath, $bomBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T13' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $bomPath 2>&1
        Assert-Pass 'ST13' ($LASTEXITCODE -eq 2 -and $r -match 'BOM') "BOM rejection"

        # ST14: no final LF
        $noLfContent = "| T14 | Done | No LF | `aaaaaaa` | Low | Notes"
        $noLfBytes = [System.Text.Encoding]::UTF8.GetBytes($noLfContent)
        $noLfBytes = $noLfBytes[0..($noLfBytes.Length - 2)]
        $noLfPath = Join-Path $tempDir 'nolf.md'
        [System.IO.File]::WriteAllBytes($noLfPath, $noLfBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T14' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $noLfPath 2>&1
        Assert-Pass 'ST14' ($LASTEXITCODE -eq 2 -and $r -match 'does not end with exactly one LF') "no final LF exits RED"

        # ST15: no-op dry-run
        $noopSha = 'aaaaaaa' + '0' * 33
        $noopFix = Ensure-Lf "| T15 | Done | No-op | `aaaaaaa` | Low | Notes"
        $noopPath = Join-Path $tempDir 'noop.md'
        [System.IO.File]::WriteAllText($noopPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopPath 2>&1
        Assert-Pass 'ST15' ($LASTEXITCODE -eq 0) "no-op dry-run returns GREEN"

        # ST16: no-op apply with Git repo
        $noopRepo = Join-Path $tempDir 'nooprepo'
        New-TempRepo $noopRepo
        $noopAppPath = Join-Path $noopRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($noopAppPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        Push-Location $noopRepo; git add . 2>&1 | Out-Null; git commit -m 'init' 2>&1 | Out-Null; Pop-Location
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopAppPath -Apply 2>&1
        Assert-Pass 'ST16' ($LASTEXITCODE -eq 0) "no-op apply returns GREEN"

        # ST17: long cells preserved (Git repo)
        $longRepo = Join-Path $tempDir 'longrepo'
        New-TempRepo $longRepo
        $LongAppPath = Join-Path $longRepo 'phase_index.md'
        $longP = "A" * 500; $longR = "B" * 500; $longN = "C" * 500
        $longFix = Ensure-Lf "| T17 | Done | $longP | `aaaaaaa` | $longR | $longN |"
        [System.IO.File]::WriteAllText($LongAppPath, $longFix, [System.Text.UTF8Encoding]::new($false))
        Push-Location $longRepo; git add . 2>&1 | Out-Null; git commit -m 'init' 2>&1 | Out-Null; Pop-Location
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T17' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $LongAppPath -Apply 2>&1
        Assert-Pass 'ST17' ($LASTEXITCODE -eq 0) "long cells preserved after apply"
        Assert-Pass 'ST17b' ([System.IO.File]::ReadAllText($LongAppPath, [System.Text.UTF8Encoding]::new($false)) -match "A{500}") "long Purpose preserved"
        Assert-Pass 'ST17c' ([System.IO.File]::ReadAllText($LongAppPath, [System.Text.UTF8Encoding]::new($false)) -match "B{500}") "long Runtime Impact preserved"
        Assert-Pass 'ST17d' ([System.IO.File]::ReadAllText($LongAppPath, [System.Text.UTF8Encoding]::new($false)) -match "C{500}") "long Notes preserved"

        # ST18: byte preservation (Git repo)
        $byteRepo = Join-Path $tempDir 'byterepo'
        New-TempRepo $byteRepo
        $byteAppPath = Join-Path $byteRepo 'phase_index.md'
        $byteFix = Ensure-Lf "| T18 | Done | Byte test | `aaaaaaa` | Low | Notes"
        [System.IO.File]::WriteAllText($byteAppPath, $byteFix, [System.Text.UTF8Encoding]::new($false))
        Push-Location $byteRepo; git add . 2>&1 | Out-Null; git commit -m 'init' 2>&1 | Out-Null; Pop-Location
        $beforeBytes = [System.IO.File]::ReadAllBytes($byteAppPath)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T18' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $byteAppPath -Apply 2>&1
        Assert-Pass 'ST18' ($LASTEXITCODE -eq 0) "apply returns GREEN for byte preservation"
        $afterBytes = [System.IO.File]::ReadAllBytes($byteAppPath)
        $beforeStr = [System.Text.Encoding]::UTF8.GetString($beforeBytes)
        $afterStr = [System.Text.Encoding]::UTF8.GetString($afterBytes)
        $ic = 0; $ml = [Math]::Min($beforeStr.Length, $afterStr.Length)
        for ($bi = 0; $bi -lt $ml; $bi++) { if ($beforeStr[$bi] -eq $afterStr[$bi]) { $ic++ } }
        Assert-Pass 'ST18b' (($beforeStr.Length - $ic) -le 10) "only target bytes changed"

    } finally {
        try { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-Host ''
    Write-Host "Self-test completed: $script:assertCount assertions, $(if ($script:allPassed) { 'all passed' } else { "$($script:failures.Count) failed" })"
    if (-not $script:allPassed) { foreach ($msg in $script:failures) { Write-Host "  FAILURE: $msg" } }
    return $(if ($script:allPassed) { $script:ExitCodeGreen } else { $script:ExitCodeRed })
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

if ($SelfTest) { $code = Invoke-SelfTest; exit $code }

if ([string]::IsNullOrEmpty($PhaseId)) { Write-ErrorAndExit 'PhaseId must be non-empty' }
if (-not (Test-IsValidHex -Value $OldShortSha -Length 7)) { Write-ErrorAndExit "OldShortSha must be exactly seven hexadecimal characters, got '$OldShortSha'" }
if (-not (Test-IsValidHex -Value $NewFullSha -Length 40)) { Write-ErrorAndExit "NewFullSha must be exactly forty hexadecimal characters, got '$NewFullSha'" }

$NewShortSha = $NewFullSha.Substring(0, 7)

$resolvedIndexPath = Resolve-Path -LiteralPath $IndexPath -ErrorAction SilentlyContinue
if (-not $resolvedIndexPath) { Write-ErrorAndExit "IndexPath not found or not a file: $IndexPath" }

Test-InputFileIntegrity -FilePath $resolvedIndexPath
$content = [System.IO.File]::ReadAllText($resolvedIndexPath, [System.Text.UTF8Encoding]::new($false))

$targetRow = Find-PhaseRow -Content $content -PhaseId $PhaseId -ExpectedOldShortSha $OldShortSha
Write-Host "Found phase row: $($targetRow.RawLine)"
Write-Host "OLD COMMIT: $OldShortSha"
Write-Host "NEW COMMIT: $NewShortSha"

if ($OldShortSha -eq $NewShortSha) { Write-Host "APPLIED: false"; Write-Host "GREEN"; exit $script:ExitCodeGreen }

if (-not $Apply) {
    $newRow = Build-NewRow -OriginalRow $targetRow -OldShortSha $OldShortSha -NewShortSha $NewShortSha
    Write-Host "BEFORE: $($targetRow.RawLine)"
    Write-Host "AFTER:  $newRow"
    Write-Host "APPLIED: false"
    exit $script:ExitCodeGreen
}

$branch = & git rev-parse --abbrev-ref HEAD 2>&1
if ($branch -ne 'master') { Write-ErrorAndExit "Apply requires branch master, current is '$branch'" }
$status = & git status -sb 2>&1
if ($status) { Write-ErrorAndExit "Apply requires clean tree, found: $status" }
try { $null = & git ls-files --error-unmatch $IndexPath 2>&1 } catch { Write-ErrorAndExit "IndexPath '$IndexPath' is not tracked by Git" }
$numstatUnstaged = @(git diff --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$numstatCached = @(git diff --cached --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($numstatUnstaged.Count -gt 0 -or $numstatCached.Count -gt 0) { Write-ErrorAndExit "Apply requires no staged or unstaged changes" }
$localHead = & git rev-parse HEAD 2>&1
$remoteHead = & git rev-parse origin/master 2>&1
if ($localHead -ne $remoteHead) { Write-ErrorAndExit "Apply requires local HEAD to equal origin/master" }
$lsRemoteHead = (& git ls-remote origin refs/heads/master 2>&1).Split()[0]
if ($lsRemoteHead -ne $localHead) { Write-ErrorAndExit "Apply requires git ls-remote to equal local HEAD" }
$preflightSha = Get-FileSha256 -FilePath $resolvedIndexPath
$currentSha = Get-FileSha256 -FilePath $resolvedIndexPath
if ($currentSha -ne $preflightSha) { Write-ErrorAndExit "FilePath SHA-256 changed between preflight and write" }

Apply-Sync -IndexPath $resolvedIndexPath -OldShortSha $OldShortSha -NewShortSha $NewShortSha -PhaseId $PhaseId
Write-Host "APPLIED: true"
Write-Host "GREEN"
exit $script:ExitCodeGreen
