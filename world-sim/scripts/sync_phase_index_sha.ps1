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

# ---------------------------------------------------------------------------
# Resolve repo root and validate IndexPath containment (Defect 4)
# Note: repoRoot is resolved after IndexPath is resolved, from the IndexPath's directory
# ---------------------------------------------------------------------------

$script:repoRoot = $null

function Write-ErrorAndExit {
    param([string]$Message)
    Write-Host "ERROR: $Message"
    exit $script:ExitCodeRed
}

function Get-FileSha256 {
    param([string]$FilePath)
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return [BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant()
}

# ---------------------------------------------------------------------------
# Input normalization (Defect 3)
# ---------------------------------------------------------------------------

function Normalize-PhaseId {
    param([string]$Value)
    return $Value.Trim()
}

function Normalize-ShortSha {
    param([string]$Value)
    return $Value.Trim().ToLowerInvariant()
}

function Normalize-FullSha {
    param([string]$Value)
    return $Value.Trim().ToLowerInvariant()
}

# ---------------------------------------------------------------------------
# Strict Commit-cell grammar (Defect 2)
# ---------------------------------------------------------------------------

function Test-RawCommitCell {
    param([string]$RawCell)
    $pattern = '^\s*`[0-9a-f]{7}`\s*$'
    return ($RawCell -cmatch $pattern)
}

function Test-IsValidHex {
    param(
        [string]$Value,
        [int]$Length
    )
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    if ($Value.Length -ne $Length) { return $false }
    $hexPattern = '^[0-9a-fA-F]{' + $Length + '}$'
    return ($Value -match $hexPattern)
}

# ---------------------------------------------------------------------------
# UTF-8 validation (Defect 7)
# ---------------------------------------------------------------------------

function Test-ValidUtf8 {
    param([string]$FilePath)
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    try {
        $null = [System.Text.Encoding]::UTF8.GetString($bytes)
        # Additional check: decode with the throwing decoder
        $decoder = [System.Text.UTF8Encoding]::new($false, $true).GetDecoder()
        $charCount = $decoder.GetCharCount($bytes, 0, $bytes.Length)
        return $true
    } catch {
        return $false
    }
}

function Test-InputFileIntegrity {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        Write-ErrorAndExit "IndexPath not found: $FilePath"
    }
    # Strict UTF-8 validation
    if (-not (Test-ValidUtf8 -FilePath $FilePath)) {
        Write-ErrorAndExit "Invalid UTF-8 encoding in $FilePath"
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
    $rawCommitCell = $matchingRows[0].LogicalCells[3]
    if (-not (Test-RawCommitCell -RawCell $rawCommitCell)) { Write-ErrorAndExit "Commit cell does not match required grammar: $rawCommitCell" }
    $commitSha = $rawCommitCell.Trim('`').Trim()
    if ($commitSha -ne $ExpectedOldShortSha) { Write-ErrorAndExit "Commit cell '$commitSha' does not match OldShortSha '$ExpectedOldShortSha' for PhaseId '$PhaseId'" }
    return $matchingRows[0]
}

# ---------------------------------------------------------------------------
# Span-only replacement (Defect 1)
# ---------------------------------------------------------------------------

function Invoke-SpanReplacement {
    param([string]$RawLine, [string]$OldSha, [string]$NewSha)
    $shaIdx = $RawLine.IndexOf($OldSha)
    if ($shaIdx -eq -1) { Write-ErrorAndExit "SHA '$OldSha' not found in raw line for span replacement" }
    $before = $RawLine.Substring(0, $shaIdx)
    $after = $RawLine.Substring($shaIdx + 7)
    $newLine = $before + $NewSha + $after
    if ($newLine.Length -ne $RawLine.Length) { Write-ErrorAndExit "Span replacement produced different length" }
    if ($newLine.Substring($shaIdx, 7) -ne $NewSha) { Write-ErrorAndExit "Span replacement SHA mismatch" }
    if ($shaIdx -gt 0 -and $newLine.Substring(0, $shaIdx) -ne $RawLine.Substring(0, $shaIdx)) { Write-ErrorAndExit "Span replacement corrupted before-SHA content" }
    $afterLen = $RawLine.Length - $shaIdx - 7
    if ($afterLen -gt 0 -and $newLine.Substring($shaIdx + 7, $afterLen) -ne $RawLine.Substring($shaIdx + 7, $afterLen)) { Write-ErrorAndExit "Span replacement corrupted after-SHA content" }
    return $newLine
}

function Confirm-OnlyCommitChanged {
    param([string]$OldContent, [string]$NewContent, [string]$PhaseId)
    $oldRows = Parse-MarkdownRows -Content $OldContent
    $newRows = Parse-MarkdownRows -Content $NewContent
    if ($oldRows.Count -ne $newRows.Count) { Write-ErrorAndExit "Row count changed during replacement" }
    $oldTarget = $null; $newTarget = $null
    foreach ($r in $oldRows) { if ($r.LogicalCells[0].Trim() -eq $PhaseId) { $oldTarget = $r } }
    foreach ($r in $newRows) { if ($r.LogicalCells[0].Trim() -eq $PhaseId) { $newTarget = $r } }
    for ($i = 0; $i -lt 6; $i++) {
        if ($i -eq 3) { continue }
        if ($oldTarget.LogicalCells[$i] -ne $newTarget.LogicalCells[$i]) { Write-ErrorAndExit "Cell index $i changed unexpectedly (not Commit)" }
    }
}

function Invoke-PostWriteValidation {
    param([string]$FilePath, [string]$ExpectedContent, [int]$ExpectedLength)
    $writtenBytes = [System.IO.File]::ReadAllBytes($FilePath)
    if ($writtenBytes.Length -ne $ExpectedLength) { Write-ErrorAndExit "Written byte count mismatch" }
    $writtenStr = [System.Text.Encoding]::UTF8.GetString($writtenBytes)
    if ($writtenStr -ne $ExpectedContent) { Write-ErrorAndExit "Written content string mismatch" }
    for ($i = 0; $i -lt $writtenBytes.Length - 1; $i++) {
        if ($writtenBytes[$i] -eq 0x0D -and $writtenBytes[$i + 1] -eq 0x0A) { Write-ErrorAndExit "CRLF in written file" }
    }
    if ($writtenBytes[$writtenBytes.Length - 1] -ne 0x0A) { Write-ErrorAndExit "Written content does not end with LF" }
    # Verify written bytes match expected content bytes exactly
    $expectedBytes = [System.Text.Encoding]::UTF8.GetBytes($ExpectedContent)
    if ($writtenBytes.Length -ne $expectedBytes.Length) { Write-ErrorAndExit "Written file byte length does not match expected content" }
    for ($i = 0; $i -lt $writtenBytes.Length; $i++) {
        if ($writtenBytes[$i] -ne $expectedBytes[$i]) { Write-ErrorAndExit "Written file byte $i mismatch" }
    }
}

# ---------------------------------------------------------------------------
# Apply safety checks (Defects 4, 5)
# ---------------------------------------------------------------------------

function Invoke-ApplySafetyChecks {
    param([string]$ResolvedIndexPath, [string]$RepoRoot, [string]$IndexPath)
    $branch = & git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>&1
    if ($branch -ne 'master') { Write-ErrorAndExit "Apply requires branch master, current is '$branch'" }
    $status = & git -C $RepoRoot status --porcelain 2>&1
    if ($status) { Write-ErrorAndExit "Apply requires clean tree, found: $status" }
    $numstatUnstaged = @(git -C $RepoRoot diff --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $numstatCached = @(git -C $RepoRoot diff --cached --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($numstatUnstaged.Count -gt 0 -or $numstatCached.Count -gt 0) { Write-ErrorAndExit "Apply requires no staged or unstaged changes" }
    # Verify IndexPath is tracked
    try { $null = & git -C $RepoRoot ls-files --error-unmatch $IndexPath 2>&1 } catch { Write-ErrorAndExit "IndexPath '$IndexPath' is not tracked by Git" }
    # Verify IndexPath is under repo root
    $normIndexPath = $ResolvedIndexPath.Replace('\', '/').ToLowerInvariant()
    $normRepoRoot = $RepoRoot.Replace('\', '/').ToLowerInvariant()
    if (-not $normIndexPath.StartsWith($normRepoRoot + '/')) {
        Write-ErrorAndExit "IndexPath is not inside the repository root"
    }
    # Require origin (Defect 5)
    $originUrl = & git -C $RepoRoot remote get-url origin 2>&1
    if ($LASTEXITCODE -ne 0) { Write-ErrorAndExit "Apply requires an origin remote" }
    $remoteHead = & git -C $RepoRoot rev-parse origin/master 2>&1
    if ($LASTEXITCODE -ne 0) { Write-ErrorAndExit "Apply requires origin/master to exist" }
    $localHead = & git -C $RepoRoot rev-parse HEAD 2>&1
    if ($localHead -ne $remoteHead) { Write-ErrorAndExit "Apply requires local HEAD to equal origin/master" }
    $lsRemoteOutput = & git -C $RepoRoot ls-remote origin refs/heads/master 2>&1
    $lsRemoteLines = @($lsRemoteOutput | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lsRemoteLines.Count -ne 1) { Write-ErrorAndExit "Apply requires exactly one master row from ls-remote" }
    $lsRemoteSha = ($lsRemoteLines[0] -split "`t")[0]
    if ($lsRemoteSha -ne $localHead) { Write-ErrorAndExit "Apply requires ls-remote SHA to equal local HEAD" }
}

function Invoke-ApplyWrite {
    param([string]$ResolvedIndexPath, [string]$NewContent, [int]$NewLength, [string]$PreflightSha)
    $newBytes = [System.Text.Encoding]::UTF8.GetBytes($NewContent)
    [System.IO.File]::WriteAllBytes($ResolvedIndexPath, $newBytes)
    Invoke-PostWriteValidation -FilePath $ResolvedIndexPath -ExpectedContent $NewContent -ExpectedLength $NewLength
}

# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

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
        param([string]$Name, [bool]$Condition, [string]$Description, $DebugOutput = $null)
        $script:assertCount++
        if ($Condition) { Write-Host "  [PASS] $Name : $Description" }
        else { Write-Host "  [FAIL] $Name : $Description"; if ($DebugOutput) { Write-Host "    DEBUG OUTPUT:"; $DebugOutput | ForEach-Object { Write-Host "      $_" } }; $script:allPassed = $false; $script:failures += $Name }
    }

    function Ensure-Lf {
        param([string]$Content)
        if (-not $Content.EndsWith("`n")) { return $Content + "`n" }
        return $Content
    }

    function New-TempRepo {
        param([string]$RepoDir, [bool]$WithOrigin = $true)
        $null = New-Item -ItemType Directory -Path $RepoDir -Force
        Push-Location $RepoDir
        git init 2>&1 | Out-Null
        git config user.name 'SelfTest' 2>&1 | Out-Null
        git config user.email 'selftest@example.invalid' 2>&1 | Out-Null
        git branch -M master 2>&1 | Out-Null
        if ($WithOrigin) {
            # Create bare origin OUTSIDE the worktree to avoid untracked files
            $bareDir = Join-Path ([System.IO.Path]::GetDirectoryName($RepoDir)) ([System.IO.Path]::GetFileName($RepoDir) + '_bare.git')
            git init --bare $bareDir 2>&1 | Out-Null
            git remote add origin $bareDir 2>&1 | Out-Null
        }
        Pop-Location
    }

    function Push-InitialCommit {
        param([string]$RepoDir)
        Push-Location $RepoDir
        git add . 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        git push -u origin master 2>&1 | Out-Null
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

        # ST02: valid apply with Git repo + temp origin
        $r2 = Join-Path $tempDir 'repo02'
        New-TempRepo $r2
        $af = Join-Path $r2 'phase_index.md'
        [System.IO.File]::WriteAllText($af, ($fixture + '| S02b | Done | Dup phase | `abcdef0` | Low | Dup notes' + $NL), [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $r2
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $af -Apply 2>&1
        Assert-Pass 'ST02' ($LASTEXITCODE -eq 0) "valid apply returns GREEN" $r
        Assert-Pass 'ST02b' ([System.IO.File]::ReadAllText($af, [System.Text.UTF8Encoding]::new($false)) -match '`1234567`') "apply changed Commit to new SHA"

        # ST03: zero matches
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'NONE' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $p 2>&1
        Assert-Pass 'ST03' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "zero matches exits RED"

        # ST04: duplicate matches
        $dupFix = Ensure-Lf ('| DUP | Done | First | `abcdef0` | Low | NA |' + $NL + '| DUP | Done | Second | `1234567` | Low | NA |')
        $dupPath = Join-Path $tempDir 'dup.md'
        [System.IO.File]::WriteAllText($dupPath, $dupFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'DUP' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $dupPath 2>&1
        Assert-Pass 'ST04' ($LASTEXITCODE -eq 2 -and $r -match 'Multiple matching') "duplicate matches exits RED" $r

        # ST05: substring-only fixture (S010 exists but not S01; S01 returns RED)
        $subOnlyFix = Ensure-Lf ('| S010 | Done | Sub | `abcdef0` | Low | Sub notes |' + $NL + '| S02 | Done | Other | `1234567` | Low | Other notes |')
        $subOnlyPath = Join-Path $tempDir 'subonly.md'
        [System.IO.File]::WriteAllText($subOnlyPath, $subOnlyFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $subOnlyPath 2>&1
        Assert-Pass 'ST05' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "substring-only S01 (no exact S01) returns RED" $r

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
        $badFix = Ensure-Lf ('| Phase | Status | Purpose | Commit | Runtime Impact |' + $NL + '|---|---|---|---|---|---|' + $NL + '| BAD1 | Done | Bad | `aaaaaaa` | Low |')
        $badPath = Join-Path $tempDir 'bad.md'
        [System.IO.File]::WriteAllText($badPath, $badFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'BAD1' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $badPath 2>&1
        Assert-Pass 'ST09' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "malformed row (5 cells) exits RED"

        # ST10: old SHA in Notes but not Commit cell
        $noteFix = Ensure-Lf '| TN | Done | Notes SHA | `bbbbbbb` | Low | prev abcdef0 was here |'
        $notePath = Join-Path $tempDir 'note.md'
        [System.IO.File]::WriteAllText($notePath, $noteFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TN' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $notePath 2>&1
        Assert-Pass 'ST10' ($LASTEXITCODE -eq 2 -and $r -match 'does not match') "old SHA in Notes but not Commit exits RED"

        # ST11: same old SHA in another row; Apply changes only the target row
        $multiFix = Ensure-Lf ('| M1 | Done | Other | `abcdef0` | Low | NA |' + $NL + '| M2 | Done | Target | `abcdef0` | Low | NA |')
        $multiRepo = Join-Path $tempDir 'multirepo'
        New-TempRepo $multiRepo
        $multiPath = Join-Path $multiRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($multiPath, $multiFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $multiRepo
        $beforeMultiContent = [System.IO.File]::ReadAllText($multiPath, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'M2' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $multiPath -Apply 2>&1
        Assert-Pass 'ST11' ($LASTEXITCODE -eq 0) "apply with same SHA in another row returns GREEN" $r
        $afterMultiContent = [System.IO.File]::ReadAllText($multiPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST11b' ($afterMultiContent -match '\| M1 \| Done \| Other \| `abcdef0` \| Low \| NA \|') "M1 row unchanged" $r
        Assert-Pass 'ST11c' ($afterMultiContent -match '\| M2 \| Done \| Target \| `1234567` \| Low \| NA \|') "M2 row updated" $r

        # ST12: CRLF rejection
        $crlfBytes = [System.Text.Encoding]::ASCII.GetBytes(('| T12 | Done | CRLF | ' + '`aaaaaaa`' + ' | Low | Notes |') + "`r`n")
        $crlfPath = Join-Path $tempDir 'crlf.md'
        [System.IO.File]::WriteAllBytes($crlfPath, $crlfBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T12' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $crlfPath 2>&1
        Assert-Pass 'ST12' ($LASTEXITCODE -eq 2 -and $r -match 'CRLF') "CRLF rejection"

        # ST13: BOM rejection
        $bomBytes = [byte[]](0xEF, 0xBB, 0xBF) + [System.Text.Encoding]::ASCII.GetBytes(('| T13 | Done | BOM | ' + '`aaaaaaa`' + ' | Low | Notes |' + $NL))
        $bomPath = Join-Path $tempDir 'bom.md'
        [System.IO.File]::WriteAllBytes($bomPath, $bomBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T13' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $bomPath 2>&1
        Assert-Pass 'ST13' ($LASTEXITCODE -eq 2 -and $r -match 'BOM') "BOM rejection"

        # ST14: missing final LF
        $noLfContent = '| T14 | Done | No LF | `aaaaaaa` | Low | Notes |'
        $noLfBytes = [System.Text.Encoding]::UTF8.GetBytes($noLfContent)
        $noLfPath = Join-Path $tempDir 'nolf.md'
        [System.IO.File]::WriteAllBytes($noLfPath, $noLfBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T14' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $noLfPath 2>&1
        Assert-Pass 'ST14' ($LASTEXITCODE -eq 2 -and $r -match 'does not end with exactly one LF') "missing final LF exits RED"

        # ST14b: multiple final LFs
        $multiLfContent = '| T14b | Done | Multi LF | `aaaaaaa` | Low | Notes |' + $NL + $NL
        $multiLfBytes = [System.Text.Encoding]::UTF8.GetBytes($multiLfContent)
        $multiLfPath = Join-Path $tempDir 'multilf.md'
        [System.IO.File]::WriteAllBytes($multiLfPath, $multiLfBytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T14b' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $multiLfPath 2>&1
        Assert-Pass 'ST14b' ($LASTEXITCODE -eq 2 -and $r -match 'Multiple final LFs') "multiple final LFs exits RED"

        # ST15: no-op dry-run (still must pass safety checks, but not -Apply)
        $noopSha = 'aaaaaaa' + '0' * 33
        $noopFix = Ensure-Lf '| T15 | Done | No-op | `aaaaaaa` | Low | Notes |'
        $noopPath = Join-Path $tempDir 'noop.md'
        [System.IO.File]::WriteAllText($noopPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopPath 2>&1
        Assert-Pass 'ST15' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "no-op dry-run returns GREEN and APPLIED:false" $r

        # ST16: no-op Apply on clean aligned repo
        $noopRepo = Join-Path $tempDir 'nooprepo'
        New-TempRepo $noopRepo
        $noopAppPath = Join-Path $noopRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($noopAppPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $noopRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopAppPath -Apply 2>&1
        Assert-Pass 'ST16' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "no-op Apply on clean repo returns GREEN and APPLIED:false" $r

        # ST17: long cells preserved (Git repo)
        $longRepo = Join-Path $tempDir 'longrepo'
        New-TempRepo $longRepo
        $LongAppPath = Join-Path $longRepo 'phase_index.md'
        $longP = "A" * 500; $longR = "B" * 500; $longN = "C" * 500
        $longFix = Ensure-Lf ("| T17 | Done | $longP | " + '`aaaaaaa`' + " | $longR | $longN |")
        [System.IO.File]::WriteAllText($LongAppPath, $longFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $longRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T17' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $LongAppPath -Apply 2>&1
        Assert-Pass 'ST17' ($LASTEXITCODE -eq 0) "long cells preserved after apply" $r
        $afterLong = [System.IO.File]::ReadAllText($LongAppPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST17b' ($afterLong -match "A{500}") "long Purpose preserved"
        Assert-Pass 'ST17c' ($afterLong -match "B{500}") "long Runtime Impact preserved"
        Assert-Pass 'ST17d' ($afterLong -match "C{500}") "long Notes preserved"

        # ST18: exact byte preservation (Git repo)
        $byteRepo = Join-Path $tempDir 'byterepo'
        New-TempRepo $byteRepo
        $byteAppPath = Join-Path $byteRepo 'phase_index.md'
        $byteFix = Ensure-Lf '| T18 | Done | Byte test | `aaaaaaa` | Low | Notes |'
        [System.IO.File]::WriteAllText($byteAppPath, $byteFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $byteRepo
        $beforeBytes = [System.IO.File]::ReadAllBytes($byteAppPath)
        $beforeLen = $beforeBytes.Length
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T18' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $byteAppPath -Apply 2>&1
        Assert-Pass 'ST18' ($LASTEXITCODE -eq 0) "apply returns GREEN for byte preservation" $r
        $afterBytes = [System.IO.File]::ReadAllBytes($byteAppPath)
        Assert-Pass 'ST18b' ($afterBytes.Length -eq $beforeLen) "byte count unchanged"
        $diffCount = 0
        for ($bi = 0; $bi -lt $beforeLen; $bi++) { if ($beforeBytes[$bi] -ne $afterBytes[$bi]) { $diffCount++ } }
        Assert-Pass 'ST18c' ($diffCount -eq 7) "exactly 7 bytes differ (7 SHA chars replaced)"

        # ST19: irregular spacing preserved
        $irregFix = Ensure-Lf '|T19 |  Done  |  Irregular  |  `aaaaaaa`  |  Low  |  Spacing |'
        $irregRepo = Join-Path $tempDir 'irregrepo'
        New-TempRepo $irregRepo
        $irregPath = Join-Path $irregRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($irregPath, $irregFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $irregRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T19' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $irregPath -Apply 2>&1
        Assert-Pass 'ST19' ($LASTEXITCODE -eq 0) "irregular spacing apply returns GREEN" $r
        $afterIrreg = [System.IO.File]::ReadAllText($irregPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST19b' ($afterIrreg -match '^\|T19 \|  Done  \|  Irregular  \|  `1234567`  \|  Low  \|  Spacing \|') "irregular spacing preserved" $afterIrreg

        # ST20: unwrapped Commit-cell SHA (no backticks) returns RED
        $unwrappedFix = Ensure-Lf '| TW | Done | Unwrapped | abcdef0 | Low | Notes |'
        $unwrappedPath = Join-Path $tempDir 'unwrapped.md'
        [System.IO.File]::WriteAllText($unwrappedPath, $unwrappedFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TW' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $unwrappedPath 2>&1
        Assert-Pass 'ST20' ($LASTEXITCODE -eq 2 -and $r -match 'Commit cell does not match required grammar') "unwrapped Commit-cell SHA returns RED" $r

        # ST21: uppercase Commit-cell SHA returns RED
        $upperFix = Ensure-Lf '| TU | Done | Upper | `ABCDEF0` | Low | Notes |'
        $upperPath = Join-Path $tempDir 'upper.md'
        [System.IO.File]::WriteAllText($upperPath, $upperFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TU' -OldShortSha 'ABCDEF0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $upperPath 2>&1
        Assert-Pass 'ST21' ($LASTEXITCODE -eq 2 -and $r -match 'Commit cell does not match required grammar') "uppercase Commit-cell SHA returns RED" $r

        # ST22: uppercase input SHAs normalize correctly — ABCDEF0 normalizes to abcdef0, matches cell
        $normFix = Ensure-Lf '| TN2 | Done | Normalize | `abcdef0` | Low | Notes |'
        $normPath = Join-Path $tempDir 'norm.md'
        [System.IO.File]::WriteAllText($normPath, $normFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TN2' -OldShortSha 'ABCDEF0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $normPath 2>&1
        Assert-Pass 'ST22' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "uppercase OldShortSha normalized; ABCDEF0 matches abcdef0 returns GREEN" $r

        # ST23: invalid UTF-8 returns RED
        $invalidUtf8Bytes = [byte[]](0x60, 0x61, 0xFF, 0xFE, 0x62)
        $invalidUtf8Path = Join-Path $tempDir 'invalidutf8.md'
        [System.IO.File]::WriteAllBytes($invalidUtf8Path, $invalidUtf8Bytes)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'X' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $invalidUtf8Path 2>&1
        Assert-Pass 'ST23' ($LASTEXITCODE -eq 2 -and $r -match 'Invalid UTF-8') "invalid UTF-8 returns RED" $r

        # ST24: IndexPath outside the repository returns RED
        $outsidePath = Join-Path $tempDir 'outside.md'
        [System.IO.File]::WriteAllText($outsidePath, $fixture, [System.Text.UTF8Encoding]::new($false))
        $outsideRepo = Join-Path $tempDir 'outsiderepo'
        New-TempRepo $outsideRepo
        Push-InitialCommit $outsideRepo
        Push-Location $outsideRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $outsidePath -Apply 2>&1
        Pop-Location
        Assert-Pass 'ST24' ($LASTEXITCODE -eq 2 -and $r -match 'not inside the repository') "IndexPath outside repo returns RED" $r

        # ST25: invocation from outside the repo still checks the correct repo
        $invRepo = Join-Path $tempDir 'invrepo'
        New-TempRepo $invRepo
        $invPath = Join-Path $invRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($invPath, $fixture, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $invRepo
        Push-Location $tempDir
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $invPath -Apply 2>&1
        Pop-Location
        Assert-Pass 'ST25' ($LASTEXITCODE -eq 0) "invocation from outside repo applies correctly" $r
        $afterInv = [System.IO.File]::ReadAllText($invPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST25b' ($afterInv -match '`1234567`') "file updated from outside invocation"

        # ST26: Apply with no origin returns RED
        $noOriginRepo = Join-Path $tempDir 'nooriginrepo'
        New-TempRepo $noOriginRepo -WithOrigin $false
        $noOriginPath = Join-Path $noOriginRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($noOriginPath, $fixture, [System.Text.UTF8Encoding]::new($false))
        Push-Location $noOriginRepo; git add . 2>&1 | Out-Null; git commit -m 'init' 2>&1 | Out-Null; Pop-Location
        Push-Location $noOriginRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $noOriginPath -Apply 2>&1
        Pop-Location
        Assert-Pass 'ST26' ($LASTEXITCODE -eq 2 -and $r -match 'origin') "Apply with no origin returns RED" $r

        # ST27: no-op Apply on dirty tree returns RED
        $dirtyRepo = Join-Path $tempDir 'dirtyrepo'
        New-TempRepo $dirtyRepo
        $dirtyPath = Join-Path $dirtyRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($dirtyPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $dirtyRepo
        # Create a dirty state by adding an untracked file
        Set-Content -Path (Join-Path $dirtyRepo 'untracked.txt') -Value 'dirty'
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $dirtyPath -Apply 2>&1
        Assert-Pass 'ST27' ($LASTEXITCODE -eq 2 -and $r -match 'clean tree') "no-op Apply on dirty tree returns RED" $r

        # ST28: no-op Apply on clean aligned repo (already ST16, add explicit APPLIED:false check)
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopAppPath -Apply 2>&1
        Assert-Pass 'ST28' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "no-op Apply on clean aligned returns APPLIED:false" $r

    } finally {
        try { Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-Host ''
    Write-Host "Self-test completed: $script:assertCount assertions, $(if ($script:allPassed) { 'all passed' } else { "$($script:failures.Count) failed" })"
    if (-not $script:allPassed) { foreach ($msg in $script:failures) { Write-Host "  FAILURE: $msg" } }
    if ($script:allPassed) { Write-Host 'SELF-TEST PASSED' }
    return $(if ($script:allPassed) { $script:ExitCodeGreen } else { $script:ExitCodeRed })
}

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

if ($SelfTest) { $code = Invoke-SelfTest; exit $code }

# --- Normalize inputs (Defect 3) ---
if ([string]::IsNullOrEmpty($PhaseId)) { Write-ErrorAndExit 'PhaseId must be non-empty' }
$PhaseId = Normalize-PhaseId -Value $PhaseId
if (-not (Test-IsValidHex -Value $OldShortSha -Length 7)) { Write-ErrorAndExit "OldShortSha must be exactly seven hexadecimal characters, got '$OldShortSha'" }
$OldShortSha = Normalize-ShortSha -Value $OldShortSha
if (-not (Test-IsValidHex -Value $NewFullSha -Length 40)) { Write-ErrorAndExit "NewFullSha must be exactly forty hexadecimal characters, got '$NewFullSha'" }
$NewFullSha = Normalize-FullSha -Value $NewFullSha
$NewShortSha = $NewFullSha.Substring(0, 7).ToLowerInvariant()

# --- Resolve IndexPath and validate containment (Defect 4) ---
$resolvedIndexPath = Resolve-Path -LiteralPath $IndexPath -ErrorAction SilentlyContinue
if (-not $resolvedIndexPath) { Write-ErrorAndExit "IndexPath not found or not a file: $IndexPath" }
$resolvedIndexPath = $resolvedIndexPath.Path

Test-InputFileIntegrity -FilePath $resolvedIndexPath

# Resolve repo root: try IndexPath directory first, then cwd
# Only needed for Apply mode
$isApply = $Apply.IsPresent
if ($isApply) {
    # First try from the IndexPath directory (most reliable for self-test)
    $indexPathDir = [System.IO.Path]::GetDirectoryName($resolvedIndexPath)
    if (-not $script:repoRoot) {
        try {
            $gitRoot = & git -C $indexPathDir rev-parse --show-toplevel 2>&1
            if ($LASTEXITCODE -eq 0) { $script:repoRoot = (Resolve-Path -LiteralPath $gitRoot -ErrorAction SilentlyContinue).Path }
        } catch {}
    }
    # Then try from cwd (normal usage)
    if (-not $script:repoRoot) {
        try {
            $gitRoot = & git rev-parse --show-toplevel 2>&1
            if ($LASTEXITCODE -eq 0) { $script:repoRoot = (Resolve-Path -LiteralPath $gitRoot -ErrorAction SilentlyContinue).Path }
        } catch {}
    }
    # Fallback: walk up from the script's own location (world-sim/scripts/)
    if (-not $script:repoRoot -and $PSScriptRoot) {
        $checkDir = $PSScriptRoot
        while ($checkDir) {
            if (Test-Path -LiteralPath (Join-Path $checkDir '.git') -PathType Container) {
                $script:repoRoot = $checkDir
                break
            }
            $parentDir = [System.IO.Path]::GetDirectoryName($checkDir)
            if ($parentDir -eq $checkDir) { break }
            $checkDir = $parentDir
        }
    }
    # Fallback: walk up from IndexPath directory
    if (-not $script:repoRoot) {
        $checkDir = $indexPathDir
        while ($checkDir) {
            if (Test-Path -LiteralPath (Join-Path $checkDir '.git') -PathType Container) {
                $script:repoRoot = $checkDir
                break
            }
            $parentDir = [System.IO.Path]::GetDirectoryName($checkDir)
            if ($parentDir -eq $checkDir) { break }
            $checkDir = $parentDir
        }
    }
    if (-not $script:repoRoot) { $script:repoRoot = $indexPathDir }

    # Verify IndexPath is under repoRoot
    $normIndexPath = $resolvedIndexPath.Replace('\', '/').ToLowerInvariant()
    $normRepoRoot = $script:repoRoot.Replace('\', '/').ToLowerInvariant()
    if (-not $normIndexPath.StartsWith($normRepoRoot + '/')) {
        Write-ErrorAndExit "IndexPath is not inside the repository root"
    }
}

# Derive repo-relative path for Git operations (only needed for Apply)
if ($isApply) {
    $relativeIndexPath = $resolvedIndexPath.Substring($script:repoRoot.Length + 1)
}

# --- Read and parse ---
$content = [System.IO.File]::ReadAllText($resolvedIndexPath, [System.Text.UTF8Encoding]::new($false))
$targetRow = Find-PhaseRow -Content $content -PhaseId $PhaseId -ExpectedOldShortSha $OldShortSha
Write-Host "Found phase row: $($targetRow.RawLine)"
Write-Host "OLD COMMIT: $OldShortSha"
Write-Host "NEW COMMIT: $NewShortSha"

# --- No-op detection after safety validation (Defect 6) ---
# Safety checks run first for BOTH -Apply and no-op Apply
$isApply = $Apply.IsPresent
$isNoOp = ($OldShortSha -eq $NewShortSha)

if ($isApply) {
    # Run ALL safety checks before detecting no-op
    Invoke-ApplySafetyChecks -ResolvedIndexPath $resolvedIndexPath -RepoRoot $script:repoRoot -IndexPath $relativeIndexPath

    if ($isNoOp) {
        # No-op: still validated everything, now confirm no change needed
        Write-Host "APPLIED: false"
        Write-Host "GREEN"
        exit $script:ExitCodeGreen
    }

    # Real apply
    $newRow = Invoke-SpanReplacement -RawLine $targetRow.RawLine -OldSha $OldShortSha -NewSha $NewShortSha
    $newContent = $content.Replace($targetRow.RawLine, $newRow)
    Confirm-OnlyCommitChanged -OldContent $content -NewContent $newContent -PhaseId $PhaseId
    $newContentBytes = [System.Text.Encoding]::UTF8.GetBytes($newContent)
    [System.IO.File]::WriteAllBytes($resolvedIndexPath, $newContentBytes)
    Invoke-PostWriteValidation -FilePath $resolvedIndexPath -ExpectedContent $newContent -ExpectedLength $newContentBytes.Length
    Write-Host "APPLIED: true"
    Write-Host "GREEN"
    exit $script:ExitCodeGreen
}

# --- Dry-run (no -Apply) ---
$newRow = Invoke-SpanReplacement -RawLine $targetRow.RawLine -OldSha $OldShortSha -NewSha $NewShortSha
Write-Host "BEFORE: $($targetRow.RawLine)"
Write-Host "AFTER:  $newRow"
Write-Host "APPLIED: false"
Write-Host "GREEN"
exit $script:ExitCodeGreen
