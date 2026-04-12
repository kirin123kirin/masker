/**
 * PII Masker メインアプリケーション
 * ファイルをドロップ/選択 → 処理 → ダウンロードボタン表示
 */

console.log('[app.js] module loading...');

import { Masker } from './masker.js';
import { processTxt } from './handlers/txt.js';
import { processHtml } from './handlers/html.js';
import { processSvg } from './handlers/svg.js';
import { processDocx } from './handlers/docx.js';
import { processPptx } from './handlers/pptx.js';
import { processXlsx } from './handlers/xlsx.js';

// ── NER Worker ラッパー ──────────────────────────────────────────────────────

class NerProxy {
    constructor() {
        this._worker = new Worker('./js/ner_worker.js', { type: 'module' });
        this._pending = new Map(); // id -> { resolve, reject }
        this._nextId = 0;
        this._ready = false;
        this._readyPromise = new Promise((res, rej) => {
            this._readyResolve = res;
            this._readyReject = rej;
        });

        this._worker.onmessage = (e) => {
            const { type, id, result, error } = e.data;
            if (type === 'ready') {
                this._ready = true;
                this._readyResolve();
                setNerStatus('ready', 'NERモデル準備完了');
            } else if (type === 'error') {
                if (!this._ready) {
                    this._readyReject(new Error(error));
                    setNerStatus('error', 'NERモデルエラー: ' + error);
                }
            } else if (type === 'result') {
                const pending = this._pending.get(id);
                if (pending) {
                    pending.resolve(result);
                    this._pending.delete(id);
                }
            }
        };

        this._worker.onerror = (e) => {
            if (!this._ready) {
                this._readyReject(new Error(e.message));
                setNerStatus('error', 'NERワーカーエラー: ' + e.message);
            }
        };
    }

    async detect(text) {
        // 10秒でタイムアウト（ONNX WASM ロードハング対策）
        const readyTimeout = new Promise((_, rej) =>
            setTimeout(() => rej(new Error('NER ready timeout')), 10000)
        );
        await Promise.race([this._readyPromise, readyTimeout]);
        const id = this._nextId++;
        // 検出自体にも30秒タイムアウト
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this._pending.delete(id);
                reject(new Error('NER detection timeout'));
            }, 30000);
            this._pending.set(id, {
                resolve: (result) => { clearTimeout(timer); resolve(result); }
            });
            this._worker.postMessage({ type: 'detect', id, text });
        });
    }
}

// ── UI ───────────────────────────────────────────────────────────────────────

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const statusDiv = document.getElementById('status');
const nerStatusDiv = document.getElementById('ner-status');

function setNerStatus(state, message) {
    nerStatusDiv.className = `ner-${state}`;
    const icons = { loading: '🔄', ready: '✅', error: '❌' };
    nerStatusDiv.textContent = (icons[state] || '') + ' ' + message;
}

// ── NER 初期化 ──────────────────────────────────────────────────────────────

let nerProxy = null;
let masker = null;

// NERプロキシを作成（バックグラウンドでモデルロード）
try {
    nerProxy = new NerProxy();
} catch (e) {
    setNerStatus('error', 'NERワーカー初期化失敗: ' + e.message);
}

// NERが失敗してもルールベースで動作するMaskerを作成
masker = new Masker(nerProxy);
console.log('[app.js] Masker created, nerProxy:', !!nerProxy);

// NER準備完了を待ち、失敗してもMaskerを再作成
if (nerProxy) {
    nerProxy._readyPromise.catch(err => {
        console.warn('NER初期化失敗、ルールベースのみで動作します:', err);
        setNerStatus('error', 'NERモデル読み込み失敗（ルールベースで動作）');
        masker = new Masker(null); // NERなしのMasker
    });
}

// 動作確認用セルフテスト（NER付き）
if (nerProxy) {
    nerProxy._readyPromise.then(() => {
        const testText = '田中角栄さん';
        masker.mask(testText).then(result => {
            console.log('[selftest NER] input:', testText, '→ output:', result);
        }).catch(err => {
            console.error('[selftest NER] error:', err);
        });
    });
}

// ── ドラッグ＆ドロップ ───────────────────────────────────────────────────────

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
});

dropZone.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    handleFiles(files);
    fileInput.value = ''; // リセット
});

// ── ファイル処理 ─────────────────────────────────────────────────────────────

const SUPPORTED_EXTENSIONS = new Set(['.txt', '.html', '.htm', '.svg', '.docx', '.pptx', '.xlsx']);

