/**
 * テキストファイル (.txt) ハンドラー
 * BOM (EF BB BF) 付きUTF-8対応
 */

const _UTF8_BOM = new Uint8Array([0xef, 0xbb, 0xbf]);

export async function processTxt(file, masker) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);

    // BOM判定
    const hasBom = bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;

    // デコード（BOMは自動除去される utf-8-sig 相当）
    const decoder = new TextDecoder('utf-8');
    const text = decoder.decode(hasBom ? bytes.slice(3) : bytes);

    const masked = await masker.mask(text);

    // BOM復元
    const encoder = new TextEncoder();
    const maskedBytes = encoder.encode(masked);

    let outputBytes;
    if (hasBom) {
        outputBytes = new Uint8Array(_UTF8_BOM.length + maskedBytes.length);
        outputBytes.set(_UTF8_BOM);
        outputBytes.set(maskedBytes, _UTF8_BOM.length);
    } else {
        outputBytes = maskedBytes;
    }

    return new Blob([outputBytes], { type: 'text/plain' });
}
