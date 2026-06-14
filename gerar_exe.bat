@echo off
echo ====================================================
echo Iniciando compilacao do ADB Companion...
echo ====================================================
echo.

echo [1/2] Rodando build_exe.py (frontend + PyInstaller)...
python build_exe.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRO] Ocorreu uma falha ao compilar o executavel.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Rodando build_installer.py (Instalador Inno Setup)...
python build_installer.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [AVISO] Nao foi possivel compilar o instalador do Inno Setup (Inno Setup pode nao estar instalado).
)

echo.
echo ====================================================
echo Processo concluido!
echo ====================================================
pause
