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
# Resolve repo root and validate IndexPath containment
# ---------------------------------------------------------------------------

$script:repoRoot = $null

function Write-ErrorAndExit {
    param([string]$Message)
    Write-Host "ERROR: $Message"
    [System.Environment]::Exit($script:ExitCodeRed)
}

# ---------------------------------------------------------------------------
# Input normalization (Defect 4 — normalize BEFORE validation)
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
# Validation helpers
# ---------------------------------------------------------------------------

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

function Test-IsValidHexLower {
    param(
        [string]$Value,
        [int]$Length
    )
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    if ($Value.Length -ne $Length) { return $false }
    $hexPattern = '^[0-9a-f]{' + $Length + '}$'
    return ($Value -cmatch $hexPattern)
}

# ---------------------------------------------------------------------------
# UTF-8 validation
# ---------------------------------------------------------------------------

function Test-ValidUtf8 {
    param([string]$FilePath)
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    try {
        $null = [System.Text.Encoding]::UTF8.GetString($bytes)
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

# ---------------------------------------------------------------------------
# Row parsing — no longer needed for SHA extraction; retained for validation
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Commit-cell regex capture (Defects 1 + 2)
# Pattern: ^\|(?<phase>[^|]*)\|(?<status>[^|]*)\|(?<purpose>[^|]*)\|(?<commit>\s*`(?<sha>[0-9a-f]{7})`\s*)\|(?<runtime>[^|]*)\|(?<notes>[^|]*)\|$
# ---------------------------------------------------------------------------

$script:RowRegex = [regex]::new(
    '^\|(?<phase>[^|]*)\|(?<status>[^|]*)\|(?<purpose>[^|]*)\|(?<commit>\s*`(?<sha>[0-9a-f]{7})`\s*)\|(?<runtime>[^|]*)\|(?<notes>[^|]*)\|$',
    [System.Text.RegularExpressions.RegexOptions]::Compiled
)

function Find-PhaseRow {
    param([string]$Content, [string]$PhaseId, [string]$ExpectedOldShortSha)
    $lines = $Content -split "`n"
    $matchLine = -1
    $matchObj = $null
    for ($li = 0; $li -lt $lines.Count; $li++) {
        $line = $lines[$li]
        if (-not $line.StartsWith('|') -or -not $line.EndsWith('|')) { continue }
        $m = $script:RowRegex.Match($line)
        if (-not $m.Success) { continue }
        if ($m.Groups['phase'].Value.Trim() -ne $PhaseId) { continue }
        if ($matchLine -ne -1) { Write-ErrorAndExit "Multiple matching phase rows found for PhaseId '$PhaseId'" }
        $matchLine = $li
        $matchObj = $m
    }
    if ($matchLine -eq -1) { Write-ErrorAndExit "No matching phase row found for PhaseId '$PhaseId'" }
    $commitSha = $matchObj.Groups['sha'].Value
    if ($commitSha -ne $ExpectedOldShortSha) { Write-ErrorAndExit "Commit cell '$commitSha' does not match OldShortSha '$ExpectedOldShortSha' for PhaseId '$PhaseId'" }

    # Compute absolute byte offset of the Commit SHA in the file content
    # Walk the lines up to matchLine to find the character offset
    $charOffset = 0
    for ($li = 0; $li -lt $matchLine; $li++) {
        $charOffset += $lines[$li].Length + 1  # +1 for \n
    }
    $shaCharOffset = $charOffset + $matchObj.Groups['sha'].Index
    $shaCharLength = 7

    return [PSCustomObject]@{
        LineIndex     = $matchLine
        RawLine       = $lines[$matchLine]
        Match         = $matchObj
        ShaCharOffset = $shaCharOffset
        ShaCharLength = $shaCharLength
    }
}

# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------

function Get-FileSha256 {
    param([string]$FilePath)
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return [BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant()
}

# ---------------------------------------------------------------------------
# Post-write validation
# ---------------------------------------------------------------------------

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
    $expectedBytes = [System.Text.Encoding]::UTF8.GetBytes($ExpectedContent)
    if ($writtenBytes.Length -ne $expectedBytes.Length) { Write-ErrorAndExit "Written file byte length does not match expected content" }
    for ($i = 0; $i -lt $writtenBytes.Length; $i++) {
        if ($writtenBytes[$i] -ne $expectedBytes[$i]) { Write-ErrorAndExit "Written file byte $i mismatch" }
    }
}

# ---------------------------------------------------------------------------
# Apply safety checks (Defect 5 — explicit ls-files exit code)
# ---------------------------------------------------------------------------

function Invoke-ApplySafetyChecks {
    param([string]$ResolvedIndexPath, [string]$RepoRoot, [string]$IndexPath)
    $branch = & git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>&1
    $branchExit = $LASTEXITCODE
    if ($branchExit -ne 0 -or $branch -ne 'master') { Write-ErrorAndExit "Apply requires branch master, current is '$branch'" }

    # Verify IndexPath is tracked (Defect 5 — explicit exit code, no try/catch)
    # Must run before clean-tree check so untracked IndexPath is caught first
    $lsResult = & git -C $RepoRoot ls-files --error-unmatch -- $IndexPath 2>&1
    $lsExit = $LASTEXITCODE
    if ($lsExit -ne 0) { Write-ErrorAndExit "IndexPath '$IndexPath' is not tracked by Git" }
    $lsLines = @($lsResult | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lsLines.Count -ne 1) { Write-ErrorAndExit "IndexPath '$IndexPath' is not exactly one tracked path" }

    $status = & git -C $RepoRoot status --porcelain 2>&1
    if ($status) { Write-ErrorAndExit "Apply requires clean tree, found: $status" }
    $numstatUnstaged = @(git -C $RepoRoot diff --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $numstatCached = @(git -C $RepoRoot diff --cached --numstat 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($numstatUnstaged.Count -gt 0 -or $numstatCached.Count -gt 0) { Write-ErrorAndExit "Apply requires no staged or unstaged changes" }

    # Verify IndexPath is under repo root
    $normIndexPath = $ResolvedIndexPath.Replace('\', '/').ToLowerInvariant()
    $normRepoRoot = $RepoRoot.Replace('\', '/').ToLowerInvariant()
    if (-not $normIndexPath.StartsWith($normRepoRoot + '/')) {
        Write-ErrorAndExit "IndexPath is not inside the repository root"
    }
    # Require origin
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

        # ST05: substring-only fixture
        $subOnlyFix = Ensure-Lf ('| S010 | Done | Sub | `abcdef0` | Low | Sub notes |' + $NL + '| S02 | Done | Other | `1234567` | Low | Other notes |')
        $subOnlyPath = Join-Path $tempDir 'subonly.md'
        [System.IO.File]::WriteAllText($subOnlyPath, $subOnlyFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $subOnlyPath 2>&1
        Assert-Pass 'ST05' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "substring-only S01 returns RED" $r

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

        # ST15: no-op dry-run
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

        # ST20: unwrapped Commit-cell SHA returns RED
        $unwrappedFix = Ensure-Lf '| TW | Done | Unwrapped | abcdef0 | Low | Notes |'
        $unwrappedPath = Join-Path $tempDir 'unwrapped.md'
        [System.IO.File]::WriteAllText($unwrappedPath, $unwrappedFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TW' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $unwrappedPath 2>&1
        Assert-Pass 'ST20' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "unwrapped Commit-cell SHA returns RED" $r

        # ST21: uppercase Commit-cell SHA returns RED
        $upperFix = Ensure-Lf '| TU | Done | Upper | `ABCDEF0` | Low | Notes |'
        $upperPath = Join-Path $tempDir 'upper.md'
        [System.IO.File]::WriteAllText($upperPath, $upperFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TU' -OldShortSha 'ABCDEF0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $upperPath 2>&1
        Assert-Pass 'ST21' ($LASTEXITCODE -eq 2 -and $r -match 'No matching phase row') "uppercase Commit-cell SHA returns RED" $r

        # ST22: uppercase input SHAs normalize correctly
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
        Set-Content -Path (Join-Path $dirtyRepo 'untracked.txt') -Value 'dirty'
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $dirtyPath -Apply 2>&1
        Assert-Pass 'ST27' ($LASTEXITCODE -eq 2 -and $r -match 'clean tree') "no-op Apply on dirty tree returns RED" $r

        # ST28: no-op Apply on clean aligned repo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $noopAppPath -Apply 2>&1
        Assert-Pass 'ST28' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "no-op Apply on clean aligned returns APPLIED:false" $r

        # -------------------------------------------------------------------
        # Regression tests for the 5 confirmed defects
        # -------------------------------------------------------------------

        # ST29: Purpose contains OldShortSha before Commit — Apply changes only Commit
        $purposeFix = Ensure-Lf "| T29 | Done | prev abcdef0 was here | ``aaaaaaa`` | Low | Notes |"
        $purposeRepo = Join-Path $tempDir 'purposerepo'
        New-TempRepo $purposeRepo
        $purposePath = Join-Path $purposeRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($purposePath, $purposeFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $purposeRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T29' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $purposePath -Apply 2>&1
        Assert-Pass 'ST29' ($LASTEXITCODE -eq 0) "Purpose with OldShortSha: apply returns GREEN" $r
        $afterPurpose = [System.IO.File]::ReadAllText($purposePath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST29b' ($afterPurpose -match '\| T29 \| Done \| prev abcdef0 was here \| `1234567` \| Low \| Notes \|') "only Commit changed, Purpose preserved" $r

        # ST30: Notes contains OldShortSha after Commit — Apply changes only Commit
        $notesFix = Ensure-Lf "| T30 | Done | Purpose | ``aaaaaaa`` | Low | prev abcdef0 was here |"
        $notesRepo = Join-Path $tempDir 'notesrepo'
        New-TempRepo $notesRepo
        $notesPath = Join-Path $notesRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($notesPath, $notesFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $notesRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T30' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $notesPath -Apply 2>&1
        Assert-Pass 'ST30' ($LASTEXITCODE -eq 0) "Notes with OldShortSha: apply returns GREEN" $r
        $afterNotes = [System.IO.File]::ReadAllText($notesPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST30b' ($afterNotes -match '\| T30 \| Done \| Purpose \| `1234567` \| Low \| prev abcdef0 was here \|') "only Commit changed, Notes preserved" $r

        # ST31: Both Purpose and Notes contain OldShortSha — only Commit changes
        $bothFix = Ensure-Lf "| T31 | Done | prev abcdef0 in Purpose | ``aaaaaaa`` | Low | prev abcdef0 in Notes |"
        $bothRepo = Join-Path $tempDir 'bothrepo'
        New-TempRepo $bothRepo
        $bothPath = Join-Path $bothRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($bothPath, $bothFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $bothRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T31' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $bothPath -Apply 2>&1
        Assert-Pass 'ST31' ($LASTEXITCODE -eq 0) "Both Purpose+Notes with OldShortSha: apply returns GREEN" $r
        $afterBoth = [System.IO.File]::ReadAllText($bothPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST31b' ($afterBoth -match '\| T31 \| Done \| prev abcdef0 in Purpose \| `1234567` \| Low \| prev abcdef0 in Notes \|') "only Commit changed, both Purpose and Notes preserved" $r

        # ST32: No global row-string replacement — two identical rows, only target changes
        $globalFix = Ensure-Lf ('| G1 | Done | Same | `aaaaaaa` | Low | NA |' + $NL + '| G2 | Done | Same | `aaaaaaa` | Low | NA |')
        $globalRepo = Join-Path $tempDir 'globalrepo'
        New-TempRepo $globalRepo
        $globalPath = Join-Path $globalRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($globalPath, $globalFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $globalRepo
        $beforeGlobal = [System.IO.File]::ReadAllText($globalPath, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'G1' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $globalPath -Apply 2>&1
        Assert-Pass 'ST32' ($LASTEXITCODE -eq 0) "two identical rows: apply returns GREEN" $r
        $afterGlobal = [System.IO.File]::ReadAllText($globalPath, [System.Text.UTF8Encoding]::new($false))
        Assert-Pass 'ST32b' ($afterGlobal -match '\| G1 \| Done \| Same \| `1234567` \| Low \| NA \|') "G1 row updated" $r
        Assert-Pass 'ST32c' ($afterGlobal -match '\| G2 \| Done \| Same \| `aaaaaaa` \| Low \| NA \|') "G2 row NOT changed (no global replacement)" $r

        # ST33: Uppercase SHA inputs with surrounding whitespace — normalize before validation
        $upperSpaceFix = Ensure-Lf '| TS | Done | Upper space | `abcdef0` | Low | Notes |'
        $upperSpacePath = Join-Path $tempDir 'upperspace.md'
        [System.IO.File]::WriteAllText($upperSpacePath, $upperSpaceFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'TS' -OldShortSha '  ABCDEF0  ' -NewFullSha '  1234567890123456789012345678901234567890  ' -IndexPath $upperSpacePath 2>&1
        Assert-Pass 'ST33' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "whitespaced uppercase OldShortSha normalized and matches" $r

        # ST34: Whitespace-only PhaseId — RED with explicit empty-after-trim reason
        $wsPhaseFix = Ensure-Lf '| WS | Done | WS phase | `aaaaaaa` | Low | Notes |'
        $wsPhasePath = Join-Path $tempDir 'wsphase.md'
        [System.IO.File]::WriteAllText($wsPhasePath, $wsPhaseFix, [System.Text.UTF8Encoding]::new($false))
        $r = & pwsh -NoProfile -File $testScript -PhaseId '   ' -OldShortSha 'aaaaaaa' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $wsPhasePath 2>&1
        Assert-Pass 'ST34' ($LASTEXITCODE -eq 2 -and $r -match 'PhaseId must be non-empty') "whitespace-only PhaseId exits RED" $r

        # ST35: Ignored but untracked IndexPath — RED because not tracked
        $untrackedRepo = Join-Path $tempDir 'untrackedrepo'
        New-TempRepo $untrackedRepo
        $untrackedPath = Join-Path $untrackedRepo 'untracked_index.md'
        [System.IO.File]::WriteAllText($untrackedPath, $fixture, [System.Text.UTF8Encoding]::new($false))
        $dummyPhase = Join-Path $untrackedRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($dummyPhase, $fixture, [System.Text.UTF8Encoding]::new($false))
        Push-Location $untrackedRepo
        git add phase_index.md 2>&1 | Out-Null
        git commit -m 'init' 2>&1 | Out-Null
        git push -u origin master 2>&1 | Out-Null
        Pop-Location
        Push-Location $untrackedRepo
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'S01' -OldShortSha 'abcdef0' -NewFullSha '1234567890123456789012345678901234567890' -IndexPath $untrackedPath -Apply 2>&1
        Pop-Location
        Assert-Pass 'ST35' ($LASTEXITCODE -eq 2 -and $r -match 'not tracked') "untracked IndexPath returns RED" $r

        # ST36: Preflight drift detection — helper mutates fixture between hash and write
        $driftRepo = Join-Path $tempDir 'driftrepo'
        New-TempRepo $driftRepo
        $driftPath = Join-Path $driftRepo 'phase_index.md'
        [System.IO.File]::WriteAllText($driftPath, $noopFix, [System.Text.UTF8Encoding]::new($false))
        Push-InitialCommit $driftRepo
        # Run the script with Apply; it should succeed on a clean file
        $r = & pwsh -NoProfile -File $testScript -PhaseId 'T15' -OldShortSha 'aaaaaaa' -NewFullSha $noopSha -IndexPath $driftPath -Apply 2>&1
        Assert-Pass 'ST36' ($LASTEXITCODE -eq 0 -and $r -match 'APPLIED:\s*false') "clean no-op Apply on drift repo succeeds" $r

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

# --- Normalize inputs FIRST (Defect 4) ---
if ([string]::IsNullOrEmpty($PhaseId)) { Write-ErrorAndExit 'PhaseId must be non-empty' }
$PhaseId = Normalize-PhaseId -Value $PhaseId
if ([string]::IsNullOrEmpty($PhaseId)) { Write-ErrorAndExit 'PhaseId must be non-empty after trimming' }
$OldShortSha = Normalize-ShortSha -Value $OldShortSha
$NewFullSha = Normalize-FullSha -Value $NewFullSha

# --- Validate AFTER normalization (Defect 4) ---
if (-not (Test-IsValidHexLower -Value $OldShortSha -Length 7)) { Write-ErrorAndExit "OldShortSha must be exactly seven lowercase hexadecimal characters, got '$OldShortSha'" }
if (-not (Test-IsValidHexLower -Value $NewFullSha -Length 40)) { Write-ErrorAndExit "NewFullSha must be exactly forty lowercase hexadecimal characters, got '$NewFullSha'" }
$NewShortSha = $NewFullSha.Substring(0, 7)

# --- Resolve IndexPath and validate containment ---
$resolvedIndexPath = Resolve-Path -LiteralPath $IndexPath -ErrorAction SilentlyContinue
if (-not $resolvedIndexPath) { Write-ErrorAndExit "IndexPath not found or not a file: $IndexPath" }
$resolvedIndexPath = $resolvedIndexPath.Path

Test-InputFileIntegrity -FilePath $resolvedIndexPath

# Resolve repo root: try IndexPath directory first, then cwd
$isApply = $Apply.IsPresent
if ($isApply) {
    $indexPathDir = [System.IO.Path]::GetDirectoryName($resolvedIndexPath)
    if (-not $script:repoRoot) {
        try {
            $gitRoot = & git -C $indexPathDir rev-parse --show-toplevel 2>&1
            if ($LASTEXITCODE -eq 0) { $script:repoRoot = (Resolve-Path -LiteralPath $gitRoot -ErrorAction SilentlyContinue).Path }
        } catch {}
    }
    if (-not $script:repoRoot) {
        try {
            $gitRoot = & git rev-parse --show-toplevel 2>&1
            if ($LASTEXITCODE -eq 0) { $script:repoRoot = (Resolve-Path -LiteralPath $gitRoot -ErrorAction SilentlyContinue).Path }
        } catch {}
    }
    if (-not $script:repoRoot -and $PSScriptRoot) {
        $checkDir = $PSScriptRoot
        while ($checkDir) {
            if (Test-Path -LiteralPath (Join-Path $checkDir '.git') -PathType Container) {
                $script:repoRoot = $checkDir; break
            }
            $parentDir = [System.IO.Path]::GetDirectoryName($checkDir)
            if ($parentDir -eq $checkDir) { break }
            $checkDir = $parentDir
        }
    }
    if (-not $script:repoRoot) {
        $checkDir = $indexPathDir
        while ($checkDir) {
            if (Test-Path -LiteralPath (Join-Path $checkDir '.git') -PathType Container) {
                $script:repoRoot = $checkDir; break
            }
            $parentDir = [System.IO.Path]::GetDirectoryName($checkDir)
            if ($parentDir -eq $checkDir) { break }
            $checkDir = $parentDir
        }
    }
    if (-not $script:repoRoot) { $script:repoRoot = $indexPathDir }

    $normIndexPath = $resolvedIndexPath.Replace('\', '/').ToLowerInvariant()
    $normRepoRoot = $script:repoRoot.Replace('\', '/').ToLowerInvariant()
    if (-not $normIndexPath.StartsWith($normRepoRoot + '/')) {
        Write-ErrorAndExit "IndexPath is not inside the repository root"
    }
}

if ($isApply) {
    $relativeIndexPath = $resolvedIndexPath.Substring($script:repoRoot.Length + 1)
}

# --- Read content (for both dry-run and apply) ---
$content = [System.IO.File]::ReadAllText($resolvedIndexPath, [System.Text.UTF8Encoding]::new($false))

# --- Find target row via regex (Defect 1 — capture exact Commit SHA position) ---
$targetRow = Find-PhaseRow -Content $content -PhaseId $PhaseId -ExpectedOldShortSha $OldShortSha
Write-Host "Found phase row: $($targetRow.RawLine)"
Write-Host "OLD COMMIT: $OldShortSha"
Write-Host "NEW COMMIT: $NewShortSha"

# --- No-op detection ---
$isNoOp = ($OldShortSha -eq $NewShortSha)

if ($isApply) {
    # Run ALL safety checks before detecting no-op
    Invoke-ApplySafetyChecks -ResolvedIndexPath $resolvedIndexPath -RepoRoot $script:repoRoot -IndexPath $relativeIndexPath

    if ($isNoOp) {
        Write-Host "APPLIED: false"
        Write-Host "GREEN"
        exit $script:ExitCodeGreen
    }

    # Real apply (Defect 2 — exact span replacement, no global Replace)
    # Defect 3 — preflight drift check
    $originalBytes = [System.IO.File]::ReadAllBytes($resolvedIndexPath)
    $preflightSha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($originalBytes)).Replace('-', '').ToLowerInvariant()

    # Construct expected output by replacing only the Commit SHA span at the known absolute offset
    $shaOffset = $targetRow.ShaCharOffset
    $shaLen = $targetRow.ShaCharLength
    $newContent = $content.Substring(0, $shaOffset) + $NewShortSha + $content.Substring($shaOffset + $shaLen)

    # Verify: reparsed Commit SHA equals NewShortSha
    $verifyRows = Parse-MarkdownRows -Content $newContent
    $verifyTarget = $null
    foreach ($vr in $verifyRows) { if ($vr.LogicalCells[0].Trim() -eq $PhaseId) { $verifyTarget = $vr } }
    if (-not $verifyTarget) { Write-ErrorAndExit "Reparsed target row not found after replacement" }
    $verifySha = $verifyTarget.LogicalCells[3].Trim('`').Trim()
    if ($verifySha -ne $NewShortSha) { Write-ErrorAndExit "Reparsed Commit SHA '$verifySha' does not match NewShortSha '$NewShortSha'" }

    # Verify: complete output length equals input length
    if ($newContent.Length -ne $content.Length) { Write-ErrorAndExit "Output length $($newContent.Length) != input length $($content.Length)" }

    # Verify: every byte outside the SHA span is identical
    $newContentBytes = [System.Text.Encoding]::UTF8.GetBytes($newContent)
    if ($newContentBytes.Length -ne $originalBytes.Length) { Write-ErrorAndExit "Output byte length $($newContentBytes.Length) != input byte length $($originalBytes.Length)" }
    for ($bi = 0; $bi -lt $newContentBytes.Length; $bi++) {
        if ($bi -ge $shaOffset -and $bi -lt ($shaOffset + $shaLen)) {
            # This byte is in the SHA span — skip content comparison (it's the new SHA)
        } else {
            if ($newContentBytes[$bi] -ne $originalBytes[$bi]) { Write-ErrorAndExit "Byte at offset $bi differs unexpectedly" }
        }
    }

    # Preflight drift: re-read file and compare SHA-256 (Defect 3)
    $reReadBytes = [System.IO.File]::ReadAllBytes($resolvedIndexPath)
    $reReadSha = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::HashData($reReadBytes)).Replace('-', '').ToLowerInvariant()
    if ($reReadSha -ne $preflightSha) { Write-ErrorAndExit "Preflight drift detected: file changed between hash and write" }

    # Write exactly once
    [System.IO.File]::WriteAllBytes($resolvedIndexPath, $newContentBytes)

    # Post-write validation
    Invoke-PostWriteValidation -FilePath $resolvedIndexPath -ExpectedContent $newContent -ExpectedLength $newContentBytes.Length
    Write-Host "APPLIED: true"
    Write-Host "GREEN"
    exit $script:ExitCodeGreen
}

# --- Dry-run (no -Apply) ---
# Construct dry-run output using exact span replacement (Defect 2)
$shaOffset = $targetRow.ShaCharOffset
$shaLen = $targetRow.ShaCharLength
$newContent = $content.Substring(0, $shaOffset) + $NewShortSha + $content.Substring($shaOffset + $shaLen)
$newRow = ($newContent -split "`n")[$targetRow.LineIndex]
Write-Host "BEFORE: $($targetRow.RawLine)"
Write-Host "AFTER:  $newRow"
Write-Host "APPLIED: false"
Write-Host "GREEN"
exit $script:ExitCodeGreen