function getExtension(name) {
    const dot = name.lastIndexOf('.');
    return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

function getMimeType(ext) {
    const map = {
        '.txt': 'text/plain',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.svg': 'image/svg+xml',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    };
    return map[ext] || 'application/octet-stream';
}

async function handleFiles(files) {
    console.log('[handleFiles] files:', files.length);
    for (const file of files) {
        const ext = getExtension(file.name);
        console.log('[handleFiles] processing:', file.name, 'ext:', ext);
        if (!SUPPORTED_EXTENSIONS.has(ext)) {
            addCard(file.name, '❌', '非対応形式', `${ext} は処理できません`, null);
            continue;
        }
        await processFile(file, ext);
    }
}

async function processFile(file, ext) {
    console.log('[processFile] start:', file.name, 'ext:', ext, 'masker:', !!masker);
    const cardId = `card-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const card = addCard(file.name, '⏳', '処理中...', 'マスク処理を実行中', null);
    card.id = cardId;

    try {
        let resultBlob;

        switch (ext) {
            case '.txt':
                resultBlob = await processTxt(file, masker);
                break;
            case '.html':
            case '.htm':
                resultBlob = await processHtml(file, masker);
                break;
            case '.svg':
                resultBlob = await processSvg(file, masker);
                break;
            case '.docx':
                resultBlob = await processDocx(file, masker);
                break;
            case '.pptx':
                resultBlob = await processPptx(file, masker);
                break;
            case '.xlsx':
                resultBlob = await processXlsx(file, masker);
                break;
            default:
                throw new Error('非対応形式');
        }

        // マッピングTSVも生成
        const tsvContent = masker.exportTSV();
        const tsvBlob = new Blob([tsvContent], { type: 'text/tab-separated-values' });

        // 出力ファイル名
        const baseName = file.name.slice(0, file.name.lastIndexOf('.') >= 0 ? file.name.lastIndexOf('.') : undefined);
        const maskedName = `${baseName}_masked${ext}`;
        const tsvName = `${baseName}_mapping.tsv`;

        // カードを更新
        updateCard(card, '✅', '完了', `${file.name} のマスク処理が完了しました`, [
            { blob: resultBlob, name: maskedName, label: 'マスク済みファイル' },
            { blob: tsvBlob, name: tsvName, label: 'マッピングTSV' },
        ]);

    } catch (err) {
        console.error('処理エラー:', err);
        updateCard(card, '❌', 'エラー', err.message, null);
    }
}

// ── UI カード ─────────────────────────────────────────────────────────────────

function addCard(fileName, icon, status, detail, downloads) {
    const card = document.createElement('div');
    card.className = 'status-card';

    const iconEl = document.createElement('div');
    iconEl.className = 'status-icon';
    iconEl.textContent = icon;

    const textEl = document.createElement('div');
    textEl.className = 'status-text';

    const nameEl = document.createElement('div');
    nameEl.className = 'status-name';
    nameEl.textContent = fileName;

    const detailEl = document.createElement('div');
    detailEl.className = 'status-detail';
    detailEl.textContent = `${status}: ${detail}`;

    textEl.appendChild(nameEl);
    textEl.appendChild(detailEl);
    card.appendChild(iconEl);
    card.appendChild(textEl);

    if (downloads) {
        const btnsEl = document.createElement('div');
        btnsEl.style.display = 'flex';
        btnsEl.style.flexDirection = 'column';
        btnsEl.style.gap = '0.3rem';
        for (const { blob, name, label } of downloads) {
            const btn = createDownloadButton(blob, name, label);
            btnsEl.appendChild(btn);
        }
        card.appendChild(btnsEl);
    }

    statusDiv.prepend(card);
    return card;
}

function updateCard(card, icon, status, detail, downloads) {
    const iconEl = card.querySelector('.status-icon');
    const detailEl = card.querySelector('.status-detail');

    if (iconEl) iconEl.textContent = icon;
    if (detailEl) detailEl.textContent = `${status}: ${detail}`;

    // 既存のダウンロードボタンを削除
    const existingBtns = card.querySelectorAll('.btn-dl, .btn-container');
    existingBtns.forEach(el => el.remove());

    if (downloads) {
        const btnsEl = document.createElement('div');
        btnsEl.className = 'btn-container';
        btnsEl.style.display = 'flex';
        btnsEl.style.flexDirection = 'column';
        btnsEl.style.gap = '0.3rem';
        for (const { blob, name, label } of downloads) {
            const btn = createDownloadButton(blob, name, label);
            btnsEl.appendChild(btn);
        }
        card.appendChild(btnsEl);
    }
}

function createDownloadButton(blob, filename, label) {
    const btn = document.createElement('button');
    btn.className = 'btn-dl';
    btn.textContent = `⬇ ${label}`;
    btn.addEventListener('click', () => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
    });
    return btn;
}
