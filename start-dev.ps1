param(
  [int]$BackendPort = 8001,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot

# === helper: find free port ==============================================
function Get-FreePort($PreferredPort) {
  for ($p = $PreferredPort; $p -lt ($PreferredPort + 50); $p++) {
    try {
      $l = New-Object Net.Sockets.TcpListener('127.0.0.1', $p)
      $l.Start(); $l.Stop()
      return $p
    } catch {}
  }
  return $PreferredPort
}

# === helper: test if port is listening ===================================
function Test-Port($Port) {
  try {
    $c = New-Object Net.Sockets.TcpClient
    $r = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
    if ($r.AsyncWaitHandle.WaitOne(1000)) {
      $c.EndConnect($r); $c.Close(); return $true
    }
    $c.Close()
  } catch {}
  return $false
}

# === resolve ports =======================================================
$BackendPort = Get-FreePort $BackendPort
$FrontendPort = Get-FreePort $FrontendPort

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Amusement Park AI - Dev Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Root     : $Root"
Write-Host "Backend  : http://127.0.0.1:$BackendPort"
Write-Host "Frontend : http://127.0.0.1:$FrontendPort"
Write-Host "========================================" -ForegroundColor Cyan

# === Step 1: Docker (Redis only — DB is remote, Docker is optional) =====
Write-Host "[1/4] Starting Docker (Redis)..." -ForegroundColor Green
Set-Location $Root
$dockerOk = $false
try {
  docker compose up -d redis 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Redis started" -ForegroundColor Green
    $dockerOk = $true
  } else {
    Write-Host "  [WARN] Docker exit code: $LASTEXITCODE (Redis may be unavailable)" -ForegroundColor Yellow
  }
} catch {
  Write-Host "  [WARN] Docker not running — Redis unavailable, sessions will not persist" -ForegroundColor Yellow
}

# === Step 2: Backend venv & deps =========================================
Write-Host "[2/4] Preparing backend environment..." -ForegroundColor Green
Set-Location "$Root\backend"
try {
  if (-not (Test-Path .venv)) {
    Write-Host "  Creating venv..." -ForegroundColor Gray
    python -m venv .venv
  }
  & .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] pip install failed" -ForegroundColor Red
    Write-Host "Press Enter to exit..."; Read-Host; exit 1
  }
  Write-Host "  [OK] Dependencies ready" -ForegroundColor Green
} catch {
  Write-Host "  [ERROR] Backend prep failed: $_" -ForegroundColor Red
  Write-Host "Press Enter to exit..."; Read-Host; exit 1
}

# === Step 3: Start Backend ===============================================
Write-Host "[3/4] Starting backend server..." -ForegroundColor Green

$beCmd = "Set-Location '$Root\backend'; `$env:PYTHONUTF8='1'; & .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port $BackendPort"
$beProc = Start-Process powershell -ArgumentList @('-NoExit','-Command',$beCmd) -PassThru
Write-Host "  Backend PID=$($beProc.Id), waiting for port $BackendPort ..." -ForegroundColor Gray

$waited = 0
while ($waited -lt 60) {
  if (Test-Port $BackendPort) {
    Write-Host "  [OK] Backend ready ($($waited)s)" -ForegroundColor Green
    break
  }
  Start-Sleep -Seconds 2
  $waited += 2
}
if ($waited -ge 60) {
  Write-Host "  [WARN] Backend not ready after 60s" -ForegroundColor Yellow
}

# === Step 4: Start Frontend ==============================================
Write-Host "[4/4] Starting frontend..." -ForegroundColor Green

$feCmd = "Set-Location '$Root\frontend'; yarn install; `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:$BackendPort'; & yarn dev --host 127.0.0.1 --port $FrontendPort"
$feProc = Start-Process powershell -ArgumentList @('-NoExit','-Command',$feCmd) -PassThru
Write-Host "  Frontend PID=$($feProc.Id), waiting for port $FrontendPort ..." -ForegroundColor Gray

$waited = 0
while ($waited -lt 30) {
  if (Test-Port $FrontendPort) {
    Write-Host "  [OK] Frontend ready ($($waited)s)" -ForegroundColor Green
    break
  }
  Start-Sleep -Seconds 1
  $waited++
}

# === Open Browser =========================================================
Start-Process "http://127.0.0.1:$FrontendPort"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Startup complete!" -ForegroundColor Green
Write-Host "  Frontend : http://127.0.0.1:$FrontendPort" -ForegroundColor White
Write-Host "  Backend  : http://127.0.0.1:$BackendPort" -ForegroundColor White
Write-Host "  Health   : http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nPress Enter to close this window..." -ForegroundColor Gray
Read-Host
