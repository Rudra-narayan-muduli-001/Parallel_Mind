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

    @abstractmethod
    async def call(self, model: str, prompt: str, api_key: str, **gen_params) -> LLMResponse: ...

    async def list_models(self) -> list[ModelInfo]:
        """Fetch the live model list from the provider's API.
        Returns an empty list on failure — callers should fall back to a static catalog."""
        return []

    def is_healthy(self) -> bool:
        return self.breaker.allow_request() and self.key_pool.has_healthy_key()

    def is_enabled(self) -> bool:
        return len(self.key_pool.keys) > 0
