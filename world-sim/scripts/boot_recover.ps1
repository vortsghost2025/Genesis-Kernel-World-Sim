# Genesis boot recovery - runs at logon, unattended.
#
# Windows updated and rebooted on 2026-09-30, killing a census mid-run,
# and nobody found out for hours. This script is the answer to that, and
# it is registered as a Windows Scheduled Task.
#
# Two rules, both learned the hard way:
#
#   1. Every python script path is passed QUOTED. The repo path contains
#      a space, and an unquoted path makes python try to open "S:\Genesis"
#      and exit 2 - silently, from a script that looked like it worked.
#   2. Every launch is VERIFIED alive afterwards. A start that reports a
#      pid is not a start that worked. A boot script which says "started"
#      while its process died is the same class of bug as a run that
#      reported "complete" while both agents were frozen.
#
# Idempotent: each step checks before starting anything, so a second run
# is a no-op rather than a duplicate writing one store.
#
# NOT the sim's own scheduler/daemon - this is OS-level autostart for the
# monitoring and recovery layer. world-sim/data is only read.

$ErrorActionPreference = "Continue"
$repo = "S:\Genesis Kernel World Sim"
$worldSim = Join-Path $repo "world-sim"
$logDir = Join-Path $worldSim ".scratch\boot"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = (Get-Date -Format "yyyyMMdd-HHmmss")
$log = Join-Path $logDir "boot-$stamp.log"
$failures = @()

function Say([string]$m) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $m"
    Write-Output $line
    Add-Content -Path $log -Value $line
}

# Quote a path for python. Without this, a path containing a space is
# split on the space and python exits 2 with a bare Errno.
function Q([string]$p) { '"' + $p + '"' }

function Running([string]$pattern) {
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -like "*$pattern*" }
    } catch { @() }
}

