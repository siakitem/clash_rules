import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cache import TtlCache  # noqa: E402


class TtlCacheTest(unittest.TestCase):
    def test_disabled_cache_never_returns_values(self) -> None:
        cache = TtlCache(0)
        cache.put("key", "value")
        self.assertIsNone(cache.get("key"))

    def test_value_is_returned_before_expiry(self) -> None:
        cache = TtlCache(1)
        cache.put("key", "value")
        self.assertEqual("value", cache.get("key"))


if __name__ == "__main__":
    unittest.main()
