@echo off
chcp 65001 > nul
set "BASE=%~dp0"
set "PYEXE=%BASE%web\runtime\python.exe"

if not exist "%PYEXE%" (
    echo [ERROR] web\runtime\python.exe が見つかりません。
    echo         先に web\setup.bat を実行してください。
    pause & exit /b 1
)

echo [PII Masker] 起動中...
"%PYEXE%" "%BASE%web\app\server.py"
