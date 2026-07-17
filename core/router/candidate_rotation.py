import asyncio


class RotatingCandidatePool:
    def __init__(self, candidates: list[tuple[str, str]]):
        self._candidates = candidates
        self._counter = 0
        self._lock = asyncio.Lock()

    async def next_ordering(self) -> list[tuple[str, str]]:
        if not self._candidates:
            return []
        async with self._lock:
            start = self._counter % len(self._candidates)
            self._counter += 1
        return self._candidates[start:] + self._candidates[:start]
