"""
トークン発番・一意性管理
"""

import string


class TokenStore:
    def __init__(self):
        self._fwd: dict[str, dict[str, str]] = {}
        self._counters: dict[str, int] = {}

    def reset(self):
        self._fwd.clear()
        self._counters.clear()

    def get_or_create(self, category: str, original: str) -> str:
        cat_map = self._fwd.setdefault(category, {})
        if original in cat_map:
            return cat_map[original]
        idx = self._counters.get(category, 0)
        token_id = self._index_to_label(idx)
        self._counters[category] = idx + 1
        cat_map[original] = token_id
        return token_id

    def get_fwd(self) -> dict[str, dict[str, str]]:
        return self._fwd

    def load_fwd(self, fwd: dict[str, dict[str, str]]):
        self._fwd = fwd
        self._counters = {cat: len(pairs) for cat, pairs in fwd.items()}

    @staticmethod
    def _index_to_label(n: int) -> str:
        letters = string.ascii_uppercase
        result = ""
        n += 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = letters[remainder] + result
        return result
