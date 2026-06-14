@echo off
echo ====================================================
echo Limpando arquivos obsoletos e temporarios do projeto...
echo ====================================================
echo.

if exist instalador.py (
    del instalador.py
    echo [OK] Legacy App Tkinter removido.
)

if exist scratch_convert.py (
    del scratch_convert.py
    echo [OK] scratch_convert.py removido.
)

if exist installer.iss (
    del installer.iss
    echo [OK] installer.iss removido.
)

if exist ADB_Companion.spec (
    del ADB_Companion.spec
    echo [OK] ADB_Companion.spec removido.
)

echo.
echo ====================================================
echo Limpeza concluida com sucesso!
echo ====================================================
pause
