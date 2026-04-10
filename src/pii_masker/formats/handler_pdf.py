"""
PDFファイル (.pdf) ハンドラー

方針:
  - pdfplumber でテキスト抽出
  - マスキング処理
  - Markdown 形式で出力（.md ファイルとして保存）
  - スキャンPDF（画像PDF）は非対応と明示

出力フォーマット:
  # ページ 1
  本文テキスト...

  ---

  # ページ 2
  ...
"""

from pathlib import Path
from pii_masker.engine.masker import Masker

try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False


def process_pdf(src: Path, masker: Masker) -> tuple[str, str, str]:
    """
    Returns:
        (output_markdown_str, original_text, masked_text)
    output は .md ファイルとして保存する文字列
    """
    if not _PDFPLUMBER_OK:
        raise RuntimeError(
            "pdfplumber がインストールされていません。\n"
            "pip install pdfplumber を実行してください。"
        )

    original_pages: list[str] = []
    masked_pages:   list[str] = []

    with pdfplumber.open(str(src)) as pdf:
        total = len(pdf.pages)

        if total == 0:
            raise ValueError("PDFにページが見つかりませんでした。")

        for i, page in enumerate(pdf.pages, start=1):
            # テキスト抽出
            raw = page.extract_text(layout=True) or ""

            if not raw.strip():
                # テキストが取れないページ（スキャンPDF等）
                raw = f"[ページ {i}: テキスト抽出不可 — スキャンPDFの可能性があります]"

            masked = masker.mask(raw)
            original_pages.append(raw)
            masked_pages.append(masked)

    # Markdown 組み立て
    original_md = _build_markdown(original_pages)
    masked_md   = _build_markdown(masked_pages)

    return masked_md, original_md, masked_md


def _build_markdown(pages: list[str]) -> str:
    """ページリストを Markdown 文字列に変換"""
    parts: list[str] = []
    for i, text in enumerate(pages, start=1):
        parts.append(f"# ページ {i}\n\n{text.strip()}")
    return "\n\n---\n\n".join(parts) + "\n"
