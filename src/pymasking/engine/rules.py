"""
マスキングルール定義
優先度順（上が先に適用される）:
  日付 → 郵便番号付き住所 → 都道府県起点住所 → 市区町村住所
  → 建物 → 地名言及 → メール → SNS → 電話
  → 特許 → シリアル → 型番 → 金額 → 数値 → 年齢
"""

import re

# ── 都道府県リスト ──
PREFECTURES = [
    "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
    "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
    "新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県",
    "静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県",
    "奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県",
    "徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県",
    "熊本県","大分県","宮崎県","鹿児島県","沖縄県",
]

PREFECTURE_NAMES = [p.rstrip("都道府県") for p in PREFECTURES]

_BUILDING_SUFFIX = (
    r"(?:ビル(?:ディング)?|タワー|マンション|アパート"
    r"|ハイツ|コーポ|レジデンス|プラザ|センター|ホール|スクエア)"
)
_BUILDING = (
    r"[^\s\u3000、。\n]{1,20}" + _BUILDING_SUFFIX +
    r"(?:\d+館)?(?:\s*(?:\d+F|\d+階|\d+号室|[A-Za-z]?\d+))?"
)

_GENGO = r"(?:令和|平成|昭和|大正|明治)"


def _age_to_decade(m: re.Match) -> str:
    age = int(m.group(1))
    return f"{(age // 10) * 10}代"


