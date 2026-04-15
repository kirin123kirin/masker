"""
PII Masker - Web UI サーバー
Flask + pymasking によるポータブル PII マスキングアプリ

対応入力: txt / html / svg / docx / pptx / xlsx / pdf / jpg / png
         + クリップボード画像 (OCR)
"""
import base64
import io
import re
import sys
import tempfile
import webbrowser
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# ── pymasking をロード（リポジトリ内 src/ → インストール済み の順）──
_SRC = Path(__file__).parent.parent / "src"
if _SRC.exists():
    sys.path.insert(0, str(_SRC))

from pymasking.engine.masker import Masker                    # noqa: E402
from pymasking.engine.ner_detector import get_detection_mode  # noqa: E402

# ── OCR (easyocr) ── オプション ──
try:
    import easyocr
    _ocr = easyocr.Reader(["ja", "en"], gpu=False)
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ── Flask ────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 拡張子 → ハンドラー種別
_EXT_KIND = {
    ".txt":  "txt",
    ".html": "html", ".htm": "html",
    ".svg":  "svg",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".pdf":  "pdf",
    ".jpg":  "img", ".jpeg": "img",
    ".png":  "img",
}

# 復元対応拡張子（バイナリ ZIP 系 + テキスト系）
_RESTORE_EXTS = {".txt", ".html", ".htm", ".svg", ".md",
                 ".docx", ".pptx", ".xlsx"}

_TOKEN_PAT = re.compile(r'【[^【】]+】')


# ── マスキング処理 ────────────────────────────────────────────────────────────

def _process(src: Path, masker: Masker) -> tuple[bytes, str]:
    """ファイルをマスキングして (result_bytes, result_filename) を返す"""
    ext  = src.suffix.lower()
    stem = src.stem
    kind = _EXT_KIND.get(ext)

    if kind == "txt":
        from pymasking.formats.handler_txt import process_txt
        out_str, _, _ = process_txt(src, masker)
        return out_str.encode("utf-8"), f"{stem}_masked.txt"

    if kind == "html":
        from pymasking.formats.handler_html import process_html
        out_str, _, _ = process_html(src, masker)
        return out_str.encode("utf-8"), f"{stem}_masked{ext}"

    if kind == "svg":
        from pymasking.formats.handler_svg import process_svg
        out_str, _, _ = process_svg(src, masker)
        return out_str.encode("utf-8"), f"{stem}_masked.svg"

    if kind == "pdf":
        from pymasking.formats.handler_pdf import process_pdf
        out_str, _, _ = process_pdf(src, masker)
        return out_str.encode("utf-8"), f"{stem}_masked.md"

    if kind == "docx":
        from pymasking.formats.handler_docx import process_docx
        out_bytes, _, _ = process_docx(src, masker)
        return out_bytes, f"{stem}_masked.docx"

    if kind == "pptx":
        from pymasking.formats.handler_pptx import process_pptx
        out_bytes, _, _ = process_pptx(src, masker)
        return out_bytes, f"{stem}_masked.pptx"

    if kind == "xlsx":
        from pymasking.formats.handler_xlsx import process_xlsx
        out_bytes, _, _ = process_xlsx(src, masker)
        return out_bytes, f"{stem}_masked.xlsx"

    if kind == "img":
        if not OCR_AVAILABLE:
            raise RuntimeError(
                "OCR (easyocr) が利用できません。\n"
                "setup.bat を再実行するか、pip install easyocr を実行してください。"
            )
        results = _ocr.readtext(str(src))
        text = "\n".join(r[1] for r in results)
        masked = masker.mask(text)
        return masked.encode("utf-8"), f"{stem}_masked.txt"

    raise ValueError(f"非対応形式: {ext}")


def _export_tsv(masker: Masker) -> bytes:
    """マッピング TSV を bytes で返す"""
    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    masker.save_mapping(tmp_path)
    data = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)
    return data


# ── 復元処理 ─────────────────────────────────────────────────────────────────

def _build_restore_map(tsv_bytes: bytes) -> dict[str, str]:
    """TSV バイト列からトークン→元テキストのマップを構築"""
    restore_map: dict[str, str] = {}
    for line in tsv_bytes.decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 4:
            cat, orig_esc, _, label = parts
            orig = (orig_esc
                    .replace("\\t", "\t").replace("\\n", "\n")
                    .replace("\\r", "\r").replace("\\\\", "\\"))
            restore_map[f"【{cat}{label}】"] = orig
    return restore_map


def _restore_text(text: str, restore_map: dict) -> str:
    return _TOKEN_PAT.sub(lambda m: restore_map.get(m.group(0), m.group(0)), text)


