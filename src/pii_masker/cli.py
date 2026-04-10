"""
pii-masker CLI

使い方:
  mask   <file> [options]   # マスキング実行
  unmask <file> [options]   # 復元実行
"""

import argparse
import sys
from pathlib import Path


# ━━ ハンドラーマップ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_handler(ext: str):
    """拡張子からハンドラーと出力拡張子を返す"""
    from pii_masker.formats.handler_txt  import process_txt
    from pii_masker.formats.handler_html import process_html
    from pii_masker.formats.handler_svg  import process_svg
    from pii_masker.formats.handler_docx import process_docx
    from pii_masker.formats.handler_pptx import process_pptx
    from pii_masker.formats.handler_pdf  import process_pdf
    from pii_masker.formats.handler_xlsx import process_xlsx

    HANDLERS: dict[str, tuple] = {
        ".txt":  (process_txt,  ".txt"),
        ".html": (process_html, ".html"),
        ".htm":  (process_html, ".htm"),
        ".svg":  (process_svg,  ".svg"),
        ".docx": (process_docx, ".docx"),
        ".pptx": (process_pptx, ".pptx"),
        ".pdf":  (process_pdf,  ".md"),
        ".xlsx": (process_xlsx, ".xlsx"),
    }
    return HANDLERS.get(ext.lower())


SUPPORTED_EXTS = ".txt .html .htm .svg .docx .pptx .pdf .xlsx"


# ━━ mask コマンド ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cmd_mask(args: argparse.Namespace) -> int:
    from pii_masker.engine.masker import Masker

    src = Path(args.file)
    if not src.exists():
        print(f"[error] ファイルが見つかりません: {src}", file=sys.stderr)
        return 1

    handler_info = _get_handler(src.suffix)
    if handler_info is None:
        print(f"[error] 非対応の形式です: {src.suffix}", file=sys.stderr)
        print(f"        対応形式: {SUPPORTED_EXTS}", file=sys.stderr)
        return 1

    handler, out_ext = handler_info

    # 出力先の決定
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = src.with_stem(src.stem + "_masked").with_suffix(out_ext)

    # マッピングファイルの決定
    if args.mapping:
        map_path = Path(args.mapping)
    else:
        map_path = src.with_stem(src.stem + "_mapping").with_suffix(".tsv")

    print(f"[mask] {src.name} → {out_path.name}")

    masker = Masker()

    # 既存マッピングを事前ロード（セッション間でラベルを一貫させる）
    if map_path.exists():
        masker.load_mapping(map_path)
        print(f"[mask] マッピング引き継ぎ: {map_path}")

    output, _, _ = handler(src, masker)

    if isinstance(output, bytes):
        out_path.write_bytes(output)
    else:
        out_path.write_text(output, encoding="utf-8")

    masker.save_mapping(map_path)

    print(f"[mask] 完了")
    print(f"       変換済み: {out_path}")
    print(f"       マッピング: {map_path}")
    return 0


# ━━ unmask コマンド ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def cmd_unmask(args: argparse.Namespace) -> int:
    from pii_masker.engine.masker import Masker

    src = Path(args.file)
    if not src.exists():
        print(f"[error] ファイルが見つかりません: {src}", file=sys.stderr)
        return 1

    ext = src.suffix.lower()
    if ext not in (".txt", ".html", ".htm", ".svg", ".md"):
        print(f"[error] unmask の対応形式: .txt .html .htm .svg .md", file=sys.stderr)
        print(f"        docx/pptx は書式付き復元に未対応です。", file=sys.stderr)
        return 1

    # マッピングファイルの特定
    if args.mapping:
        map_path = Path(args.mapping)
    else:
        # "_masked" を除いた名前の "_mapping.tsv" を自動検索
        stem = src.stem.removesuffix("_masked")
        map_path = src.with_stem(stem + "_mapping").with_suffix(".tsv")

    if not map_path.exists():
        print(f"[error] マッピングファイルが見つかりません: {map_path}", file=sys.stderr)
        print(f"        --mapping で明示的に指定してください。", file=sys.stderr)
        return 1

    # 出力先の決定
    if args.output:
        out_path = Path(args.output)
    else:
        stem = src.stem.removesuffix("_masked")
        out_path = src.with_stem(stem + "_restored").with_suffix(ext)

    print(f"[unmask] {src.name} → {out_path.name}")
    print(f"         マッピング: {map_path}")

    masker = Masker()
    content = src.read_text(encoding="utf-8")
    restored = masker.restore(content, map_path)
    out_path.write_text(restored, encoding="utf-8")

    print(f"[unmask] 完了: {out_path}")
    return 0


# ━━ CLI エントリポイント ━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pii-masker",
        description="個人情報・機密情報マスキングツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # マスキング（出力: 議事録_masked.docx + 議事録_mapping.tsv）
  mask 議事録.docx

  # マスキング（既存のマッピングに追記して一貫性を維持）
  mask 提案書.docx --mapping 共通_mapping.tsv

  # マスキング（出力先を指定）
  mask 議事録.docx --output 送付用.docx --mapping .secret/mapping.tsv

  # 復元
  unmask 議事録_masked.txt

  # 復元（マッピングファイルを明示指定）
  unmask 議事録_masked.txt --mapping .secret/mapping.tsv --output 復元済み.txt
        """,
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── mask ──
    p_mask = sub.add_parser(
        "mask",
        help="ファイルをマスキングする",
        description="ファイル内の機密情報をトークンに変換します。"
                    "既存のマッピングファイルがあれば自動的に読み込み、ラベルを引き継ぎます。",
    )
    p_mask.add_argument("file", help=f"入力ファイル（対応形式: {SUPPORTED_EXTS}）")
    p_mask.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="変換済みファイルの出力先（省略時: <元ファイル名>_masked.<拡張子>）",
    )
    p_mask.add_argument(
        "-m", "--mapping",
        metavar="FILE",
        help="マッピングTSVのパス（省略時: <元ファイル名>_mapping.tsv）。"
             "既存ファイルがあれば読み込んでから追記保存する。",
    )
    p_mask.set_defaults(func=cmd_mask)

    # ── unmask ──
    p_unmask = sub.add_parser(
        "unmask",
        help="マスキングを元に戻す",
        description="マスク済みファイルをマッピングファイルを使って復元します。",
    )
    p_unmask.add_argument("file", help="マスク済みファイル（対応形式: .txt .html .htm .svg .md）")
    p_unmask.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="復元ファイルの出力先（省略時: <元ファイル名>_restored.<拡張子>）",
    )
    p_unmask.add_argument(
        "-m", "--mapping",
        metavar="FILE",
        help="マッピングTSVのパス（省略時: 自動検索）",
    )
    p_unmask.set_defaults(func=cmd_unmask)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
