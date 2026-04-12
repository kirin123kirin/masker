"""
pii-masker CLI

使い方:
  mask   [files...] [オプション]   # マスキング実行
  unmask [files...] [オプション]   # 復元実行

ファイル引数はワイルドカード対応（例: *.docx, reports/**/*.txt）

引数なしの場合はクリップボードを入力として使用:
  - エクスプローラーでコピーしたファイル / ファイルパステキスト
      → TEMP ディレクトリに処理後、デフォルトアプリで自動起動
  - その他テキスト
      → マスク/復元してクリップボードに返す
"""

import argparse
import ctypes
import glob as globmod
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SUPPORTED_EXTS = ".txt .html .htm .svg .docx .pptx .pdf .xlsx"


# ━━ ハンドラーマップ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_handler(ext: str):
    e = ext.lower()
    if e == ".txt":
        from pii_masker.formats.handler_txt  import process_txt
        return (process_txt,  ".txt")
    if e in (".html", ".htm"):
        from pii_masker.formats.handler_html import process_html
        return (process_html, e)
    if e == ".svg":
        from pii_masker.formats.handler_svg  import process_svg
        return (process_svg,  ".svg")
    if e == ".docx":
        from pii_masker.formats.handler_docx import process_docx
        return (process_docx, ".docx")
    if e == ".pptx":
        from pii_masker.formats.handler_pptx import process_pptx
        return (process_pptx, ".pptx")
    if e == ".pdf":
        from pii_masker.formats.handler_pdf  import process_pdf
        return (process_pdf,  ".md")
    if e == ".xlsx":
        from pii_masker.formats.handler_xlsx import process_xlsx
        return (process_xlsx, ".xlsx")
    return None


# ━━ ファイルリスト展開 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _expand_files(patterns: list[str]) -> list[Path]:
    """ワイルドカードを展開してファイルリストを返す（Windows でも動作）"""
    result = []
    for pattern in patterns:
        expanded = sorted(globmod.glob(pattern, recursive=True))
        if expanded:
            result.extend(Path(p) for p in expanded)
        else:
            result.append(Path(pattern))  # 展開なし（存在チェックは後で）
    return result


# ━━ デフォルトアプリ起動 ━━━━━━━━━━━━━━━━━━━━━━━━━━

def _open_file(path: Path) -> None:
    """デフォルトアプリでファイルを開く"""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        print(f"[warn] 自動起動に失敗: {e}", file=sys.stderr)


# ━━ クリップボード（プラットフォーム別実装）━━━━━━━━━━━━

def _clipboard_read_files_win32() -> list[Path] | None:
    """Windows: エクスプローラーでコピーしたファイルリストを取得 (CF_HDROP)"""
    if sys.platform != "win32":
        return None
    try:
        user32  = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        CF_HDROP = 15

        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(CF_HDROP)
            if not handle:
                return None
            count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
            files = []
            for i in range(count):
                buf = ctypes.create_unicode_buffer(32768)
                shell32.DragQueryFileW(handle, i, buf, 32768)
                files.append(Path(buf.value))
            return files if files else None
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def _clipboard_paste() -> str:
    """テキストクリップボードを読む（外部依存なし）"""
    # pyperclip があれば優先使用
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except ImportError:
        pass

    if sys.platform == "win32":
        try:
            CF_UNICODETEXT = 13
            user32  = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return ""
                size = kernel32.GlobalSize(handle)
                ptr  = kernel32.GlobalLock(handle)
                raw  = ctypes.string_at(ptr, size)
                kernel32.GlobalUnlock(handle)
                return raw.decode("utf-16-le").rstrip("\x00")
            finally:
                user32.CloseClipboard()
        except Exception:
            return ""
    elif sys.platform == "darwin":
        r = subprocess.run(["pbpaste"], capture_output=True)
        return r.stdout.decode("utf-8", errors="replace")
    else:
        for cmd in [["xclip", "-selection", "clipboard", "-o"],
                    ["xsel", "--clipboard", "--output"]]:
            try:
                r = subprocess.run(cmd, capture_output=True)
                if r.returncode == 0:
                    return r.stdout.decode("utf-8", errors="replace")
            except FileNotFoundError:
                continue
    return ""


def _clipboard_copy(text: str) -> None:
    """テキストをクリップボードにコピー（外部依存なし）"""
    try:
        import pyperclip
        pyperclip.copy(text)
        return
    except ImportError:
        pass

    if sys.platform == "win32":
        try:
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE  = 0x0002
            user32   = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            encoded  = text.encode("utf-16-le") + b"\x00\x00"
            hMem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            ptr  = kernel32.GlobalLock(hMem)
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(hMem)
            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_UNICODETEXT, hMem)
                user32.CloseClipboard()
        except Exception as e:
            print(f"[warn] クリップボードへの書き込みに失敗: {e}", file=sys.stderr)
    elif sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
    else:
        for cmd in [["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"]]:
            try:
                subprocess.run(cmd, input=text.encode(), check=False)
                return
            except FileNotFoundError:
                continue


