import asyncio
import logging
import time

from core.executor import AgentExecutor
from core.models import AgentResult, AgentTask

logger = logging.getLogger("parallelmind.pipeline")


async def run_agent_batch(executor: AgentExecutor, policy, agent, tasks: list[AgentTask],
                          gen_params: dict, max_concurrency: int = 5) -> list[AgentResult]:
    semaphore = asyncio.Semaphore(max_concurrency)
    gen_params = gen_params or {}

    async def _run_one(task: AgentTask) -> AgentResult:
        async with semaphore:
            candidates = await policy.decide(task)
            return await executor.run(agent, task, candidates, gen_params)

    results = await asyncio.gather(
        *[_run_one(t) for t in tasks],
        return_exceptions=True,
    )
    final: list[AgentResult] = []
    for task, r in zip(tasks, results):
        if isinstance(r, Exception):
            final.append(AgentResult(task_id=task.id, success=False, error=str(r), latency_sec=0.0))
        else:
            assert isinstance(r, AgentResult)
            final.append(r)
    return final


def build_orchestrator(executor: AgentExecutor, policy, max_concurrency: int = 5):
    class _Orchestrator:
        def __init__(self, executor, policy, max_concurrency):
            self.executor = executor
            self.policy = policy
            self.max_concurrency = max_concurrency

        async def run_batch(self, agent, tasks: list[AgentTask], gen_params: dict | None = None) -> list[AgentResult]:
            return await run_agent_batch(self.executor, self.policy, agent, tasks, gen_params or {}, self.max_concurrency)

    return _Orchestrator(executor, policy, max_concurrency)