from abc import ABC, abstractmethod
from core.models import AgentTask


class BaseAgent(ABC):
    @abstractmethod
    async def execute(self, task: AgentTask, provider, model: str, api_key: str, gen_params: dict) -> dict:
        """Build prompt from task, call provider, parse+validate response, raise on failure.
        Do NOT catch/swallow exceptions here — the Executor handles failover."""
        ...