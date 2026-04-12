"""
テキストファイル (.txt) ハンドラー

BOM (EF BB BF) 付き UTF-8 ファイルを読み込んだ場合、
出力ファイルにも BOM を付与して元のエンコーディング指定を維持する。
"""

from pathlib import Path
from pymasking.engine.masker import Masker

_UTF8_BOM = b"\xef\xbb\xbf"


def process_txt(src: Path, masker: Masker) -> tuple[str, str, str]:
    """
    Returns:
        (output_content, original_text, masked_text)
    """
    raw = src.read_bytes()
    has_bom = raw.startswith(_UTF8_BOM)
    original = raw.decode("utf-8-sig")  # BOM を除去してデコード
    masked = masker.mask(original)
    output = ("\ufeff" + masked) if has_bom else masked
    return output, original, masked
