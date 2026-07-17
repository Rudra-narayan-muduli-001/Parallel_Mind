import asyncio
import time


class NoAvailableKeyError(Exception):
    pass


class APIKeyPool:
    """Round-robins across all configured API keys for a single provider.
    Tracks per-key health (failure count + cooldown) so failing keys are
    automatically skipped without manual intervention."""

    def __init__(self, keys: list[str]):
        self.keys = keys
        self._index = 0
        self._lock = asyncio.Lock()
        self.status = {
            k: {"healthy": True, "cooldown_until": 0.0, "failures": 0}
            for k in keys
        }

    async def get_key(self) -> str:
        if not self.keys:
            raise NoAvailableKeyError("No API keys configured for this provider")
        async with self._lock:
            n = len(self.keys)
            for _ in range(n):
                key = self.keys[self._index]
                self._index = (self._index + 1) % n
                s = self.status[key]
                if s["healthy"] and time.time() > s["cooldown_until"]:
                    return key
            raise NoAvailableKeyError("All API keys exhausted/unhealthy for this provider")

    def report_failure(self, key: str, cooldown_sec: float = 30.0, fail_threshold: int = 5):
        s = self.status.get(key)
        if s is None:
            return
        s["failures"] += 1
        s["cooldown_until"] = time.time() + cooldown_sec
        if s["failures"] >= fail_threshold:
            s["healthy"] = False

    def report_success(self, key: str):
        s = self.status.get(key)
        if s is None:
            return
        s["failures"] = 0
        s["healthy"] = True
        s["cooldown_until"] = 0.0

    def has_healthy_key(self) -> bool:
        now = time.time()
        return any(s["healthy"] and now > s["cooldown_until"] for s in self.status.values())

    def reset(self):
        for k in self.status:
            self.status[k] = {"healthy": True, "cooldown_until": 0.0, "failures": 0}