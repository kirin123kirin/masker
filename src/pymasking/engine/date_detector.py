"""
日付検出モジュール
正規表現で候補を抽出 → 正規化 → dateutil で解釈 → 文脈フィルタ
"""

import re
from dateutil import parser as du_parser
from dateutil.parser import ParserError

# ━━ 正規化ユーティリティ ━━━━━━━━━━━━━━━━━━━━━━━━

_ZEN_NUM  = str.maketrans("０１２３４５６７８９", "0123456789")
_ZEN_MARK = str.maketrans("／－．　", "/-. ")

_KANJI_DIGIT = {
    "〇":"0","一":"1","二":"2","三":"3","四":"4",
    "五":"5","六":"6","七":"7","八":"8","九":"9",
}

def _normalize(s: str) -> str:
    """全角・漢数字を半角に正規化"""
    s = s.translate(_ZEN_NUM).translate(_ZEN_MARK)
    for k, v in _KANJI_DIGIT.items():
        s = s.replace(k, v)
    # 「十一」→「11」等の十の位
    s = re.sub(r"10(\d)", lambda m: str(10 + int(m.group(1))), s)
    return s

# 和暦 → 西暦オフセット
_GENGO = {
    "令和":"2018","R":"2018",
    "平成":"1988","H":"1988",
    "昭和":"1925","S":"1925",
    "大正":"1911","T":"1911",
    "明治":"1867","M":"1867",
}
_GENGO_PAT = re.compile(r"(令和|平成|昭和|大正|明治|[RHTMS])(\d{1,2})")

def _wareki_to_seireki(s: str) -> str:
    def _repl(m: re.Match) -> str:
        g, y = m.group(1), int(m.group(2))
        offset = int(_GENGO.get(g, "0"))
        return str(offset + y)
    return _GENGO_PAT.sub(_repl, s)

def _to_dateutil_str(s: str) -> str:
    """年月日・漢字区切りをハイフン区切りに変換"""
    s = re.sub(r"年", "-", s)
    s = re.sub(r"月", "-", s)
    s = re.sub(r"日", "",  s)
    return s.strip("-").strip()

# ━━ 候補パターン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# (pattern, needs_context)

_CANDIDATES: list[tuple[re.Pattern, bool]] = [

    # 日本語年月日（西暦・和暦・全角・漢数字すべて対応）
    # 例: 2025年4月1日 / 令和7年4月1日 / ２０２５年４月１日 / 二〇二五年四月一日
    (re.compile(
        r"(?:令和|平成|昭和|大正|明治)?\s*"
        r"[０-９\d〇一二三四五六七八九十]{1,4}年"
        r"\s*[０-９\d〇一二三四五六七八九十]{1,2}月"
        r"(?:\s*[０-９\d〇一二三四五六七八九十]{1,2}日)?"
    ), False),

    # 西暦 スラッシュ: 2025/4/1, 2025/04/01, ２０２５／４／１
    (re.compile(
        r"(?<!\d)[12１２][0-9０-９]{3}[/／][01０１]?[0-9０-９][/／][0-3０-３]?[0-9０-９](?!\d)"
    ), False),

    # 西暦 ハイフン: 2025-04-01, 2025-4-1
    (re.compile(
        r"(?<!\d)[12１２][0-9０-９]{3}[-－][01０１]?[0-9０-９][-－][0-3０-３]?[0-9０-９](?!\d)"
    ), False),

    # 西暦 ドット: 2025.04.01, 2025.4.1
    (re.compile(
        r"(?<!\d)[12１２][0-9０-９]{3}[\.．][01０１]?[0-9０-９][\.．][0-3０-３]?[0-9０-９](?!\d)"
    ), False),

    # 8桁連番: 20250401（「20」で始まる8桁）
    (re.compile(
        r"(?<![\dA-Za-z\-])20[2-9][0-9][01][0-9][0-3][0-9](?![\dA-Za-z\-])"
    ), False),

    # 月日のみ（日本語）: 4月1日 / ４月１日 / 四月一日
    (re.compile(
        r"(?<!\d)[０-９\d〇一二三四五六七八九十]{1,2}月"
        r"\s*[０-９\d〇一二三四五六七八九十]{1,2}日"
    ), False),

    # 英語表記: April 1, 2025 / 1st April 2025 / Apr. 1 2025
    (re.compile(
        r"(?:"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
        r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
        r"|\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
        r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\.?\s+\d{4}"
        r")"
    ), False),

    # 和暦省略形: R7.4.1 / H30.3.31
    # (?<![A-Za-z0-9_]) で英数字・アンダースコアに後続する M/S 等を除外
    # （例: M25ボルト・SM25.3.31・v1R7.4.1 などの誤検出を防ぐ）
    (re.compile(
        r"(?<![A-Za-z0-9_])[RHTMS]\d{1,2}[\.．][01]?\d[\.．][0-3]?\d(?!\d)"
    ), False),

    # MM/DD 年なし（文脈チェック必要）
    (re.compile(
        r"(?<!\d)[01]?\d[/／][0-3]?\d(?!\d)"
    ), True),
]

# 文脈キーワード（前後50文字以内）
_CONTEXT_PAT = re.compile(
    r"(?:年|月|日|date|dated?|as\s+of|on\s+the|〜|から|まで|期限|締切|締め切り"
    r"|納期|予定|時点|以降|以前|当日|翌日|前日|開始|終了|発効|有効|期日"
    r"|schedule|due|deadline|effective|expir)",
    re.IGNORECASE,
)

# ━━ 解釈・検証 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _is_valid_date(raw: str) -> bool:
    """正規化 → dateutil で解釈できるか確認"""
    s = _normalize(raw)
    s = _wareki_to_seireki(s)

    # 年月日漢字区切りをハイフンに変換
    if "年" in s or "月" in s:
        s = _to_dateutil_str(s)

    # 8桁連番
    if re.fullmatch(r"20[2-9]\d[01]\d[0-3]\d", s):
        try:
            m, d = int(s[4:6]), int(s[6:8])
            return 1 <= m <= 12 and 1 <= d <= 31
        except ValueError:
            return False

    try:
        result = du_parser.parse(s, dayfirst=False, yearfirst=True, fuzzy=False)
        return 1900 <= result.year <= 2100
    except (ParserError, ValueError, OverflowError):
        return False

# ━━ メイン検出関数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def find_dates(text: str) -> list[tuple[int, int, str]]:
    """
    テキストから日付を検出し [(start, end, raw_str), ...] を返す。
    重複区間はより長いマッチを優先する。
    """
    hits: list[tuple[int, int, str]] = []

    for pattern, needs_ctx in _CANDIDATES:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            raw = m.group(0)

            if needs_ctx:
                window = text[max(0, start - 50): end + 50]
                if not _CONTEXT_PAT.search(window):
                    continue

            if not _is_valid_date(raw):
                continue

            hits.append((start, end, raw))

    return _dedup(hits)


def _dedup(hits: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """重複・包含区間を除去。より長いマッチを優先。"""
    if not hits:
        return []
    hits = sorted(hits, key=lambda x: -(x[1] - x[0]))
    kept: list[tuple[int, int, str]] = []
    for h in hits:
        hs, he = h[0], h[1]
        if any(s < he and hs < e for s, e, _ in kept):
            continue
        kept.append(h)
    kept.sort(key=lambda x: x[0])
    return kept
