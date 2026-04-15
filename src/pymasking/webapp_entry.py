"""pymasking.exe（GUI エントリポイント）

pip によって python/Scripts/pymasking.exe として生成され、
setup.bat でリポジトリルートにコピーされます。

pythonw.exe を使用してコンソールウィンドウなしで Flask サーバーを起動します。
"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    # editable install 時は __file__ ベースでリポジトリルートを特定
    # src/pymasking/webapp_entry.py → src/ → masker/
    src_dir = Path(__file__).parent.parent
    if src_dir.name == "src" and (src_dir.parent / "webapp" / "server.py").exists():
        base = src_dir.parent
    else:
        # 通常インストール時: python/python.exe → python/ → masker/
        base = Path(sys.executable).parent.parent

    server = base / "webapp" / "server.py"

    # pythonw.exe でコンソールウィンドウなしで起動
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    exe = pythonw if pythonw.exists() else Path(sys.executable)

    subprocess.Popen([str(exe), str(server)])
