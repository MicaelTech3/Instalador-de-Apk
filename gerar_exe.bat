@echo off
echo =======================================
echo Gerando Executavel (.exe) do ADB Companion...
echo =======================================
call "%~dp0\.venv\Scripts\activate.bat"
python "%~dp0\build_exe.py"
pause
