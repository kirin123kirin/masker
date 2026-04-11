"""
SVGファイル (.svg) ハンドラー
XMLとして解析し、text/tspan/title/desc 要素のテキストのみマスクする

エンコーディング:
  ファイルをバイト列として読み込み ET.fromstring(bytes) に渡すことで
  XML宣言 (encoding="...") や BOM を自動処理する。
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from pii_masker.engine.masker import Masker

# テキストコンテンツを持つ要素タグ（名前空間なし・あり両対応）
_TEXT_TAGS = {"text", "tspan", "title", "desc", "textPath"}

# SVG 名前空間をモジュールロード時に登録（出力 XML の xmlns 属性を簡潔に保つ）
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def process_svg(src: Path, masker: Masker) -> tuple[str, str, str]:
    raw_bytes = src.read_bytes()

    # ElementTree がバイト列から XML 宣言のエンコーディングを自動検出する
    try:
        root = ET.fromstring(raw_bytes)
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

    # オリジナルの XML 宣言をバイト列から抽出して先頭に付与
    xml_decl = ""
    stripped = raw_bytes.lstrip()
    if stripped.startswith(b"<?xml"):
        decl_end = stripped.find(b"?>")
        if decl_end != -1:
            xml_decl = stripped[:decl_end + 2].decode("ascii", errors="replace") + "\n"

    output = xml_decl + masked_xml

    return output, "\n".join(original_texts), "\n".join(masked_texts)
