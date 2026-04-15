"""unmask.exe から呼ばれるエントリポイント

argv[0] を 'unmask' に固定してから cli.main() を呼ぶことで、
unmask モード（復元）で動作させます。
"""
import sys

sys.argv[0] = "unmask"

from pymasking.cli import main  # noqa: E402

main()