def _clipboard_read() -> tuple[str, list[Path] | str] | None:
    """
    クリップボードの内容を解析して返す。

    Returns:
        ('files', list[Path])  コピーファイル or ファイルパステキスト
        ('text',  str)         マスク対象のテキスト
        None                   空またはエラー
    """
    # 1. Windows CF_HDROP（エクスプローラーでコピーしたファイル）
    files = _clipboard_read_files_win32()
    if files:
        return ("files", files)

    # 2. テキストクリップボード
    text = _clipboard_paste().strip()
    if not text:
        return None

    # 3. テキストがすべてファイルパスか判定
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        paths = [Path(l) for l in lines if Path(l).exists() and Path(l).is_file()]
        if paths and len(paths) == len(lines):
            return ("files", paths)

    return ("text", text)


# ━━ mask コアロジック ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _do_mask_file(
    src: Path,
    out_path: Path | None,
    map_path: Path | None,
) -> int:
    from pii_masker.engine.masker import Masker

    handler_info = _get_handler(src.suffix)
    if handler_info is None:
        print(f"[error] 非対応の形式: {src.suffix}  （対応: {SUPPORTED_EXTS}）",
              file=sys.stderr)
        return 1

    handler, out_ext = handler_info
    if out_path is None:
        out_path = src.with_stem(src.stem + "_masked").with_suffix(out_ext)
    if map_path is None:
        map_path = src.with_stem(src.stem + "_mapping").with_suffix(".tsv")

    print(f"[mask] {src.name} → {out_path.name}")
    masker = Masker()
    if map_path.exists():
        masker.load_mapping(map_path)
        print(f"       マッピング引き継ぎ: {map_path}")

    output, _, _ = handler(src, masker)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(output, bytes):
        out_path.write_bytes(output)
    else:
        out_path.write_text(output, encoding="utf-8")

    masker.save_mapping(map_path)
    print(f"       完了: {out_path}")
    print(f"       マッピング: {map_path}")
    return 0


