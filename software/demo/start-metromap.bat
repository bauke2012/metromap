@echo off
rem MetroMap Live: dubbelklik dit bestand om de demo te starten.
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"
where py >nul 2>nul && (py server.py) || (python server.py)
pause