def _restore_zip(data: bytes, restore_map: dict) -> bytes:
    """docx / pptx / xlsx (ZIP+XML) 内の全トークンを復元"""
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data), "r") as zin, \
         zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            name_lower = item.filename.lower()
            if name_lower.endswith(".xml") or name_lower.endswith(".rels"):
                text = content.decode("utf-8", errors="replace")
                text = _restore_text(text, restore_map)
                content = text.encode("utf-8")
            zout.writestr(item, content)
    return buf.getvalue()


def _restore_file(masked_data: bytes, ext: str,
                  restore_map: dict, stem: str) -> tuple[bytes, str]:
    """マスク済みファイルを復元して (result_bytes, filename) を返す"""
    ext = ext.lower()

    if ext in (".docx", ".pptx", ".xlsx"):
        result = _restore_zip(masked_data, restore_map)
        return result, f"{stem}_restored{ext}"

    # テキスト系（txt / html / htm / svg / md）
    text = masked_data.decode("utf-8", errors="replace")
    restored = _restore_text(text, restore_map)
    return restored.encode("utf-8"), f"{stem}_restored{ext}"


# ── ルーティング ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        ner_mode=get_detection_mode(),
        ocr_available=OCR_AVAILABLE,
        supported_exts=sorted(_EXT_KIND.keys()),
        restore_exts=sorted(_RESTORE_EXTS),
    )


@app.route("/mask", methods=["POST"])
def mask_api():
    """ファイルアップロード → マスキング"""
    if "file" not in request.files:
        return jsonify({"error": "ファイルがありません"}), 400

    f   = request.files["file"]
    ext = Path(f.filename).suffix.lower()
    if ext not in _EXT_KIND:
        return jsonify({"error": f"非対応形式: {ext}"}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        f.save(tmp_path)

    try:
        masker = Masker()
        result_bytes, result_name = _process(tmp_path, masker)
        tsv_bytes = _export_tsv(masker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        tmp_path.unlink(missing_ok=True)

    stem = Path(f.filename).stem
    return jsonify({
        "result":      base64.b64encode(result_bytes).decode(),
        "result_name": result_name,
        "tsv":         base64.b64encode(tsv_bytes).decode(),
        "tsv_name":    f"{stem}_mapping.tsv",
    })


@app.route("/mask-clipboard", methods=["POST"])
def mask_clipboard():
    """クリップボード画像（base64 data URL）→ OCR → マスキング"""
    if not OCR_AVAILABLE:
        return jsonify({"error": "OCR (easyocr) が利用できません。setup.bat を再実行してください。"}), 503

    payload = request.get_json(silent=True) or {}
    if "data" not in payload:
        return jsonify({"error": "画像データがありません"}), 400

    try:
        img_b64  = payload["data"].split(",")[-1]
        img_data = base64.b64decode(img_b64)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_bytes(img_data)

        masker = Masker()
        result_bytes, result_name = _process(tmp_path, masker)
        tsv_bytes = _export_tsv(masker)
        tmp_path.unlink(missing_ok=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "result":      base64.b64encode(result_bytes).decode(),
        "result_name": "clipboard_masked.txt",
        "tsv":         base64.b64encode(tsv_bytes).decode(),
        "tsv_name":    "clipboard_mapping.tsv",
    })


@app.route("/unmask", methods=["POST"])
def unmask_api():
    """マスク済みファイル + マッピング TSV → 元ファイル復元"""
    if "file" not in request.files or "tsv" not in request.files:
        return jsonify({"error": "マスク済みファイルとマッピングTSVの両方が必要です"}), 400

    f        = request.files["file"]
    tsv_file = request.files["tsv"]
    ext      = Path(f.filename).suffix.lower()

    if ext not in _RESTORE_EXTS:
        return jsonify({"error": f"復元非対応形式: {ext}"}), 400

    try:
        masked_data  = f.read()
        tsv_bytes    = tsv_file.read()
        restore_map  = _build_restore_map(tsv_bytes)
        stem         = Path(f.filename).stem.removesuffix("_masked")
        result_bytes, result_name = _restore_file(masked_data, ext, restore_map, stem)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "result":      base64.b64encode(result_bytes).decode(),
        "result_name": result_name,
    })


# ── エントリポイント ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    url = "http://localhost:8765"
    print(f"\n{'='*50}")
    print(f"  PII Masker 起動中: {url}")
    print(f"  終了: Ctrl+C")
    print(f"{'='*50}\n")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=8765, debug=False)
