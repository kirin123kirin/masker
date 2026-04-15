# pymasking — 開発ガイド

個人情報・機密情報を可逆・一意なトークンにマスキングするオフラインライブラリ。

## リポジトリ構成

```
masker/
├── setup.bat               # セットアップ + 実行ファイルビルド（Windows、まずここを実行）
├── pyproject.toml
├── MANIFEST.in
├── README.md
│
├── src/pymasking/          # ── Python ライブラリ（pip install / PyPI）──
│   ├── __init__.py
│   ├── cli.py              # mask / unmask コマンド
│   ├── webapp_entry.py     # pymasking.exe GUI エントリポイント
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
│
├── tests/                  # ── テスト ──
│   └── test_masker.py
│
├── webapp/                 # ── スタンドアロン Web アプリ（Windows 配布）──
│   ├── requirements.txt    # Web UI 依存パッケージ
│   ├── server.py           # Flask サーバー
│   └── templates/
│       └── index.html      # Web UI テンプレート
│
├── python/                 # Python embedded runtime（setup.bat が生成、git 管理外）
├── output/                 # 処理済みファイル出力先（git 管理外）
└── .EasyOCR/               # easyocr モデルキャッシュ（git 管理外）
```

## Git 運用ルール

- **必ず `main` ブランチで作業し、`main` に直接コミット・プッシュすること**
- フィーチャーブランチは作成しない
- 作業完了後は必ず `git push origin main` を実行する
- プッシュ前に `git pull origin main --rebase` で最新を取り込む

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
- `webapp/`・`tests/` フォルダは PyPI に含めない（MANIFEST.in で `prune`）
- ビルド: `python -m build`
- 公開: `twine upload dist/*`

## Web UI 起動手順（Windows）

```
setup.bat   # 初回のみ（Python ランタイム・ライブラリ・exe コピー）
```

完了後、リポジトリルートに以下が生成されます:

| ファイル | 用途 |
|---|---|
| `pymasking.exe` | ダブルクリックで Web UI を起動 |
| `mask.exe` | コマンドラインからマスキング |
| `unmask.exe` | コマンドラインから復元 |

## カスタム辞書

`src/pymasking/dict/custom_dict.txt` に以下の書式で追記:

```
人物,田中太郎
組織,ABC商事
```
