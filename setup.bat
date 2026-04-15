@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

echo ============================================================
echo  PII Masker ^| セットアップ
echo ============================================================
echo.

set "BASE=%~dp0"
set "PYDIR=%BASE%python"
set "PYEXE=%PYDIR%\python.exe"
set "PYVER=3.12.9"
set "PYZIP=python-%PYVER%-embed-amd64.zip"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/%PYZIP%"

:: ═══════════════════════════════════════════════════════════
::  Step 1: Python 3.12 embedded runtime
:: ═══════════════════════════════════════════════════════════
echo [1/5] Python %PYVER% embedded runtime...
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
echo [2/5] pip のセットアップ...
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
echo [3/5] ライブラリのインストール ^(flask / pillow / pdfplumber / easyocr ...^)...

:: pymasking: リポジトリ内 src/ があればローカルから、なければ PyPI から
if exist "%BASE%src\pymasking\__init__.py" (
    "%PYEXE%" -m pip install -e "%BASE%" --no-warn-script-location -q
) else (
    "%PYEXE%" -m pip install pymasking --no-warn-script-location -q
)

"%PYEXE%" -m pip install flask pillow easyocr --no-warn-script-location -q
echo       ライブラリ完了

:: ═══════════════════════════════════════════════════════════
::  Step 4: NER モデル (GiNZA)
:: ═══════════════════════════════════════════════════════════
echo [4/5] NER モデル ^(GiNZA^) のダウンロード ^(約 100 MB^)...
"%PYEXE%" -m pip install ginza ja-ginza --no-warn-script-location -q
echo       GiNZA インストール完了

:: ═══════════════════════════════════════════════════════════
::  Step 5: 実行ファイルのビルド
:: ═══════════════════════════════════════════════════════════
echo [5/5] 実行ファイル ^(pymasking.exe / mask.exe / unmask.exe^) をビルド中...
"%PYEXE%" -m pip install pyinstaller --no-warn-script-location -q

set "WORK=%BASE%.build_tmp"
if not exist "%WORK%" mkdir "%WORK%"

echo       pymasking.exe...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name pymasking ^
    --distpath "%BASE%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%webapp\exe\web_launcher.py"
if errorlevel 1 ( echo [ERROR] pymasking.exe のビルド失敗 & pause & exit /b 1 )

echo       mask.exe...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name mask ^
    --distpath "%BASE%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%webapp\exe\mask_launcher.py"
if errorlevel 1 ( echo [ERROR] mask.exe のビルド失敗 & pause & exit /b 1 )

echo       unmask.exe...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name unmask ^
    --distpath "%BASE%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%webapp\exe\unmask_launcher.py"
if errorlevel 1 ( echo [ERROR] unmask.exe のビルド失敗 & pause & exit /b 1 )

if exist "%WORK%" rd /s /q "%WORK%"
echo       ビルド完了

echo.
echo ============================================================
echo  セットアップ完了!
echo    pymasking.exe  ^← ダブルクリックで Web UI を起動
echo    mask.exe       ^← CLI マスキング ^(コマンドプロンプトから使用^)
echo    unmask.exe     ^← CLI 復元  ^(コマンドプロンプトから使用^)
echo ============================================================
pause
