# pymasking

**個人情報・機密情報マスキングライブラリ** — 完全オフライン動作

議事録・提案書などのドキュメント内の機密情報を、人間が読んで意味のわかるトークンに**可逆変換**します。

```python
from pymasking import Masker

masker = Masker()
masked = masker.mask("田中太郎部長、ABC株式会社、03-1234-5678、3,000万円、2025年4月1日")
# → "【人物A】部長、【組織A】、【電話A】、【金額A】万円、【日付A】"
```

## インストール

```bash
pip install pymasking
```

人名・組織名の高精度NLP検出（オプション）:

```bash
pip install "pymasking[nlp]"
```

> **動作環境**: Python 3.12 以上。外部通信不要（初回 `pip install` 後は完全オフライン動作）。

---

## 基本的な使い方

### テキストのマスキング

```python
from pymasking import Masker
from pathlib import Path

masker = Masker()

# テキストをマスク
masked = masker.mask("田中太郎部長、03-1234-5678、2025年4月1日")
# → "【人物A】部長、【電話A】、【日付A】"

# マッピング保存（復元用）
masker.save_mapping(Path("mapping.json"))

# 復元（年齢変換のみ非可逆）
restored = masker.restore(masked, Path("mapping.json"))
assert restored == "田中太郎部長、03-1234-5678、2025年4月1日"
```

### ファイルのマスキング

```python
from pathlib import Path
from pymasking import Masker
from pymasking.formats.handler_docx import process_docx

masker = Masker()
src = Path("議事録.docx")

# 書式保持でマスキング（フォント・色・表・ヘッダーを維持）
output_bytes, original_text, masked_text = process_docx(src, masker)
Path("議事録_masked.docx").write_bytes(output_bytes)

# マッピング保存
masker.save_mapping(Path("議事録_mapping.json"))
```

各フォーマットハンドラーはすべて同じシグネチャを持ちます:

```python
handler(src: Path, masker: Masker) -> tuple[bytes | str, str, str]
#                                             出力データ  原文   マスク後テキスト
```

### カスタム辞書

社内固有の人名・組織名を辞書登録すると確実に検出されます。

`src/pymasking/dict/custom_dict.txt` を直接編集:

```
# カテゴリ,名称
人物,田中太郎
人物,山田花子
組織,ABC商事
組織,XYZ研究所
```

コードから辞書パスを指定する場合:

```python
from pymasking.engine.ner_detector import _CUSTOM_DICT_PATH
_CUSTOM_DICT_PATH.write_text("人物,田中太郎\n組織,ABC商事\n", encoding="utf-8")
```

---

## CLIリファレンス

`pip install pymasking` で `mask` / `unmask` コマンドが利用可能になります。

### `mask` — マスキング実行

```
mask <file> [-o OUTPUT] [-m MAPPING]
```

| 引数 | 説明 |
|------|------|
| `file` | 入力ファイル（対応形式: `.txt .html .htm .svg .docx .pptx .pdf .xlsx`）|
| `-o`, `--output FILE` | 出力先ファイルパス（省略時: `<元ファイル名>_masked.<拡張子>`）|
| `-m`, `--mapping FILE` | マッピングJSON保存先（省略時: `<元ファイル名>_mapping.json`）|

**実行例:**

```bash
# 基本（自動命名）
mask 議事録.docx
# → 議事録_masked.docx + 議事録_mapping.json

# 出力先を明示指定
mask 議事録.docx -o 送付用.docx -m .secret/mapping.json

# PDF → Markdown変換
mask 報告書.pdf
# → 報告書_masked.md + 報告書_mapping.json

# Excelファイル（文字列セルのみマスク）
mask 顧客一覧.xlsx
# → 顧客一覧_masked.xlsx + 顧客一覧_mapping.json
```

**終了コード**: 成功 = `0`、エラー = `1`

### `unmask` — 復元実行

```
unmask <file> [-o OUTPUT] [-m MAPPING]
```

| 引数 | 説明 |
|------|------|
| `file` | マスク済みファイル（対応形式: `.txt .html .htm .svg .md`）|
| `-o`, `--output FILE` | 復元ファイルの出力先（省略時: `<元ファイル名>_restored.<拡張子>`）|
| `-m`, `--mapping FILE` | マッピングJSONのパス（省略時: 自動検索）|

> **注意**: `docx` / `pptx` / `xlsx` は書式付き復元に未対応です。テキストのみ復元したい場合は `.txt` 等で復元してください。

**実行例:**

```bash
# マッピングを自動検索（「_masked」除いた名前の「_mapping.json」を探す）
unmask 議事録_masked.txt

# マッピングファイルを明示指定
unmask 議事録_masked.txt -m .secret/mapping.json -o 議事録_復元済み.txt
```

