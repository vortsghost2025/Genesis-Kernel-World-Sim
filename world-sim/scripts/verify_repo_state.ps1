#requires -Version 7.0
<#
verify_repo_state.ps1 — Genesis Kernel World Sim repository-state verifier.

Read-only pre-flight verification: branch, triple-SHA alignment, dirty-tree,
diff-check, CRLF, BOM, and credential-shaped scan. The script has zero
file-write authority against the real repository and never commits, pushes,
stashes, resets, reverts, cleans, or modifies Git configuration.

Exit codes:
  0 = GREEN (all checks pass)
  1 = YELLOW (non-fatal operational warnings only)
  2 = RED (any hard failure)
#>
[CmdletBinding()]
param(
    [string]$ExpectedSha,
    [string]$Remote = 'origin',
    [string]$Branch = 'master',
    [string[]]$Path,
    [switch]$AllTracked,
    [switch]$AllowDirty,
    [switch]$SkipDiffCheck,
    [switch]$SkipCrlfCheck,
    [switch]$SkipSecretScan,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

$script:ExitCodeGreen = 0
$script:ExitCodeYellow = 1
$script:ExitCodeRed = 2

function Write-CheckLine {
    param([string]$Level, [string]$Check, [string]$Result)
    Write-Host "[$Level] $Check`: $Result"
}

function Test-LowerHex40 {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    if ($Value.Length -ne 40) { return $false }
    return ($Value -match '^[0-9a-f]{40}$')
}

function Test-LowerHex7 {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    if ($Value.Length -ne 7) { return $false }
    return ($Value -match '^[0-9a-f]{7}$')
}

function Get-RepoRoot {
    try {
        $root = git rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($root)) {
            return $null
        }
        return $root
    } catch {
        return $null
    }
}

function Invoke-GitSafe {
    param([string[]]$Arguments)
    $output = & git @Arguments 2>&1
    if ($null -eq $output) { return @() }
    $result = @($output | ForEach-Object { [string]$_ })
    return [string[]]$result
}

function Convert-ToRepoRelative {
    param([string]$AbsPath, [string]$Root)
    $normalizedRoot = $Root -replace '\\', '/'
    $normalizedPath = $AbsPath -replace '\\', '/'
    if ($normalizedPath.StartsWith($normalizedRoot + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $normalizedPath.Substring($normalizedRoot.Length + 1)
    }
    return $null
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

# ---------------------------------------------------------------------------
# CRLF and BOM checks
# ---------------------------------------------------------------------------

$script:TextExtensions = @('.ps1', '.md', '.py', '.yml', '.yaml', '.json', '.toml', '.txt')

function Test-IsTextFile {
    param([string]$FilePath)
    $ext = [System.IO.Path]::GetExtension($FilePath).ToLowerInvariant()
    return ($script:TextExtensions -contains $ext)
}

function Test-IsBinaryFile {
    param([string]$FilePath)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        $chunkSize = [Math]::Min(8192, $bytes.Length)
        for ($i = 0; $i -lt $chunkSize; $i++) {
            if ($bytes[$i] -eq 0) { return $true }
        }
        return $false
    } catch {
        return $true
    }
}

function Get-CrlfCount {
    param([string]$FilePath)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        $count = 0
        for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
            if ($bytes[$i] -eq 0x0D -and $bytes[$i + 1] -eq 0x0A) { $count++ }
        }
        return $count
    } catch {
        return -1
    }
}

function Test-HasBom {
    param([string]$FilePath)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        if ($bytes.Length -ge 3 -and
            $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            return $true
        }
        return $false
    } catch {
        return $false
    }
}

function Test-HasFinalNewline {
    param([string]$FilePath)
    try {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        if ($bytes.Length -eq 0) { return $false }
        return ($bytes[$bytes.Length - 1] -eq 0x0A)
    } catch {
        return $false
    }
}

# ---------------------------------------------------------------------------
# Credential-shaped scan
# ---------------------------------------------------------------------------

# Keyword list (not regex) for Class A notices.
$script:KeywordNotices = @('token', 'key', 'api', 'secret', 'credential', 'password', 'authorization')

