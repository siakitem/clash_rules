import threading
import time
from dataclasses import dataclass
from typing import Dict, Hashable, Optional


@dataclass(frozen=True)
class CacheEntry:
    expires_at: float
    value: str


class TtlCache:
    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = max(0, ttl_seconds)
        self._entries: Dict[Hashable, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Optional[str]:
        if self._ttl_seconds == 0:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    def put(self, key: Hashable, value: str) -> None:
        if self._ttl_seconds == 0:
            return
        with self._lock:
            self._entries[key] = CacheEntry(
                expires_at=time.monotonic() + self._ttl_seconds,
                value=value,
            )