# ━━ unmask コアロジック ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _do_unmask_file(
    src: Path,
    out_path: Path | None,
    map_path: Path | None,
) -> int:
    from pii_masker.engine.masker import Masker

    ext = src.suffix.lower()
    if ext not in (".txt", ".html", ".htm", ".svg", ".md"):
        print(f"[error] unmask の対応形式: .txt .html .htm .svg .md", file=sys.stderr)
        return 1

    if map_path is None:
        stem     = src.stem.removesuffix("_masked")
        map_path = src.with_stem(stem + "_mapping").with_suffix(".tsv")

    if not map_path.exists():
        print(f"[error] マッピングファイルが見つかりません: {map_path}", file=sys.stderr)
        print( "        --mapping で明示的に指定してください。", file=sys.stderr)
        return 1

    if out_path is None:
        stem     = src.stem.removesuffix("_masked")
        out_path = src.with_stem(stem + "_restored").with_suffix(ext)

    print(f"[unmask] {src.name} → {out_path.name}")
    masker  = Masker()
    content = src.read_text(encoding="utf-8")
    restored = masker.restore(content, map_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(restored, encoding="utf-8")
    print(f"         完了: {out_path}")
    return 0


# ━━ ファイルコマンド ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cmd_mask(args: argparse.Namespace) -> int:
    files = _expand_files(args.files)
    multi = len(files) > 1
    rc = 0
    for src in files:
        if not src.exists():
            print(f"[error] ファイルが見つかりません: {src}", file=sys.stderr)
            rc = 1
            continue
        out  = Path(args.output)  if (args.output  and not multi) else None
        mapp = Path(args.mapping) if args.mapping                 else None
        rc  |= _do_mask_file(src, out, mapp)
    return rc


def cmd_unmask(args: argparse.Namespace) -> int:
    files = _expand_files(args.files)
    multi = len(files) > 1
    rc = 0
    for src in files:
        if not src.exists():
            print(f"[error] ファイルが見つかりません: {src}", file=sys.stderr)
            rc = 1
            continue
        out  = Path(args.output)  if (args.output  and not multi) else None
        mapp = Path(args.mapping) if args.mapping                 else None
        rc  |= _do_unmask_file(src, out, mapp)
    return rc


# ━━ クリップボードコマンド ━━━━━━━━━━━━━━━━━━━━━━━━━━

def cmd_clipboard(mode: str, args: argparse.Namespace) -> int:
    from pii_masker.engine.masker import Masker

    clip = _clipboard_read()
    if clip is None:
        print("[error] クリップボードが空です", file=sys.stderr)
        return 1

    kind, value = clip

    # ── ファイルモード ──
    if kind == "files":
        temp_dir = Path(tempfile.gettempdir()) / "pii_masker"
        temp_dir.mkdir(parents=True, exist_ok=True)
        rc = 0
        for src in value:
            if mode == "mask":
                handler_info = _get_handler(src.suffix)
                if handler_info is None:
                    print(f"[error] 非対応の形式: {src.suffix}", file=sys.stderr)
                    rc = 1
                    continue
                _, out_ext = handler_info
                out_path = temp_dir / (src.stem + "_masked" + out_ext)
                map_path = temp_dir / (src.stem + "_mapping.tsv")
                r = _do_mask_file(src, out_path, map_path)
            else:
                out_path = temp_dir / (src.stem + "_restored" + src.suffix)
                mapp = Path(args.mapping) if args.mapping else None
                r = _do_unmask_file(src, out_path, mapp)
            rc |= r
            if r == 0:
                print(f"[open] {out_path}")
                _open_file(out_path)
        return rc

    # ── テキストモード ──
    text = value
    if mode == "mask":
        masker = Masker()
        result = masker.mask(text)

        # マッピングを TEMP に保存（後で unmask できるよう）
        temp_dir = Path(tempfile.gettempdir()) / "pii_masker"
        temp_dir.mkdir(parents=True, exist_ok=True)
        map_path = temp_dir / "clipboard_mapping.tsv"
        masker.save_mapping(map_path)

        _clipboard_copy(result)
        print("[mask] テキストをマスキングしてクリップボードに返しました")
        print(f"       マッピング: {map_path}  （unmask -m で使用）")
    else:
        if not args.mapping:
            # デフォルトの TEMP マッピングを自動参照
            default_map = Path(tempfile.gettempdir()) / "pii_masker" / "clipboard_mapping.tsv"
            if default_map.exists():
                map_path = default_map
                print(f"[unmask] マッピング自動使用: {map_path}")
            else:
                print("[error] テキスト復元には --mapping が必要です", file=sys.stderr)
                print(f"        または先に mask を実行してください（{default_map}）",
                      file=sys.stderr)
                return 1
        else:
            map_path = Path(args.mapping)

        masker   = Masker()
        result   = masker.restore(text, map_path)
        _clipboard_copy(result)
        print("[unmask] テキストを復元してクリップボードに返しました")

    return 0


# ━━ パーサー構築 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_parser(mode: str) -> argparse.ArgumentParser:
    epilog_mask = """
使用例:
  mask 議事録.docx
  mask 提案書.docx --mapping 共通_mapping.tsv
  mask reports/*.docx
  mask "C:\\Users\\user\\docs\\*.xlsx"
  mask                              # クリップボードから入力
"""
    epilog_unmask = """
使用例:
  unmask 議事録_masked.txt
  unmask reports/*_masked.txt
  unmask 議事録_masked.txt --mapping .secret/mapping.tsv
  unmask                            # クリップボードから入力
"""
    if mode == "mask":
        desc   = "ファイル内の機密情報をトークンに変換します。"
        epilog = epilog_mask
        files_help = f"入力ファイル（対応: {SUPPORTED_EXTS}）、ワイルドカード可"
    else:
        desc   = "マスク済みファイルをマッピングファイルを使って復元します。"
        epilog = epilog_unmask
        files_help = "マスク済みファイル（対応: .txt .html .htm .svg .md）、ワイルドカード可"

    parser = argparse.ArgumentParser(
        prog=mode,
        description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help=files_help,
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="出力先（単一ファイル指定時のみ有効）",
    )
    parser.add_argument(
        "-m", "--mapping",
        metavar="FILE",
        help="マッピングTSVのパス（省略時は自動決定）",
    )
    return parser


# ━━ エントリポイント ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    # argv[0] のファイル名でマスク/復元を判定
    prog = Path(sys.argv[0]).stem.lower()
    mode = "unmask" if "unmask" in prog else "mask"

    parser = _build_parser(mode)
    args   = parser.parse_args()

    if args.files:
        # ファイル指定モード
        fn = cmd_mask if mode == "mask" else cmd_unmask
        sys.exit(fn(args))
    else:
        # クリップボードモード
        sys.exit(cmd_clipboard(mode, args))


if __name__ == "__main__":
    main()
