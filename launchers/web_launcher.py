"""pymasking.exe  –  PII Masker Web UI を起動します

web\\runtime\\python.exe を使用してローカル Flask サーバーを起動し、
ブラウザで自動的に開きます。
"""
import ctypes
import os
import subprocess
import sys


def _base_dir() -> str:
    """実行ファイル（または本スクリプト）と同じディレクトリの親を返す"""
    if getattr(sys, 'frozen', False):
        # PyInstaller --onefile: sys.executable が .exe のパス
        return os.path.dirname(os.path.abspath(sys.executable))
    # 開発実行時: launchers/ の一つ上がリポジトリルート
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    base    = _base_dir()
    runtime = os.path.join(base, "web", "runtime", "python.exe")
    server  = os.path.join(base, "web", "app", "server.py")

    if not os.path.exists(runtime):
        ctypes.windll.user32.MessageBoxW(
            0,
            "セットアップが未完了です。\n\n"
            "  web\\setup.bat  を実行してから\n"
            "再度起動してください。",
            "PII Masker – セットアップ必要",
            0x10,   # MB_ICONERROR
        )
        sys.exit(1)

    subprocess.run([runtime, server])


if __name__ == "__main__":
    main()
