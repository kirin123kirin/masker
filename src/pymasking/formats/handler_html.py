"""
HTMLファイル (.html/.htm) ハンドラー
タグ・属性は保持し、テキストノードのみマスクする

BOM (EF BB BF) 付き UTF-8 ファイルを読み込んだ場合、
出力ファイルにも BOM を付与して元のエンコーディング指定を維持する。
"""

import re
from pathlib import Path
from pymasking.engine.masker import Masker

_UTF8_BOM = b"\xef\xbb\xbf"

# マスク対象外タグ（スクリプト・スタイルは処理しない）
_SKIP_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

# テキストノード（タグとタグの間）
_TEXT_NODE = re.compile(r"(>)([^<]+)(<)", re.DOTALL)


def process_html(src: Path, masker: Masker) -> tuple[str, str, str]:
    raw = src.read_bytes()
    has_bom = raw.startswith(_UTF8_BOM)
    original = raw.decode("utf-8-sig")  # BOM を除去してデコード

    # script/style はスキップ（プレースホルダーに退避）
    skipped: list[str] = []
    def _stash(m: re.Match) -> str:
        skipped.append(m.group(0))
        return f"%%SKIP{len(skipped)-1}%%"

    working = _SKIP_TAGS.sub(_stash, original)

    # テキストノードをマスク
    def _mask_node(m: re.Match) -> str:
        return m.group(1) + masker.mask(m.group(2)) + m.group(3)

    masked_working = _TEXT_NODE.sub(_mask_node, working)

    # プレースホルダーを元に戻す
    for i, content in enumerate(skipped):
        masked_working = masked_working.replace(f"%%SKIP{i}%%", content)

    # BOM を復元
    output = ("\ufeff" + masked_working) if has_bom else masked_working

    # プレビュー用テキスト抽出（タグ除去）
    original_text = re.sub(r"<[^>]+>", "", original)
    masked_text = re.sub(r"<[^>]+>", "", masked_working)

    return output, original_text, masked_text
