# pii-masker

**個人情報・機密情報マスキングライブラリ** — 完全オフライン動作

議事録・提案書などのドキュメント内の機密情報を、人間が読んで意味のわかるトークンに**可逆変換**します。

```python
from pii_masker import Masker

masker = Masker()
masked = masker.mask("田中太郎部長、ABC株式会社、03-1234-5678、3,000万円、2025年4月1日")
# → "【人物A】部長、【組織A】、【電話A】、【金額A】万円、【日付A】"
```

## インストール

```bash
pip install pii-masker
```

人名・組織名の高精度NLP検出（オプション）:

```bash
pip install "pii-masker[nlp]"
```

## 基本的な使い方

### テキストのマスキング

```python
from pii_masker import Masker
from pathlib import Path

masker = Masker()

# テキストをマスク
masked = masker.mask("田中太郎部長、03-1234-5678、2025年4月1日")
# → "【人物A】部長、【電話A】、【日付A】"

# マッピング保存（復元用）
masker.save_mapping(Path("mapping.json"))

# 復元（年齢変換のみ非可逆）
restored = masker.restore(masked, Path("mapping.json"))
```

### ファイルのマスキング

```python
from pathlib import Path
from pii_masker import Masker
from pii_masker.formats.handler_docx import process_docx
from pii_masker.formats.handler_pptx import process_pptx
from pii_masker.formats.handler_pdf  import process_pdf
from pii_masker.formats.handler_html import process_html
from pii_masker.formats.handler_txt  import process_txt

masker = Masker()
src = Path("議事録.docx")

# 書式保持でマスキング（docx/pptxは書式・表・ヘッダーを維持）
output_bytes, original_text, masked_text = process_docx(src, masker)
Path("議事録_masked.docx").write_bytes(output_bytes)

# マッピング保存
masker.save_mapping(Path("議事録_mapping.json"))
```

### カスタム辞書

社内固有の人名・組織名を辞書登録すると確実に検出されます。

```python
# dict/custom_dict.txt に記述
# カテゴリ,名称
# 人物,田中太郎
# 組織,ABC商事
```

またはコードから辞書パスを直接編集:

```python
from pii_masker.engine.ner_detector import _CUSTOM_DICT_PATH
_CUSTOM_DICT_PATH.write_text("人物,田中太郎\n組織,ABC商事\n", encoding="utf-8")
```

## マスキングルール

| 対象 | 変換例 | 備考 |
|------|--------|------|
| 人名 | `田中太郎部長` → `【人物A】部長` | 役職・敬称は残す |
| 組織名 | `ABC株式会社` → `【組織A】` | |
| 金額 | `3,000万円` → `【金額A】万円` | 単位は残す |
| 数値 | `2.5kg` → `【数値A】kg` | 単位は残す |
| 日付 | `2025年4月1日` → `【日付A】` | 多形式対応 |
| 年齢 | `42歳` → `40代` | 年代に丸める（非可逆）|
| 住所 | `東京都新宿区〜` → `東京都【住所A】` | 都道府県は残す |
| 電話番号 | `03-1234-5678` → `【電話A】` | |
| メール | `foo@bar.com` → `【メールA】` | |
| SNS ID | `@handle` → `【SNSA】` | |
| 型番 | `ABC-12345` → `【型番A】` | |
| シリアル番号 | `SN20251234` → `【シリアルA】` | |
| 特許番号 | `特許第1234567号` → `特許【特許A】号` | |

## 対応ファイル形式

| 形式 | ハンドラー | 出力 |
|------|-----------|------|
| `.txt` | `handler_txt` | `.txt` |
| `.html` / `.htm` | `handler_html` | `.html`（タグ保持）|
| `.svg` | `handler_svg` | `.svg`（`<text>`要素のみ処理）|
| `.docx` | `handler_docx` | `.docx`（書式・表・ヘッダー保持）|
| `.pptx` | `handler_pptx` | `.pptx`（書式・表・ノート保持）|
| `.pdf` | `handler_pdf` | `.md`（Markdown形式）|

## 日付対応フォーマット

`python-dateutil` ベースで以下を自動検出します。

| パターン | 例 |
|---------|-----|
| 西暦年月日 | `2025年4月1日` |
| 和暦 | `令和7年4月1日` / `R7.4.1` |
| 全角 | `２０２５年４月１日` |
| 漢数字 | `二〇二五年四月一日` |
| 区切り記号 | `2025/04/01` / `2025-04-01` / `2025.04.01` |
| 8桁連番 | `20250401` |
| 英語 | `April 1, 2025` / `1st April 2025` |
| 月日のみ | `4月1日` |

## 動作環境

- Python 3.12 以上
- 外部通信不要（初回 `pip install` 後は完全オフライン動作）

## ライセンス

MIT License