---

## Python APIリファレンス

### `Masker` クラス

```python
from pymasking import Masker
```

#### `Masker()`

新しいMaskerインスタンスを生成します。インスタンスはトークン割り当て状態をセッション全体で保持します。

#### `masker.mask(text: str) -> str`

テキスト内の機密情報をトークンに変換します。同一セッション内では同じ文字列に同じトークンが割り当てられます（一意性保証）。

```python
masker = Masker()
masker.mask("田中太郎部長")       # → "【人物A】部長"
masker.mask("田中太郎部長")       # → "【人物A】部長"（同じトークン）
masker.mask("鈴木花子さん")       # → "【人物B】さん"（異なるトークン）
```

#### `masker.reset()`

トークン割り当て状態をリセットします。`reset()` 後は採番がAから再開されます。

#### `masker.save_mapping(path: Path)`

現在のトークン↔原文マッピングをJSONファイルに保存します。

```python
masker.save_mapping(Path("mapping.json"))
```

**出力JSONの構造:**

```json
{
  "mapping": {
    "人物": { "田中太郎": "A", "鈴木花子": "B" },
    "電話": { "03-1234-5678": "A" }
  },
  "restore": {
    "【人物A】": "田中太郎",
    "【人物B】": "鈴木花子",
    "【電話A】": "03-1234-5678"
  }
}
```

#### `masker.load_mapping(path: Path)`

保存済みマッピングを読み込み、トークン状態を復元します。同一セッションを別プロセスで継続する場合に使用します。

```python
masker = Masker()
masker.load_mapping(Path("mapping.json"))
```

#### `masker.restore(text: str, mapping_path: Path) -> str`

マスク済みテキストを原文に復元します。年齢変換（`42歳` → `40代`）は非可逆のため復元されません。

```python
original = "田中太郎部長、03-1234-5678"
masked   = masker.mask(original)
masker.save_mapping(Path("mapping.json"))

restored = masker.restore(masked, Path("mapping.json"))
assert restored == original
```

#### `masker.detection_mode: str` _(property)_

現在の人名・組織名検出モードを返します。

- `"ginza"` — GiNZA（spaCy）による高精度NLP検出
- `"heuristic"` — 辞書＋正規表現によるフォールバック検出

```python
print(masker.detection_mode)  # "ginza" または "heuristic"
```

### スタンドアロン関数

```python
from pymasking import find_dates, find_persons_orgs
```

#### `find_dates(text: str) -> list[tuple[int, int, str]]`

テキスト内の日付を検出します。

```python
results = find_dates("会議は2025年4月1日と4月15日に開催")
# → [(3, 12, "2025年4月1日"), (13, 18, "4月15日")]
# 各タプル: (開始位置, 終了位置, マッチした文字列)
```

#### `find_persons_orgs(text: str) -> list[tuple[int, int, str, str]]`

テキスト内の人名・組織名を検出します。

```python
results = find_persons_orgs("田中太郎部長とABC株式会社の契約")
# → [(0, 4, "田中太郎", "人物"), (7, 13, "ABC株式会社", "組織")]
# 各タプル: (開始位置, 終了位置, マッチした文字列, カテゴリ)
```

---

## マスキングルール

| 対象 | 変換例 | 備考 |
|------|--------|------|
| 人名 | `田中太郎部長` → `【人物A】部長` | 役職・敬称は残す |
| 組織名 | `ABC株式会社` → `【組織A】` | |
| 金額 | `3,000万円` → `【金額A】万円` | 単位（万・億・円）は残す |
| 数値 | `2.5kg` → `【数値A】kg` | 単位（kg・℃・ml 等）は残す |
| 日付 | `2025年4月1日` → `【日付A】` | 多形式対応（下記参照）|
| 年齢 | `42歳` → `40代` | **年代に丸める（非可逆）** |
| 住所 | `東京都新宿区〜` → `東京都【住所A】` | 都道府県は残す |
| 郵便番号 | `〒160-0023 新宿区〜` → `〒【住所A】` | |
| 電話番号（固定）| `03-1234-5678` → `【電話A】` | |
| 電話番号（携帯）| `090-9876-5432` → `【電話A】` | |
| 国際電話 | `+81-3-1234-5678` → `【電話A】` | |
| フリーダイヤル | `0120-xxx-xxx` → `【電話A】` | |
| メール | `foo@bar.com` → `【メールA】` | |
| SNS ID | `@handle` → `【SNSA】` | Twitter/GitHub/LinkedIn等 |
| 型番 | `ABC-12345` → `【型番A】` | |
| シリアル番号 | `SN20251234` → `【シリアルA】` | SN / S/N 等 |
| 特許番号（日本）| `特許第1234567号` → `特許【特許A】号` | |
| 特許番号（米国）| `US Patent 9,123,456` → `【特許A】` | |

