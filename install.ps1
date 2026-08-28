# Cai dat Video Dich Viet bang 1 lenh:
#   irm https://raw.githubusercontent.com/ayyastu999-crypto/video-dich-viet/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$repo = "ayyastu999-crypto/video-dich-viet"
$dest = Join-Path $env:USERPROFILE "video-dich-viet"

Write-Host ""
Write-Host "  ===================================================" -ForegroundColor DarkYellow
Write-Host "     CAI DAT: VIDEO DICH VIET" -ForegroundColor Yellow
Write-Host "  ===================================================" -ForegroundColor DarkYellow
Write-Host ""

# Duong dan cai dat khong dau tieng Viet, tranh loi ma hoa cua cmd
Write-Host "  Se cai vao: $dest"
$ans = Read-Host "  Enter de dong y, hoac go duong dan khac"
if ($ans.Trim()) { $dest = $ans.Trim() }

if (Test-Path $dest) {
  $ow = Read-Host "  Thu muc da ton tai. Ghi de? (c/k)"
  if ($ow -ne "c") { Write-Host "  Da huy."; return }
  Remove-Item -Recurse -Force $dest
}

Write-Host ""
Write-Host "  [1/3] Dang tai ma nguon..." -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP "vdv-$(Get-Random).zip"
Invoke-WebRequest -Uri "https://github.com/$repo/archive/refs/heads/main.zip" -OutFile $tmp

Write-Host "  [2/3] Dang giai nen..." -ForegroundColor Cyan
$stage = Join-Path $env:TEMP "vdv-x-$(Get-Random)"
Expand-Archive -Path $tmp -DestinationPath $stage -Force
$inner = Get-ChildItem $stage -Directory | Select-Object -First 1
Move-Item $inner.FullName $dest
Remove-Item $tmp, $stage -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "  [3/3] Xong phan tai ve." -ForegroundColor Cyan
Write-Host ""
Write-Host "  ===================================================" -ForegroundColor DarkYellow
Write-Host "     Da tai ve: $dest" -ForegroundColor Green
Write-Host ""
Write-Host "     Tiep theo, chay trinh cai dat thu vien:"
Write-Host "       bam dup file  'Cai Dat.bat'  trong thu muc do"
Write-Host ""
Write-Host "     Sau do chay app:"
Write-Host "       bam dup file  'Dich Video Viet.bat'"
Write-Host "  ===================================================" -ForegroundColor DarkYellow
Write-Host ""

$run = Read-Host "  Chay 'Cai Dat.bat' luon bay gio? (c/k)"
if ($run -eq "c") { Start-Process -FilePath (Join-Path $dest "Cai Dat.bat") -WorkingDirectory $dest }
else { Start-Process explorer.exe $dest }
