/**
 * 日付検出モジュール
 * Python版 date_detector.py を JavaScript に移植
 * ES2018 lookbehind assertion を使用
 */

// ── 正規化ユーティリティ ──────────────────────────────────────────────────────

const _ZEN_NUM = { '０':'0','１':'1','２':'2','３':'3','４':'4','５':'5','６':'6','７':'7','８':'8','９':'9' };
const _ZEN_MARK = { '／':'/', '－':'-', '．':'.', '　':' ' };
const _KANJI_DIGIT = {
    '〇':'0','一':'1','二':'2','三':'3','四':'4',
    '五':'5','六':'6','七':'7','八':'8','九':'9',
};

function _normalize(s) {
    // 全角数字 → 半角
    s = s.replace(/[０-９]/g, c => _ZEN_NUM[c] || c);
    // 全角記号 → 半角
    s = s.replace(/[／－．　]/g, c => _ZEN_MARK[c] || c);
    // 漢数字 → 半角
    for (const [k, v] of Object.entries(_KANJI_DIGIT)) {
        s = s.replaceAll(k, v);
    }
    // 「10X」→「1X」の十の位変換は省略（元の実装は re.sub(r"10(\d)", ...)）
    s = s.replace(/10(\d)/g, (_, d) => String(10 + parseInt(d)));
    return s;
}

// 和暦 → 西暦オフセット
const _GENGO = {
    '令和': 2018, 'R': 2018,
    '平成': 1988, 'H': 1988,
    '昭和': 1925, 'S': 1925,
    '大正': 1911, 'T': 1911,
    '明治': 1867, 'M': 1867,
};
function _wareki_to_seireki(s) {
    // 毎回新しいRegExpを生成してlastIndex問題を回避
    return s.replace(/(令和|平成|昭和|大正|明治|[RHTMS])(\d{1,2})/g, (_, g, y) => {
        const offset = _GENGO[g] ?? 0;
        return String(offset + parseInt(y));
    });
}

function _to_date_str(s) {
    s = s.replace(/年/g, '-').replace(/月/g, '-').replace(/日/g, '');
    return s.replace(/^-+|-+$/g, '').trim();
}

// ── 日付バリデーション ─────────────────────────────────────────────────────────

function _isValidDate(raw) {
    let s = _normalize(raw);
    s = _wareki_to_seireki(s);

    // 年月日の漢字区切りをハイフンに変換
    if (s.includes('年') || s.includes('月')) {
        s = _to_date_str(s);
    }

    // 8桁連番: 20250401
    if (/^20[2-9]\d[01]\d[0-3]\d$/.test(s)) {
        const m = parseInt(s.slice(4, 6));
        const d = parseInt(s.slice(6, 8));
        return m >= 1 && m <= 12 && d >= 1 && d <= 31;
    }

    // スラッシュ・ハイフン・ドット区切り
    let year, month, day;
    let m;

    // YYYY[-/.]MM[-/.]DD
    m = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
    if (m) {
        [, year, month, day] = m.map(Number);
        return _checkDate(year, month, day);
    }

    // YYYY-MM（日なし）
    m = s.match(/^(\d{4})[-/.](\d{1,2})$/);
    if (m) {
        year = parseInt(m[1]);
        month = parseInt(m[2]);
        return year >= 1900 && year <= 2100 && month >= 1 && month <= 12;
    }

    // MM/DD（年なし）
    m = s.match(/^(\d{1,2})\/(\d{1,2})$/);
    if (m) {
        month = parseInt(m[1]);
        day = parseInt(m[2]);
        return month >= 1 && month <= 12 && day >= 1 && day <= 31;
    }

    // 月日のみ日本語形式（正規化後: X-X）
    m = s.match(/^(\d{1,2})-(\d{1,2})$/);
    if (m) {
        month = parseInt(m[1]);
        day = parseInt(m[2]);
        return month >= 1 && month <= 12 && day >= 1 && day <= 31;
    }

    // 英語月名
    const MONTH_NAMES = {
        jan:1, january:1, feb:2, february:2, mar:3, march:3,
        apr:4, april:4, may:5, jun:6, june:6, jul:7, july:7,
        aug:8, august:8, sep:9, september:9, oct:10, october:10,
        nov:11, november:11, dec:12, december:12,
    };
    const engM = s.match(/(\w+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})/i)
               || s.match(/(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\.?\s+(\d{4})/i);
    if (engM) {
        const mnStr = (engM[1].match(/^\d/) ? engM[2] : engM[1]).toLowerCase();
        year = parseInt(engM[3]) || parseInt(engM[1].match(/^\d/) ? engM[3] : engM[3]);
        const yearM = s.match(/(\d{4})/);
        if (yearM) year = parseInt(yearM[1]);
        month = MONTH_NAMES[mnStr];
        if (month && year >= 1900 && year <= 2100) return true;
    }

    // YYYY年M月D日 形式（正規化後にハイフン区切りになっているはず）
    // 上でカバーされているが念のため
    m = s.match(/(\d{4})-(\d{1,2})(?:-(\d{1,2}))?/);
    if (m) {
        year = parseInt(m[1]);
        month = parseInt(m[2]);
        day = m[3] ? parseInt(m[3]) : 1;
        return _checkDate(year, month, day);
    }

    return false;
}

