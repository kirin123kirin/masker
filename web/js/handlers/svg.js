/**
 * SVGファイル (.svg) ハンドラー
 * DOMParser で SVG をパース
 * text/tspan/title/desc/textPath 要素のテキストをマスク
 * XMLSerializer で出力
 */

const _TEXT_ELEMENTS = new Set(['text', 'tspan', 'title', 'desc', 'textPath']);

export async function processSvg(file, masker) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);

    // BOM判定
    const hasBom = bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;

    const decoder = new TextDecoder('utf-8');
    const svgText = decoder.decode(hasBom ? bytes.slice(3) : bytes);

    const parser = new DOMParser();
    const doc = parser.parseFromString(svgText, 'image/svg+xml');

    // パースエラー確認
    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        throw new Error('SVGのパースに失敗しました: ' + parseError.textContent);
    }

    // テキスト要素を再帰的に処理
    await _processNode(doc.documentElement, masker);

    const serializer = new XMLSerializer();
    let output = serializer.serializeToString(doc);

    // BOM復元
    if (hasBom) {
        output = '\ufeff' + output;
    }

    const encoder = new TextEncoder();
    return new Blob([encoder.encode(output)], { type: 'image/svg+xml' });
}

async function _processNode(node, masker) {
    if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.localName || node.tagName.split(':').pop();
        if (_TEXT_ELEMENTS.has(tagName)) {
            // テキストノードの子のみをマスク（子要素は再帰で処理）
            for (const child of node.childNodes) {
                if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
                    child.textContent = await masker.mask(child.textContent);
                }
            }
        }
        // 子要素を再帰処理
        for (const child of node.childNodes) {
            if (child.nodeType === Node.ELEMENT_NODE) {
                await _processNode(child, masker);
            }
        }
    }
}
