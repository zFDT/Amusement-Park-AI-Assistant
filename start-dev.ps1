param(
  [int]$BackendPort = 8001,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-FreePort {
  param([int]$PreferredPort)
  for ($port = $PreferredPort; $port -lt ($PreferredPort + 50); $port++) {
    $listener = $null
    try {
      $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $port)
      $listener.Start()
      $listener.Stop()
      return $port
    }
    catch {
      if ($listener) { try { $listener.Stop() } catch {} }
    }
  }
  Write-Host "[WARN] No free port found near $PreferredPort, using $PreferredPort" -ForegroundColor Yellow
  return $PreferredPort
}

function Test-TcpPort {
  param([int]$Port, [int]$TimeoutMs = 500)
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    if ($connect.AsyncWaitHandle.WaitOne($TimeoutMs)) {
      $client.EndConnect($connect)
      $client.Close()
      return $true
    }
    $client.Close()
    return $false
  }
  catch {
    return $false
  }
}

# ── Main (wrapped for error visibility) ────────────────────────────────────

try {
  $BackendPort = Get-FreePort -PreferredPort $BackendPort
  $FrontendPort = Get-FreePort -PreferredPort $FrontendPort

  Write-Host "========================================" -ForegroundColor Cyan
  Write-Host "  游园AI助手 - 开发环境启动" -ForegroundColor Cyan
  Write-Host "========================================" -ForegroundColor Cyan
  Write-Host "Project root : $Root" -ForegroundColor Gray
  Write-Host "Backend port : $BackendPort" -ForegroundColor Yellow
  Write-Host "Frontend port: $FrontendPort" -ForegroundColor Yellow
  Write-Host "========================================" -ForegroundColor Cyan

  # ── Step 1: Docker ─────────────────────────────────────────────────────

  Write-Host "`n[1/4] 启动 Docker 容器..." -ForegroundColor Green
  Push-Location $Root
  try {
    $dockerOutput = docker compose up -d 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Host "  [WARN] Docker 可能未运行: $dockerOutput" -ForegroundColor Yellow
    } else {
      Write-Host "  [OK] PostgreSQL + Redis 已启动" -ForegroundColor Green
    }
  }
  catch {
    Write-Host "  [WARN] Docker 不可用，请确保 Docker Desktop 已启动" -ForegroundColor Yellow
  }
  finally {
    Pop-Location
  }

  # ── Step 2: Backend venv & deps ────────────────────────────────────────

  Write-Host "`n[2/4] 准备后端环境..." -ForegroundColor Green
  Push-Location "$Root/backend"
  try {
    if (-not (Test-Path .venv)) {
      Write-Host "  创建虚拟环境..." -ForegroundColor Gray
      python -m venv .venv
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "pip install failed (exit code: $LASTEXITCODE)"
    }
    Write-Host "  [OK] 后端依赖已就绪" -ForegroundColor Green
  }
  catch {
    Write-Host "  [ERROR] 后端环境准备失败: $_" -ForegroundColor Red
    throw
  }
  finally {
    Pop-Location
  }

  # ── Step 3: Start Backend ──────────────────────────────────────────────

  Write-Host "`n[3/4] 启动后端服务器..." -ForegroundColor Green

  $backendCmd = "Set-Location '$Root/backend'; `$env:PYTHONUTF8='1'; & .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port $BackendPort"

  $backendProc = Start-Process powershell -ArgumentList @('-NoExit','-Command',$backendCmd) -PassThru
  Write-Host "  后端进程 PID=$($backendProc.Id)，等待端口 $BackendPort ..." -ForegroundColor Gray

  $maxWait = 60; $waited = 0
  while ($waited -lt $maxWait) {
    if (Test-TcpPort -Port $BackendPort -TimeoutMs 1000) {
      Write-Host "  [OK] 后端已就绪 (${waited}s)" -ForegroundColor Green
      break
    }
    Write-Host "  ...${waited}s" -ForegroundColor Gray -NoNewline
    Start-Sleep -Seconds 2
    $waited += 2
  }
  Write-Host ""

  if ($waited -ge $maxWait) {
    Write-Host "  [WARN] 后端未在 ${maxWait}s 内就绪，请检查后端窗口" -ForegroundColor Yellow
  }

  # ── Step 4: Start Frontend ─────────────────────────────────────────────

  Write-Host "`n[4/4] 启动前端..." -ForegroundColor Green

  $frontendCmd = "Set-Location '$Root/frontend'; yarn install; `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:$BackendPort'; & yarn dev --host 127.0.0.1 --port $FrontendPort"

  Start-Process powershell -ArgumentList @('-NoExit','-Command',$frontendCmd) | Out-Null
  Write-Host "  前端进程已启动，等待端口 $FrontendPort ..." -ForegroundColor Gray

  $maxWait = 30; $waited = 0
  while ($waited -lt $maxWait) {
    if (Test-TcpPort -Port $FrontendPort -TimeoutMs 1000) {
      Write-Host "  [OK] 前端已就绪 (${waited}s)" -ForegroundColor Green
      break
    }
    Start-Sleep -Seconds 1
    $waited++
  }

  # ── Browser ────────────────────────────────────────────────────────────

  Start-Process "http://127.0.0.1:$FrontendPort"

  Write-Host "`n========================================" -ForegroundColor Cyan
  Write-Host "  启动完成！" -ForegroundColor Green
  Write-Host "  前端: http://127.0.0.1:$FrontendPort" -ForegroundColor White
  Write-Host "  后端: http://127.0.0.1:$BackendPort" -ForegroundColor White
  Write-Host "========================================" -ForegroundColor Cyan
}
catch {
  Write-Host "`n[FATAL] 启动失败: $_" -ForegroundColor Red
  Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
}
finally {
  Write-Host "`n按任意键退出..." -ForegroundColor Gray
  Read-Host
}
