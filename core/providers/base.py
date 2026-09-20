import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    text: str
    raw: dict
    tokens_used: Optional[int] = None


@dataclass
class ModelInfo:
    id: str
    display_name: str = ""


class NoAvailableKeyError(Exception):
    pass


class BaseProvider(ABC):
    def __init__(self, name: str, api_keys: list[str], base_url: str, default_model: str = "",
                 fail_threshold: int = 5, reset_timeout: float = 60.0):
        self.name = name
        self.base_url = base_url
        self.default_model = default_model

        # Key pool (inlined from key_pool.py)
        self._keys = api_keys
        self._key_index = 0
        self._key_lock = asyncio.Lock()
        self._key_status = {k: {"healthy": True, "cooldown_until": 0.0, "failures": 0} for k in api_keys}

        # Circuit breaker (inlined from circuit_breaker.py)
        self._fail_threshold = fail_threshold
        self._reset_timeout = reset_timeout
        self._failures = 0
        self._breaker_state = "CLOSED"
        self._opened_at = None

        self.rate_limited_until: float = 0.0

    # Key pool methods
    async def _get_key(self) -> str:
        if not self._keys:
            raise NoAvailableKeyError("No API keys configured for this provider")
        async with self._key_lock:
            n = len(self._keys)
            now = time.time()
            for _ in range(n):
                key = self._keys[self._key_index]
                self._key_index = (self._key_index + 1) % n
                s = self._key_status[key]
                if now > s["cooldown_until"]:
                    if not s["healthy"]:
                        s["healthy"] = True
                        s["failures"] = 0
                    return key
            raise NoAvailableKeyError("All API keys exhausted/unhealthy for this provider")

    def _report_key_failure(self, key: str, cooldown_sec: float = 30.0, fail_threshold: int = 20):
        s = self._key_status.get(key)
        if s is None:
            return
        s["failures"] += 1
        s["cooldown_until"] = time.time() + cooldown_sec
        if s["failures"] >= fail_threshold:
            s["healthy"] = False

    def _report_key_success(self, key: str):
        s = self._key_status.get(key)
        if s is None:
            return
        s["failures"] = 0
        s["healthy"] = True
        s["cooldown_until"] = 0.0

    def _has_healthy_key(self) -> bool:
        now = time.time()
        return any(s["healthy"] and now > s["cooldown_until"] for s in self._key_status.values())

    # Circuit breaker methods
    def _breaker_allow_request(self) -> bool:
        if self._breaker_state == "OPEN":
            if self._opened_at and (time.time() - self._opened_at) > self._reset_timeout:
                self._breaker_state = "HALF_OPEN"
                return True
            return False
        return True

    def _breaker_record_success(self):
        self._failures = 0
        self._breaker_state = "CLOSED"
        self._opened_at = None

    def _breaker_record_failure(self):
        self._failures += 1
        if self._breaker_state == "HALF_OPEN":
            self._breaker_state = "OPEN"
            self._opened_at = time.time()
            return
        if self._failures >= self._fail_threshold:
            self._breaker_state = "OPEN"
            self._opened_at = time.time()

    @abstractmethod
    async def call(self, model: str, prompt: str, api_key: str, **gen_params) -> LLMResponse: ...

    async def list_models(self) -> list[ModelInfo]:
        return []

    def is_healthy(self) -> bool:
        if time.time() < self.rate_limited_until:
            return False
        return self._breaker_allow_request() and self._has_healthy_key()

    def is_enabled(self) -> bool:
        return len(self._keys) > 0

    def mark_rate_limited(self, cooldown_sec: float = 30.0):
        self.rate_limited_until = max(self.rate_limited_until, time.time() + cooldown_sec)
        self._breaker_record_failure()

    # Properties for backward compatibility with executor.py
    @property
    def key_pool(self):
        class KeyPoolProxy:
            def __init__(self, provider):
                self._provider = provider

            async def get_key(self):
                return await self._provider._get_key()

            def report_failure(self, key, cooldown_sec=30.0, fail_threshold=20):
                self._provider._report_key_failure(key, cooldown_sec, fail_threshold)

            def report_success(self, key):
                self._provider._report_key_success(key)

            @property
            def keys(self):
                return self._provider._keys
        return KeyPoolProxy(self)

    @property
    def breaker(self):
        class BreakerProxy:
            def __init__(self, provider):
                self._provider = provider

            def allow_request(self):
                return self._provider._breaker_allow_request()

            def record_success(self):
                self._provider._breaker_record_success()

            def record_failure(self):
                self._provider._breaker_record_failure()
        return BreakerProxy(self)