# pymasking — 開発ガイド

個人情報・機密情報を可逆・一意なトークンにマスキングするオフラインライブラリ。

## リポジトリ構成

```
masker/
├── src/pymasking/          # Python ライブラリ本体
│   ├── __init__.py
│   ├── cli.py              # mask / unmask コマンド
│   ├── engine/
│   │   ├── masker.py       # Masker クラス（メインエンジン）
│   │   ├── date_detector.py
│   │   ├── ner_detector.py # 人名・組織名検出（GiNZA or ヒューリスティック）
│   │   ├── rules.py        # 正規表現ルール
│   │   └── token_store.py
│   ├── formats/            # ファイル形式ハンドラー
│   │   ├── handler_txt.py
│   │   ├── handler_html.py
│   │   ├── handler_svg.py
│   │   ├── handler_docx.py
│   │   ├── handler_pptx.py
│   │   ├── handler_pdf.py
│   │   └── handler_xlsx.py
│   └── dict/
│       └── custom_dict.txt # ユーザー定義固有名詞辞書
├── web/                    # ブラウザ版（PyPI には含めない）
│   ├── index.html
│   ├── js/
│   ├── dict/
│   ├── start.bat
│   └── download_model.py
├── tests/
│   └── test_masker.py
├── pyproject.toml
├── MANIFEST.in
└── README.md
```

## 開発環境セットアップ

```bash
pip install -e ".[dev]"
```

NLP（GiNZA）付きの場合:

```bash
pip install -e ".[dev,nlp]"
```

## テスト実行

```bash
pytest tests/ -v
```

## コマンドエントリポイント

| コマンド | 関数 |
|---------|------|
| `mask`   | `pymasking.cli:main` |
| `unmask` | `pymasking.cli:main` |

`argv[0]` のファイル名に `unmask` が含まれる場合は復元モードで動作します。

## PyPI パッケージ

- パッケージ名: `pymasking`
- `web/` フォルダは PyPI に含めない（MANIFEST.in で `prune web`）
- ビルド: `python -m build`
- 公開: `twine upload dist/*`

## ブラウザ版

`web/` フォルダは独立した静的ウェブアプリ。Transformers.js（ONNX）でオフライン NER を実現。

起動手順:

```bash
cd web
python download_model.py   # 初回のみ（モデルダウンロード・ONNX 変換）
start.bat                  # Windows
```

モデルは `web/models/tsmatz/xlm-roberta-ner-japanese/onnx/model_quantized.onnx` に配置。

## カスタム辞書

`src/pymasking/dict/custom_dict.txt`（Python ライブラリ用）および `web/dict/custom_dict.txt`（ブラウザ版用）に以下の書式で追記:

```
人物,田中太郎
組織,ABC商事
```
