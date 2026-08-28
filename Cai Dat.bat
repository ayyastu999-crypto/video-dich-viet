@echo off
setlocal
title Cai dat - Video Dich Viet
cd /d "%~dp0"

echo.
echo   ===================================================
echo      CAI DAT: VIDEO DICH VIET
echo   ===================================================
echo.

echo   [1/5] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo         [LOI] Chua cai Python. Tai ban 3.11 tro len tai python.org
  echo         Nho tick "Add Python to PATH" khi cai.
  pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo         OK - Python %%v

echo   [2/5] Kiem tra FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
  echo         [LOI] Chua co FFmpeg trong PATH.
  echo         Cai bang: winget install Gyan.FFmpeg
  pause & exit /b 1
)
echo         OK

echo   [3/5] Tao moi truong ao .venv...
if exist ".venv\Scripts\python.exe" (
  echo         Da co san, bo qua.
) else (
  python -m venv .venv
  if errorlevel 1 ( echo         [LOI] Tao venv that bai. & pause & exit /b 1 )
  echo         OK
)
set PY=.venv\Scripts\python.exe

echo   [4/5] Cai thu vien co ban... (vai phut)
%PY% -m pip install --quiet --upgrade pip
%PY% -m pip install --quiet -r requirements-app.txt
if errorlevel 1 ( echo         [LOI] Cai that bai. & pause & exit /b 1 )
echo         OK

echo.
echo   [5/5] Card do hoa NVIDIA?
echo         Co GPU thi tach nhac nen va xoa phu de cu se chay duoc,
echo         nhung phai tai them khoang 3GB.
echo.
set /p GPU="        Cai phan GPU? (c/k): "
if /i not "%GPU%"=="c" goto skip_gpu

echo.
echo         Dang cai demucs + easyocr...
%PY% -m pip install --quiet demucs soundfile opencv-python easyocr
echo         Dang cai torch ban CUDA...
echo         (BAT BUOC lam sau cung: 2 goi tren keo torch ban CPU ve,
echo          phai ghi de lai bang ban CUDA thi GPU moi chay)
%PY% -m pip install --quiet --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
%PY% -c "import torch; print('        CUDA:', torch.cuda.is_available())"

:skip_gpu
echo.
echo   ===================================================
echo      XONG!
echo.
echo      Chay app: bam dup file "Dich Video Viet.bat"
echo      Lan dau mo, nhap API key vao o Cai dat (bieu tuong banh rang)
echo      Lay key mien phi: https://aistudio.google.com/apikey
echo   ===================================================
echo.
pause