# Construct credential-shaped patterns from fragments. By splitting the prefixes
# into concatenated string fragments, the script source itself does not produce
# literal matches for these patterns.
function Get-CredentialShapedPatterns {
    $patterns = @()

    # Private key block headers (PEM-style) — assembled from fragments
    $begin = '-----' + 'BEGIN '
    $priv = 'PRIVATE' + ' KEY-----'
    $rsaPriv = 'RSA' + ' PRIVATE KEY-----'
    $ecPriv = 'EC' + ' PRIVATE KEY-----'
    $openSsh = 'OPENSSH' + ' PRIVATE KEY-----'
    $pgpPriv = 'PGP' + ' PRIVATE KEY BLOCK-----'
    $patterns += [PSCustomObject]@{
        Label = 'private-key-header'
        Regex = [regex]::New([regex]::Escape($begin) + '(' + [regex]::Escape($priv) + '|' + [regex]::Escape($rsaPriv) + '|' + [regex]::Escape($ecPriv) + '|' + [regex]::Escape($openSsh) + '|' + [regex]::Escape($pgpPriv) + ')')
    }

    # Known provider-token prefixes — assembled from fragments
    $ghpPrefix = 'ghp' + '_'
    $ghoPrefix = 'gho' + '_'
    $ghuPrefix = 'ghu' + '_'
    $ghsPrefix = 'ghs' + '_'
    $ghrPrefix = 'ghr' + '_'
    $glptPrefix = 'glpat' + '-'
    $xoxbPrefix = 'xoxb' + '-'
    $xoxpPrefix = 'xoxp' + '-'
    $skPrefix = 'sk' + '-'
    $skLive = 'sk' + '_live_'
    $skTest = 'sk' + '_test_'
    $akiaPrefix = 'AKIA'
    $iaKey = 'ASIA'
    $aiKey = 'AIza'
    $patterns += [PSCustomObject]@{
        Label = 'provider-token-prefix'
        Regex = [regex]::New('(' + [regex]::Escape($ghpPrefix) + '|' + [regex]::Escape($ghoPrefix) + '|' + [regex]::Escape($ghuPrefix) + '|' + [regex]::Escape($ghsPrefix) + '|' + [regex]::Escape($ghrPrefix) + '|' + [regex]::Escape($glptPrefix) + '|' + [regex]::Escape($xoxbPrefix) + '|' + [regex]::Escape($xoxpPrefix) + '|' + [regex]::Escape($skPrefix) + '|' + [regex]::Escape($skLive) + '|' + [regex]::Escape($skTest) + '|' + [regex]::Escape($akiaPrefix) + '|' + [regex]::Escape($iaKey) + '|' + [regex]::Escape($aiKey) + ')[A-Za-z0-9_' + [regex]::Escape('-') + ']{8,}')
    }

    # Credential assignments: name = "value" or name: "value"
    # Match api_key, token, password, client_secret, credential, secret_key
    $credNames = @('api_key', 'token', 'password', 'client_secret', 'credential', 'secret_key', 'access_token', 'refresh_token')
    foreach ($name in $credNames) {
        $patterns += [PSCustomObject]@{
            Label = 'credential-assignment'
            Regex = [regex]::New('(?i)\b' + [regex]::Escape($name) + '\b\s*[:=]\s*[''"]([^''"]{8,})[''"]')
        }
    }

    return $patterns
}

# Obvious placeholders that should never be treated as real credentials.
# Kept for reference; matching is handled by explicit exact-equality rules in Test-IsPlaceholder.
$script:PlaceholderTokens = @(
    '[REDACTED]',
    '<placeholder>',
    '<redacted>',
    'changeme',
    'change-me',
    'example',
    'example-only',
    'test-only',
    'fake',
    'mock',
    'dummy',
    'sample',
    'placeholder',
    'redacted',
    'your-secret-here',
    'your-token-here',
    'your-key-here',
    'your-password-here'
)

function Test-IsPlaceholder {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return $false }

    $lower = $Value.ToLowerInvariant()

    # Exact-match placeholders (case-insensitive)
    $exactPlaceholders = @(
        '[REDACTED]',
        '<placeholder>',
        '<redacted>',
        'changeme',
        'change-me',
        'example',
        'example-only',
        'test-only',
        'fake',
        'mock',
        'dummy',
        'sample',
        'placeholder',
        'redacted',
        'your-secret-here',
        'your-token-here',
        'your-key-here',
        'your-password-here'
    )
    foreach ($ph in $exactPlaceholders) {
        if ($lower -eq $ph.ToLowerInvariant()) { return $true }
    }

    # Repeated single character sentinel values
    if ($Value.Length -ge 4) {
        $first = $Value[0]
        $allSame = $true
        for ($i = 1; $i -lt $Value.Length; $i++) {
            if ($Value[$i] -ne $first) { $allSame = $false; break }
        }
        if ($allSame) { return $true }
    }

    # Regex source definitions (common in the verifier itself)
    if ($lower.StartsWith('regex') -or $lower.StartsWith('[regex') -or $lower.Contains('::escape(') -or $lower.Contains('::new(')) {
        return $true
    }

    return $false
}

function Test-IsRegexSourceLine {
    param([string]$Line)
    $lower = $Line.ToLowerInvariant()
    if ($lower.Contains('[regex]::escape(') -or $lower.Contains('[regex]::new(') -or $lower.Contains('get-credentialshapedpatterns')) {
        return $true
    }
    if ($lower.Contains('private-key-header') -or $lower.Contains('provider-token-prefix') -or $lower.Contains('credential-assignment')) {
        return $true
    }
    return $false
}

function Invoke-CredentialScan {
    param(
        [string[]]$Files,
        [string]$Root
    )

    $keywordCounts = @{}
    $credentialMatches = @()

    foreach ($file in $Files) {
        $fullPath = Join-Path $Root $file
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) { continue }
        if (Test-IsTextFile -FilePath $fullPath) {
            try {
                $lines = [System.IO.File]::ReadAllLines($fullPath, [System.Text.UTF8Encoding]::new($false))
            } catch {
                continue
            }
            for ($i = 0; $i -lt $lines.Length; $i++) {
                $line = $lines[$i]
                $lineLower = $line.ToLowerInvariant()

                # Skip regex-source lines in the verifier itself
                if (Test-IsRegexSourceLine -Line $line) { continue }

                # Class A: keyword notice (count only, never BLOCK)
                foreach ($kw in $script:KeywordNotices) {
                    if ($lineLower.Contains($kw)) {
                        if (-not $keywordCounts.ContainsKey($file)) {
                            $keywordCounts[$file] = 0
                        }
                        $keywordCounts[$file]++
                    }
                }

                # Class B: credential-shaped match (BLOCK)
                $patterns = Get-CredentialShapedPatterns
                foreach ($pat in $patterns) {
                    $matches = $pat.Regex.Matches($line)
                    foreach ($m in $matches) {
                        $candidate = $null
                        switch ($pat.Label) {
                            'credential-assignment' {
                                if ($m.Groups.Count -ge 2) { $candidate = $m.Groups[1].Value }
                            }
                            'provider-token-prefix' {
                                $candidate = $m.Value
                            }
                            'private-key-header' {
                                $candidate = $m.Value
                            }
                        }
                        if ($candidate -and (Test-IsPlaceholder -Value $candidate)) { continue }
                        if (-not $candidate) { continue }
                        $credentialMatches += [PSCustomObject]@{
                            Path    = $file
                            LineNum = $i + 1
                            Label   = $pat.Label
                        }
                    }
                }
            }
        }
    }

    return [PSCustomObject]@{
        KeywordCounts      = $keywordCounts
        CredentialMatches  = $credentialMatches
    }
}

