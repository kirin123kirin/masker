/**
 * NER Web Worker (ES module worker)
 * Transformers.js を ES module として import する
 */

import { pipeline, env } from '../lib/transformers.min.js';

env.localModelPath = '../models/';
env.allowRemoteModels = false;

let ner = null;

async function init() {
    ner = await pipeline('token-classification', 'Xenova/bert-base-multilingual-cased-ner-hrl', {
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
