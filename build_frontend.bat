@echo off
echo =======================================
echo Compilando Frontend React em Producao...
echo =======================================
cd %~dp0\frontend
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Falha ao compilar o frontend!
    pause
    exit /b %ERRORLEVEL%
)
cd ..
echo.
echo =======================================
echo [SUCESSO] Compilacao Concluida!
echo A pasta frontend/dist foi gerada com sucesso.
echo =======================================
pause
