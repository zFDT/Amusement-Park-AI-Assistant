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

function Test-TcpPort {
  param([int]$Port, [int]$TimeoutMs = 500)
  try {
    $client = [System.Net.Sockets.TcpClient]::new()
    $result = $client.BeginConnect([System.Net.IPAddress]::Loopback, $Port, $null, $null)
    if ($result.AsyncWaitHandle.WaitOne($TimeoutMs)) {
      $client.EndConnect($result)
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

$BackendPort = Get-FreePort -PreferredPort $BackendPort
$FrontendPort = Get-FreePort -PreferredPort $FrontendPort

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  游园AI助手 - 开发环境启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project root : $Root" -ForegroundColor Gray
Write-Host "Backend port : $BackendPort" -ForegroundColor Yellow
Write-Host "Frontend port: $FrontendPort" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# ── Step 1: Docker ─────────────────────────────────────────────────────────

Write-Host "`n[1/4] 启动 Docker 容器..." -ForegroundColor Green
Push-Location $Root
try {
  docker compose up -d 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  [警告] Docker 启动失败或 Docker Desktop 未运行，请手动启动 Docker Desktop" -ForegroundColor Yellow
  } else {
    Write-Host "  [OK] PostgreSQL + Redis 已启动" -ForegroundColor Green
  }
}
catch {
  Write-Host "  [警告] Docker 不可用: $_" -ForegroundColor Yellow
}
finally {
  Pop-Location
}

# ── Step 2: Backend venv & deps ───────────────────────────────────────────

Write-Host "`n[2/4] 准备后端环境..." -ForegroundColor Green
Push-Location "$Root/backend"
try {
  if (-not (Test-Path .venv)) {
    Write-Host "  创建虚拟环境..." -ForegroundColor Gray
    python -m venv .venv
  }
  & .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q 2>&1 | Out-Null
  Write-Host "  [OK] 后端依赖已就绪" -ForegroundColor Green
}
catch {
  Write-Host "  [错误] 后端环境准备失败: $_" -ForegroundColor Red
  throw
}
finally {
  Pop-Location
}

# ── Step 3: Start Backend ─────────────────────────────────────────────────

Write-Host "`n[3/4] 启动后端服务器..." -ForegroundColor Green

$backendCommand = @"
Set-Location '$Root/backend'
`$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port $BackendPort
"@

$backendProcess = Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendCommand) -PassThru
Write-Host "  后端进程已启动 (PID: $($backendProcess.Id))，等待就绪..." -ForegroundColor Gray

# 等待后端健康检查通过（最多 60 秒）
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
  if (Test-TcpPort -Port $BackendPort -TimeoutMs 1000) {
    Write-Host "  [OK] 后端已就绪 (http://127.0.0.1:$BackendPort) [${waited}s]" -ForegroundColor Green
    break
  }
  Write-Host "  等待后端启动... (${waited}s)" -ForegroundColor Gray
  Start-Sleep -Seconds 1
  $waited++
}

if ($waited -ge $maxWait) {
  Write-Host "  [警告] 后端 ${maxWait}s 内未就绪，前端代理可能会失败" -ForegroundColor Yellow
  Write-Host "  请检查后端窗口是否有错误信息" -ForegroundColor Yellow
}

# ── Step 4: Start Frontend ────────────────────────────────────────────────

Write-Host "`n[4/4] 启动前端开发服务器..." -ForegroundColor Green

$frontendCommand = @"
Set-Location '$Root/frontend'
yarn install
`$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:$BackendPort'
& yarn dev --host 127.0.0.1 --port $FrontendPort
"@

Start-Process powershell -ArgumentList @('-NoExit', '-Command', $frontendCommand) | Out-Null
Write-Host "  前端进程已启动，等待 Vite 编译..." -ForegroundColor Gray

# 等待前端就绪
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
  if (Test-TcpPort -Port $FrontendPort -TimeoutMs 1000) {
    Write-Host "  [OK] 前端已就绪 (http://127.0.0.1:$FrontendPort) [${waited}s]" -ForegroundColor Green
    break
  }
  Start-Sleep -Seconds 1
  $waited++
}

# ── Open Browser ──────────────────────────────────────────────────────────

Start-Process "http://127.0.0.1:$FrontendPort"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host "  前端: http://127.0.0.1:$FrontendPort" -ForegroundColor White
Write-Host "  后端: http://127.0.0.1:$BackendPort" -ForegroundColor White
Write-Host "  API:  http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
