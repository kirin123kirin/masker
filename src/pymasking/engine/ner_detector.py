"""
固有表現検出モジュール（人名・組織名）

優先順位:
  1. GiNZA (spaCy) が利用可能な場合 → NLPで高精度検出
  2. 利用不可の場合 → 辞書＋ヒューリスティック方式にフォールバック

ヒューリスティック方式の検出戦略:
  A. カスタム辞書に登録された人名・組織名を直接マッチ
  B. 役職・敬称の直前テキストを人名として抽出
  C. 組織名サフィックスを含む文字列を組織名として抽出
"""

import re
import warnings
from pathlib import Path

# ━━ GiNZA ロード試行 ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_nlp = None
_load_attempted = False  # ロード試行済みフラグ（再試行コストを防ぐ）


def _try_load_ginza() -> bool:
    global _nlp, _load_attempted
    if _load_attempted:
        return _nlp is not None
    _load_attempted = True
    try:
        import spacy
        _nlp = spacy.load("ja_ginza")
        return True
    except ImportError:
        # spaCy / ja_ginza 未インストール → 正常なフォールバック
        return False
    except Exception as e:
        warnings.warn(
            f"GiNZA のロードに失敗しました（ヒューリスティックモードで継続）: {e}",
            stacklevel=2,
        )
        return False

# ━━ 役職・敬称定義 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TITLES = [
    # 役員・経営層（長い順）
    "代表取締役社長", "代表取締役副社長", "代表取締役",
    "取締役社長", "取締役副社長", "取締役会長", "取締役",
    "執行役員", "監査役", "副社長", "会長", "社長", "頭取", "総裁",
    "理事長", "専務", "常務",
    # 管理職
    "本部長", "事業部長", "副部長", "部長", "担当課長", "課長",
    "係長", "主任", "グループ長", "チームリーダー",
    "マネージャー", "ディレクター",
    # 専門職
    "主任研究員", "研究員", "教授", "准教授", "講師", "博士",
    "公認会計士", "弁理士", "弁護士", "税理士", "司法書士", "医師",
    # 英語役職
    "President", "Director", "Manager", "CEO", "CFO", "COO",
    "CTO", "CMO", "CISO",
    # 敬称
    "さん", "様", "氏", "君", "ちゃん", "殿",
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.",
    "Mr", "Mrs", "Ms", "Dr", "Prof",
]
# 長い順にソート（部分マッチ防止）
TITLES = sorted(set(TITLES), key=len, reverse=True)

# ━━ 人名パターン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 日本語人名: 漢字2〜4文字（姓名）またはひらがな・カタカナ混在
_JP_NAME   = r"[\u4E00-\u9FFF]{2,4}(?:[\u3040-\u309F\u30A0-\u30FF]{1,4})?"
# 英語人名: 大文字始まり1〜15文字（ファーストネーム + オプションでラストネーム）
_EN_NAME   = r"[A-Z][a-z]{1,14}(?:\s[A-Z][a-z]{1,14})?"
# 名前全体パターン
_NAME_CORE = rf"(?:{_JP_NAME}|{_EN_NAME})"

# 「名前 + 役職/敬称」のパターン（役職は後方参照でチェック）
_TITLE_PAT_STR = "|".join(re.escape(t) for t in TITLES)
_NAME_TITLE_PAT = re.compile(
    rf"({_NAME_CORE})"         # グループ1: 名前
    rf"(?={_TITLE_PAT_STR})"   # 直後に役職・敬称
)

# ━━ 日本語姓リスト（姓+名パターン用）━━━━━━━━━━━━━━━━━━━━━━━━

JP_SURNAMES: list[str] = sorted({
    # 3文字姓
    "佐々木", "長谷川", "久保田", "小野寺", "五十嵐",
    # 2文字姓
    "田中", "鈴木", "佐藤", "高橋", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "山口", "松本", "井上", "木村", "斎藤", "清水", "山崎", "阿部",
    "池田", "橋本", "山下", "石川", "中島", "前田", "藤田", "後藤", "岡田", "村上",
    "近藤", "石井", "坂本", "遠藤", "青木", "藤井", "西村", "福田", "太田", "三浦",
    "岡本", "松田", "中川", "中野", "原田", "小川", "竹内", "金子", "和田", "中山",
    "藤原", "石田", "上田", "森田", "松井", "菊池", "宮崎", "渡部", "岩田", "久保",
    "野口", "大野", "中田", "村田", "武田", "横山", "野村", "安藤", "松尾", "今井",
    "内田", "水野", "江口", "松下", "黒田", "小野", "吉川", "上野", "大島", "田村",
    "桜井", "川口", "萩原", "菅原", "角田", "栗田", "栗原", "栗山", "永田", "永井",
    "永野", "川上", "川田", "宮田", "宮本", "宮下", "宮川", "宮野", "宮島", "宮内",
    "伊東", "伊野", "伊原", "伊沢", "松岡", "松村", "松浦", "岩崎", "岩本",
    "岸本", "岸田", "小島", "小松", "大西", "大田", "大山", "大石", "大塚",
    "河野", "河田", "河合", "川村", "川本", "川島", "新田", "新井", "新村", "浜田",
    "浜野", "田島", "田原", "田口", "辻", "辻本", "塩田", "塩野", "長田", "長野",
    "織田", "豊臣", "徳川", "足利", "北条", "今川", "上杉", "毛利", "島津", "伊達",
    "源", "平", "森", "林",
}, key=len, reverse=True)