function _checkDate(year, month, day) {
    if (year < 1900 || year > 2100) return false;
    if (month < 1 || month > 12) return false;
    if (day < 1 || day > 31) return false;
    return true;
}

// ── 候補パターン ──────────────────────────────────────────────────────────────
// [pattern, needsContext]

const _CANDIDATES = [
    // 日本語年月日（西暦・和暦・全角・漢数字すべて対応）
    [/(?:令和|平成|昭和|大正|明治)?\s*[０-９\d〇一二三四五六七八九十]{1,4}年\s*[０-９\d〇一二三四五六七八九十]{1,2}月(?:\s*[０-９\d〇一二三四五六七八九十]{1,2}日)?/g, false],

    // 西暦 スラッシュ: 2025/4/1
    [/(?<!\d)[12][0-9]{3}\/[01]?[0-9]\/[0-3]?[0-9](?!\d)/g, false],

    // 西暦 ハイフン: 2025-04-01
    [/(?<!\d)[12][0-9]{3}-[01]?[0-9]-[0-3]?[0-9](?!\d)/g, false],

    // 西暦 ドット: 2025.04.01
    [/(?<!\d)[12][0-9]{3}\.[01]?[0-9]\.[0-3]?[0-9](?!\d)/g, false],

    // 8桁連番: 20250401
    [/(?<![\dA-Za-z\-])20[2-9][0-9][01][0-9][0-3][0-9](?![\dA-Za-z\-])/g, false],

    // 月日のみ（日本語）: 4月1日
    [/(?<!\d)[０-９\d〇一二三四五六七八九十]{1,2}月\s*[０-９\d〇一二三四五六七八九十]{1,2}日/g, false],

    // 英語表記: April 1, 2025 / 1st April 2025
    [/(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{4}/gi, false],

    // 和暦省略形: R7.4.1 / H30.3.31
    [/(?<![A-Za-z0-9_])[RHTMS]\d{1,2}[.][01]?\d[.][0-3]?\d(?!\d)/g, false],

    // MM/DD 年なし（文脈チェック必要）
    [/(?<!\d)[01]?\d\/[0-3]?\d(?!\d)/g, true],
];

// 文脈キーワード（前後50文字以内）
const _CONTEXT_PAT = /年|月|日|date|dated?|as\s+of|on\s+the|〜|から|まで|期限|締切|締め切り|納期|予定|時点|以降|以前|当日|翌日|前日|開始|終了|発効|有効|期日|schedule|due|deadline|effective|expir/i;

// ── メイン検出関数 ─────────────────────────────────────────────────────────────

export function findDates(text) {
    const hits = [];

    for (const [pattern, needsCtx] of _CANDIDATES) {
        // パターンのフラグをリセットして再利用
        const re = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : pattern.flags + 'g');
        let m;
        while ((m = re.exec(text)) !== null) {
            const start = m.index;
            const end = m.index + m[0].length;
            const raw = m[0];

            if (needsCtx) {
                const window = text.slice(Math.max(0, start - 50), end + 50);
                if (!_CONTEXT_PAT.test(window)) continue;
            }

            if (!_isValidDate(raw)) continue;

            hits.push([start, end, raw]);
        }
    }

    return _dedup(hits);
}

function _dedup(hits) {
    if (!hits.length) return [];
    // 長いマッチを優先してソート
    hits.sort((a, b) => (b[1] - b[0]) - (a[1] - a[0]));
    const kept = [];
    for (const h of hits) {
        const [hs, he] = h;
        if (kept.some(([s, e]) => s < he && hs < e)) continue;
        kept.push(h);
    }
    kept.sort((a, b) => a[0] - b[0]);
    return kept;
}
