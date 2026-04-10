"""
テキストファイル (.txt) ハンドラー
"""

from pathlib import Path
from pii_masker.engine.masker import Masker


def process_txt(src: Path, masker: Masker) -> tuple[str, str, str]:
    """
    Returns:
        (output_content, original_text, masked_text)
    """
    original = src.read_text(encoding="utf-8-sig")  # BOM付きにも対応
    masked = masker.mask(original)
    return masked, original, masked
