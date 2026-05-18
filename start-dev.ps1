param(
  [int]$BackendPort = 8001,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-FreePort {
  param(
    [int]$PreferredPort
  )

  for ($port = $PreferredPort; $port -lt ($PreferredPort + 50); $port++) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try {
      $listener.Start()
      $listener.Stop()
      return $port
    }
    catch {
      try { $listener.Stop() } catch {}
    }
  }

  throw "No free port found after 50 attempts starting from $PreferredPort."
}

$BackendPort = Get-FreePort -PreferredPort $BackendPort
$FrontendPort = Get-FreePort -PreferredPort $FrontendPort

Write-Host "Project root: $Root" -ForegroundColor Cyan
Write-Host "Backend port: $BackendPort" -ForegroundColor Cyan
Write-Host "Frontend port: $FrontendPort" -ForegroundColor Cyan

Push-Location $Root
try {
  docker compose up -d
}
finally {
  Pop-Location
}

$backendCommand = @"
Set-Location '$Root/backend'
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt



`$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port $BackendPort
"@

$frontendCommand = @"
Set-Location '$Root/frontend'
yarn install
`$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:$BackendPort'
& yarn dev --host 127.0.0.1 --port $FrontendPort
"@

Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendCommand) | Out-Null
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $frontendCommand) | Out-Null

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:$FrontendPort"

Write-Host "Startup complete. The browser will open the frontend URL." -ForegroundColor Green
