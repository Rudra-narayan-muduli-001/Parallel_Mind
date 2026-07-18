import asyncio
from typing import Any


class SharedContext:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        async with self._lock:
            return self._store.get(key)

    async def set(self, key: str, value: Any):
        async with self._lock:
            self._store[key] = value

    async def append(self, key: str, value: Any):
        async with self._lock:
            self._store.setdefault(key, [])
            self._store[key].append(value)

    async def snapshot(self) -> dict:
        async with self._lock:
            return dict(self._store)
