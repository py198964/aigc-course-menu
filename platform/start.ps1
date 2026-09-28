param([string]$Python = "python")
$ErrorActionPreference = 'Stop'
$platformRoot = $PSScriptRoot
$repoRoot = Split-Path $platformRoot -Parent
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv (Join-Path $repoRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
    & $venvPython -m pip install -r (Join-Path $platformRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$runtimeDir = Join-Path $platformRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$pidPath = Join-Path $runtimeDir 'server.pid'
if (Test-Path -LiteralPath $pidPath) {
    $runningPid = [int](Get-Content -LiteralPath $pidPath)
    $running = Get-Process -Id $runningPid -ErrorAction SilentlyContinue
    if ($running) { Write-Output "Existing process: $runningPid. Use stop.ps1 first if restarting."; exit 0 }
}
$runFile = Join-Path $platformRoot 'run.py'
$previousPidFile=$env:COURSE_PID_FILE
try {
    $env:COURSE_PID_FILE=$pidPath
    $proc = Start-Process -FilePath $venvPython -ArgumentList @('"' + $runFile + '"') -WorkingDirectory $platformRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'server.log') -RedirectStandardError (Join-Path $runtimeDir 'server-error.log')
} finally { $env:COURSE_PID_FILE=$previousPidFile }
Write-Output "Started PID $($proc.Id). Default URL: http://127.0.0.1:8765"
Write-Output "First login credentials: $runtimeDir\首次登录.txt"
