/**
 * HTMLファイル (.html/.htm) ハンドラー
 * Python版 handler_html.py のポート
 * タグ・属性は保持し、テキストノードのみマスクする
 * BOM (EF BB BF) 対応
 */

const _UTF8_BOM = new Uint8Array([0xef, 0xbb, 0xbf]);

// マスク対象外タグ（スクリプト・スタイルは処理しない）
const _SKIP_TAGS = /<(script|style)[^>]*>[\s\S]*?<\/\1>/gi;

// テキストノード（タグとタグの間）
const _TEXT_NODE = /(>)([^<]+)(<)/g;

export async function processHtml(file, masker) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);

    // BOM判定
    const hasBom = bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;

    // デコード（BOMは除去）
    const decoder = new TextDecoder('utf-8');
    const original = decoder.decode(hasBom ? bytes.slice(3) : bytes);

    // script/style をプレースホルダーに退避
    const skipped = [];
    const working = original.replace(_SKIP_TAGS, match => {
        skipped.push(match);
        return `%%SKIP${skipped.length - 1}%%`;
    });

    // テキストノードをマスク（非同期）
    // _TEXT_NODE は stateful なので毎回新しいRegExpを使う
    const textNodeRe = new RegExp(_TEXT_NODE.source, _TEXT_NODE.flags);
    const parts = [];
    let lastIndex = 0;
    let m;
    while ((m = textNodeRe.exec(working)) !== null) {
        // マッチ前の部分
        parts.push(working.slice(lastIndex, m.index));
        // グループ1: '>'
        parts.push(m[1]);
        // テキストノードをマスク（後でまとめてreplaceするためにPromiseを積む）
        parts.push({ text: m[2] });
        // グループ3: '<'
        parts.push(m[3]);
        lastIndex = m.index + m[0].length;
    }
    parts.push(working.slice(lastIndex));

    // 非同期マスク処理
    const resolved = await Promise.all(
        parts.map(async p => {
            if (typeof p === 'string') return p;
            return await masker.mask(p.text);
        })
    );
    let maskedWorking = resolved.join('');

    // プレースホルダーを元に戻す
    for (let i = 0; i < skipped.length; i++) {
        maskedWorking = maskedWorking.replace(`%%SKIP${i}%%`, skipped[i]);
    }

    // BOM復元
    const output = hasBom ? '\ufeff' + maskedWorking : maskedWorking;

    const encoder = new TextEncoder();
    return new Blob([encoder.encode(output)], { type: 'text/html' });
}
