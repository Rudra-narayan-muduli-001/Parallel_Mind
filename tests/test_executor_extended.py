import asyncio
import time

import pytest

from core.executor import AgentExecutor
from core.models import AgentTask


class MockBreaker:
    def __init__(self, healthy=True):
        self._healthy = healthy
        self.success_count = 0
        self.failure_count = 0

    def allow_request(self):
        return self._healthy

    def record_success(self):
        self.success_count += 1

    def record_failure(self):
        self.failure_count += 1


class MockKeyPool:
    def __init__(self, keys=None, fail_get=False):
        self.keys = keys or ["k1"]
        self._fail = fail_get
        self.success_reported = []
        self.failure_reported = []

    async def get_key(self):
        if self._fail:
            raise Exception("no healthy key")
        return self.keys[0]

    def report_success(self, key):
        self.success_reported.append(key)

    def report_failure(self, key):
        self.failure_reported.append(key)


class MockProvider:
    def __init__(self, name, healthy=True, has_keys=True, breaker=None, key_pool=None):
        self.name = name
        self.breaker = breaker or MockBreaker(healthy=healthy)
        self.key_pool = key_pool or MockKeyPool(keys=["k1"] if has_keys else [])
        self.rate_limited_until = 0.0
        self.mark_called = False

    def mark_rate_limited(self, cooldown_sec=30):
        self.mark_called = True
        self.rate_limited_until = max(self.rate_limited_until, time.time() + cooldown_sec)
        self.breaker.record_failure()


class SuccessAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        return {"text": "ok"}


class SlowAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        await asyncio.sleep(10)
        return {"text": "too slow"}


class FailAgent:
    async def execute(self, task, provider, model, api_key, gen_params):
        raise RuntimeError("fail")


@pytest.mark.asyncio
async def test_executor_timeout_triggers_failover():
    providers = {
        "p1": MockProvider("p1"),
        "p2": MockProvider("p2"),
    }
    executor = AgentExecutor(providers, default_timeout=60)
    task = AgentTask(id="t1", prompt="hi")
    # p1 is slow and should timeout, p2 succeeds
    class HalfSlowAgent:
        async def execute(self, task, provider, model, api_key, gen_params):
            if provider.name == "p1":
                await asyncio.sleep(10)
                return {"text": "slow"}
            return {"text": "fast from p2"}

    result = await executor.run(HalfSlowAgent(), task, [("p1", "m1"), ("p2", "m2")], {"timeout_sec": 0.05})
    assert result.success is True
    assert result.provider_used == "p2"


@pytest.mark.asyncio
async def test_executor_all_timeout_returns_failure():
    providers = {"p1": MockProvider("p1")}
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(SlowAgent(), task, [("p1", "m1")], {"timeout_sec": 0.05})
    assert result.success is False


@pytest.mark.asyncio
async def test_executor_unknown_provider_skipped():
    providers = {"p2": MockProvider("p2")}
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(SuccessAgent(), task, [("unknown", "m1"), ("p2", "m2")])
    assert result.success is True
    assert result.provider_used == "p2"


@pytest.mark.asyncio
async def test_executor_no_healthy_key_skips_provider():
    pool_fail = MockKeyPool(fail_get=True)
    providers = {
        "p1": MockProvider("p1", key_pool=pool_fail),
        "p2": MockProvider("p2"),
    }
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(SuccessAgent(), task, [("p1", "m1"), ("p2", "m2")])
    assert result.success is True
    assert result.provider_used == "p2"


@pytest.mark.asyncio
async def test_executor_records_success_on_breaker_and_keypool():
    breaker = MockBreaker()
    pool = MockKeyPool()
    providers = {"p1": MockProvider("p1", breaker=breaker, key_pool=pool)}
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(SuccessAgent(), task, [("p1", "m1")])
    assert result.success is True
    assert breaker.success_count == 1
    assert "k1" in pool.success_reported


@pytest.mark.asyncio
async def test_executor_records_failure_on_exception():
    breaker = MockBreaker()
    pool = MockKeyPool()
    providers = {"p1": MockProvider("p1", breaker=breaker, key_pool=pool)}
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(FailAgent(), task, [("p1", "m1")])
    assert result.success is False
    assert breaker.failure_count == 1
    assert "k1" in pool.failure_reported


@pytest.mark.asyncio
async def test_executor_rate_limit_does_not_penalize_key():
    breaker = MockBreaker()
    pool = MockKeyPool()
    providers = {"p1": MockProvider("p1", breaker=breaker, key_pool=pool)}

    class RateLimitAgent:
        async def execute(self, task, provider, model, api_key, gen_params):
            raise Exception("429 Too Many Requests")

    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(RateLimitAgent(), task, [("p1", "m1")])
    assert result.success is False
    # key should NOT be penalized on 429
    assert pool.failure_reported == []
    assert providers["p1"].mark_called is True


@pytest.mark.asyncio
async def test_executor_is_rate_limit_error_detection():
    assert AgentExecutor._is_rate_limit_error(Exception("429 Too Many Requests")) is True
    assert AgentExecutor._is_rate_limit_error(Exception("rate limit exceeded")) is True
    assert AgentExecutor._is_rate_limit_error(Exception("Rate Limit")) is True
    assert AgentExecutor._is_rate_limit_error(Exception("some other error")) is False

    # httpx variant
    import httpx

    req = httpx.Request("GET", "http://test")
    resp = httpx.Response(429, request=req)
    err = httpx.HTTPStatusError("429", request=req, response=resp)
    assert AgentExecutor._is_rate_limit_error(err) is True
    resp2 = httpx.Response(500, request=req)
    err2 = httpx.HTTPStatusError("500", request=req, response=resp2)
    assert AgentExecutor._is_rate_limit_error(err2) is False


@pytest.mark.asyncio
async def test_executor_latency_recorded():
    providers = {"p1": MockProvider("p1")}
    executor = AgentExecutor(providers)
    task = AgentTask(id="t1", prompt="hi")
    result = await executor.run(SuccessAgent(), task, [("p1", "m1")])
    assert result.latency_sec >= 0
    assert result.tokens_used is None  # executor doesn't set tokens, agent does via output


@pytest.mark.asyncio
async def test_executor_custom_rate_limit_cooldown():
    class Always429Agent:
        async def execute(self, task, provider, model, api_key, gen_params):
            raise Exception("429")

    p1 = MockProvider("p1")
    executor = AgentExecutor({"p1": p1})
    task = AgentTask(id="t1", prompt="hi")
    await executor.run(Always429Agent(), task, [("p1", "m1")], {"rate_limit_cooldown_sec": 99})
    assert p1.rate_limited_until > time.time() + 90