# Start a python script and PROVE it survived. Returns the process or $null.
function LaunchPy([string]$name, [string]$script, [string[]]$extra,
                  [string]$outDir, [string]$outName) {
    $existing = Running (Split-Path $script -Leaf)
    if ($existing) {
        Say "$name already running (pid $($existing.ProcessId -join ',')) - not starting another"
        return $existing[0]
    }
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $out = Join-Path $outDir $outName
    $err = Join-Path $outDir ($outName -replace '\.log$', '.err.log')
    $argList = @(Q $script) + ($extra | ForEach-Object { Q $_ })
    try {
        $p = Start-Process -FilePath "python" -ArgumentList $argList `
            -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $out -RedirectStandardError $err
    } catch {
        Say "$name FAILED to start: $($_.Exception.Message)"
        $script:failures += $name
        return $null
    }
    Start-Sleep -Milliseconds 1200
    if ($p.HasExited) {
        $tail = (Get-Content $err -Raw -ErrorAction SilentlyContinue)
        if ($tail) { $tail = ($tail -replace "`r?`n", " | ").Trim() }
        Say "$name STARTED BUT DIED (exit $($p.ExitCode)): $tail"
        $script:failures += $name
        return $null
    }
    Say "$name alive pid=$($p.Id)"
    return $p
}

Say "BOOT recovery starting (pwsh $($PSVersionTable.PSVersion))"

# --- 0. Fail closed if the sim is not where we think it is -------------
if (-not (Test-Path (Join-Path $worldSim "scripts\lockstep_chain.py"))) {
    Say "ABORT: world-sim not found at $worldSim - nothing started"
    exit 1
}

# --- 1. Telegram credentials from user scope ---------------------------
# User-scope env vars are not visible to freshly spawned shells, so they
# are read explicitly and passed to every child.
foreach ($name in @("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")) {
    $val = [Environment]::GetEnvironmentVariable($name, "User")
    if ($val) {
        Set-Item -Path "env:$name" -Value $val
    } else {
        Say "WARNING: $name not in user environment - notifications will fail"
        $script:failures += $name
    }
}

# --- 2. Agent watcher (read-only log watcher) --------------------------
LaunchPy "agent_watch" `
    (Join-Path $worldSim "scripts\start_agent_watch.py") @("--restart") `
    (Join-Path $worldSim ".scratch\agent_watch") "boot.stdout.log" | Out-Null

# --- 3. Watch bridge (nudges on new asks / stuck agents) ---------------
LaunchPy "watch_bridge" `
    (Join-Path $worldSim "scripts\watch_bridge.py") @("--interval", "90") `
    (Join-Path $worldSim ".scratch\watch_bridge") "boot.stdout.log" | Out-Null

# --- 4. Recover an interrupted census ---------------------------------
# The decision lives in recover_runs.py and is unit-tested: it resumes
# only when the store shows a genuinely unfinished run, never while a
# chain is alive, and never when it cannot read the store.
$statePath = Join-Path $worldSim ".scratch\lockstep\current_run.json"
$state = $null
if (Test-Path $statePath) {
    $state = Get-Content $statePath -Raw | ConvertFrom-Json
    Say "recorded run: $($state.pair) HB$($state.start)-$($state.end)"
} else {
    Say "no recorded run state - nothing to recover"
}
try {
    $recOut = Join-Path $logDir "recover-$stamp.log"
    $recErr = Join-Path $logDir "recover-$stamp.err"
    $rec = Start-Process -FilePath "python" `
        -ArgumentList (Q (Join-Path $worldSim "scripts\recover_runs.py")) `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $recOut -RedirectStandardError $recErr
    # Bounded poll, NOT -Wait. recover_runs.py launches the resumed chain
    # as a CHILD process that inherits these handles, and PowerShell's
    # -Wait blocks on the whole tree - so the boot script hung for the
    # full duration of the run it had just started. The first version of
    # this script timed out at 400s for exactly that reason.
    $waited = 0
    while (-not $rec.HasExited -and $waited -lt 60) {
        Start-Sleep -Seconds 1
        $waited += 1
    }
    if (-not $rec.HasExited) {
        Say "recover_runs still running after ${waited}s - continuing without its result"
        Say "  (its output so far: " + (((Get-Content $recOut -Raw -ErrorAction SilentlyContinue) -replace "`r?`n", " | ").Trim()) + ")"
    } else {
        $body = (Get-Content $recOut -Raw -ErrorAction SilentlyContinue)
        if ($body) { Say ("recover: " + ($body -replace "`r?`n", " | ").Trim()) }
        if ($rec.ExitCode -ne 0) {
            $e = (Get-Content $recErr -Raw -ErrorAction SilentlyContinue)
            Say "recover_runs exit=$($rec.ExitCode) $e"
            $script:failures += "recover_runs"
        } else {
            Say "recover_runs ok"
        }
    }
} catch {
    Say "recover_runs FAILED: $($_.Exception.Message)"
    $script:failures += "recover_runs"
}

# --- 5. Chain monitor for whatever chain is now running ----------------
# Started LAST: a chain that has just been resumed needs a monitor, and
# re-attaching when none is running costs nothing when one is.
if ($state -and $state.pair) {
    LaunchPy "chain_watch" `
        (Join-Path $worldSim "scripts\chain_watch.py") `
        @("--pair", $state.pair, "--start", $state.start,
          "--end", $state.end, "--progress-every", "25") `
        (Join-Path $worldSim ".scratch\chain_watch") "boot.stdout.log" | Out-Null
} else {
    Say "no run state - chain_watch not started"
}

# --- 6. Say plainly what did not work ----------------------------------
# A boot that half-works must not read as a boot that worked.
if ($failures.Count -eq 0) {
    Say "BOOT recovery complete - all steps healthy"
} else {
    Say "BOOT recovery FINISHED WITH PROBLEMS: $($failures -join ', ')"
    try {
        $env:PYTHONUTF8 = "1"
        $msg = "Genesis: I restarted after a reboot and something did not come back: $($failures -join ', '). The world may not be running. Details in the boot log."
        & python -c "import sys,os; sys.path.insert(0, r'$worldSim\scripts'); from agent_watch import send_telegram; send_telegram({'severity':'warn','title':'boot recovery','pair':'-','agent':'-','heartbeat':'-','body':sys.argv[1]}, os.environ.get('TELEGRAM_BOT_TOKEN',''), os.environ.get('TELEGRAM_CHAT_ID',''))" $msg 2>&1 | Out-Null
    } catch { }
}
Say "log: $log"
exit 0
