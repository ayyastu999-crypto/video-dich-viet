@echo off
setlocal enabledelayedexpansion
title Cai dat - Video Dich Viet
cd /d "%~dp0"

echo.
echo   ===================================================
echo      CAI DAT: VIDEO DICH VIET
echo      Thieu gi se tu cai, khong bat ban lam tay.
echo   ===================================================
echo.

:: ---------- 1. Python ----------
echo   [1/5] Kiem tra Python...
python --version >nul 2>&1
if not errorlevel 1 goto py_ok

echo         Chua co Python. Dang cai tu dong...
where winget >nul 2>&1
if errorlevel 1 (
  echo         [LOI] May khong co winget. Tai Python tai python.org
  echo         Nho tick "Add Python to PATH" khi cai.
  pause & exit /b 1
)
winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
echo.
echo   ================================================
echo      Da cai Python. PHAI MO LAI file nay mot lan
echo      nua thi Windows moi nhan duoc lenh python.
echo   ================================================
pause & exit /b 0

:py_ok
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo         OK - Python %%v

:: ---------- 2. FFmpeg ----------
echo   [2/5] Kiem tra FFmpeg...
ffmpeg -version >nul 2>&1
if not errorlevel 1 goto ff_ok

echo         Chua co FFmpeg. Dang cai tu dong...
where winget >nul 2>&1
if errorlevel 1 (
  echo         [LOI] May khong co winget. Tai FFmpeg tai ffmpeg.org
  pause & exit /b 1
)
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements

:: winget ghi PATH vao registry, phien cmd dang chay khong thay ngay.
:: Tim thang file ffmpeg.exe roi them vao PATH cho rieng phien nay.
echo         Dang tim FFmpeg vua cai...
for /f "delims=" %%p in ('dir /b /s "%LOCALAPPDATA%\Microsoft\WinGet\Packages\ffmpeg.exe" 2^>nul') do (
  set "FFDIR=%%~dpp"
  goto ff_found
)
echo.
echo   ================================================
echo      Da cai FFmpeg. PHAI MO LAI file nay mot lan
echo      nua thi Windows moi nhan duoc lenh ffmpeg.
echo   ================================================
pause & exit /b 0

:ff_found
set "PATH=%FFDIR%;%PATH%"
ffmpeg -version >nul 2>&1
if errorlevel 1 (
  echo         [LOI] Cai xong nhung van chua goi duoc. Mo lai file nay.
  pause & exit /b 1
)
echo         OK - da them vao PATH cho phien nay

:ff_ok
echo         OK

:: ---------- 3. Moi truong ao ----------
echo   [3/5] Tao moi truong ao .venv...
if exist ".venv\Scripts\python.exe" (
  echo         Da co san, bo qua.
) else (
  python -m venv .venv
  if errorlevel 1 ( echo         [LOI] Tao venv that bai. & pause & exit /b 1 )
  echo         OK
)
set PY=.venv\Scripts\python.exe

:: ---------- 4. Thu vien co ban ----------
echo   [4/5] Cai thu vien co ban... (vai phut)
%PY% -m pip install --quiet --upgrade pip
%PY% -m pip install --quiet -r requirements-app.txt
if errorlevel 1 ( echo         [LOI] Cai that bai. & pause & exit /b 1 )
echo         OK

:: ---------- 5. Phan GPU ----------
echo.
echo   [5/5] Phan GPU (tach nhac nen + xoa phu de cu)
nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo         May khong co card NVIDIA - bo qua phan nay.
  echo         App van chay binh thuong, chi cham hon.
  goto xong
)
echo         Phat hien card NVIDIA. Phan nay tai them khoang 3GB.
set /p GPU="        Cai luon? (c/k): "
if /i not "%GPU%"=="c" goto xong

echo         Dang cai demucs + easyocr...
%PY% -m pip install --quiet demucs soundfile opencv-python easyocr
echo         Dang cai torch ban CUDA...
echo         (phai lam SAU CUNG: 2 goi tren keo torch ban CPU ve,
echo          khong ghi de lai bang ban CUDA thi GPU khong chay)
%PY% -m pip install --quiet --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
%PY% -c "import torch; print('        CUDA chay duoc:', torch.cuda.is_available())"

:xong
echo.
echo   ===================================================
echo      XONG!
echo.
echo      Chay app: bam dup file "Dich Video Viet.bat"
echo      Lan dau mo, bam nut banh rang de dan API key.
echo      Trong app co nut "Lay key" dan thang toi trang lay.
echo   ===================================================
echo.
pause
