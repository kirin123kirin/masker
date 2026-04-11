"""
モデルとライブラリのダウンロードスクリプト
実行: python download_model.py
"""
import subprocess, sys, urllib.request, os
from pathlib import Path

def pip_install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])

# huggingface_hub インストール
try:
    from huggingface_hub import snapshot_download
except ImportError:
    pip_install('huggingface_hub')
    from huggingface_hub import snapshot_download

# モデルダウンロード
model_dir = Path('models/Xenova/bert-base-multilingual-cased-ner-hrl')
model_dir.mkdir(parents=True, exist_ok=True)
print('モデルをダウンロード中...')
snapshot_download(
    'Xenova/bert-base-multilingual-cased-ner-hrl',
    local_dir=str(model_dir),
    ignore_patterns=['*.msgpack', '*.h5', 'flax_model.*', 'tf_model.*', 'rust_model.*'],
)
print('モデルダウンロード完了')

# JSZipダウンロード
lib_dir = Path('lib')
lib_dir.mkdir(exist_ok=True)
jszip_url = 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js'
print('JSZipをダウンロード中...')
urllib.request.urlretrieve(jszip_url, lib_dir / 'jszip.min.js')
print('JSZipダウンロード完了')

# Transformers.jsダウンロード
tjs_url = 'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js'
print('Transformers.jsをダウンロード中...')
urllib.request.urlretrieve(tjs_url, lib_dir / 'transformers.min.js')
print('Transformers.jsダウンロード完了')

print('\nセットアップ完了。start.bat (Windows) または start.sh (Mac/Linux) を実行してください。')
