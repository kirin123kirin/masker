"""
Excelファイル (.xlsx) ハンドラー

方針:
  - openpyxl でセルを走査
  - 文字列型セルのみマスク（書式・数値・数式セルは保持）
  - 全シート・全セル対応
"""

import io
from pathlib import Path
from pii_masker.engine.masker import Masker

try:
    import openpyxl
    from openpyxl.cell.cell import TYPE_STRING, TYPE_INLINE, TYPE_FORMULA_CACHE_STRING
    _OPENPYXL_OK = True
except ImportError:
    _OPENPYXL_OK = False

# マスク対象のセルデータ型
_STRING_TYPES = frozenset(("s", "str", "inlineStr"))


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

    wb = openpyxl.load_workbook(str(src))

    all_original: list[str] = []
    all_masked:   list[str] = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                # 文字列セルのみ対象
                # data_type: 's'=文字列, 'n'=数値, 'f'=数式, 'b'=bool, None=空
                if cell.data_type not in _STRING_TYPES:
                    continue
                if not cell.value or not str(cell.value).strip():
                    continue

                original = str(cell.value)
                masked   = masker.mask(original)

                if original != masked:
                    all_original.append(original)
                    all_masked.append(masked)
                    cell.value = masked

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), "\n".join(all_original), "\n".join(all_masked)