RULES: list[tuple[str, re.Pattern, callable]] = [

    # ━━ 日付（最優先）━━
    (
        "日付",
        re.compile(r"\d{4}年\d{1,2}月(?:\d{1,2}日)?"),
        lambda m: "【日付{token}】",
    ),
    (
        "日付",
        re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"),
        lambda m: "【日付{token}】",
    ),
    (
        "日付",
        re.compile(r"(?<!\d)\d{1,2}月\d{1,2}日"),
        lambda m: "【日付{token}】",
    ),
    (
        "日付",
        re.compile(_GENGO + r"\d+年\d{1,2}月(?:\d{1,2}日)?"),
        lambda m: "【日付{token}】",
    ),

    # ━━ 住所 ━━
    (
        "住所",
        re.compile(
            r"〒\s*\d{3}[-－]\d{4}"
            r"(?:\s*(?:" + "|".join(re.escape(p) for p in PREFECTURES) + r"))?"
            r"(?:[^\s\u3000。、\n]{1,50})?"
        ),
        lambda m: "〒【住所{token}】",
    ),
    (
        "住所",
        re.compile(
            r"(?P<pref>" + "|".join(re.escape(p) for p in PREFECTURES) + r")"
            r"[^\s\u3000。、\n]{2,60}"
        ),
        lambda m: m.group("pref") + "【住所{token}】",
    ),
    (
        "住所",
        re.compile(
            r"[^\s\u3000。、\n]{2,6}(?:市|区|町|村)"
            r"[^\s\u3000。、\n]{1,40}"
        ),
        lambda m: "【住所{token}】",
    ),
    (
        "住所",
        re.compile(_BUILDING),
        lambda m: "【住所{token}】",
    ),
    (
        "住所",
        re.compile(
            r"(?P<pref2>" + "|".join(re.escape(p) for p in PREFECTURE_NAMES) + r")"
            r"(?P<suf>支社|支店|営業所|オフィス|本社|拠点|工場|センター|倉庫|事業所)"
        ),
        lambda m: "【住所{token}】" + m.group("suf"),
    ),

    # ━━ 連絡先 ━━
    (
        "メール",
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        lambda m: "【メール{token}】",
    ),
    (
        "SNS",
        re.compile(
            r"(?:"
            r"@[\w\-\.]{1,50}"
            r"|(?:twitter|x|instagram|facebook)\.com/[\w\-\.]{1,50}"
            r"|linkedin\.com/in/[\w\-]{1,50}"
            r"|github\.com/[\w\-]{1,50}"
            r"|tiktok\.com/@[\w\-\.]{1,50}"
            r"|youtube\.com/@[\w\-\.]{1,50}"
            r"|@[\w\u3040-\u9FFF\u30A0-\u30FF]+#\d{4}"
            r")"
        ),
        lambda m: "【SNS{token}】",
    ),
    (
        "電話",
        re.compile(
            r"(?:"
            r"\+81[\-\s]?\d{1,4}[\-\s]?\d{1,4}[\-\s]?\d{4}"
            r"|0\d{1,4}[\-\s]\d{1,4}[\-\s]\d{4}"
            r"|0[789]0[\-\s]\d{4}[\-\s]\d{4}"
            r"|0120[\-\s]\d{3}[\-\s]\d{3}"
            r")"
        ),
        lambda m: "【電話{token}】",
    ),

    # ━━ 番号類 ━━
    (
        "特許",
        re.compile(
            r"(?P<pre>(?:特許|実用新案|意匠|商標)(?:登録)?第)(?P<num>[\d,，]+)(?P<suf>号)"
            r"|(?P<intl>(?:US|EP|JP|WO)\s*(?:Patent\s*)?)(?P<intlnum>[\d,，/]+(?:\s*[AB]\d?)?)"
            r"|(?P<app>特願\d{4}[-－]\d+)"
            r"|(?P<pub>特開\d{4}[-－]\d+)"
        ),
        lambda m: (
            (m.group("pre") or "") + "【特許{token}】" + (m.group("suf") or "")
            if m.group("pre") else
            (m.group("intl") or "") + "【特許{token}】"
            if m.group("intl") else
            "【特許{token}】"
        ),
    ),
    (
        "シリアル",
        re.compile(
            r"(?:S/?N|シリアル(?:番号)?|製造番号|SERIAL)[\s:：]?\s*[A-Z0-9\-]{4,24}"
            r"|(?<![A-Z])[A-Z]{2,4}\d{6,12}(?![A-Z\d])"
        ),
        lambda m: "【シリアル{token}】",
    ),
    (
        "型番",
        re.compile(
            r"(?:型番|型式|品番|モデル|Model|Part\s*No\.?|P/?N)[\s:：]?\s*"
            r"[A-Z0-9][A-Z0-9\-－_/\.]{3,24}"
            r"|(?<![A-Z\d])[A-Z]{1,5}[-－]\d{3,8}(?:[-－][A-Z0-9]{1,6})?(?![A-Z\d])"
        ),
        lambda m: "【型番{token}】",
    ),

    # ━━ 数値 ━━
    (
        "金額",
        re.compile(
            r"(?:[¥￥]\s*)?"
            r"(?<!\d)[\d,，]+(?:\.\d+)?"
            r"(?=\s*(?:億|万|千)?円)"
        ),
        lambda m: "【金額{token}】",
    ),
    (
        "数値",
        re.compile(
            r"(?<!\d)\d+(?:\.\d+)?"
            r"(?=\s*(?:"
            r"kg|g(?!円)|mg|t(?!円)|km|cm|mm|μm|nm"
            r"|m(?!円|月|日|分|名|枚)"
            r"|mL|ml|㎥|m²|m3|m2|L(?!円)"
            r"|W(?!円)|kW|MW|V(?!円)|A(?!円)|Hz|dB|kWh|Wh"
            r"|℃|°C|°F|K(?!円)"
            r"|rpm|bps|Mbps|Gbps|kbps|TB|GB|MB|KB"
            r"|個|本|枚|台|件|冊|式|セット|箱|袋|缶"
            r"|時間|秒(?!間)|分(?!間|円|岐)"
            r"|人(?!分)|名(?!円)|社(?!円)|店(?!円)"
            r"))"
        ),
        lambda m: "【数値{token}】",
    ),
    (
        "数値",
        re.compile(
            r"(?<!\d)\d+(?=\s*(?:"
            r"日間?|週間?|ヶ月間?|か月間?|カ月間?"  # 期間（日間・日も含む）
            r"))"
        ),
        lambda m: "【数値{token}】",
    ),
    (
        "数値",
        re.compile(
            # 「45日」「5日以内」など単独の日数（日付・日間でない）
            r"(?<!\d)\d+(?=\s*日(?!間|付|程|時|々|曜|数|照|野|産|米|系|本(?!社)))"
        ),
        lambda m: "【数値{token}】",
    ),

    # ━━ 年齢（直接変換）━━
    (
        "年齢",
        re.compile(r"(?<!\d)(\d{1,2})歳(?!\d)"),
        _age_to_decade,
    ),
]
