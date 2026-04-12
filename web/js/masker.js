/**
 * マスキングエンジン本体
 * Python版 masker.py を async でポート
 *
 * 処理順序（優先度順）:
 *   1. 日付      ← date_detector
 *   2. 人物・組織 ← NER (nerProxy)
 *   3. その他    ← rules.js (正規表現)
 */

import { TokenStore } from './token_store.js';
import { findDates } from './date_detector.js';
import { RULES, PREFECTURES } from './rules.js';
import { findPersonsOrgsHeuristic } from './heuristic_ner.js';

const _ADDR_SUFFIXES = ['支社','支店','営業所','オフィス','本社','拠点','工場','センター','倉庫','事業所'];
const _ADDR_SUFFIX_PAT = _ADDR_SUFFIXES.map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
const _PREF_PAT = PREFECTURES.map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');

// 復元時の住所トークンパターン
const _RESTORE_ADDR_PAT = new RegExp(
    `(〒|(?:${_PREF_PAT}))?` +
    `(【住所[A-Z]+】)` +
    `(${_ADDR_SUFFIX_PAT})?`,
    'g'
);

export class Masker {
    /**
     * @param {object|null} nerProxy - { detect(text): Promise<entities[]> } | null
     */
    constructor(nerProxy) {
        this._store = new TokenStore();
        this._ner = nerProxy;
    }

    reset() {
        this._store.reset();
    }

    /**
     * テキストをマスクする（async）
     * @param {string} text
     * @returns {Promise<string>}
     */
    async mask(text) {
        console.log('[mask] called, length:', text.length, 'preview:', text.slice(0, 40));
        const maskedRanges = []; // [start, end][]
        const replacements = []; // [start, end, rep][]

        const _register = (start, end, rep) => {
            // overlap check: s < end && start < e
            if (maskedRanges.some(([s, e]) => s < end && start < e)) return;
            replacements.push([start, end, rep]);
            maskedRanges.push([start, end]);
        };

        // ── 1. 日付（最優先）──
        for (const [start, end, raw] of findDates(text)) {
            const tokenId = this._store.getOrCreate('日付', raw);
            _register(start, end, `【日付${tokenId}】`);
        }

        // ── 2. 人物・組織名 ──
        // 2a. Transformers.js NER（利用可能な場合）
        let nerDone = false;
        if (this._ner) {
            try {
                const entities = await this._ner.detect(text);
                for (const entity of entities) {
                    const { entity_group, start, end } = entity;
                    let category;
                    if (entity_group === 'PER') category = '人物';
                    else if (entity_group === 'ORG') category = '組織';
                    else continue;
                    const original = text.slice(start, end);
                    if (!original.trim()) continue;
                    const tokenId = this._store.getOrCreate(category, original);
                    _register(start, end, `【${category}${tokenId}】`);
                }
                nerDone = true;
            } catch (_) {
                // NER失敗 → ヒューリスティックにフォールバック
            }
        }

        // 2b. ヒューリスティック（NER結果を補完、常に実行）
        // NERが成功しても検出漏れを補うため常に実行。_register の重複チェックで二重マスクを防ぐ。
        {
            const heuristic = await findPersonsOrgsHeuristic(text);
            if (heuristic.length > 0) console.log('[heuristic]', heuristic);
            for (const [start, end, original, category] of heuristic) {
                const tokenId = this._store.getOrCreate(category, original);
                _register(start, end, `【${category}${tokenId}】`);
            }
        }

        // ── 3. 正規表現ルール ──
        for (const [cat, pattern, transform] of RULES) {
            // パターンのlastIndexをリセット
            pattern.lastIndex = 0;
            let m;
            while ((m = pattern.exec(text)) !== null) {
                const start = m.index;
                const end = m.index + m[0].length;
                if (maskedRanges.some(([s, e]) => s < end && start < e)) continue;
                const rep = this._makeReplacement(cat, m, transform);
                _register(start, end, rep);
            }
        }

        // 後ろから適用してオフセットズレを防ぐ
        replacements.sort((a, b) => b[0] - a[0]);
        let result = text;
        for (const [start, end, rep] of replacements) {
            result = result.slice(0, start) + rep + result.slice(end);
        }
        return result;
    }

    _makeReplacement(category, m, transform) {
        if (category === '年齢') {
            return transform(m);
        }
        const raw = transform(m);
        if (!raw.includes('{token}')) return raw;
        const original = m[0];
        const tokenId = this._store.getOrCreate(category, original);
        return raw.replace('{token}', tokenId);
    }

    // ── TSVマッピング ────────────────────────────────────────────────────────

    /**
     * マッピングをTSV形式のテキストとして返す
     * @returns {string}
     */
    exportTSV() {
        const lines = ['#カテゴリ\t元テキスト\tMD5\tラベル'];
        for (const [cat, orig, h, label] of this._store.rows()) {
            const origEsc = orig
                .replace(/\\/g, '\\\\')
                .replace(/\t/g, '\\t')
                .replace(/\n/g, '\\n')
                .replace(/\r/g, '\\r');
            lines.push(`${cat}\t${origEsc}\t${h}\t${label}`);
        }
        return lines.join('\n') + '\n';
    }

    /**
     * TSVテキストからマッピングをロード（既存にマージ）
     * @param {string} text
     */
    importTSV(text) {
        const rows = [];
        for (const line of text.split('\n')) {
            if (!line || line.startsWith('#')) continue;
            const parts = line.split('\t');
            if (parts.length === 4) {
                const [cat, origEsc, h, label] = parts;
                const orig = origEsc
                    .replace(/\\t/g, '\t')
                    .replace(/\\n/g, '\n')
                    .replace(/\\r/g, '\r')
                    .replace(/\\\\/g, '\\');
                rows.push([cat, orig, h, label]);
            }
        }
        this._store.loadRows(rows);
    }

    /**
     * マスク済みテキストを元に復元
     * @param {string} text - マスク済みテキスト
     * @param {string} tsvText - マッピングTSVテキスト
     * @returns {string}
     */
    restore(text, tsvText) {
        const restoreMap = {};
        for (const line of tsvText.split('\n')) {
            if (!line || line.startsWith('#')) continue;
            const parts = line.split('\t');
            if (parts.length === 4) {
                const [cat, origEsc, , label] = parts;
                const orig = origEsc
                    .replace(/\\t/g, '\t')
                    .replace(/\\n/g, '\n')
                    .replace(/\\r/g, '\r')
                    .replace(/\\\\/g, '\\');
                restoreMap[`【${cat}${label}】`] = orig;
            }
        }

        // 住所トークンの特殊復元（prefix・suffix の二重化防止）
        let result = text.replace(_RESTORE_ADDR_PAT, (_, prefix, token, suffix) => {
            prefix = prefix || '';
            suffix = suffix || '';
            const original = restoreMap[token] ?? token;
            let res;
            if (original.startsWith('〒')) {
                res = original;
            } else if (prefix === '〒') {
                res = '〒' + original;
            } else {
                res = original;
            }
            if (suffix && !res.endsWith(suffix)) {
                res += suffix;
            }
            return res;
        });

        // 残りの全トークン復元
        result = result.replace(/【[^【】]+】/g, m => restoreMap[m] ?? m);
        return result;
    }
}
