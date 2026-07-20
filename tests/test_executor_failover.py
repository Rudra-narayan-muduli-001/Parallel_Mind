import pytest

from core.executor import AgentExecutor
from core.models import AgentTask


class MockProvider:
    def __init__(self, name: str, healthy=True, has_keys=True, call_succeeds=True):
        self.name = name
        self._healthy = healthy
        self._has_keys = has_keys
        self._call_succeeds = call_succeeds

        class MockBreaker:
            def allow_request(self):
                return healthy

            def record_success(self):
                pass

            def record_failure(self):
                pass

        class MockKeyPool:
            async def get_key(self):
                if not has_keys:
                    raise Exception("No keys")
                return "test-key"

            def report_success(self, key):
                pass

            def report_failure(self, key):
                pass

        self.breaker = MockBreaker()
        self.key_pool = MockKeyPool()


class MockAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        if provider._call_succeeds:
            return {"text": f"result from {provider.name}/{model}", "tokens": 10}
        raise Exception(f"{provider.name}/{model} failed")


@pytest.mark.asyncio
async def test_first_candidate_succeeds():
    providers = {
        "p1": MockProvider("p1", call_succeeds=True),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="test")
    candidates = [("p1", "model1")]
    result = await executor.run(MockAgent(), task, candidates)
    assert result.success is True
    assert result.provider_used == "p1"


@pytest.mark.asyncio
async def test_failover_to_second_candidate():
    providers = {
        "p1": MockProvider("p1", call_succeeds=False),
        "p2": MockProvider("p2", call_succeeds=True),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t2", prompt="test")
    candidates = [("p1", "m1"), ("p2", "m2")]
    result = await executor.run(MockAgent(), task, candidates)
    assert result.success is True
    assert result.provider_used == "p2"


@pytest.mark.asyncio
async def test_all_candidates_fail():
    providers = {
        "p1": MockProvider("p1", call_succeeds=False),
        "p2": MockProvider("p2", call_succeeds=False),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t3", prompt="test")
    candidates = [("p1", "m1"), ("p2", "m2")]
    result = await executor.run(MockAgent(), task, candidates)
    assert result.success is False


@pytest.mark.asyncio
async def test_skip_unhealthy_provider():
    providers = {
        "p1": MockProvider("p1", healthy=False),
        "p2": MockProvider("p2", call_succeeds=True),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t4", prompt="test")
    candidates = [("p1", "m1"), ("p2", "m2")]
    result = await executor.run(MockAgent(), task, candidates)
    assert result.success is True
    assert result.provider_used == "p2"


@pytest.mark.asyncio
async def test_empty_candidates():
    executor = AgentExecutor({})
    task = AgentTask(id="t5", prompt="test")
    result = await executor.run(MockAgent(), task, [])
    assert result.success is False
    assert "No candidates" in (result.error or "")
