$ErrorActionPreference='Stop'
$pidPath=Join-Path $PSScriptRoot 'runtime\server.pid'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Output 'No PID file.'; exit 0 }
$runningPid=[int](Get-Content -LiteralPath $pidPath)
$expected=Join-Path $PSScriptRoot 'run.py'
$processes=@(Get-CimInstance Win32_Process | Where-Object { ($_.ProcessId -eq $runningPid -or $_.ParentProcessId -eq $runningPid) -and $_.CommandLine -and $_.CommandLine.Contains($expected) })
if ($processes.Count -gt 0) {
    foreach ($target in ($processes | Sort-Object ProcessId)) { Stop-Process -Id $target.ProcessId -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $pidPath
    Write-Output 'Course platform stopped.'
} elseif (!(Get-Process -Id $runningPid -ErrorAction SilentlyContinue)) { Remove-Item -LiteralPath $pidPath; Write-Output 'Process already stopped.' }
else { throw 'PID belongs to another process; refusing to stop it.' }
