@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

echo ============================================================
echo  PII Masker ^| セットアップ
echo ============================================================
echo.

set "BASE=%~dp0"
set "PYDIR=%BASE%runtime"
set "PYEXE=%PYDIR%\python.exe"
set "PYVER=3.12.9"
set "PYZIP=python-%PYVER%-embed-amd64.zip"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/%PYZIP%"

:: ═══════════════════════════════════════════════════════════
::  Step 1: Python 3.12 embedded runtime
:: ═══════════════════════════════════════════════════════════
echo [1/4] Python %PYVER% embedded runtime...
if not exist "%PYDIR%" mkdir "%PYDIR%"

if exist "%PYEXE%" (
    echo       已インストール済み ^(スキップ^)
) else (
    echo       ダウンロード中 ^(約 20 MB^)...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYDIR%\py.zip' -UseBasicParsing"
    if errorlevel 1 ( echo [ERROR] ダウンロード失敗 & pause & exit /b 1 )
    powershell -NoProfile -Command ^
        "Expand-Archive -Path '%PYDIR%\py.zip' -DestinationPath '%PYDIR%' -Force"
    del "%PYDIR%\py.zip"
    echo       展開完了
)

:: python312._pth : "#import site" -> "import site" で pip を有効化
set "PTH=%PYDIR%\python312._pth"
if exist "%PTH%" (
    powershell -NoProfile -Command ^
        "(Get-Content '%PTH%') -replace '^#import site','import site' | Set-Content '%PTH%'"
)

:: ═══════════════════════════════════════════════════════════
::  Step 2: pip
:: ═══════════════════════════════════════════════════════════
echo [2/4] pip のセットアップ...
"%PYEXE%" -m pip --version > nul 2>&1
if errorlevel 1 (
    echo       get-pip.py をダウンロード中...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYDIR%\get-pip.py' -UseBasicParsing"
    "%PYEXE%" "%PYDIR%\get-pip.py" --no-warn-script-location -q
    del "%PYDIR%\get-pip.py"
    echo       pip インストール完了
) else (
    echo       已インストール済み ^(スキップ^)
)

:: ═══════════════════════════════════════════════════════════
::  Step 3: Python ライブラリ
:: ═══════════════════════════════════════════════════════════
echo [3/4] ライブラリのインストール ^(flask / pillow / pdfplumber / easyocr ...^)...

:: pymasking: リポジトリ内 src/ があればローカルから、なければ PyPI から
if exist "%BASE%..\src\pymasking\__init__.py" (
    "%PYEXE%" -m pip install -e "%BASE%.." --no-warn-script-location -q
) else (
    "%PYEXE%" -m pip install pymasking --no-warn-script-location -q
)

"%PYEXE%" -m pip install flask pillow easyocr --no-warn-script-location -q
echo       ライブラリ完了

:: ═══════════════════════════════════════════════════════════
::  Step 4: NER モデル (GiNZA)
:: ═══════════════════════════════════════════════════════════
echo [4/4] NER モデル ^(GiNZA^) のダウンロード ^(約 100 MB^)...
"%PYEXE%" -m pip install ginza ja-ginza --no-warn-script-location -q
echo       GiNZA インストール完了

echo.
echo ============================================================
echo  セットアップ完了!  start.bat で起動してください。
echo ============================================================
pause
