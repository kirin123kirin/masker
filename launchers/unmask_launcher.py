"""unmask.exe  –  PII マスク復元 CLI

python\\python.exe を使用して pymasking の復元 CLI を実行します。

使用例:
  unmask 議事録_masked.txt
  unmask *_masked.txt --mapping shared_mapping.tsv
  unmask                  # クリップボード入力
"""
import os
import subprocess
import sys


def _base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    entry = os.path.join(base, "src", "pymasking", "entry_unmask.py")
    env   = os.environ.copy()
    src   = os.path.join(base, "src")
    if os.path.exists(src):
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")

    sys.exit(subprocess.call([runtime, entry] + sys.argv[1:], env=env))


if __name__ == "__main__":
    main()
