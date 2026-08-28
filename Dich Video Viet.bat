@echo off
chcp 65001 >nul
title Video Dich Viet  -  http://localhost:5177
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [LOI] Khong tim thay .venv trong thu muc nay.
  echo   Chay lenh sau de tao lai:
  echo       python -m venv .venv
  echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo.
echo   ===================================================
echo      VIDEO DICH VIET
echo.
echo      Dia chi:  http://localhost:5177
echo      Trinh duyet se tu mo sau vai giay.
echo.
echo      DONG CUA SO NAY = TAT SERVER
echo   ===================================================
echo.

rem Mo trinh duyet sau 5 giay (doi server kip khoi dong), khong chan tien trinh chinh
start "" /b cmd /c "timeout /t 5 /nobreak >nul & explorer http://localhost:5177"

.venv\Scripts\python.exe -m uvicorn webui.server:app --port 5177

echo.
echo   Server da dung. Nhan phim bat ky de dong cua so.
pause >nul
