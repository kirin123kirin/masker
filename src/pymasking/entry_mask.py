"""mask.exe から呼ばれるエントリポイント

argv[0] を 'mask' に固定してから cli.main() を呼ぶことで、
mask モード（マスキング）で動作させます。
"""
import sys

sys.argv[0] = "mask"

from pymasking.cli import main  # noqa: E402

main()
