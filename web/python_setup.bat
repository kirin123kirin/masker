@echo off
setlocal
cd /d %~dp0
where python >nul 2>nul
if %errorlevel% neq 0 (
    if not exist "python" mkdir "python"
    cd "python"
    curl -L -o python_tmp.zip "https://www.python.org/ftp/python/3.12.3/python-3.12.3-embed-amd64.zip"
    tar -xf python_tmp.zip
    del python_tmp.zip
)