# ---------------------------------------------------------------------------
# Core state checks
# ---------------------------------------------------------------------------

function Get-PorcelainStatus {
    $output = Invoke-GitSafe -Arguments @('status', '--porcelain=v1')
    $entries = @()
    foreach ($line in $output) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $status = $line.Substring(0, 2)
        $filePath = $line.Substring(3).Trim()
        # Handle rename: "R  old -> new" — take the "new" side
        if ($filePath.Contains(' -> ')) {
            $parts = $filePath -split ' -> ', 2
            $filePath = $parts[-1]
        }
        $entries += [PSCustomObject]@{
            Status   = $status
            FilePath = $filePath
        }
    }
    return [array]$entries
}

function Get-ChangedPaths {
    param([string]$Root)
    $entries = @(Get-PorcelainStatus)
    $paths = @()
    foreach ($e in $entries) {
        $paths += $e.FilePath
    }
    return [string[]]$paths
}

function Select-FilesForScanning {
    param(
        [string]$Root,
        [string[]]$PathArgs,
        [switch]$AllTracked,
        [string[]]$ChangedPaths
    )

    $selected = @()

    if ($PathArgs -and $PathArgs.Count -gt 0) {
        foreach ($p in $PathArgs) {
            $norm = ($p -replace '\\', '/').TrimStart('./')
            $fullPath = Join-Path $Root $norm
            if (-not (Test-Path -LiteralPath $fullPath)) {
                return [PSCustomObject]@{
                    Files   = @()
                    Error   = "explicit path not found: $norm"
                    Notice  = $null
                }
            }
            if (Test-Path -LiteralPath $fullPath -PathType Container) {
                $children = Get-ChildItem -LiteralPath $fullPath -Recurse -File -ErrorAction SilentlyContinue
                foreach ($child in $children) {
                    $rel = Convert-ToRepoRelative -AbsPath $child.FullName -Root $Root
                    if ($rel) { $selected += $rel }
                }
            } else {
                $rel = Convert-ToRepoRelative -AbsPath $fullPath -Root $Root
                if ($rel) { $selected += $rel }
            }
        }
        return [PSCustomObject]@{
            Files  = ($selected | Select-Object -Unique)
            Error  = $null
            Notice = "selected $([Math]::Max($selected.Count, 0)) file(s) via explicit -Path"
        }
    }

    if ($AllTracked) {
        $tracked = Invoke-GitSafe -Arguments @('ls-files')
        $trackedClean = $tracked | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        return [PSCustomObject]@{
            Files  = $trackedClean
            Error  = $null
            Notice = "selected $($trackedClean.Count) file(s) via -AllTracked"
        }
    }

    # Default: union of changed/staged/untracked
    if ($ChangedPaths -and $ChangedPaths.Count -gt 0) {
        $selected = $ChangedPaths | Select-Object -Unique
        return [PSCustomObject]@{
            Files  = $selected
            Error  = $null
            Notice = "selected $($selected.Count) file(s) from changed/staged/untracked set"
        }
    }

    return [PSCustomObject]@{
        Files  = @()
        Error  = $null
        Notice = 'no files selected; no -Path, -AllTracked, or detectable changes — skipped CRLF/BOM/credential scan'
    }
}

# ---------------------------------------------------------------------------
# Top-level verification
# ---------------------------------------------------------------------------

