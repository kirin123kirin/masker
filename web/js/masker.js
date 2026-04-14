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
import { TITLES, findPersonsOrgsHeuristic } from './heuristic_ner.js';

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

/**
 * NER生トークン列を集約してエンティティ配列に正規化する。
 *
 * ONNX版Transformers.jsでは aggregation_strategy が効かず、以下の問題が発生する:
 *   - フィールドが entity_group ではなく entity
 *   - start / end が null
 *   - 1文字ずつのトークンが返ってくる
 *
 * この関数で:
 *   1. entity / entity_group どちらにも対応
 *   2. B-/I- プレフィックスを除去
 *   3. 同ラベルが連続するトークンを1エンティティに集約
 *   4. text.indexOf() でオフセットを再計算
 *
 * すでに集約済み（entity_group + 数値オフセット）の場合はそのまま返す。
 */
function _aggregateNerEntities(rawEntities, text) {
    if (!rawEntities || rawEntities.length === 0) return [];

    // 集約済みかどうかを確認（entity_group があり start が数値ならそのまま返す）
    if (rawEntities[0].entity_group != null && typeof rawEntities[0].start === 'number') {
        return rawEntities;
    }

    const results = [];
    let searchFrom = 0;
    let i = 0;

    while (i < rawEntities.length) {
        const tok = rawEntities[i];
        const rawLabel = tok.entity_group || tok.entity || '';
        if (!rawLabel || rawLabel === 'O') { i++; continue; }
        const label = rawLabel.replace(/^[BI]-/, '');

        // 同じラベルが連続する間トークンを集約
        const words = [tok.word];
        let j = i + 1;
        while (j < rawEntities.length) {
            const next = rawEntities[j];
            const nextRaw = next.entity_group || next.entity || '';
            const nextLabel = nextRaw.replace(/^[BI]-/, '');
            if (nextLabel === label) { words.push(next.word); j++; }
            else break;
        }

        // SentencePiece の ▁ を除去して結合
        const word = words.join('').replace(/▁/g, ' ').trim();

        if (word.length >= 2) {
            const pos = text.indexOf(word, searchFrom);
            if (pos !== -1) {
                results.push({ entity_group: label, word, start: pos, end: pos + word.length, score: tok.score });
                searchFrom = pos + word.length;
            }
        }
        i = j;
    }
    return results;
}

/**
 * NERがORGと誤認識した「人名+役職」パターンを修正する。
 *
 * 例: NER が「田中課」をORGと検出し、直後に「長」→「課長」が続く場合、
 *     「田中」をPERとして扱い直す。
 *
 * アルゴリズム:
 *   各ORGエンティティについて、そのword内のどこかからTITLEが始まっていないか確認。
 *   見つかれば TITLE開始位置までをPERに差し替える。
 */
function _fixNerOrgWithTitle(entities, text) {
    const result = [];
    for (const ent of entities) {
        const { entity_group, start, end, word, score } = ent;
        if (entity_group !== 'ORG' && entity_group !== 'ORG-P' && entity_group !== 'ORG-O') {
            result.push(ent);
            continue;
        }
        // wordの末尾数文字 + 直後数文字 を合わせてTITLEが含まれるか確認
        // extended: エンティティ範囲 + 後ろ最大6文字
        const extended = text.slice(start, Math.min(end + 6, text.length));
        let corrected = false;
        for (const title of TITLES) {
            const idx = extended.indexOf(title);
            // エンティティの先頭でなく（idx > 0）、かつエンティティ内に境界がある場合
            if (idx > 0 && idx <= word.length) {
                const newEnd = start + idx;
                if (newEnd - start >= 2) {
                    result.push({ entity_group: 'PER', word: text.slice(start, newEnd), start, end: newEnd, score });
                    corrected = true;
                    break;
                }
            }
        }
        if (!corrected) result.push(ent);
    }
    return result;
}

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

        // ── 2. 人物・組織名（優先順位: NER → カスタム辞書 → ヒューリスティック）──

        // 2a. Transformers.js NER（最優先）
        if (this._ner) {
            try {
                const rawEntities = await this._ner.detect(text);
                console.log('[NER raw]', JSON.stringify(rawEntities));
                // ONNX版では entity_group の代わりに entity、start/end が null で
                // 1文字ずつ返ってくるため、masker 側で集約・オフセット再計算を行う
                const aggregated = _aggregateNerEntities(rawEntities, text);
                // NERがORGと誤認識した「人名+役職」パターンを修正
                const entities = _fixNerOrgWithTitle(aggregated, text);
                console.log('[NER processed]', JSON.stringify(entities));
                for (const { entity_group, start, end } of entities) {
                    let category;
                    if (entity_group === 'PER') category = '人物';
                    else if (entity_group === 'ORG' || entity_group === 'ORG-P' || entity_group === 'ORG-O') category = '組織';
                    else continue;
                    const original = text.slice(start, end);
                    console.log('[NER hit]', entity_group, start, end, JSON.stringify(original));
                    if (!original.trim()) continue;
                    const tokenId = this._store.getOrCreate(category, original);
                    _register(start, end, `【${category}${tokenId}】`);
                }
            } catch (err) {
                console.error('[NER error]', err);
            }
        }

        // 2b. カスタム辞書＋ヒューリスティック（NERで拾えなかった箇所を補完）
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
