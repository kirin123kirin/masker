/**
 * トークン発番・一意性管理
 * 2層構造:
 *   第1層: 元テキスト → MD5ハッシュ（決定論的・セッション不変）
 *   第2層: MD5ハッシュ → ラベル（蓄積テーブルへの初登場順）
 */

// ── RFC 1321準拠 MD5実装 ────────────────────────────────────────────────────
// UTF-8文字列対応（TextEncoderでバイト列化してから計算）

function md5(str) {
    // UTF-8エンコード
    const bytes = new TextEncoder().encode(str);
    return _md5Bytes(bytes);
}

function _md5Bytes(bytes) {
    // 初期ハッシュ値
    let a0 = 0x67452301;
    let b0 = 0xefcdab89;
    let c0 = 0x98badcfe;
    let d0 = 0x10325476;

    // メッセージをパディング
    const msgLen = bytes.length;
    const bitLen = msgLen * 8;

    // パディング: 1ビット追加後、512ビット境界まで0パディング、最後に64ビット長
    // ブロック数の計算: (msgLen + 1 + 8) を64で切り上げ
    const padLen = 64 - ((msgLen + 9) % 64);
    const totalLen = msgLen + 1 + padLen + 8;
    const padded = new Uint8Array(totalLen);
    padded.set(bytes);
    padded[msgLen] = 0x80;
    // 最後の8バイトにビット長（リトルエンディアン64bit）
    // JavaScriptのNumberは53bitまで正確なので下位32bitと上位32bitに分けて書く
    const lo = bitLen >>> 0;
    const hi = Math.floor(bitLen / 0x100000000) >>> 0;
    padded[totalLen - 8] = lo & 0xff;
    padded[totalLen - 7] = (lo >>> 8) & 0xff;
    padded[totalLen - 6] = (lo >>> 16) & 0xff;
    padded[totalLen - 5] = (lo >>> 24) & 0xff;
    padded[totalLen - 4] = hi & 0xff;
    padded[totalLen - 3] = (hi >>> 8) & 0xff;
    padded[totalLen - 2] = (hi >>> 16) & 0xff;
    padded[totalLen - 1] = (hi >>> 24) & 0xff;

    // 各ラウンドで使うシフト量
    const S = [
        7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,
        5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,
        4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,
        6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21,
    ];

    // 事前計算定数 T[i] = floor(abs(sin(i+1)) * 2^32)
    const T = new Uint32Array(64);
    for (let i = 0; i < 64; i++) {
        T[i] = (Math.abs(Math.sin(i + 1)) * 0x100000000) >>> 0;
    }

    // ブロック処理
    const view = new DataView(padded.buffer);
    for (let offset = 0; offset < totalLen; offset += 64) {
        // 16個の32bitワード（リトルエンディアン）を読み込む
        const M = new Uint32Array(16);
        for (let j = 0; j < 16; j++) {
            M[j] = view.getUint32(offset + j * 4, true);
        }

        let A = a0, B = b0, C = c0, D = d0;

        for (let i = 0; i < 64; i++) {
            let F, g;
            if (i < 16) {
                F = (B & C) | (~B & D);
                g = i;
            } else if (i < 32) {
                F = (D & B) | (~D & C);
                g = (5 * i + 1) % 16;
            } else if (i < 48) {
                F = B ^ C ^ D;
                g = (3 * i + 5) % 16;
            } else {
                F = C ^ (B | ~D);
                g = (7 * i) % 16;
            }
            F = (F + A + T[i] + M[g]) >>> 0;
            A = D;
            D = C;
            C = B;
            B = (B + _rotl32(F, S[i])) >>> 0;
        }

        a0 = (a0 + A) >>> 0;
        b0 = (b0 + B) >>> 0;
        c0 = (c0 + C) >>> 0;
        d0 = (d0 + D) >>> 0;
    }

    // ダイジェストをリトルエンディアンで16バイトに変換
    const digest = new Uint8Array(16);
    const dv = new DataView(digest.buffer);
    dv.setUint32(0, a0, true);
    dv.setUint32(4, b0, true);
    dv.setUint32(8, c0, true);
    dv.setUint32(12, d0, true);

    return Array.from(digest).map(b => b.toString(16).padStart(2, '0')).join('');
}

function _rotl32(x, n) {
    return ((x << n) | (x >>> (32 - n))) >>> 0;
}

// ── TokenStore ───────────────────────────────────────────────────────────────

export class TokenStore {
    constructor() {
        this._textToHash = {}; // cat -> { text -> hash }
        this._hashToLabel = {}; // cat -> { hash -> label }
    }

    reset() {
        this._textToHash = {};
        this._hashToLabel = {};
    }

    getOrCreate(category, original) {
        const t2h = this._textToHash[category] ??= {};
        if (!(original in t2h)) {
            t2h[original] = md5(original).slice(0, 8).toUpperCase();
        }
        const h = t2h[original];
        const h2l = this._hashToLabel[category] ??= {};
        if (!(h in h2l)) {
            h2l[h] = indexToLabel(Object.keys(h2l).length);
        }
        return h2l[h];
    }

    *rows() {
        for (const [cat, t2h] of Object.entries(this._textToHash)) {
            const h2l = this._hashToLabel[cat] ?? {};
            for (const [orig, h] of Object.entries(t2h)) {
                yield [cat, orig, h, h2l[h] ?? ''];
            }
        }
    }

    loadRows(rows) {
        for (const [cat, orig, h, label] of rows) {
            (this._textToHash[cat] ??= {})[orig] = h;
            (this._hashToLabel[cat] ??= {})[h] = label;
        }
    }
}

function indexToLabel(n) {
    let result = '';
    let x = n + 1;
    while (x > 0) {
        const r = (x - 1) % 26;
        result = String.fromCharCode(65 + r) + result;
        x = Math.floor((x - 1) / 26);
    }
    return result;
}