function Invoke-RepoStateCheck {
    $results = @()
    $finalState = 'GREEN'
    $stopStep = $null
    $stopReason = $null
    $localHead = $null
    $remoteTracking = $null
    $lsRemote = $null
    $porcelainSummary = $null

    $root = Get-RepoRoot
    if (-not $root) {
        $stopStep = 'repo-root'
        $stopReason = 'not inside a Git repository'
        $finalState = 'RED'
        return [PSCustomObject]@{
            Results       = @([PSCustomObject]@{ Level = 'FAIL'; Check = 'repo-root'; Result = $stopReason })
            FinalState    = $finalState
            StopStep      = $stopStep
            StopReason    = $stopReason
            LocalHead     = $localHead
            RemoteTracking = $remoteTracking
            LsRemote      = $lsRemote
            Porcelain     = $porcelainSummary
        }
    }

    # Check 1: current branch
    $currentBranch = (Invoke-GitSafe -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')) | Select-Object -First 1
    if ($currentBranch -ne $Branch) {
        $stopStep = 'branch'
        $stopReason = "expected $Branch, found $currentBranch"
        $finalState = 'RED'
        $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'branch'; Result = $stopReason }
        return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
    }
    $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'branch'; Result = $currentBranch }

    # Check 2: porcelain status
    $entries = @(Get-PorcelainStatus)
    $porcelainSummary = ($entries | ForEach-Object { $_.Status + ' ' + $_.FilePath }) -join '; '
    if (-not $porcelainSummary) { $porcelainSummary = '(empty)' }

    if (-not $AllowDirty) {
        if ($entries.Count -gt 0) {
            $stopStep = 'dirty-tree'
            $stopReason = "dirty tree with $($entries.Count) entr" + $(if ($entries.Count -eq 1) { 'y' } else { 'ies' }) + " (use -AllowDirty with -Path to authorize)"
            $finalState = 'RED'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'dirty-tree'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'dirty-tree'; Result = 'clean' }
    } else {
        if (-not $Path -or $Path.Count -eq 0) {
            $stopStep = 'allowdirty-requires-path'
            $stopReason = '-AllowDirty requires -Path'
            $finalState = 'RED'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'allowdirty-requires-path'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $unauthorized = @()
        foreach ($e in $entries) {
            if (-not (Test-PathAuthorized -Candidate $e.FilePath -Authorized $Path)) {
                $unauthorized += $e.FilePath
            }
        }
        if ($unauthorized.Count -gt 0) {
            $stopStep = 'unauthorized-paths'
            $stopReason = "unauthorized changed paths: " + ($unauthorized -join ', ')
            $finalState = 'RED'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'unauthorized-paths'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'dirty-tree'; Result = "$($entries.Count) authorized change(s) under -Path" }
    }

    # Check 3: local HEAD
    $localHead = (Invoke-GitSafe -Arguments @('rev-parse', 'HEAD')) | Select-Object -First 1
    if ([string]::IsNullOrEmpty($localHead)) {
        $stopStep = 'local-head'
        $stopReason = 'could not read local HEAD'
        $finalState = 'RED'
        $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'local-head'; Result = $stopReason }
        return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
    }
    $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'local-head'; Result = $localHead }

    # Check 4: expected SHA
    if ($ExpectedSha) {
        $normalized = $ExpectedSha.ToLowerInvariant()
        if (-not (Test-LowerHex40 -Value $normalized)) {
            $stopStep = 'expected-sha-format'
            $stopReason = 'ExpectedSha is not a valid 40-char lowercase hex SHA'
            $finalState = 'RED'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'expected-sha-format'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        if ($localHead.ToLowerInvariant() -ne $normalized) {
            $stopStep = 'expected-sha-mismatch'
            $stopReason = "local HEAD $localHead != expected $normalized"
            $finalState = 'RED'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'expected-sha'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'expected-sha'; Result = $localHead }
    } else {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'expected-sha'; Result = 'not supplied -- skipped exact comparison' }
    }

    # Check 5: remote-tracking ref
    $remoteRef = "$Remote/$Branch"
    $remoteTracking = (Invoke-GitSafe -Arguments @('rev-parse', $remoteRef)) | Select-Object -First 1
    if ([string]::IsNullOrEmpty($remoteTracking)) {
        $stopStep = 'remote-tracking'
        $stopReason = "remote-tracking ref $remoteRef not found"
        $finalState = 'YELLOW'
        $results += [PSCustomObject]@{ Level = 'WARN'; Check = 'remote-tracking'; Result = $stopReason }
    } elseif ($remoteTracking.ToLowerInvariant() -ne $localHead.ToLowerInvariant()) {
        $stopStep = 'remote-tracking-mismatch'
        $stopReason = "remote-tracking $remoteTracking != local $localHead"
        $finalState = 'YELLOW'
        $results += [PSCustomObject]@{ Level = 'WARN'; Check = 'remote-tracking'; Result = $stopReason }
    } else {
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'remote-tracking'; Result = $remoteTracking }
    }

    # Check 6: git ls-remote
    $lsRemoteOutput = Invoke-GitSafe -Arguments @('ls-remote', $Remote, "refs/heads/$Branch")
    $lsRemoteLines = @($lsRemoteOutput | Where-Object { $_ -match '^[0-9a-f]{40}\s' })
    if ($lsRemoteLines.Count -eq 0) {
        $lsRemote = $null
        if ($finalState -eq 'GREEN') {
            $finalState = 'YELLOW'
        }
        $results += [PSCustomObject]@{ Level = 'WARN'; Check = 'ls-remote'; Result = 'no results (remote unavailable?)' }
    } elseif ($lsRemoteLines.Count -gt 1) {
        $lsRemote = $null
        $finalState = 'RED'
        $stopStep = 'ls-remote-ambiguous'
        $stopReason = "$($lsRemoteLines.Count) results from ls-remote"
        $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'ls-remote'; Result = $stopReason }
        return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
    } else {
        $lsRemote = ($lsRemoteLines[0] -split '\s')[0]
        if ($lsRemote.ToLowerInvariant() -ne $localHead.ToLowerInvariant()) {
            $finalState = 'RED'
            $stopStep = 'ls-remote-mismatch'
            $stopReason = "ls-remote $lsRemote != local $localHead"
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'ls-remote'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'ls-remote'; Result = $lsRemote }
    }

    # Check 7: git diff --check
    if (-not $SkipDiffCheck) {
        $diffCheck = Invoke-GitSafe -Arguments @('diff', '--check')
        $diffCachedCheck = Invoke-GitSafe -Arguments @('diff', '--cached', '--check')
        $diffFail = $false
        foreach ($line in $diffCheck) {
            if ($line -match 'error:' -or $line -match 'warning:') { $diffFail = $true }
        }
        foreach ($line in $diffCachedCheck) {
            if ($line -match 'error:' -or $line -match 'warning:') { $diffFail = $true }
        }
        if ($diffFail) {
            $finalState = 'RED'
            $stopStep = 'diff-check'
            $stopReason = 'git diff --check reported errors or warnings'
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'diff-check'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'diff-check'; Result = 'clean' }
    } else {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'diff-check'; Result = 'skipped via -SkipDiffCheck' }
    }

    # Check 8: numstat summaries (informational)
    $numstatUnstaged = @(Invoke-GitSafe -Arguments @('diff', '--numstat'))
    $numstatCached = @(Invoke-GitSafe -Arguments @('diff', '--cached', '--numstat'))
    $numstatUnstagedClean = @($numstatUnstaged | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $numstatCachedClean = @($numstatCached | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $numstatSummary = "unstaged=$($numstatUnstagedClean.Count) staged=$($numstatCachedClean.Count)"
    $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'numstat'; Result = $numstatSummary }

    # File selection for CRLF/BOM/credential
    $changedPaths = Get-ChangedPaths -Root $root
    $selected = Select-FilesForScanning -Root $root -PathArgs $Path -AllTracked:$AllTracked -ChangedPaths $changedPaths
    if ($selected.Error) {
        $finalState = 'RED'
        $stopStep = 'file-selection'
        $stopReason = $selected.Error
        $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'file-selection'; Result = $stopReason }
        return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
    }
    if ($selected.Notice) {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'file-selection'; Result = $selected.Notice }
    }
    $filesToScan = @($selected.Files)

    # Check 9: CRLF and BOM
    if (-not $SkipCrlfCheck -and $filesToScan -and $filesToScan.Count -gt 0) {
        $crlfFailures = @()
        $bomFailures = @()
        $binarySkips = @()
        $textScanned = 0
        foreach ($f in $filesToScan) {
            $fullPath = Join-Path $root $f
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) { continue }
            if (Test-IsBinaryFile -FilePath $fullPath) {
                $binarySkips += $f
                continue
            }
            if (-not (Test-IsTextFile -FilePath $fullPath)) { continue }
            $textScanned++
            $crlf = Get-CrlfCount -FilePath $fullPath
            if ($crlf -gt 0) {
                $crlfFailures += [PSCustomObject]@{ Path = $f; Count = $crlf }
            }
            if (Test-HasBom -FilePath $fullPath) {
                $bomFailures += $f
            }
        }
        if ($binarySkips.Count -gt 0) {
            $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'binary-skip'; Result = "skipped $($binarySkips.Count) binary file(s)" }
        }
        if ($crlfFailures.Count -gt 0) {
            $finalState = 'RED'
            $stopStep = 'crlf'
            $stopReason = "CRLF found in: " + (($crlfFailures | ForEach-Object { $_.Path + " (" + $_.Count + ")" }) -join ', ')
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'crlf'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        if ($bomFailures.Count -gt 0) {
            $finalState = 'RED'
            $stopStep = 'bom'
            $stopReason = "UTF-8 BOM found in: " + ($bomFailures -join ', ')
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'bom'; Result = $stopReason }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'crlf'; Result = "0 CRLF in $textScanned text file(s)" }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'bom'; Result = "0 BOM in $textScanned text file(s)" }
    } elseif (-not $SkipCrlfCheck -and (-not $filesToScan -or $filesToScan.Count -eq 0)) {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'crlf'; Result = 'no files selected; skipped' }
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'bom'; Result = 'no files selected; skipped' }
    } else {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'crlf'; Result = 'skipped via -SkipCrlfCheck' }
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'bom'; Result = 'skipped via -SkipCrlfCheck' }
    }

    # Check 10: credential-shaped scan
    if (-not $SkipSecretScan -and $filesToScan -and $filesToScan.Count -gt 0) {
        $scanResult = Invoke-CredentialScan -Files $filesToScan -Root $root

        # Class A: keyword notices
        $totalKeywords = 0
        if ($scanResult.KeywordCounts) {
            foreach ($kv in $scanResult.KeywordCounts.GetEnumerator()) {
                $totalKeywords += $kv.Value
                $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'keyword-notice'; Result = "$($kv.Key): $($kv.Value) keyword occurrence(s)" }
            }
        }
        if ($totalKeywords -eq 0) {
            $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'keyword-notice'; Result = 'no keyword notices' }
        }

        # Class B: credential-shaped matches
        $credMatches = @($scanResult.CredentialMatches)
        if ($credMatches.Count -gt 0) {
            $finalState = 'RED'
            $stopStep = 'credential-shaped'
            $stopReason = "credential-shaped match — human review required in " + (($credMatches | ForEach-Object { "$($_.Path):$($_.LineNum) [$($_.Label)] [REDACTED]" }) -join ', ')
            $results += [PSCustomObject]@{ Level = 'FAIL'; Check = 'credential-shaped'; Result = 'credential-shaped match — human review required [REDACTED]' }
            return [PSCustomObject]@{ Results = $results; FinalState = $finalState; StopStep = $stopStep; StopReason = $stopReason; LocalHead = $localHead; RemoteTracking = $remoteTracking; LsRemote = $lsRemote; Porcelain = $porcelainSummary }
        }
        $results += [PSCustomObject]@{ Level = 'PASS'; Check = 'credential-shaped'; Result = 'no credential-shaped matches' }
    } elseif (-not $SkipSecretScan -and (-not $filesToScan -or $filesToScan.Count -eq 0)) {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'credential-shaped'; Result = 'no files selected; skipped' }
    } else {
        $results += [PSCustomObject]@{ Level = 'NOTICE'; Check = 'credential-shaped'; Result = 'skipped via -SkipSecretScan' }
    }

    return [PSCustomObject]@{
        Results        = $results
        FinalState     = $finalState
        StopStep       = $stopStep
        StopReason     = $stopReason
        LocalHead      = $localHead
        RemoteTracking = $remoteTracking
        LsRemote       = $lsRemote
        Porcelain      = $porcelainSummary
    }
}

