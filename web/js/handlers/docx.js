/**
 * Wordファイル (.docx) ハンドラー
 * JSZip を使って docx (ZIP) を展開
 * w:p（段落）を処理、w:r (run) のテキストを結合→マスク→最初のrunに書き戻す
 * 表 (w:tbl)、ヘッダー・フッター も処理
 */

console.log('[docx.js] module loaded');

export async function processDocx(file, masker) {
    console.log('[docx] processDocx called:', file.name);
    const JSZip = window.JSZip;
    console.log('[docx] JSZip available:', !!JSZip);
    if (!JSZip) throw new Error('JSZipが読み込まれていません');

    const arrayBuffer = await file.arrayBuffer();
    const zip = await JSZip.loadAsync(arrayBuffer);

    // 処理対象ファイルを特定
    const fileNames = Object.keys(zip.files);
    console.log('[docx] zip entries:', fileNames.length, fileNames.slice(0, 10));
    const targetFiles = fileNames.filter(name =>
        name === 'word/document.xml' ||
        /^word\/header\d*\.xml$/.test(name) ||
        /^word\/footer\d*\.xml$/.test(name)
    );
    console.log('[docx] targetFiles:', targetFiles);

    for (const fileName of targetFiles) {
        const xmlStr = await zip.file(fileName).async('string');
        const maskedXml = await _processDocxXml(xmlStr, masker);
        zip.file(fileName, maskedXml);
    }

    const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
    return blob;
}

/**
 * docx XML を処理: w:p 要素の run を結合→マスク→書き戻し
 */
async function _processDocxXml(xmlStr, masker) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'application/xml');

    // パースエラー確認
    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        // XMLパースエラーの場合は文字列操作でフォールバック
        return await _processDocxXmlString(xmlStr, masker);
    }

    // 名前空間
    const W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';

    // w:p 要素を全取得（w:tbl 内も含む）
    const paragraphs = doc.getElementsByTagNameNS(W_NS, 'p');
    console.log('[docx] paragraphs found:', paragraphs.length, 'in', 'document');

    for (const para of Array.from(paragraphs)) {
        await _maskParagraph(para, W_NS, masker);
    }

    const serializer = new XMLSerializer();
    return serializer.serializeToString(doc);
}

async function _maskParagraph(para, W_NS, masker) {
    // w:r (run) 要素を取得
    const runs = para.getElementsByTagNameNS(W_NS, 'r');
    if (!runs.length) return;

    // 各 run から w:t テキストを収集
    const runTexts = [];
    for (const run of Array.from(runs)) {
        const tElems = run.getElementsByTagNameNS(W_NS, 't');
        let text = '';
        for (const t of Array.from(tElems)) {
            text += t.textContent;
        }
        runTexts.push(text);
    }

    const original = runTexts.join('');
    console.log('[docx] paragraph original:', JSON.stringify(original));
    if (!original.trim()) return;

    const masked = await masker.mask(original);
    if (original === masked) return;

    // 最初のrunに全テキストを書き戻し、残りを空にする
    const firstRun = runs[0];
    const firstTElems = firstRun.getElementsByTagNameNS(W_NS, 't');
    if (firstTElems.length > 0) {
        firstTElems[0].textContent = masked;
        // xml:space="preserve" を設定してスペースを保持
        firstTElems[0].setAttributeNS(
            'http://www.w3.org/XML/1998/namespace',
            'xml:space',
            'preserve'
        );
        // 残りのt要素を空に
        for (let i = 1; i < firstTElems.length; i++) {
            firstTElems[i].textContent = '';
        }
    }

    // 残りのrunのテキストを空に
    for (let i = 1; i < runs.length; i++) {
        const tElems = runs[i].getElementsByTagNameNS(W_NS, 't');
        for (const t of Array.from(tElems)) {
            t.textContent = '';
        }
    }
}

/**
 * XMLパース失敗時の文字列操作フォールバック
 * w:t タグのテキストを正規表現で直接マスク
 */
async function _processDocxXmlString(xmlStr, masker) {
    // w:p ブロックを処理
    const pPattern = /(<w:p[ >][\s\S]*?<\/w:p>)/g;
    const parts = [];
    let lastIndex = 0;
    let m;

    while ((m = pPattern.exec(xmlStr)) !== null) {
        parts.push(xmlStr.slice(lastIndex, m.index));
        const maskedP = await _maskParagraphString(m[1], masker);
        parts.push(maskedP);
        lastIndex = m.index + m[0].length;
    }
    parts.push(xmlStr.slice(lastIndex));
    return parts.join('');
}

async function _maskParagraphString(paraXml, masker) {
    // w:t タグからテキストを収集
    const tPattern = /(<w:t(?:\s[^>]*)?>)([\s\S]*?)(<\/w:t>)/g;
    const matches = [];
    let m;
    while ((m = tPattern.exec(paraXml)) !== null) {
        matches.push({ start: m.index, end: m.index + m[0].length, open: m[1], text: m[2], close: m[3] });
    }

    if (!matches.length) return paraXml;

    const original = matches.map(x => x.text).join('');
    if (!original.trim()) return paraXml;

    const masked = await masker.mask(original);
    if (original === masked) return paraXml;

    // 最初のw:tに全テキストを書き戻し、残りを空にする
    let result = paraXml;
    // 後ろから処理してオフセットズレを防ぐ
    for (let i = matches.length - 1; i >= 0; i--) {
        const { start, end, open, close } = matches[i];
        const newText = i === 0
            ? `<w:t xml:space="preserve">${_escapeXml(masked)}</w:t>`
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
