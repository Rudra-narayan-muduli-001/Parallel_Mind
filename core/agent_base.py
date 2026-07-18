from abc import ABC, abstractmethod
from core.models import AgentTask


class BaseAgent(ABC):
    @abstractmethod
    async def execute(self, task: AgentTask, provider, model: str, api_key: str, gen_params: dict) -> dict: ...
