# Refresh the viewer snapshot every 15 minutes
$wsRoot = "S:\Genesis Kernel World Sim\world-sim"
$viewerDir = "$wsRoot\viewer"
try {
    python "$wsRoot\scripts\export_viewer_snapshot.py" --slim --out "$viewerDir\viewer_data.js" 2>&1 | Out-Null
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] viewer refreshed"
} catch {
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] refresh failed: $($_.Exception.Message)"
}
