/**
 * Excelファイル (.xlsx) ハンドラー
 * JSZip で xlsx 展開
 * xl/sharedStrings.xml の <si><t> 要素のテキストをマスク
 * 数値・数式セルは変更しない
 */

export async function processXlsx(file, masker) {
    const JSZip = window.JSZip;
    if (!JSZip) throw new Error('JSZipが読み込まれていません');

    const arrayBuffer = await file.arrayBuffer();
    const zip = await JSZip.loadAsync(arrayBuffer);

    // sharedStrings.xml が存在するか確認
    const sharedStringsFile = zip.file('xl/sharedStrings.xml');
    if (!sharedStringsFile) {
        // sharedStrings なし → 文字列セルなしと判断してそのまま返す
        return await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
    }

    const xmlStr = await sharedStringsFile.async('string');
    const maskedXml = await _processSharedStrings(xmlStr, masker);
    zip.file('xl/sharedStrings.xml', maskedXml);

    const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
    return blob;
}

/**
 * sharedStrings.xml を処理
 * <si> 要素ごとにテキストを結合→マスク→書き戻す
 *
 * sharedStrings.xml の構造:
 *   <sst>
 *     <si><t>テキスト</t></si>
 *     <si><r><t>部分1</t></r><r><t>部分2</t></r></si>  ← rich text
 *   </sst>
 */
async function _processSharedStrings(xmlStr, masker) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'application/xml');

    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        return await _processSharedStringsString(xmlStr, masker);
    }

    // 名前空間
    const SS_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';

    // <si> 要素を全取得
    const siElems = doc.getElementsByTagNameNS(SS_NS, 'si');

    for (const si of Array.from(siElems)) {
        await _maskSi(si, SS_NS, masker);
    }

    const serializer = new XMLSerializer();
    return serializer.serializeToString(doc);
}

async function _maskSi(si, SS_NS, masker) {
    // <t> 要素を全収集
    const tElems = Array.from(si.getElementsByTagNameNS(SS_NS, 't'));
    if (!tElems.length) return;

    const original = tElems.map(t => t.textContent).join('');
    if (!original.trim()) return;

    const masked = await masker.mask(original);
    if (original === masked) return;

    // 最初の <t> に全テキストを書き戻し、残りを空にする
    tElems[0].textContent = masked;
    // xml:space="preserve" 属性を設定
    tElems[0].setAttributeNS(
        'http://www.w3.org/XML/1998/namespace',
        'xml:space',
        'preserve'
    );
    for (let i = 1; i < tElems.length; i++) {
        tElems[i].textContent = '';
    }
}

/**
 * XMLパース失敗時の文字列操作フォールバック
 * <si>...</si> ブロックを処理
 */
async function _processSharedStringsString(xmlStr, masker) {
    const siPattern = /(<si[ >][\s\S]*?<\/si>)/g;
    const parts = [];
    let lastIndex = 0;
    let m;

    while ((m = siPattern.exec(xmlStr)) !== null) {
        parts.push(xmlStr.slice(lastIndex, m.index));
        const maskedSi = await _maskSiString(m[1], masker);
        parts.push(maskedSi);
        lastIndex = m.index + m[0].length;
    }
    parts.push(xmlStr.slice(lastIndex));
    return parts.join('');
}

async function _maskSiString(siXml, masker) {
    // <t> タグからテキストを収集
    const tPattern = /(<t(?:\s[^>]*)?>)([\s\S]*?)(<\/t>)/g;
    const matches = [];
    let m;
    while ((m = tPattern.exec(siXml)) !== null) {
        matches.push({ start: m.index, end: m.index + m[0].length, open: m[1], text: m[2], close: m[3] });
    }

    if (!matches.length) return siXml;

    const original = matches.map(x => x.text).join('');
    if (!original.trim()) return siXml;

    const masked = await masker.mask(original);
    if (original === masked) return siXml;

    let result = siXml;
    for (let i = matches.length - 1; i >= 0; i--) {
        const { start, end, open, close } = matches[i];
        const newText = i === 0
            ? `<t xml:space="preserve">${_escapeXml(masked)}</t>`
            : `${open}${close}`;
        result = result.slice(0, start) + newText + result.slice(end);
    }
    return result;
}

function _escapeXml(s) {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}
