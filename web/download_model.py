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
model_dir = Path('models') / 'tsmatz' / 'xlm-roberta-ner-japanese'
onnx_path  = model_dir / 'model.onnx'
quant_path = model_dir / 'model_quantized.onnx'

if quant_path.exists():
    print(f'\n[済] {MODEL_ID} の量子化モデルがすでに存在します: {quant_path}')

else:
    if not onnx_path.exists():
        print(f'\n{MODEL_ID} をONNXに変換中...')
        print('（初回は5〜15分かかる場合があります）')
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            from optimum.exporters.onnx import main_export
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

    # int8 動的量子化でサイズを約1/4に圧縮
    print('\nint8量子化中（ブラウザ向けサイズ圧縮）...')
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(
            model_input=str(onnx_path),
            model_output=str(quant_path),
            weight_type=QuantType.QUInt8,
        )
        print(f'量子化完了: {quant_path}')
        # float32 元モデルを削除してサイズ節約
        if onnx_path.exists():
            onnx_path.unlink()
            print('float32モデルを削除しました（量子化版を使用）')
    except Exception as e:
        print(f'量子化をスキップします（{e}）')
        print('float32モデルをそのまま使用します')

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
