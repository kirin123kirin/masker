"""
マスキングエンジン本体

処理順序（優先度順）:
  1. 日付      ← date_detector (dateutil)
  2. 人物・組織 ← ner_detector (GiNZA or ヒューリスティック)
  3. その他    ← rules.py (正規表現)

役職・敬称は人名の後ろに残す。
"""

import re
import json
from pathlib import Path
from pii_masker.engine.rules import RULES, PREFECTURES
from pii_masker.engine.date_detector import find_dates
from pii_masker.engine.ner_detector import find_persons_orgs, TITLES, get_detection_mode
from pii_masker.engine.token_store import TokenStore

_ADDR_SUFFIXES = (
    "支社","支店","営業所","オフィス","本社","拠点","工場","センター","倉庫","事業所"
)
_ADDR_SUFFIX_PAT = "|".join(re.escape(s) for s in _ADDR_SUFFIXES)
_PREF_PAT = "|".join(re.escape(p) for p in PREFECTURES)

# 人名直後の役職・敬称を捕捉するパターン（マスク後に残す）
_TITLE_AFTER_PAT = re.compile(
    r"^(" + "|".join(re.escape(t) for t in TITLES) + r")"
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
            if any(s <= start < e or s < end <= e for s, e in masked_ranges):
                return
            replacements.append((start, end, rep))
            masked_ranges.append((start, end))

        # ── 1. 日付（最優先）──
        for start, end, raw in find_dates(text):
            token_id = self._store.get_or_create("日付", raw)
            _register(start, end, f"【日付{token_id}】")

        # ── 2. 人物・組織名 ──
        for start, end, original, category in find_persons_orgs(text):
            # 直後に役職・敬称があれば取り込まず残す
            after = text[end:]
            title_m = _TITLE_AFTER_PAT.match(after)
            title_suffix = title_m.group(1) if title_m else ""

            token_id = self._store.get_or_create(category, original)
            _register(start, end, f"【{category}{token_id}】")

        # ── 3. 正規表現ルール ──
        for cat, pattern, transform in RULES:
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if any(s <= start < e or s < end <= e for s, e in masked_ranges):
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

    def save_mapping(self, path: Path):
        fwd = self._store.get_fwd()
        restore_map: dict[str, str] = {
            f"【{cat}{tid}】": orig
            for cat, pairs in fwd.items()
            for orig, tid in pairs.items()
        }
        path.write_text(
            json.dumps({"mapping": fwd, "restore": restore_map},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_mapping(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self._store.load_fwd(data.get("mapping", {}))

    def restore(self, text: str, mapping_path: Path) -> str:
        """マスク済みテキストを原文に復元（年齢変換は非可逆）"""
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
        restore_map: dict[str, str] = data.get("restore", {})

        # 住所トークンの特殊復元（prefix・suffix の二重化防止）
        addr_pat = re.compile(
            r"(〒|(?:" + _PREF_PAT + r"))?"
            r"(【住所[A-Z]+】)"
            r"(" + _ADDR_SUFFIX_PAT + r")?"
        )
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

        result = addr_pat.sub(_restore_addr, text)

        # 残りの全トークン復元
        result = re.sub(
            r"【[^【】]+】",
            lambda m: restore_map.get(m.group(0), m.group(0)),
            result,
        )
        return result
