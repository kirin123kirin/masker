"""
SVGファイル (.svg) ハンドラー
XMLとして解析し、text/tspan/title/desc 要素のテキストのみマスクする
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from pii_masker.engine.masker import Masker

# テキストコンテンツを持つ要素タグ（名前空間なし・あり両対応）
_TEXT_TAGS = {"text", "tspan", "title", "desc", "textPath"}


def process_svg(src: Path, masker: Masker) -> tuple[str, str, str]:
    original = src.read_text(encoding="utf-8")

    # ElementTree は名前空間をそのまま保持する
    # ただし xmlns 宣言が失われるケースがあるため文字列操作で補完
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    try:
        root = ET.fromstring(original)
    except ET.ParseError as e:
        raise ValueError(f"SVG のパースに失敗しました: {e}")

    original_texts: list[str] = []
    masked_texts: list[str] = []

    def _process_element(elem: ET.Element):
        # タグ名から名前空間を除去して比較
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if local in _TEXT_TAGS:
            if elem.text:
                orig = elem.text
                masked = masker.mask(orig)
                original_texts.append(orig)
                masked_texts.append(masked)
                elem.text = masked
            if elem.tail:
                orig = elem.tail
                masked = masker.mask(orig)
                original_texts.append(orig)
                masked_texts.append(masked)
                elem.tail = masked

        for child in elem:
            _process_element(child)

    _process_element(root)

    # XML 宣言付きで出力
    masked_xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # オリジナルの XML 宣言を先頭に付与
    xml_decl = ""
    if original.startswith("<?xml"):
        decl_end = original.find("?>")
        if decl_end != -1:
            xml_decl = original[:decl_end + 2] + "\n"
    output = xml_decl + masked_xml

    return output, "\n".join(original_texts), "\n".join(masked_texts)
