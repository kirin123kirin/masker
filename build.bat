@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

echo ============================================================
echo  PII Masker ^| 実行ファイルのビルド
echo ============================================================
echo.

set "BASE=%~dp0"
set "PYEXE=%BASE%web\runtime\python.exe"

:: ─── 事前チェック ────────────────────────────────────────────
if not exist "%PYEXE%" (
    echo [ERROR] web\runtime\python.exe が見つかりません。
    echo         先に  web\setup.bat  を実行してください。
    if not "%1"=="nopause" pause
    exit /b 1
)

:: ─── PyInstaller のインストール ──────────────────────────────
echo [1/4] PyInstaller のインストール...
"%PYEXE%" -m pip install pyinstaller --no-warn-script-location -q
if errorlevel 1 ( echo [ERROR] PyInstaller のインストール失敗 & if not "%1"=="nopause" pause & exit /b 1 )
echo       完了

:: ─── ワークディレクトリ ──────────────────────────────────────
set "DIST=%BASE%"
set "WORK=%BASE%.build_tmp"
if not exist "%WORK%" mkdir "%WORK%"

:: ─── pymasking.exe  (Web UI) ─────────────────────────────────
echo [2/4] pymasking.exe をビルド中...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name pymasking ^
    --distpath "%DIST%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%launchers\web_launcher.py"
if errorlevel 1 ( echo [ERROR] pymasking.exe のビルド失敗 & if not "%1"=="nopause" pause & exit /b 1 )
echo       完了 ^→ pymasking.exe

:: ─── mask.exe  (CLI マスキング) ──────────────────────────────
echo [3/4] mask.exe をビルド中...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name mask ^
    --distpath "%DIST%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%launchers\mask_launcher.py"
if errorlevel 1 ( echo [ERROR] mask.exe のビルド失敗 & if not "%1"=="nopause" pause & exit /b 1 )
echo       完了 ^→ mask.exe

:: ─── unmask.exe  (CLI 復元) ──────────────────────────────────
echo [4/4] unmask.exe をビルド中...
"%PYEXE%" -m PyInstaller ^
    --onefile ^
    --console ^
    --name unmask ^
    --distpath "%DIST%" ^
    --workpath "%WORK%" ^
    --specpath "%WORK%" ^
    "%BASE%launchers\unmask_launcher.py"
if errorlevel 1 ( echo [ERROR] unmask.exe のビルド失敗 & if not "%1"=="nopause" pause & exit /b 1 )
echo       完了 ^→ unmask.exe

:: ─── 一時ファイルの削除 ──────────────────────────────────────
if exist "%WORK%" rd /s /q "%WORK%"

echo.
echo ============================================================
echo  ビルド完了!
echo    pymasking.exe  ^← ダブルクリックで Web UI を起動
echo    mask.exe       ^← CLI マスキング
echo    unmask.exe     ^← CLI 復元
echo ============================================================
if not "%1"=="nopause" pause
