# install-all.ps1 — Cài đặt 1 lần cho toàn bộ pipeline Douyin
# Chạy:
#   powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install-all.ps1 -SkipKokoro

param(
    [switch]$SkipTorch,
    [switch]$SkipPlaywright,
    [switch]$SkipKokoro,
    [string]$CudaVersion = "cu124"   # cu121 / cu124 tuỳ driver
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$report = @()

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Ok($name, $detail = "")   { Write-Host "  [OK] $name $detail" -ForegroundColor Green; $script:report += @{ name=$name; status="OK"; detail=$detail } }
function Warn($name, $detail = "") { Write-Host "  [!]  $name $detail" -ForegroundColor Yellow; $script:report += @{ name=$name; status="WARN"; detail=$detail } }
function Fail($name, $detail = "") { Write-Host "  [X]  $name $detail" -ForegroundColor Red; $script:report += @{ name=$name; status="FAIL"; detail=$detail } }

Step "Cài đặt 1-click cho Douyin Pipeline"
Write-Host "Thư mục dự án: $Root"

# 0) Kiểm tra Python
Step "Kiểm tra Python"
try {
    $pyver = (python --version) 2>&1
    Ok "Python" $pyver
} catch {
    Fail "Python" "Không thấy 'python' trong PATH"
    exit 1
}

# 1) Nâng cấp pip
Step "Nâng cấp pip"
python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -eq 0) { Ok "pip" } else { Warn "pip" "exit=$LASTEXITCODE" }

# 2) requirements.txt
Step "Cài requirements.txt"
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) { Ok "requirements.txt" } else { Fail "requirements.txt" "exit=$LASTEXITCODE" }
} else {
    Warn "requirements.txt" "không tồn tại"
}

# 3) PyTorch CUDA
if (-not $SkipTorch) {
    Step "Cài PyTorch CUDA ($CudaVersion)"
    python -m pip install --upgrade torch torchvision torchaudio --index-url "https://download.pytorch.org/whl/$CudaVersion"
    if ($LASTEXITCODE -eq 0) {
        # Verify CUDA
        $cudaCheck = python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count(), torch.version.cuda)" 2>&1
        if ($cudaCheck -match "True") {
            Ok "PyTorch CUDA" $cudaCheck
        } else {
            Warn "PyTorch CUDA" "Đã cài nhưng CUDA không khả dụng: $cudaCheck"
        }
    } else {
        Fail "PyTorch CUDA" "exit=$LASTEXITCODE"
    }
} else {
    Warn "PyTorch" "bỏ qua (-SkipTorch)"
}

# 4) Playwright browser
if (-not $SkipPlaywright) {
    Step "Cài Playwright + Chromium"
    python -m pip install --upgrade playwright
    if ($LASTEXITCODE -eq 0) {
        python -m playwright install chromium
        if ($LASTEXITCODE -eq 0) { Ok "Playwright Chromium" } else { Fail "Playwright Chromium" "exit=$LASTEXITCODE" }
    } else {
        Fail "Playwright" "pip exit=$LASTEXITCODE"
    }
} else {
    Warn "Playwright" "bỏ qua (-SkipPlaywright)"
}

# 5) Kokoro models
if (-not $SkipKokoro) {
    Step "Tải mô hình Kokoro TTS"
    $kokoroDir = Join-Path $Root "models\kokoro"
    if (-not (Test-Path $kokoroDir)) { New-Item -ItemType Directory -Path $kokoroDir -Force | Out-Null }
    # Heuristic: nếu đã có file .onnx hoặc .pth là OK
    $existing = Get-ChildItem -Path $kokoroDir -Recurse -Include *.onnx,*.pth,*.bin -ErrorAction SilentlyContinue
    if ($existing) {
        Ok "Kokoro models" "đã có $($existing.Count) file"
    } else {
        # Thử pip install kokoro nếu repo không có script tải riêng
        python -m pip install --upgrade kokoro-onnx 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Ok "kokoro-onnx pip" "(model sẽ tải khi chạy lần đầu)"
        } else {
            Warn "Kokoro" "Không cài tự động được. Tải thủ công vào $kokoroDir"
        }
    }
} else {
    Warn "Kokoro" "bỏ qua (-SkipKokoro)"
}

# 6) FFmpeg + NVENC
Step "Kiểm tra FFmpeg + NVENC"
$ffmpegLocal = Join-Path $Root "workspace\ffmpeg-shared\bin\ffmpeg.exe"
$ffmpegBin = $null
if (Test-Path $ffmpegLocal) {
    $ffmpegBin = $ffmpegLocal
} else {
    try {
        $cmd = Get-Command ffmpeg -ErrorAction Stop
        $ffmpegBin = $cmd.Source
    } catch {}
}

if ($ffmpegBin) {
    $ver = & $ffmpegBin -version 2>&1 | Select-Object -First 1
    $encoders = & $ffmpegBin -hide_banner -encoders 2>&1
    if ($encoders -match "h264_nvenc") {
        Ok "FFmpeg + NVENC" "$ver"
    } else {
        Warn "FFmpeg" "Tìm thấy nhưng KHÔNG có h264_nvenc — sẽ chạy CPU"
    }
} else {
    Fail "FFmpeg" "Không thấy ffmpeg.exe — cài hoặc đặt vào workspace\ffmpeg-shared\bin"
}

# 7) psutil cho monitor
Step "Cài psutil cho monitor"
python -m pip install --upgrade psutil
if ($LASTEXITCODE -eq 0) { Ok "psutil" } else { Warn "psutil" "exit=$LASTEXITCODE" }

# ====== Health check report ======
Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  BÁO CÁO SỨC KHỎE CÀI ĐẶT" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

$okCount   = ($report | Where-Object { $_.status -eq "OK"   }).Count
$warnCount = ($report | Where-Object { $_.status -eq "WARN" }).Count
$failCount = ($report | Where-Object { $_.status -eq "FAIL" }).Count

foreach ($item in $report) {
    $color = switch ($item.status) {
        "OK"   { "Green"  }
        "WARN" { "Yellow" }
        "FAIL" { "Red"    }
    }
    $line = "  [{0,-4}] {1,-25} {2}" -f $item.status, $item.name, $item.detail
    Write-Host $line -ForegroundColor $color
}

Write-Host ""
Write-Host ("  Tổng: {0} OK, {1} cảnh báo, {2} lỗi" -f $okCount, $warnCount, $failCount) -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

if ($failCount -gt 0) {
    Write-Host "Có lỗi nghiêm trọng — xem trên." -ForegroundColor Red
    exit 1
}
Write-Host "Cài đặt hoàn tất. Chạy: python scripts\run_web.py" -ForegroundColor Green
exit 0
