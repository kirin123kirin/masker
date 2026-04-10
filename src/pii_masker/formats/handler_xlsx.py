"""
Excelファイル (.xlsx) ハンドラー

マスキング方針:
  文字列セル → マスキングエンジンに通す（書式保持）
  数値セル   → 保持（変更しない）
  数式セル   → 保持（変更しない）
  空セル     → スキップ
"""

import io
from pathlib import Path
from pii_masker.engine.masker import Masker

try:
    import openpyxl
    _OPENPYXL_OK = True
except ImportError:
    _OPENPYXL_OK = False


def process_xlsx(src: Path, masker: Masker) -> tuple[bytes, str, str]:
    """
    Returns:
        (output_bytes, original_text, masked_text)
    """
    if not _OPENPYXL_OK:
        raise RuntimeError(
            "openpyxl がインストールされていません。\n"
            "pip install openpyxl を実行してください。"
        )

    wb = openpyxl.load_workbook(str(src), data_only=False)

    all_original: list[str] = []
    all_masked:   list[str] = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                # 文字列以外（数値・数式・bool・空）はすべてスキップ
                if not isinstance(cell.value, str):
                    continue
                original = cell.value.strip()
                if not original:
                    continue

                masked = masker.mask(original)
                if original != masked:
                    all_original.append(original)
                    all_masked.append(masked)
                    cell.value = masked

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), "\n".join(all_original), "\n".join(all_masked)
