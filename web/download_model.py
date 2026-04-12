"""
モデルとライブラリのダウンロード＆変換スクリプト
実行: python download_model.py

必要環境: Python 3.8+、インターネット接続
使用モデル: tsmatz/xlm-roberta-ner-japanese
  - XLM-RoBERTa ベース（SentencePiece、MeCab不要）
  - 日本語NER専用（Stockmark Wikipedia NER データセット）
  - 人名(PER)・組織名(ORG)・地名(LOC)等を検出
  - F1 ≈ 0.893
"""
import subprocess, sys, urllib.request
from pathlib import Path


def pip_install(*pkgs):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', *pkgs, '-q'])


# ── 依存パッケージインストール ────────────────────────────────────────────────

print('依存パッケージを確認中...')

try:
    import optimum  # noqa: F401
except ImportError:
    print('optimum[onnxruntime] をインストール中（初回のみ）...')
    pip_install('optimum[onnxruntime]')

try:
    import sentencepiece  # noqa: F401
except ImportError:
    print('sentencepiece をインストール中...')
    pip_install('sentencepiece')

# ── 日本語NERモデル ONNX変換 ─────────────────────────────────────────────────

MODEL_ID = 'tsmatz/xlm-roberta-ner-japanese'
model_dir  = Path('models') / 'tsmatz' / 'xlm-roberta-ner-japanese'
onnx_dir   = model_dir / 'onnx'          # Transformers.js が参照するサブフォルダ
onnx_path  = model_dir / 'model.onnx'    # optimum 出力先（一時）
quant_path = onnx_dir  / 'model_quantized.onnx'  # 最終配置先

# 旧バージョンがルート直下に置いた場合の移行
_old_quant = model_dir / 'model_quantized.onnx'
if _old_quant.exists() and not quant_path.exists():
    import shutil
    onnx_dir.mkdir(exist_ok=True)
    shutil.move(str(_old_quant), str(quant_path))
    print(f'\n[移行] model_quantized.onnx を onnx/ 配下へ移動しました')
_old_f32 = model_dir / 'model.onnx'  # ルート直下の float32（旧）はそのまま変数で管理

if quant_path.exists():
    print(f'\n[済] {MODEL_ID} の量子化モデルがすでに存在します: {quant_path}')

else:
    if not onnx_path.exists() and not (onnx_dir / 'model.onnx').exists():
        print(f'\n{MODEL_ID} をONNXに変換中...')
        print('（初回は5〜15分かかる場合があります）')
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            from optimum.exporters.onnx import main_export
            # config/tokenizer はモデルルートへ、model.onnx もまずルートへ出力
            main_export(
                model_name_or_path=MODEL_ID,
                output=model_dir,
                task='token-classification',
            )
            print('ONNX変換完了')
        except Exception as e:
            print(f'\nONNX変換失敗: {e}')
            print('pip install "optimum[onnxruntime]" sentencepiece を確認してください')
            sys.exit(1)

    # onnx/ サブフォルダへ移動
    # （Transformers.js v2 は <model>/onnx/model_quantized.onnx を優先参照）
    onnx_dir.mkdir(exist_ok=True)

    # int8 動的量子化でサイズを約1/4に圧縮
    src_for_quant = onnx_path if onnx_path.exists() else onnx_dir / 'model.onnx'
    print('\nint8量子化中（ブラウザ向けサイズ圧縮）...')
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(
            model_input=str(src_for_quant),
            model_output=str(quant_path),
            weight_type=QuantType.QUInt8,
        )
        print(f'量子化完了: {quant_path}')
        # float32 元モデルを削除してサイズ節約
        if src_for_quant.exists():
            src_for_quant.unlink()
            print('float32モデルを削除しました（量子化版を使用）')
    except Exception as e:
        # 量子化失敗時は float32 のまま onnx/ 配下へ移動して使用
        print(f'量子化をスキップします（{e}）')
        dst = onnx_dir / 'model.onnx'
        if onnx_path.exists() and not dst.exists():
            import shutil
            shutil.move(str(onnx_path), str(dst))
            print(f'float32モデルを移動しました: {dst}')

# ── JSZip ────────────────────────────────────────────────────────────────────

lib_dir = Path('lib')
lib_dir.mkdir(exist_ok=True)

print('\nJSZipをダウンロード中...')
urllib.request.urlretrieve(
    'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',
    lib_dir / 'jszip.min.js',
)
print('JSZipダウンロード完了')

# ── Transformers.js ───────────────────────────────────────────────────────────

print('Transformers.jsをダウンロード中...')
urllib.request.urlretrieve(
    'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js',
    lib_dir / 'transformers.min.js',
)
print('Transformers.jsダウンロード完了')

print('\n===========================')
print('セットアップ完了')
print('start.bat (Windows) または start.sh (Mac/Linux) を実行してください')
print('===========================')
