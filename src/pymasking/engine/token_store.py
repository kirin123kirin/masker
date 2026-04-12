"""
トークン発番・一意性管理

2層構造:
  第1層: 元テキスト → MD5ハッシュ（決定論的・セッション不変）
  第2層: MD5ハッシュ → ラベル（蓄積テーブルへの初登場順）

同じ元テキストは常に同じハッシュになるため、
事前にマッピングをロードしておけばセッションをまたいで
同じラベルが割り当てられる。
"""

import string
import hashlib


class TokenStore:
    def __init__(self):
        self._text_to_hash: dict[str, dict[str, str]] = {}   # cat → {text → hash}
        self._hash_to_label: dict[str, dict[str, str]] = {}  # cat → {hash → label}

    def reset(self):
        self._text_to_hash.clear()
        self._hash_to_label.clear()

    def get_or_create(self, category: str, original: str) -> str:
        # 第1層: テキスト → MD5ハッシュ（決定論的）
        t2h = self._text_to_hash.setdefault(category, {})
        if original not in t2h:
            t2h[original] = hashlib.md5(original.encode()).hexdigest()[:8].upper()
        h = t2h[original]

        # 第2層: ハッシュ → ラベル（蓄積テーブルへの初登場順）
        h2l = self._hash_to_label.setdefault(category, {})
        if h not in h2l:
            h2l[h] = self._index_to_label(len(h2l))
        return h2l[h]

    def rows(self):
        """TSV書き出し用イテレータ: (category, original, hash, label)"""
        for cat, t2h in self._text_to_hash.items():
            h2l = self._hash_to_label.get(cat, {})
            for orig, h in t2h.items():
                yield cat, orig, h, h2l.get(h, "")

    def load_rows(self, rows):
        """TSV読み込み: [(category, original, hash, label), ...]"""
        for cat, orig, h, label in rows:
            self._text_to_hash.setdefault(cat, {})[orig] = h
            self._hash_to_label.setdefault(cat, {})[h] = label

    @staticmethod
    def _index_to_label(n: int) -> str:
        letters = string.ascii_uppercase
        result = ""
        n += 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = letters[remainder] + result
        return result