function Write-Report {
    param([PSCustomObject]$State)

    foreach ($r in $State.Results) {
        Write-CheckLine -Level $r.Level -Check $r.Check -Result $r.Result
    }

    Write-Host ''
    Write-Host "FINAL STATE: $($State.FinalState)"

    if ($State.FinalState -ne 'GREEN') {
        $lhDisplay = if ($State.LocalHead) { $State.LocalHead } else { 'unavailable' }
        $rtDisplay = if ($State.RemoteTracking) { $State.RemoteTracking } else { 'unavailable' }
        $lrDisplay = if ($State.LsRemote) { $State.LsRemote } else { 'unavailable' }
        Write-Host ''
        Write-Host 'STOPPED AT: ' $State.StopStep
        Write-Host 'REASON: ' $State.StopReason
        Write-Host 'LOCAL HEAD: ' $lhDisplay
        Write-Host 'REMOTE TRACKING: ' $rtDisplay
        Write-Host 'LS-REMOTE: ' $lrDisplay
        Write-Host 'STATUS: ' $State.Porcelain
        Write-Host 'MANUAL NEXT ACTION: review the failing check; do not auto-recover'
    }
}

function Invoke-Verifier {
    $state = Invoke-RepoStateCheck
    Write-Report -State $state
    switch ($state.FinalState) {
        'GREEN' { return $script:ExitCodeGreen }
        'YELLOW' { return $script:ExitCodeYellow }
        'RED' { return $script:ExitCodeRed }
        default { return $script:ExitCodeRed }
    }
}

# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

function Invoke-SelfTest {
    $tempBase = [System.IO.Path]::GetTempPath()
    $tempDir = Join-Path $tempBase ("verify_repo_state_selftest_" + [System.Guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempDir -Force
    $repoDir = Join-Path $tempDir 'repo'
    $remoteDir = Join-Path $tempDir 'remote.git'
    $script:assertionCount = 0
    $allPassed = $true
    $failureMessages = @()
    $pushedLocation = $false

    function Assert-Condition {
        param(
            [string]$Name,
            [scriptblock]$Test,
            [string]$Description
        )
        $script:assertionCount++
        try {
            $result = & $Test
            if ($result) {
                Write-Host "  [PASS] $Name : $Description"
            } else {
                Write-Host "  [FAIL] $Name : $Description"
                Set-Variable -Name 'allPassed' -Value $false -Scope 1
                Set-Variable -Name 'failureMessages' -Value ((Get-Variable -Name 'failureMessages' -Scope 1).Value + @("$Name : $Description")) -Scope 1
            }
        } catch {
            Write-Host "  [FAIL] $Name : $Description -- exception: $($_.Exception.Message)"
            Set-Variable -Name 'allPassed' -Value $false -Scope 1
            Set-Variable -Name 'failureMessages' -Value ((Get-Variable -Name 'failureMessages' -Scope 1).Value + @("$Name : $Description -- exception: $($_.Exception.Message)")) -Scope 1
        }
    }

    try {
        # Step 1: Set up remote and repo
        $null = New-Item -ItemType Directory -Path $remoteDir -Force
        & git init --bare $remoteDir 2>&1 | Out-Null
        & git init $repoDir 2>&1 | Out-Null
        Push-Location $repoDir
        $script:pushedLocation = $true
        & git config user.name 'SelfTest' 2>&1 | Out-Null
        & git config user.email 'selftest@example.invalid' 2>&1 | Out-Null
        & git branch -M master 2>&1 | Out-Null
        & git remote add origin $remoteDir 2>&1 | Out-Null

        # Step 2: Copy this script into the temp repo (so pwsh -File works)
        $testPath = Join-Path $repoDir 'verify_repo_state.ps1'
        Copy-Item -LiteralPath $PSCommandPath -Destination $testPath -Force
        # Ensure LF line endings in the copy
        $scriptText = [System.IO.File]::ReadAllText($PSCommandPath, [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($testPath, $scriptText, [System.Text.UTF8Encoding]::new($false))

        # Step 3: Create initial clean file (LF, no BOM)
        $initFile = Join-Path $repoDir 'README.md'
        [System.IO.File]::WriteAllText($initFile, "# Self-test repository`n", [System.Text.UTF8Encoding]::new($false))
        & git add README.md verify_repo_state.ps1 2>&1 | Out-Null
        & git commit -m 'initial' 2>&1 | Out-Null
        & git push origin master 2>&1 | Out-Null
        $cleanSha = (& git rev-parse HEAD) | Select-Object -First 1

        # Test 1: Clean aligned repo => GREEN
        Write-Host "`n[Test 1] Clean aligned repository expects GREEN"
        $cleanResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha 2>&1)
        $cleanExit = $LASTEXITCODE
        Assert-Condition -Name 'T01-clean-green' -Test { $cleanExit -eq 0 } -Description "exit=$cleanExit (expected 0=GREEN)"

        # Test 2: Incorrect ExpectedSha => RED
        Write-Host "`n[Test 2] Incorrect ExpectedSha expects RED"
        $badSha = '0' * 40
        $badResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $badSha 2>&1)
        $badExit = $LASTEXITCODE
        Assert-Condition -Name 'T02-bad-sha-red' -Test { $badExit -eq 2 } -Description "exit=$badExit (expected 2=RED)"

        # Test 3: Incorrect Branch => RED
        Write-Host "`n[Test 3] Incorrect Branch expects RED"
        $badBranchResult = @(& pwsh -NoProfile -File $testPath -Branch 'wrong-branch' 2>&1)
        $badBranchExit = $LASTEXITCODE
        Assert-Condition -Name 'T03-bad-branch-red' -Test { $badBranchExit -eq 2 } -Description "exit=$badBranchExit (expected 2=RED)"

        # Test 4: Dirty unauthorized path => RED
        Write-Host "`n[Test 4] Dirty unauthorized path expects RED"
        $dirtyFile = Join-Path $repoDir 'unauthorized.txt'
        [System.IO.File]::WriteAllText($dirtyFile, "dirty`n", [System.Text.UTF8Encoding]::new($false))
        $dirtyResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha 2>&1)
        $dirtyExit = $LASTEXITCODE
        Assert-Condition -Name 'T04-dirty-red' -Test { $dirtyExit -eq 2 } -Description "exit=$dirtyExit (expected 2=RED)"
        Remove-Item -LiteralPath $dirtyFile -Force

        # Test 5: AllowDirty with exact authorized path => non-RED
        Write-Host "`n[Test 5] AllowDirty with authorized path expects non-RED"
        $authFile = Join-Path $repoDir 'authorized.txt'
        [System.IO.File]::WriteAllText($authFile, "authorized`n", [System.Text.UTF8Encoding]::new($false))
        $allowResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'authorized.txt' 2>&1)
        $allowExit = $LASTEXITCODE
        Assert-Condition -Name 'T05-allowdirty-pass' -Test { $allowExit -ne 2 } -Description "exit=$allowExit (expected non-RED)"
        Remove-Item -LiteralPath $authFile -Force

        # Test 6: Selected CRLF file => RED
        Write-Host "`n[Test 6] Selected CRLF file expects RED"
        $crlfFile = Join-Path $repoDir 'crlf.txt'
        [System.IO.File]::WriteAllBytes($crlfFile, [System.Text.Encoding]::ASCII.GetBytes("line1`r`nline2`r`n"))
        $crlfResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'crlf.txt' -SkipSecretScan 2>&1)
        $crlfExit = $LASTEXITCODE
        Assert-Condition -Name 'T06-crlf-red' -Test { $crlfExit -eq 2 } -Description "exit=$crlfExit (expected 2=RED)"
        Remove-Item -LiteralPath $crlfFile -Force

        # Test 7: Selected UTF-8-BOM file => RED
        Write-Host "`n[Test 7] Selected UTF-8-BOM file expects RED"
        $bomFile = Join-Path $repoDir 'bom.md'
        $bomContent = [byte[]](0xEF, 0xBB, 0xBF) + [System.Text.Encoding]::ASCII.GetBytes("# BOM test`n")
        [System.IO.File]::WriteAllBytes($bomFile, $bomContent)
        $bomResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'bom.md' -SkipSecretScan 2>&1)
        $bomExit = $LASTEXITCODE
        Assert-Condition -Name 'T07-bom-red' -Test { $bomExit -eq 2 } -Description "exit=$bomExit (expected 2=RED)"
        Remove-Item -LiteralPath $bomFile -Force

        # Test 8: Keyword-only prose => non-blocking
        Write-Host "`n[Test 8] Keyword-only prose expects non-blocking"
        $kwFile = Join-Path $repoDir 'keywords.md'
        [System.IO.File]::WriteAllText($kwFile, "# Docs`nThis mentions token, key, api, secret in prose.`n", [System.Text.UTF8Encoding]::new($false))
        $kwResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'keywords.md' 2>&1)
        $kwExit = $LASTEXITCODE
        Assert-Condition -Name 'T08-keyword-nonblocking' -Test { $kwExit -ne 2 } -Description "exit=$kwExit (expected non-RED)"
        Remove-Item -LiteralPath $kwFile -Force

        # Test 9: Credential-shaped assignment => RED
        Write-Host "`n[Test 9] Credential-shaped assignment expects RED"
        $credFile = Join-Path $repoDir 'config.md'
        $testPrefix = 'ghp' + '_'
        $testBody = '1234567890' + 'abcdefghijklmnop'
        $testCredential = $testPrefix + $testBody
        $credText = "# Config`napi_key = `"$testCredential`"`n"
        [System.IO.File]::WriteAllText($credFile, $credText, [System.Text.UTF8Encoding]::new($false))
        $credResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'config.md' 2>&1)
        $credExit = $LASTEXITCODE
        Assert-Condition -Name 'T09-credential-red' -Test { $credExit -eq 2 } -Description "exit=$credExit (expected 2=RED)"
        # Verify [REDACTED] in output, no raw credential
        $credOutputText = $credResult -join "`n"
        Assert-Condition -Name 'T09-redacted-no-raw' -Test { $credOutputText.Contains('[REDACTED]') -and -not $credOutputText.Contains($testCredential) } -Description "output contains [REDACTED] and not the raw test credential"
        Remove-Item -LiteralPath $credFile -Force

        # Test 10: No selected paths => explicit notice, no all-repo scan
        Write-Host "`n[Test 10] No selected paths expects notice and no all-repo scan"
        $noPathResult = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha 2>&1)
        $noPathExit = $LASTEXITCODE
        $noPathText = $noPathResult -join "`n"
        Assert-Condition -Name 'T10-no-path-notice' -Test { $noPathText.Contains('no files selected') } -Description "output contains explicit 'no files selected' notice"

        # Test 11: Genuine credential containing 'test' substring => RED (exact-equality placeholder rule)
        Write-Host "`n[Test 11] Genuine credential with 'test' substring expects RED"
        $test11File = Join-Path $repoDir 'config11.md'
        $test11Cred = 'contest' + 'Credential' + '123456'
        $test11Text = "# Config`napi_key = `"$test11Cred`"`n"
        [System.IO.File]::WriteAllText($test11File, $test11Text, [System.Text.UTF8Encoding]::new($false))
        $test11Result = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'config11.md' 2>&1)
        $test11Exit = $LASTEXITCODE
        Assert-Condition -Name 'T11-test-substring-not-placeholder' -Test { $test11Exit -eq 2 } -Description "exit=$test11Exit (expected 2=RED, 'test' substring must not exempt)"
        Remove-Item -LiteralPath $test11File -Force

        # Test 12: Exact placeholder 'test-only' => non-RED (exact-equality placeholder rule)
        Write-Host "`n[Test 12] Exact placeholder 'test-only' expects non-RED"
        $test12File = Join-Path $repoDir 'config12.md'
        $test12Text = "# Config`napi_key = `"test-only`"`n"
        [System.IO.File]::WriteAllText($test12File, $test12Text, [System.Text.UTF8Encoding]::new($false))
        $test12Result = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'config12.md' 2>&1)
        $test12Exit = $LASTEXITCODE
        Assert-Condition -Name 'T12-exact-placeholder-nonblocking' -Test { $test12Exit -ne 2 } -Description "exit=$test12Exit (expected non-RED, exact placeholder 'test-only')"
        Remove-Item -LiteralPath $test12File -Force

        # Test 13: Dynamic provider-token value => RED, [REDACTED] present, raw absent
        Write-Host "`n[Test 13] Provider-token value expects RED"
        $test13File = Join-Path $repoDir 'token13.md'
        $test13Token = 'ghp' + '_' + '1234567890' + 'abcdefghijklmnop'
        $test13Text = $test13Token + "`n"
        [System.IO.File]::WriteAllText($test13File, $test13Text, [System.Text.UTF8Encoding]::new($false))
        $test13Result = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'token13.md' 2>&1)
        $test13Exit = $LASTEXITCODE
        Assert-Condition -Name 'T13-provider-token-red' -Test { $test13Exit -eq 2 } -Description "exit=$test13Exit (expected 2=RED)"
        $test13Output = $test13Result -join "`n"
        Assert-Condition -Name 'T13-provider-token-redacted' -Test { $test13Output.Contains('[REDACTED]') -and -not $test13Output.Contains($test13Token) } -Description "output contains [REDACTED] and not raw token"
        Remove-Item -LiteralPath $test13File -Force

        # Test 14: Dynamic private-key header => RED and redacted reporting
        Write-Host "`n[Test 14] Private-key header expects RED"
        $test14File = Join-Path $repoDir 'key14.txt'
        $test14Header = '-----BEGIN ' + 'RSA' + ' PRIVATE KEY-----'
        $test14Text = $test14Header + "`n"
        [System.IO.File]::WriteAllText($test14File, $test14Text, [System.Text.UTF8Encoding]::new($false))
        $test14Result = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'key14.txt' 2>&1)
        $test14Exit = $LASTEXITCODE
        Assert-Condition -Name 'T14-private-key-red' -Test { $test14Exit -eq 2 } -Description "exit=$test14Exit (expected 2=RED)"
        $test14Output = $test14Result -join "`n"
        Assert-Condition -Name 'T14-private-key-redacted' -Test { $test14Output.Contains('[REDACTED]') } -Description "output contains [REDACTED] for private-key header"
        Remove-Item -LiteralPath $test14File -Force

        # Test 15: Dynamic AKIA-form access-key identifier => RED
        Write-Host "`n[Test 15] AKIA-form access-key expects RED"
        $test15File = Join-Path $repoDir 'ak15.txt'
        $test15Key = 'AKIA' + '1234567890abcdef'
        $test15Text = $test15Key + "`n"
        [System.IO.File]::WriteAllText($test15File, $test15Text, [System.Text.UTF8Encoding]::new($false))
        $test15Result = @(& pwsh -NoProfile -File $testPath -ExpectedSha $cleanSha -AllowDirty -Path 'ak15.txt' 2>&1)
        $test15Exit = $LASTEXITCODE
        Assert-Condition -Name 'T15-akia-form-red' -Test { $test15Exit -eq 2 } -Description "exit=$test15Exit (expected 2=RED for AKIA-form key)"
        Remove-Item -LiteralPath $test15File -Force

        # Cleanup: remove any leftovers from tests
        Get-ChildItem -LiteralPath $repoDir -File | Where-Object { $_.Name -ne 'README.md' -and $_.Name -ne 'verify_repo_state.ps1' } | Remove-Item -Force -ErrorAction SilentlyContinue

        if ($script:pushedLocation) {
            Pop-Location
            $script:pushedLocation = $false
        }
    } finally {
        # Ensure working directory is restored before attempting cleanup
        if ($script:pushedLocation) {
            try { Pop-Location } catch { }
            $script:pushedLocation = $false
        }
        # Brief pause to allow any spawned pwsh processes to release file handles
        Start-Sleep -Milliseconds 200
        if (Test-Path -LiteralPath $tempDir) {
            # Best-effort recursive delete; handle access-denied on individual files
            try {
                Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction Stop
            } catch {
                # Log but do not propagate cleanup failure as test failure
            }
        }
    }

    Write-Host ''
    Write-Host "Self-test completed: $script:assertionCount assertions, $(if ($allPassed) { 'all passed' } else { "$($failureMessages.Count) failed" })"
    if (-not $allPassed) {
        foreach ($msg in $failureMessages) {
            Write-Host "  FAILURE: $msg"
        }
        return $script:ExitCodeRed
    }
    Write-Host 'SELF-TEST PASSED'
    return $script:ExitCodeGreen
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if ($SelfTest) {
    $code = Invoke-SelfTest
    exit $code
} else {
    $code = Invoke-Verifier
    exit $code
}
