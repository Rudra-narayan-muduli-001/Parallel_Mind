from abc import ABC, abstractmethod
from core.models import AgentTask, AgentResult


class AggregationStrategy(ABC):
    @abstractmethod
    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult: ...
