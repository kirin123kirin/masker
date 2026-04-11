/**
 * ヒューリスティック人名・組織名検出
 * Python版 ner_detector.py の _find_by_heuristic() を移植
 *
 * 検出戦略:
 *   A. カスタム辞書に登録された名前を直接検索
 *   B. 役職・敬称の直前テキストを人名として抽出
 *   C. 組織名サフィックスを含む文字列を組織名として抽出
 */

// ━━ 役職・敬称定義 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export const TITLES = [
    // 役員・経営層（長い順）
    '代表取締役社長', '代表取締役副社長', '代表取締役',
    '取締役社長', '取締役副社長', '取締役会長', '取締役',
    '執行役員', '監査役', '副社長', '会長', '社長', '頭取', '総裁',
    '理事長', '専務', '常務',
    // 管理職
    '本部長', '事業部長', '副部長', '部長', '担当課長', '課長',
    '係長', '主任', 'グループ長', 'チームリーダー',
    'マネージャー', 'ディレクター',
    // 専門職
    '主任研究員', '研究員', '教授', '准教授', '講師', '博士',
    '公認会計士', '弁理士', '弁護士', '税理士', '司法書士', '医師',
    // 英語役職
    'President', 'Director', 'Manager', 'CEO', 'CFO', 'COO',
    'CTO', 'CMO', 'CISO',
    // 敬称
    'さん', '様', '氏', '君', 'ちゃん', '殿',
    'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.',
    'Mr', 'Mrs', 'Ms', 'Dr', 'Prof',
].sort((a, b) => b.length - a.length); // 長い順

// ━━ 人名パターン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const _JP_NAME = '[\\u4E00-\\u9FFF]{2,4}(?:[\\u3040-\\u309F\\u30A0-\\u30FF]{1,4})?';
const _EN_NAME = '[A-Z][a-z]{1,14}(?:\\s[A-Z][a-z]{1,14})?';
const _NAME_CORE = `(?:${_JP_NAME}|${_EN_NAME})`;
const _TITLE_PAT_STR = TITLES
    .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');

function makeNameTitlePat() {
    return new RegExp(`(${_NAME_CORE})(?=${_TITLE_PAT_STR})`, 'g');
}

// ━━ 組織名パターン ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const _ORG_SUFFIXES = [
    '代表取締役社長', '株式会社', '有限会社', '合同会社', '合資会社', '合名会社',
    '一般社団法人', '公益社団法人', '一般財団法人', '公益財団法人',
    '独立行政法人', '国立研究開発法人', '社会福祉法人', '医療法人',
    '特定非営利活動法人', 'NPO法人', '学校法人', '宗教法人',
    'ホールディングス', 'コーポレーション', 'エンタープライズ', 'グループ',
    'Inc.', 'Corp.', 'Ltd.', 'LLC', 'LLP', 'Co.', 'GmbH', 'AG', 'plc',
    '信用金庫', '銀行', '証券', '保険', '信託',
].sort((a, b) => b.length - a.length);

const _ORG_BODY = '[\\u4E00-\\u9FFFa-zA-Z0-9\\u30A0-\\u30FF\\-・]{2,30}';
const _ORG_SUF_PAT = _ORG_SUFFIXES
    .map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|');

function makeOrgPat() {
    const prefixed = '(?:株式会社|有限会社|合同会社|一般社団法人|一般財団法人|特定非営利活動法人)\\s*' + _ORG_BODY;
    const suffixed = _ORG_BODY + '(?:' + _ORG_SUF_PAT + ')';
    return new RegExp(`(?:${prefixed}|${suffixed})`, 'g');
}

// ━━ カスタム辞書 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

let _customPersons = null;
let _customOrgs = null;

async function loadCustomDict() {
    if (_customPersons !== null) return;
    _customPersons = [];
    _customOrgs = [];
    try {
        const res = await fetch('../dict/custom_dict.txt');
        if (!res.ok) return;
        const text = await res.text();
        for (const line of text.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;
            const [cat, name] = trimmed.split(',', 2).map(s => s.trim());
            if (!name) continue;
            if (['人物', '人名', 'PER'].includes(cat)) _customPersons.push(name);
            else if (['組織', 'ORG'].includes(cat)) _customOrgs.push(name);
        }
        // 長い順にソート（部分マッチ防止）
        _customPersons.sort((a, b) => b.length - a.length);
        _customOrgs.sort((a, b) => b.length - a.length);
    } catch (_) {
        // 辞書なしでも継続
    }
}

// ━━ メイン検出関数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * テキストから人名・組織名を検出
 * @param {string} text
 * @returns {Promise<[number, number, string, string][]>} [start, end, original, category][]
 */
export async function findPersonsOrgsHeuristic(text) {
    await loadCustomDict();

    const results = [];
    const used = []; // [start, end][]

    function tryAdd(start, end, original, cat) {
        original = original.trim();
        if (!original || original.length < 2) return false;
        // 数字・記号のみは除外
        if (/^[\d\s\W]+$/.test(original)) return false;
        // 重複区間チェック
        if (used.some(([s, e]) => s < end && start < e)) return false;
        results.push([start, end, original, cat]);
        used.push([start, end]);
        return true;
    }

    // A. カスタム辞書（最優先）
    for (const name of (_customPersons ?? [])) {
        const pat = new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
        let m;
        while ((m = pat.exec(text)) !== null) {
            tryAdd(m.index, m.index + m[0].length, m[0], '人物');
        }
    }
    for (const name of (_customOrgs ?? [])) {
        const pat = new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
        let m;
        while ((m = pat.exec(text)) !== null) {
            tryAdd(m.index, m.index + m[0].length, m[0], '組織');
        }
    }

    // B. 役職・敬称直前の人名
    const nameTitlePat = makeNameTitlePat();
    let m;
    while ((m = nameTitlePat.exec(text)) !== null) {
        const name = m[1];
        if (TITLES.includes(name)) continue;
        tryAdd(m.index, m.index + m[1].length, name, '人物');
    }

    // C. 組織名サフィックス
    const orgPat = makeOrgPat();
    while ((m = orgPat.exec(text)) !== null) {
        tryAdd(m.index, m.index + m[0].length, m[0], '組織');
    }

    results.sort((a, b) => a[0] - b[0]);
    return results;
}
