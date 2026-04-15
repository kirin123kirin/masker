"""mask.exe  –  PII マスキング CLI

python\\python.exe を使用して pymasking のマスキング CLI を実行します。

使用例:
  mask 議事録.docx
  mask *.txt --mapping shared_mapping.tsv
  mask                    # クリップボード入力
"""
import os
import subprocess
import sys


def _base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    # 開発実行時: webapp/exe/ の二つ上がリポジトリルート
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    base    = _base_dir()
    runtime = os.path.join(base, "python", "python.exe")

    if not os.path.exists(runtime):
        print(
            "[ERROR] セットアップが未完了です。"
            " setup.bat を実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    entry = os.path.join(base, "src", "pymasking", "entry_mask.py")
    env   = os.environ.copy()
    src   = os.path.join(base, "src")
    if os.path.exists(src):
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")

    sys.exit(subprocess.call([runtime, entry] + sys.argv[1:], env=env))


if __name__ == "__main__":
    main()
