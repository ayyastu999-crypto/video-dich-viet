# deploy.ps1 — Deploy/cập nhật Web UI Douyin Pipeline
# Yêu cầu PowerShell 5+. Chạy:
#   powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -SkipGit -Port 7860

param(
    [int]$Port = 7860,
    [switch]$SkipGit,
    [switch]$SkipPip,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "  [X]  $msg" -ForegroundColor Red }

Step "Triển khai Douyin Pipeline tại $Root"

# 1) git pull
if (-not $SkipGit) {
    Step "Cập nhật mã nguồn (git pull)"
    if (Test-Path ".git") {
        try {
            git fetch --all 2>&1 | Out-Host
            git pull --ff-only 2>&1 | Out-Host
            Ok "git pull thành công"
        } catch {
            Warn "git pull lỗi: $_  -- bỏ qua"
        }
    } else {
        Warn "Không phải git repo — bỏ qua"
    }
} else {
    Warn "Bỏ qua git theo yêu cầu (-SkipGit)"
}

# 2) pip install
if (-not $SkipPip) {
    Step "Cập nhật phụ thuộc Python"
    try {
        python -m pip install --upgrade pip 2>&1 | Out-Host
        if (Test-Path "requirements.txt") {
            python -m pip install -r requirements.txt --upgrade 2>&1 | Out-Host
            Ok "Đã cập nhật requirements.txt"
        } else {
            Warn "Không thấy requirements.txt"
        }
    } catch {
        Fail "pip install lỗi: $_"
        exit 1
    }
} else {
    Warn "Bỏ qua pip theo yêu cầu (-SkipPip)"
}

# 3) Restart Web UI
if (-not $NoRestart) {
    Step "Khởi động lại Web UI (port $Port)"
    # Kill process đang giữ port
    $pids = @()
    try {
        $pids = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                 Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        # Fallback netstat
        $lines = netstat -ano -p TCP | Select-String ":$Port " | Select-String "LISTENING"
        foreach ($line in $lines) {
            $tok = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
            if ($tok.Length -ge 1) { $pids += $tok[-1] }
        }
        $pids = $pids | Select-Object -Unique
    }

    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Ok "Đã dừng PID $procId"
        } catch {
            Warn "Không dừng được PID ${procId}: $_"
        }
    }

    Start-Sleep -Seconds 2

    # Khởi động Web UI ở background
    $logDir = Join-Path $Root "workspace\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $logFile = Join-Path $logDir "web_ui.log"

    $proc = Start-Process -FilePath "python" `
        -ArgumentList @("-u", "scripts\run_web.py", "--port", "$Port", "--no-browser") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logFile.err" `
        -PassThru `
        -WindowStyle Hidden
    Ok "Web UI khởi động — PID $($proc.Id), log: $logFile"
} else {
    Warn "Bỏ qua restart theo yêu cầu (-NoRestart)"
}

# 4) Smoke test
Step "Smoke test (chờ Web UI sẵn sàng)"
$ok = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Ok "Web UI phản hồi 200 OK sau $($i*3)s"
            $ok = $true
            break
        }
    } catch {
        Write-Host "  ... thử lần $i/20" -ForegroundColor DarkGray
    }
}

if (-not $ok) {
    Fail "Web UI không phản hồi sau 60s — kiểm tra workspace\logs\web_ui.log"
    exit 1
}

Step "Triển khai hoàn tất"
Write-Host "  Truy cập: http://localhost:$Port" -ForegroundColor Green
exit 0
