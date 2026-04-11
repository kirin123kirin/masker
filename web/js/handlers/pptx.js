/**
 * PowerPointファイル (.pptx) ハンドラー
 * JSZip で pptx 展開
 * a:p（段落）の a:r (run) の a:t テキストを結合→マスク→最初のrunに書き戻し
 * スライドノート (ppt/notesSlides/) も処理
 */

export async function processPptx(file, masker) {
    const JSZip = window.JSZip;
    if (!JSZip) throw new Error('JSZipが読み込まれていません');

    const arrayBuffer = await file.arrayBuffer();
    const zip = await JSZip.loadAsync(arrayBuffer);

    const fileNames = Object.keys(zip.files);

    // スライド + スライドノート
    const targetFiles = fileNames.filter(name =>
        /^ppt\/slides\/slide\d+\.xml$/.test(name) ||
        /^ppt\/notesSlides\/notesSlide\d+\.xml$/.test(name)
    );

    for (const fileName of targetFiles) {
        const xmlStr = await zip.file(fileName).async('string');
        const maskedXml = await _processPptxXml(xmlStr, masker);
        zip.file(fileName, maskedXml);
    }

    const blob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
    return blob;
}

/**
 * pptx XML を処理: a:p 要素の run を結合→マスク→書き戻し
 */
async function _processPptxXml(xmlStr, masker) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'application/xml');

    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        return await _processPptxXmlString(xmlStr, masker);
    }

    // DrawingML 名前空間
    const A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main';

    const paragraphs = doc.getElementsByTagNameNS(A_NS, 'p');

    for (const para of Array.from(paragraphs)) {
        await _maskParagraph(para, A_NS, masker);
    }

    const serializer = new XMLSerializer();
    return serializer.serializeToString(doc);
}

async function _maskParagraph(para, A_NS, masker) {
    // a:r (run) 要素を取得（直接の子のみ）
    const runs = [];
    for (const child of para.childNodes) {
        if (child.nodeType === Node.ELEMENT_NODE) {
            const localName = child.localName || child.tagName.split(':').pop();
            if (localName === 'r') {
                // a:r かつ同じ名前空間か確認
                const ns = child.namespaceURI;
                if (!ns || ns === A_NS) {
                    runs.push(child);
                }
            }
        }
    }
    if (!runs.length) return;

    // 各 run から a:t テキストを収集
    const runTexts = [];
    for (const run of runs) {
        const tElems = run.getElementsByTagNameNS(A_NS, 't');
        let text = '';
        for (const t of Array.from(tElems)) {
            text += t.textContent;
        }
        runTexts.push(text);
    }

    const original = runTexts.join('');
    if (!original.trim()) return;

    const masked = await masker.mask(original);
    if (original === masked) return;

    // 最初のrunに全テキストを書き戻し、残りを空に
    const firstRun = runs[0];
    const firstTElems = firstRun.getElementsByTagNameNS(A_NS, 't');
    if (firstTElems.length > 0) {
        firstTElems[0].textContent = masked;
        for (let i = 1; i < firstTElems.length; i++) {
            firstTElems[i].textContent = '';
        }
    }

    for (let i = 1; i < runs.length; i++) {
        const tElems = runs[i].getElementsByTagNameNS(A_NS, 't');
        for (const t of Array.from(tElems)) {
            t.textContent = '';
        }
    }
}

/**
 * XMLパース失敗時の文字列操作フォールバック
 */
async function _processPptxXmlString(xmlStr, masker) {
    const pPattern = /(<a:p[ >][\s\S]*?<\/a:p>)/g;
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
    const tPattern = /(<a:t(?:\s[^>]*)?>)([\s\S]*?)(<\/a:t>)/g;
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

    let result = paraXml;
    for (let i = matches.length - 1; i >= 0; i--) {
        const { start, end, open, close } = matches[i];
        const newText = i === 0
            ? `<a:t>${_escapeXml(masked)}</a:t>`
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
