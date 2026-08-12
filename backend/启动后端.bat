@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0..\.venv\Scripts\activate.bat"
echo.
echo Starting backend at http://127.0.0.1:5000 ...
python app.py
pause
