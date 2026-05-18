# db/sync.ps1 — 将本地数据库导出并同步到远程服务器
# 用法：
#   .\db\sync.ps1          # 导出本地 -> 上传 -> 导入远程
#   .\db\sync.ps1 -DumpOnly  # 仅导出到 db/dump.sql，不上传

param([switch]$DumpOnly)

$ErrorActionPreference = "Stop"
$DumpFile = "$PSScriptRoot\dump.sql"
$LocalContainer = "amusement-park-ai-assistant-postgres-1"
$RemoteContainer = "hyperliquid-stats-setup-postgres-1"

Write-Host "=== 导出本地数据库 ===" -ForegroundColor Cyan
docker exec $LocalContainer pg_dump -U youyuan youyuan | Out-File -FilePath $DumpFile -Encoding utf8
$size = (Get-Item $DumpFile).Length
Write-Host "导出完成: $([math]::Round($size/1024, 1)) KB -> $DumpFile"

if ($DumpOnly) {
    Write-Host "仅导出模式，跳过上传。" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n=== 上传并导入远程数据库 ===" -ForegroundColor Cyan
$venv = "$PSScriptRoot\..\backend\.venv\Scripts\python"
& $venv "$PSScriptRoot\upload_dump.py"
Write-Host "`n同步完成！" -ForegroundColor Green
