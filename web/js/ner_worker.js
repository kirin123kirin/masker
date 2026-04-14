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

/**
 * 生トークン列を集約してエンティティ配列に変換する。
 * ONNX版では aggregation_strategy が効かず、start/end が null になることがあるため
 * ここで手動集約する。
 *
 * 入力例（1文字ずつ）:
 *   [{entity:"PER", word:"田", start:null, ...}, {entity:"PER", word:"中", ...}, ...]
 * 出力例:
 *   [{entity_group:"PER", word:"田中角栄", start:0, end:4, score:0.99}]
 */
function postprocessEntities(rawEntities, text) {
    if (!rawEntities || rawEntities.length === 0) return [];

    const results = [];
    let searchFrom = 0;
    let i = 0;

    while (i < rawEntities.length) {
        const tok = rawEntities[i];
        // entity_group（集約済み）または entity（生ラベル）を取得
        const rawLabel = tok.entity_group || tok.entity || '';
        // O（Outside）はスキップ
        if (!rawLabel || rawLabel === 'O') { i++; continue; }
        // B-PER / I-PER → PER のようにプレフィックスを除去
        const label = rawLabel.replace(/^[BI]-/, '');

        // 同じラベルが連続する間トークンを集約
        const words = [tok.word];
        let j = i + 1;
        while (j < rawEntities.length) {
            const next = rawEntities[j];
            const nextRaw = next.entity_group || next.entity || '';
            const nextLabel = nextRaw.replace(/^[BI]-/, '');
            if (nextLabel === label) {
                words.push(next.word);
                j++;
            } else {
                break;
            }
        }

        // SentencePiece の ▁（スペース代替）を除去して結合
        const word = words.join('').replace(/▁/g, ' ').trim();

        if (word.length >= 2) {
            const pos = text.indexOf(word, searchFrom);
            if (pos !== -1) {
                results.push({
                    entity_group: label,
                    word,
                    start: pos,
                    end: pos + word.length,
                    score: tok.score,
                });
                searchFrom = pos + word.length;
            }
        }

        i = j;
    }

    return results;
}

async function init() {
    ner = await pipeline('token-classification', 'tsmatz/xlm-roberta-ner-japanese', {
        aggregation_strategy: 'simple',
    });
    self.postMessage({ type: 'ready' });
}

self.onmessage = async (e) => {
    if (e.data.type === 'detect') {
        try {
            const raw = await ner(e.data.text);
            const result = postprocessEntities(raw, e.data.text);
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
