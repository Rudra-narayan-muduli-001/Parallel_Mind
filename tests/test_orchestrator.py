import asyncio

import pytest

from core.executor import AgentExecutor
from core.models import AgentResult, AgentTask
from core.orchestrator import Orchestrator


class DummyProvider:
    def __init__(self, name="p1"):
        self.name = name
        self.rate_limited_until = 0.0

        class Breaker:
            def allow_request(self):
                return True

            def record_success(self):
                pass

            def record_failure(self):
                pass

        class KeyPool:
            async def get_key(self):
                return "k"

            def report_success(self, k):
                pass

            def report_failure(self, k):
                pass

        self.breaker = Breaker()
        self.key_pool = KeyPool()

    def mark_rate_limited(self, cooldown_sec=30):
        import time

        self.rate_limited_until = time.time() + cooldown_sec


class SuccessAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        return {"text": f"ok-{task.id}", "tokens": 5}


class FailAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        raise RuntimeError(f"fail-{task.id}")


class ConditionalAgent:
    """Fails for specific task ids."""

    def __init__(self, fail_ids: set[str]):
        self.fail_ids = fail_ids

    async def execute(self, task, provider, model, api_key, gen_params):
        if task.id in self.fail_ids:
            raise ValueError("intentional failure")
        return {"text": f"ok-{task.id}"}


@pytest.mark.asyncio
async def test_orchestrator_run_batch_all_success():
    providers = {"p1": DummyProvider("p1")}
    executor = AgentExecutor(providers)
    router = DummyRouter([("p1", "m1")])
    orch = Orchestrator(executor, router, max_concurrency=2)
    tasks = [AgentTask(id=f"t{i}", prompt="hi") for i in range(3)]
    results = await orch.run_batch(SuccessAgent(), tasks)
    assert len(results) == 3
    assert all(r.success for r in results)
    assert {r.task_id for r in results} == {"t0", "t1", "t2"}


@pytest.mark.asyncio
async def test_orchestrator_run_batch_mixed_success_failure():
    providers = {"p1": DummyProvider("p1")}
    executor = AgentExecutor(providers)
    router = DummyRouter([("p1", "m1")])
    orch = Orchestrator(executor, router, max_concurrency=2)
    tasks = [AgentTask(id=f"t{i}", prompt="hi") for i in range(4)]
    agent = ConditionalAgent(fail_ids={"t1", "t3"})
    results = await orch.run_batch(agent, tasks)
    assert len(results) == 4
    success_ids = {r.task_id for r in results if r.success}
    fail_ids = {r.task_id for r in results if not r.success}
    assert success_ids == {"t0", "t2"}
    assert fail_ids == {"t1", "t3"}


@pytest.mark.asyncio
async def test_orchestrator_handles_router_exception():
    executor = AgentExecutor({})
    router = FailingRouter()
    orch = Orchestrator(executor, router, max_concurrency=2)
    tasks = [AgentTask(id="t1", prompt="hi"), AgentTask(id="t2", prompt="hi")]
    results = await orch.run_batch(SuccessAgent(), tasks)
    assert len(results) == 2
    assert all(not r.success for r in results)
    assert all("router boom" in (r.error or "") for r in results)


@pytest.mark.asyncio
async def test_orchestrator_respects_max_concurrency():
    tracker = ConcurrencyTracker()
    providers = {"p1": DummyProvider("p1")}
    executor = AgentExecutor(providers)
    router = DummyRouter([("p1", "m1")])
    orch = Orchestrator(executor, router, max_concurrency=2)
    tasks = [AgentTask(id=f"t{i}", prompt="hi") for i in range(6)]
    results = await orch.run_batch(tracker, tasks)
    assert len(results) == 6
    assert all(r.success for r in results)
    assert tracker.max_seen <= 2


@pytest.mark.asyncio
async def test_orchestrator_empty_task_list():
    providers = {"p1": DummyProvider("p1")}
    executor = AgentExecutor(providers)
    router = DummyRouter([("p1", "m1")])
    orch = Orchestrator(executor, router)
    results = await orch.run_batch(SuccessAgent(), [])
    assert results == []


@pytest.mark.asyncio
async def test_orchestrator_passes_gen_params_through():
    captured = {}

    class CapturingAgent:
        async def execute(self, task, provider, model, api_key, gen_params):
            captured.update(gen_params)
            return {"text": "ok"}

    providers = {"p1": DummyProvider("p1")}
    executor = AgentExecutor(providers)
    router = DummyRouter([("p1", "m1")])
    orch = Orchestrator(executor, router)
    task = AgentTask(id="t1", prompt="hi")
    await orch.run_batch(CapturingAgent(), [task], gen_params={"temperature": 0.9, "max_tokens": 123})
    assert captured["temperature"] == 0.9
    assert captured["max_tokens"] == 123


@pytest.mark.asyncio
async def test_orchestrator_run_one_uses_router_candidates():
    called_with = {}

    class InspectExecutor:
        async def run(self, agent, task, candidates, gen_params=None):
            called_with["candidates"] = candidates
            called_with["gen_params"] = gen_params
            return AgentResult(task_id=task.id, success=True, output="ok")

    router = DummyRouter([("p1", "m1"), ("p2", "m2")])
    orch = Orchestrator(InspectExecutor(), router)  # type: ignore[arg-type]
    task = AgentTask(id="t1", prompt="hi")
    result = await orch._run_one(SuccessAgent(), task, {"timeout_sec": 10})
    assert result.success is True
    assert called_with["candidates"] == [("p1", "m1"), ("p2", "m2")]
    assert called_with["gen_params"]["timeout_sec"] == 10


# ---- helpers ----


class DummyRouter:
    def __init__(self, candidates):
        self._candidates = candidates

    async def decide(self, task):
        return self._candidates


class FailingRouter:
    async def decide(self, task):
        raise RuntimeError("router boom")


class ConcurrencyTracker:
    def __init__(self):
        self.current = 0
        self.max_seen = 0
        self._lock = asyncio.Lock()

    async def execute(self, task, provider, model, api_key, gen_params):
        async with self._lock:
            self.current += 1
            self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.02)
        async with self._lock:
            self.current -= 1
        return {"text": "ok"}
