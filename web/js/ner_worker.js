/**
 * NER Web Worker (ES module worker)
 * Transformers.js を ES module として import する
 * モデル: tsmatz/xlm-roberta-ner-japanese
 *   - XLM-RoBERTa ベース (SentencePiece, MeCab不要)
 *   - 日本語特化NER (Stockmark Wikipedia NER, F1≈0.893)
 *   - 出力ラベル: PER / ORG / ORG-P / ORG-O / LOC / INS / PRD / EVT
 */

import { pipeline, env } from '../lib/transformers.min.js';

env.localModelPath = '../models/';
env.allowRemoteModels = false;

let ner = null;

async function init() {
    ner = await pipeline('token-classification', 'tsmatz/xlm-roberta-ner-japanese', {
        aggregation_strategy: 'simple',
    });
    self.postMessage({ type: 'ready' });
}

self.onmessage = async (e) => {
    if (e.data.type === 'detect') {
        try {
            const result = await ner(e.data.text);
            self.postMessage({ type: 'result', id: e.data.id, result });
        } catch (err) {
            self.postMessage({ type: 'result', id: e.data.id, result: [] });
        }
    }
};

// 起動時に自動初期化
init().catch(err => {
    self.postMessage({ type: 'error', error: err.message });
});
