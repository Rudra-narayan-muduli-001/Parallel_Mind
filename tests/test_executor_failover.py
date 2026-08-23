import pytest

from core.executor import AgentExecutor
from core.models import AgentTask


class MockProvider:
    def __init__(self, name: str, healthy=True, has_keys=True, call_succeeds=True, rate_limit=False):
        self.name = name
        self._healthy = healthy
        self._has_keys = has_keys
        self._call_succeeds = call_succeeds
        self._rate_limit = rate_limit
        self.rate_limited_until = 0.0
        self._failure_count = 0

        class MockBreaker:
            def __init__(self, outer):
                self.outer = outer

            def allow_request(self):
                return healthy

            def record_success(self):
                pass

            def record_failure(self):
                self.outer._failure_count += 1

        class MockKeyPool:
            async def get_key(self):
                if not has_keys:
                    raise Exception("No keys")
                return "test-key"

            def report_success(self, key):
                pass

            def report_failure(self, key):
                pass

        self.breaker = MockBreaker(self)
        self.key_pool = MockKeyPool()

    def mark_rate_limited(self, cooldown_sec: float = 30.0):
        import time as _time
        self.rate_limited_until = max(self.rate_limited_until, _time.time() + cooldown_sec)


class MockAgent:
    def __init__(self, rate_limit_providers=None):
        self.rate_limit_providers = rate_limit_providers or set()

    async def execute(self, task, provider, model, api_key, gen_params):
        if provider.name in self.rate_limit_providers:
            raise Exception(f"{provider.name}/{model} failed: 429 Too Many Requests")
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


@pytest.mark.asyncio
async def test_429_triggers_cooldown_and_failover():
    providers = {
        "p1": MockProvider("p1", call_succeeds=True),
        "p2": MockProvider("p2", call_succeeds=True),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t6", prompt="test")
    candidates = [("p1", "m1"), ("p2", "m2")]
    # Only p1 rate-limits; p2 should succeed once the executor fails over.
    result = await executor.run(MockAgent(rate_limit_providers={"p1"}), task, candidates, {"rate_limit_cooldown_sec": 5})
    assert result.success is True
    assert result.provider_used == "p2"
    assert providers["p1"].rate_limited_until > 0, "p1 should have been marked rate-limited"


@pytest.mark.asyncio
async def test_provider_in_cooldown_is_skipped():
    providers = {
        "p1": MockProvider("p1", call_succeeds=True),
        "p2": MockProvider("p2", call_succeeds=True),
    }
    # Pre-set p1 as already in cooldown.
    import time as _time
    providers["p1"].rate_limited_until = _time.time() + 30
    executor = AgentExecutor(providers)
    task = AgentTask(id="t7", prompt="test")
    candidates = [("p1", "m1"), ("p2", "m2")]
    result = await executor.run(MockAgent(), task, candidates)
    assert result.success is True
    assert result.provider_used == "p2", "cooldown provider must be skipped"
