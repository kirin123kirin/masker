# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2025-04-10

### Added
- `.xlsx` 対応（文字列セルのみマスク・数値・数式・書式保持）
- PDFファイル対応（pdfplumber によるテキスト抽出 → Markdown出力）
- `mask` / `unmask` CLI エントリポイント
- GiNZA (spaCy) による人名・組織名の高精度NLP検出（オプション）
- GiNZA 未インストール時の辞書＋ヒューリスティック方式フォールバック
- カスタム辞書機能（`dict/custom_dict.txt`）

### Changed
- 日付検出を `python-dateutil` ベースに刷新
  - 西暦・和暦・全角・漢数字・8桁連番・英語表記すべてに対応
- PyPI パッケージとして公開（`src` レイアウト採用）

## [1.2.0] - 2025-04-01

### Added
- `.docx` 対応（書式・表・ヘッダー・テキストボックス保持）
- `.pptx` 対応（書式・表・ノート・グループシェイプ保持）
- 復元（逆変換）機能

## [1.1.0] - 2025-03-15

### Added
- `.html` / `.htm` 対応（タグ・属性保持）
- `.svg` 対応（`<text>` 要素のみ処理）
- マッピング JSON 保存・読み込み

## [1.0.0] - 2025-03-01

### Added
- 初回リリース
- `.txt` 対応
- 正規表現ベースのマスキングエンジン
  - 金額・数値・電話番号・メール・SNS ID
  - 住所（都道府県残す・省略形対応・地名言及対応）
  - 年齢 → 年代変換
  - 型番・シリアル番号・特許番号
- トークン一意性保証（同じ文字列 → 同じトークン）
- 人間可読トークン（`【人物A】` `【金額A】万円` 等）
