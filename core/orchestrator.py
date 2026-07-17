import asyncio
from core.models import AgentTask, AgentResult


class Orchestrator:
    def __init__(self, executor, router, max_concurrency: int = 5):
        self.executor = executor
        self.router = router
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_one(self, agent, task: AgentTask, gen_params: dict) -> AgentResult:
        async with self.semaphore:
            candidates = await self.router.decide(task)
            return await self.executor.run(agent, task, candidates, gen_params)

    async def run_batch(self, agent, tasks: list[AgentTask], gen_params: dict = None) -> list[AgentResult]:
        gen_params = gen_params or {}
        results = await asyncio.gather(
            *[self._run_one(agent, t, gen_params) for t in tasks],
            return_exceptions=True,
        )
        final: list[AgentResult] = []
        for task, r in zip(tasks, results):
            if isinstance(r, Exception):
                final.append(AgentResult(task_id=task.id, success=False, error=str(r), latency_sec=0.0))
            else:
                final.append(r)
        return final