# 名（名前部分）: 漢字1〜3文字 + オプションでひらがな
_JP_GIVEN = r"[\u4E00-\u9FFF]{1,3}(?:[\u3040-\u309F\u30A0-\u30FF]{1,4})?"

# ━━ 組織名パターン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ORG_SUFFIXES = [
    # 法人格（長い順）
    "代表取締役社長", "株式会社", "有限会社", "合同会社", "合資会社", "合名会社",
    "一般社団法人", "公益社団法人", "一般財団法人", "公益財団法人",
    "独立行政法人", "国立研究開発法人", "社会福祉法人", "医療法人",
    "特定非営利活動法人", "NPO法人", "学校法人", "宗教法人",
    "ホールディングス", "コーポレーション", "エンタープライズ",
    "グループ",
    # 英語法人格
    "Inc.", "Corp.", "Ltd.", "LLC", "LLP", "Co.", "GmbH", "AG", "plc",
    # 金融
    "信用金庫", "銀行", "証券", "保険", "信託",
]
_ORG_SUFFIXES = sorted(set(_ORG_SUFFIXES), key=len, reverse=True)
_ORG_SUF_PAT  = "|".join(re.escape(s) for s in _ORG_SUFFIXES)

# 組織名本体（漢字・英数字・カタカナ）
_ORG_BODY = r"[\u4E00-\u9FFFa-zA-Z0-9\u30A0-\u30FF\-・]{2,30}"

_ORG_PAT = re.compile(
    rf"(?:"
    rf"(?:株式会社|有限会社|合同会社|一般社団法人|一般財団法人|特定非営利活動法人)\s*{_ORG_BODY}"  # 前置き法人格
    rf"|{_ORG_BODY}(?:{_ORG_SUF_PAT})"                                                           # 後置き法人格
    rf")"
)

# ━━ カスタム辞書 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CUSTOM_DICT_PATH = Path(__file__).parent.parent / "dict" / "custom_dict.txt"  # パッケージ内辞書


def _load_custom_dict() -> tuple[set[str], set[str]]:
    """
    カスタム辞書を読み込む。
    フォーマット: カテゴリ,名称
      人物,田中太郎
      組織,ABC商事
    """
    persons: set[str] = set()
    orgs:    set[str] = set()
    if not _CUSTOM_DICT_PATH.exists():
        return persons, orgs
    for line in _CUSTOM_DICT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            continue
        cat, name = parts[0].strip(), parts[1].strip()
        if cat in ("人物", "人名", "PER"):
            persons.add(name)
        elif cat in ("組織", "ORG"):
            orgs.add(name)
    return persons, orgs

# ━━ メイン検出関数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def find_persons_orgs(text: str) -> list[tuple[int, int, str, str]]:
    """
    人名・組織名を検出し
    [(start, end, original, category), ...] を返す。
    category: "人物" or "組織"
    """
    if _try_load_ginza():
        return _find_by_ginza(text)
    return _find_by_heuristic(text)


def _find_by_ginza(text: str) -> list[tuple[int, int, str, str]]:
    results = []
    doc = _nlp(text)
    for ent in doc.ents:
        if ent.label_ in ("Person", "PERSON"):
            results.append((ent.start_char, ent.end_char, ent.text, "人物"))
        elif ent.label_ in ("ORG", "Organization", "ORGANIZATION",
                             "Company", "COMPANY", "Corporation"):
            results.append((ent.start_char, ent.end_char, ent.text, "組織"))
    return results


def _find_by_heuristic(text: str) -> list[tuple[int, int, str, str]]:
    results: list[tuple[int, int, str, str]] = []
    used:    list[tuple[int, int]] = []

    def _try_add(start: int, end: int, original: str, cat: str) -> bool:
        original = original.strip()
        if not original or len(original) < 2:
            return False
        # 数字・記号のみは除外
        if re.fullmatch(r"[\d\s\W]+", original):
            return False
        # 重複区間チェック
        if any(s < end and start < e for s, e in used):
            return False
        results.append((start, end, original, cat))
        used.append((start, end))
        return True

    # A. カスタム辞書（最優先）
    persons, orgs = _load_custom_dict()
    for name in sorted(persons, key=len, reverse=True):
        for m in re.finditer(re.escape(name), text):
            _try_add(m.start(), m.end(), m.group(0), "人物")
    for name in sorted(orgs, key=len, reverse=True):
        for m in re.finditer(re.escape(name), text):
            _try_add(m.start(), m.end(), m.group(0), "組織")

    # B. 役職・敬称直前の人名
    for m in _NAME_TITLE_PAT.finditer(text):
        name = m.group(1)
        # 役職・敬称リストに含まれる語は除外
        if name in TITLES:
            continue
        _try_add(m.start(1), m.end(1), name, "人物")

    # C. 組織名サフィックス
    for m in _ORG_PAT.finditer(text):
        org = m.group(0)
        _try_add(m.start(), m.end(), org, "組織")

    # D. 既知の姓 + 名パターン（役職・敬称なしでも検出）
    for surname in JP_SURNAMES:
        pat = re.compile(re.escape(surname) + rf"({_JP_GIVEN})")
        for m in pat.finditer(text):
            _try_add(m.start(), m.end(), m.group(0), "人物")

    results.sort(key=lambda x: x[0])
    return results


def get_detection_mode() -> str:
    return "GiNZA (NLP)" if _try_load_ginza() else "辞書＋ヒューリスティック"
