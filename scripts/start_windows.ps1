param([switch]$NoBrowser, [switch]$NoDialog)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$appUrl = 'http://127.0.0.1:5000'
$logDir = Join-Path $env:LOCALAPPDATA 'SniperSight\logs'
$launchLock = New-Object System.Threading.Mutex($false, 'Local\SniperSightDesktopLaunch')
$lockHeld = $false

function Test-AppEndpoint([string]$Url, [string]$ExpectedText) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($response.StatusCode -eq 200 -and $response.Content -match $ExpectedText)
    } catch { return $false }
}

function Start-AppService {
    param([string]$Name, [int]$Port, [string]$Url, [string]$ExpectedText,
          [string]$Executable, [string[]]$ServiceArguments)

    if (Test-AppEndpoint $Url $ExpectedText) { return }
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is occupied, but $Name is not responding correctly. No process was stopped."
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $logDir "$Name-$stamp.out.log"
    $stderr = Join-Path $logDir "$Name-$stamp.err.log"
    $serviceProcess = Start-Process -FilePath $Executable -ArgumentList $ServiceArguments `
        -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $deadline = (Get-Date).AddSeconds(90)
    do {
        if (Test-AppEndpoint $Url $ExpectedText) { return }
        $serviceProcess.Refresh()
        if ($serviceProcess.HasExited) { throw "$Name exited. See $stderr" }
        Start-Sleep -Milliseconds 750
    } while ((Get-Date) -lt $deadline)
    throw "$Name is still starting or unavailable. See $logDir"
}

try {
    try { $lockHeld = $launchLock.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $lockHeld = $true }
    if (-not $lockHeld) { exit 0 }
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $python = Join-Path $repoRoot 'backend\venv\Scripts\python.exe'
    $vite = Join-Path $repoRoot 'node_modules\vite\bin\vite.js'
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    $node = if ($nodeCommand) { $nodeCommand.Source } else { 'C:\nodejs\node-v22.14.0-win-x64\node.exe' }
    foreach ($dependency in @($python, $node, $vite)) {
        if (-not (Test-Path -LiteralPath $dependency)) { throw "Missing dependency: $dependency" }
    }
    # These affect only this launcher and its children. Bots require an explicit UI action.
    $env:PYTHONUNBUFFERED = '1'
    $env:BACKEND_URL = 'http://127.0.0.1:8001'
    Start-AppService -Name 'backend' -Port 8001 -Url 'http://127.0.0.1:8001/api/health' `
        -ExpectedText 'healthy' -Executable $python `
        -ServiceArguments @('-B', '-m', 'uvicorn', 'backend.api_server:app', '--host', '127.0.0.1', '--port', '8001')
    Start-AppService -Name 'frontend' -Port 5000 -Url $appUrl `
        -ExpectedText 'SniperSight' -Executable $node `
        -ServiceArguments @(('"' + $vite + '"'), '--host', '127.0.0.1', '--port', '5000', '--strictPort')
    if (-not (Test-AppEndpoint "$appUrl/api/health" 'healthy')) {
        throw "The dashboard cannot reach the backend. See $logDir"
    }
    if (-not $NoBrowser) { Start-Process $appUrl }
    Write-Output "SniperSight is ready at $appUrl"
} catch {
    if (-not $NoDialog) {
        $popup = New-Object -ComObject WScript.Shell
        $popup.Popup($_.Exception.Message, 0, 'SniperSight startup', 16) | Out-Null
    }
    Write-Error $_
    exit 1
} finally {
    if ($lockHeld) { $launchLock.ReleaseMutex() }
    $launchLock.Dispose()
}
