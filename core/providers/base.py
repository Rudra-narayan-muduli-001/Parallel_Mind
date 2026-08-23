from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from core.providers.circuit_breaker import CircuitBreaker
from core.providers.key_pool import APIKeyPool


@dataclass
class LLMResponse:
    text: str
    raw: dict
    tokens_used: Optional[int] = None


@dataclass
class ModelInfo:
    id: str
    display_name: str = ""


class BaseProvider(ABC):
    def __init__(self, name: str, api_keys: list[str], base_url: str, default_model: str = ""):
        self.name = name
        self.base_url = base_url
        self.default_model = default_model
        self.key_pool = APIKeyPool(api_keys)
        self.breaker = CircuitBreaker()
        # Per-provider rate-limit cooldown (set when a 429 surfaces).
        self.rate_limited_until: float = 0.0

    @abstractmethod
    async def call(self, model: str, prompt: str, api_key: str, **gen_params) -> LLMResponse: ...

    async def list_models(self) -> list[ModelInfo]:
        """Fetch the live model list from the provider's API.
        Returns an empty list on failure — callers should fall back to a static catalog."""
        return []

    def is_healthy(self) -> bool:
        if __import__("time").time() < self.rate_limited_until:
            return False
        return self.breaker.allow_request() and self.key_pool.has_healthy_key()

    def is_enabled(self) -> bool:
        return len(self.key_pool.keys) > 0

    def mark_rate_limited(self, cooldown_sec: float = 30.0):
        """Mark provider as rate-limited for `cooldown_sec` seconds.
        During cooldown the executor skips this provider — its candidates
        are tried only after the cooldown expires."""
        import time
        self.rate_limited_until = max(self.rate_limited_until, time.time() + cooldown_sec)
        # Also trip the circuit breaker so the executor skips cleanly.
        self.breaker.record_failure()