---

## 対応ファイル形式

| 形式 | ハンドラー | 出力 | 書式保持 |
|------|-----------|------|--------|
| `.txt` | `handler_txt` | `.txt` | — |
| `.html` / `.htm` | `handler_html` | `.html` | タグ・属性保持 |
| `.svg` | `handler_svg` | `.svg` | `<text>`要素のみ処理 |
| `.docx` | `handler_docx` | `.docx` | フォント・色・表・ヘッダー・テキストボックス |
| `.pptx` | `handler_pptx` | `.pptx` | フォント・色・表・ノート・グループシェイプ |
| `.pdf` | `handler_pdf` | `.md` | テキスト抽出のみ（スキャンPDF非対応）|
| `.xlsx` | `handler_xlsx` | `.xlsx` | 数値・数式・書式保持（文字列セルのみマスク）|

---

## 日付対応フォーマット

`python-dateutil` ベースで以下を自動検出します。

| パターン | 例 |
|---------|-----|
| 西暦年月日 | `2025年4月1日` |
| 和暦（令和・平成・昭和・大正）| `令和7年4月1日` |
| 和暦略記 | `R7.4.1` / `H31.3.31` |
| 全角数字 | `２０２５年４月１日` |
| 漢数字 | `二〇二五年四月一日` |
| 区切り記号 | `2025/04/01` / `2025-04-01` / `2025.04.01` |
| 8桁連番 | `20250401` |
| 英語表記 | `April 1, 2025` / `1st April 2025` |
| 月日のみ | `4月1日` |

---

## トークンの仕組み

マスクされた各値は `【カテゴリID】` 形式のトークンになります。

- **採番規則**: 登場順に A, B, C, ..., Z, AA, AB, ... と採番
- **一意性保証**: 同じ文字列 → 同じトークン（セッション内）
- **カテゴリ分離**: カテゴリをまたいでの番号はリセット（`【人物A】`と`【電話A】`は別物）

```
03-1111-0001 → 【電話A】
03-2222-0002 → 【電話B】
03-1111-0001 → 【電話A】（再登場時は同一トークン）
```

---

## 検出モード

人名・組織名の検出には2つのモードがあります。

### GiNZAモード（高精度）

`pip install "pymasking[nlp]"` でGiNZAをインストールすると自動的に有効になります。spaCyの日本語モデルを使用した固有表現認識（NER）により、より高精度な検出が可能です。

### ヒューリスティックモード（デフォルト）

GiNZA未インストール時のフォールバック。以下の3段階で検出します:

1. **カスタム辞書**: `custom_dict.txt` に登録された語の完全一致（最優先）
2. **パターン＋役職**: `<2〜4文字の漢字><役職・敬称>` の組み合わせ
3. **組織サフィックス**: `<任意の語><株式会社・Inc. 等>` の組み合わせ

```python
masker = Masker()
print(masker.detection_mode)  # "ginza" または "heuristic"
```

---

## 処理優先順位

複数のルールが同じテキスト範囲に一致した場合、以下の優先順位で処理されます:

1. **日付** （最優先）
2. **人物・組織名** （NER）
3. **正規表現ルール** （電話・メール・住所・金額など）

一度マスクされた範囲は後続のルールでは処理されません（重複マスク防止）。

---

## 制限事項

| 制限 | 詳細 |
|------|------|
| **年齢変換は非可逆** | `42歳` → `40代` は復元不可 |
| **docx/pptx の unmask 非対応** | 書式保持でマスクしたファイルは `unmask` コマンドで復元できません |
| **PDF はテキスト抽出のみ** | スキャンPDF（画像ベース）は非対応。出力形式は `.md` のみ |
| **xlsx の unmask 非対応** | `unmask` コマンドの対象外（`.txt`/`.html`/`.svg`/`.md` のみ）|
| **人名の誤検出** | ヒューリスティックモードでは2〜4文字の漢字連続を人名と判定するため誤検出が発生することがあります。GiNZAのインストールまたはカスタム辞書で対処してください |
| **セッション単位の一意性** | `Masker` インスタンスをまたいだトークンの一意性は保証されません。複数ファイルを同一マッピングで扱う場合は同一インスタンスを使用してください |

---

## 開発

```bash
# リポジトリのクローン
git clone https://github.com/kirin123kirin/masker.git
cd masker

# 開発用インストール
pip install -e ".[dev]"

# テスト実行
pytest tests/ -v

# NLP付きテスト
pip install -e ".[dev,nlp]"
pytest tests/ -v
```

---

## ライセンス

MIT License
