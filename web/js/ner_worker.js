/**
 * NER Web Worker
 * Transformers.js を UMD として importScripts で読み込む
 */

importScripts('../lib/transformers.min.js');

const { pipeline, env } = self.transformers ?? transformers;

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
    if (e.data.type === 'init') {
        try {
            await init();
        } catch (err) {
            self.postMessage({ type: 'error', error: err.message });
        }
    } else if (e.data.type === 'detect') {
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
