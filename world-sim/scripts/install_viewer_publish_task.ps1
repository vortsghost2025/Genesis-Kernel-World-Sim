# Install (or remove) the scheduled viewer publish.
#
# WHY: the public viewer only refreshed when someone ran the deploy by hand, so
# the world the operator watches went stale between sessions. The old
# `GenesisViewerRefresh` task refreshed a local snapshot and never deployed, so
# it did nothing for the public URL.
#
# WHAT: every 30 minutes, run scripts/publish_viewer.py, which builds the
# bundle, deploys it as a PREVIEW, verifies it, and only then moves the alias.
# A bad build leaves the alias untouched -- that is the whole point, after a
# day of unverified deployments breaking the public URL.
#
# Mirrors the existing GenesisWorldSteward task: runs as seand, Interactive,
# Limited, hidden via scripts/silent_launch.vbs (python would otherwise flash a
# console window every tick).
#
# Usage:
#   pwsh -NoProfile -File install_viewer_publish_task.ps1
#   pwsh -NoProfile -File install_viewer_publish_task.ps1 -IntervalMinutes 60
#   pwsh -NoProfile -File install_viewer_publish_task.ps1 -Uninstall

param(
    [int]$IntervalMinutes = 30,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$TaskName = 'GenesisViewerPublish'
$RepoRoot = 'S:\Genesis Kernel World Sim'
$WScript = Join-Path $env:WINDIR 'System32\wscript.exe'
$Silent = Join-Path $RepoRoot 'world-sim\scripts\silent_launch.vbs'
$Python = 'C:\Users\seand\AppData\Local\Programs\Python\Python313\python.exe'
$Publish = Join-Path $RepoRoot 'world-sim\scripts\publish_viewer.py'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "removed scheduled task: $TaskName"
    } else {
        Write-Output "scheduled task not present: $TaskName"
    }
    return
}

foreach ($p in @($WScript, $Silent, $Python, $Publish)) {
    if (-not (Test-Path $p)) { throw "required path missing: $p" }
}

# silent_launch.vbs takes: <command> [args...]
$cmdArgs = '"{0}" "{1}" "-u" "{2}"' -f $Silent, $Python, $Publish

$action = New-ScheduledTaskAction -Execute $WScript -Argument $cmdArgs
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
# ExecutionTimeLimit is the interval: a build + deploy + verify takes a few
# minutes, and an overrun should not pile up (MultipleInstances IgnoreNew also
# guards this, as does the lock file inside publish_viewer.py).
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $IntervalMinutes) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description ("Publish the Genesis viewer every $IntervalMinutes minutes: " +
                  'build -> deploy preview -> verify -> move alias. ' +
                  'See world-sim/scripts/publish_viewer.py') | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
Write-Output ("installed: {0} [{1}], every {2} min, log: world-sim\.runtime\viewer_publish.log" -f `
    $t.TaskName, $t.State, $IntervalMinutes)
