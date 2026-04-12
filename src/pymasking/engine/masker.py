"""
マスキングエンジン本体

処理順序（優先度順）:
  1. 日付      ← date_detector (dateutil)
  2. 人物・組織 ← ner_detector (GiNZA or ヒューリスティック)
  3. その他    ← rules.py (正規表現)

役職・敬称は人名の後ろに残す。

マッピングファイルはTSV形式（保存時に1世代バックアップを作成）:
  #カテゴリ\t元テキスト\tMD5\tラベル
  人物\t田中太郎\t3A7F2C12\tA
"""

import re
import shutil
import tempfile
from pathlib import Path
from pymasking.engine.rules import RULES, PREFECTURES
from pymasking.engine.date_detector import find_dates
from pymasking.engine.ner_detector import find_persons_orgs, get_detection_mode
from pymasking.engine.token_store import TokenStore

_ADDR_SUFFIXES = (
    "支社","支店","営業所","オフィス","本社","拠点","工場","センター","倉庫","事業所"
)
_ADDR_SUFFIX_PAT = "|".join(re.escape(s) for s in _ADDR_SUFFIXES)
_PREF_PAT = "|".join(re.escape(p) for p in PREFECTURES)

# 復元時の住所トークンパターン（モジュールレベルで事前コンパイル）
_RESTORE_ADDR_PAT = re.compile(
    r"(〒|(?:" + _PREF_PAT + r"))?"
    r"(【住所[A-Z]+】)"
    r"(" + _ADDR_SUFFIX_PAT + r")?"
)


class Masker:
    def __init__(self):
        self._store = TokenStore()

    def reset(self):
        self._store.reset()

    @property
    def detection_mode(self) -> str:
        return get_detection_mode()

    def mask(self, text: str) -> str:
        masked_ranges: list[tuple[int, int]] = []
        replacements:  list[tuple[int, int, str]] = []

        def _register(start: int, end: int, rep: str):
            if any(s < end and start < e for s, e in masked_ranges):
                return
            replacements.append((start, end, rep))
            masked_ranges.append((start, end))

        # ── 1. 日付（最優先）──
        for start, end, raw in find_dates(text):
            token_id = self._store.get_or_create("日付", raw)
            _register(start, end, f"【日付{token_id}】")

        # ── 2. 人物・組織名 ──
        for start, end, original, category in find_persons_orgs(text):
            token_id = self._store.get_or_create(category, original)
            _register(start, end, f"【{category}{token_id}】")

        # ── 3. 正規表現ルール ──
        for cat, pattern, transform in RULES:
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if any(s < end and start < e for s, e in masked_ranges):
                    continue
                rep = self._make_replacement(cat, m, transform)
                _register(start, end, rep)

        # 後ろから適用してオフセットズレを防ぐ
        replacements.sort(key=lambda x: x[0], reverse=True)
        result = text
        for start, end, rep in replacements:
            result = result[:start] + rep + result[end:]
        return result

    def _make_replacement(self, category: str, m: re.Match, transform) -> str:
        original = m.group(0)
        if category == "年齢":
            return transform(m)
        raw = transform(m)
        if "{token}" not in raw:
            return raw
        token_id = self._store.get_or_create(category, original)
        return raw.replace("{token}", token_id)

    # ── TSVマッピング ──────────────────────────────────

    def save_mapping(self, path: Path):
        """マッピングをTSV形式で保存。既存ファイルは .bak に退避（1世代）。

        書き込みは同一ディレクトリの一時ファイル経由で行い、
        rename でアトミックに差し替える（書き込み失敗時に元ファイルを破壊しない）。
        """
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))

        lines = ["#カテゴリ\t元テキスト\tMD5\tラベル"]
        for cat, orig, h, label in self._store.rows():
            orig_esc = orig.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
            lines.append(f"{cat}\t{orig_esc}\t{h}\t{label}")
        content = "\n".join(lines) + "\n"

        # 同一ディレクトリで tmp を作成し rename でアトミックに差し替え
        tmp_fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_name).replace(path)
        except Exception:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def load_mapping(self, path: Path):
        """TSVマッピングを読み込み、既存の蓄積テーブルにマージする。"""
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 4:
                cat, orig_esc, h, label = parts
                orig = orig_esc.replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r").replace("\\\\", "\\")
                rows.append((cat, orig, h, label))
        self._store.load_rows(rows)

    def restore(self, text: str, mapping_path: Path) -> str:
        """マスク済みテキストを原文に復元（年齢変換は非可逆）"""
        restore_map: dict[str, str] = {}
        for line in mapping_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 4:
                cat, orig_esc, h, label = parts
                orig = orig_esc.replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r").replace("\\\\", "\\")
                restore_map[f"【{cat}{label}】"] = orig

        # 住所トークンの特殊復元（prefix・suffix の二重化防止）
        def _restore_addr(m: re.Match) -> str:
            prefix   = m.group(1) or ""
            token    = m.group(2)
            suffix   = m.group(3) or ""
            original = restore_map.get(token, token)
            result   = original if original.startswith("〒") else (
                           ("〒" + original) if prefix == "〒" else original
                       )
            if suffix and not result.endswith(suffix):
                result += suffix
            return result

        result = _RESTORE_ADDR_PAT.sub(_restore_addr, text)

        # 残りの全トークン復元
        result = re.sub(
            r"【[^【】]+】",
            lambda m: restore_map.get(m.group(0), m.group(0)),
            result,
        )
        return result
