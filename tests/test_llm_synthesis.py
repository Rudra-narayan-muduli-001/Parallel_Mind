import pytest

from core.aggregation.strategies import LLMSynthesisAggregator
from core.models import AgentResult, AgentTask
from core.providers.base import LLMResponse


class FakeProvider:
    def __init__(self, name, text="synthesized answer", should_fail=False, fail_msg="429 Too Many Requests"):
        self.name = name
        self.default_model = f"{name}-model"
        self._text = text
        self._should_fail = should_fail
        self._fail_msg = fail_msg
        self.rate_limited_until = 0.0

        class FakeKeyPool:
            async def get_key(self):
                return "k"

        self.key_pool = FakeKeyPool()
        self.call_count = 0

    def mark_rate_limited(self, cooldown_sec=30):
        import time

        self.rate_limited_until = time.time() + cooldown_sec

    async def call(self, model, prompt, api_key, **kwargs):
        self.call_count += 1
        if self._should_fail:
            raise Exception(self._fail_msg)
        return LLMResponse(text=self._text, raw={}, tokens_used=10)


@pytest.mark.asyncio
async def test_truncate_short_text_unchanged():
    assert LLMSynthesisAggregator._truncate("hello", 100) == "hello"


@pytest.mark.asyncio
async def test_truncate_long_text_cuts_at_word_boundary():
    text = "word " * 100
    truncated = LLMSynthesisAggregator._truncate(text, 50)
    assert len(truncated) <= 51  # 50 + ellipsis
    assert truncated.endswith("…")
    assert "word" in truncated


@pytest.mark.asyncio
async def test_llm_synthesis_success():
    providers = {"p1": FakeProvider("p1", text="final synthesis")}
    agg = LLMSynthesisAggregator(providers, default_model="p1-model")
    task = AgentTask(id="t", prompt="original question")
    results = [
        AgentResult(task_id="t", success=True, output="finding 1", provider_used="p1"),
        AgentResult(task_id="t", success=True, output="finding 2", provider_used="p1"),
    ]
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output == "final synthesis"
    assert result.tokens_used is not None


@pytest.mark.asyncio
async def test_llm_synthesis_no_successful_results():
    providers = {"p1": FakeProvider("p1")}
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    results = [AgentResult(task_id="t", success=False, error="fail")]
    result = await agg.aggregate(task, results)
    assert result.success is False
    assert "No successful" in result.error


@pytest.mark.asyncio
async def test_llm_synthesis_fallback_on_all_providers_rate_limited():
    providers = {
        "p1": FakeProvider("p1", should_fail=True, fail_msg="429 Too Many Requests"),
        "p2": FakeProvider("p2", should_fail=True, fail_msg="429"),
    }
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    results = [AgentResult(task_id="t", success=True, output="finding")]
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert "Synthesis skipped" in result.output
    assert "finding" in result.output


@pytest.mark.asyncio
async def test_llm_synthesis_failover_to_second_provider():
    providers = {
        "p1": FakeProvider("p1", should_fail=True, fail_msg="500 error"),
        "p2": FakeProvider("p2", text="from p2"),
    }
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    results = [AgentResult(task_id="t", success=True, output="finding")]
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output == "from p2"
    assert providers["p1"].call_count == 1
    assert providers["p2"].call_count == 1


@pytest.mark.asyncio
async def test_llm_synthesis_429_marks_provider_rate_limited():
    p1 = FakeProvider("p1", should_fail=True, fail_msg="429 Too Many Requests")
    providers = {"p1": p1, "p2": FakeProvider("p2", text="ok")}
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    results = [AgentResult(task_id="t", success=True, output="finding")]
    await agg.aggregate(task, results)
    assert p1.rate_limited_until > 0


@pytest.mark.asyncio
async def test_llm_synthesis_skips_already_rate_limited_provider():
    import time

    p1 = FakeProvider("p1", text="should not be called")
    p1.rate_limited_until = time.time() + 9999
    p2 = FakeProvider("p2", text="used")
    providers = {"p1": p1, "p2": p2}
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    results = [AgentResult(task_id="t", success=True, output="finding")]
    result = await agg.aggregate(task, results)
    assert result.output == "used"
    assert p1.call_count == 0


@pytest.mark.asyncio
async def test_llm_synthesis_bounds_large_findings():
    providers = {"p1": FakeProvider("p1", text="synthesized")}
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    large = "x" * 10000
    results = [AgentResult(task_id="t", success=True, output=large, provider_used="p1")]
    result = await agg.aggregate(task, results)
    assert result.success is True
    # Should have truncated input and still called provider
    assert providers["p1"].call_count == 1


@pytest.mark.asyncio
async def test_llm_synthesis_custom_template():
    providers = {"p1": FakeProvider("p1", text="out")}
    agg = LLMSynthesisAggregator(providers, synthesis_prompt_template="Q: {task_prompt}\nData: {findings}")
    task = AgentTask(id="t", prompt="my question")
    results = [AgentResult(task_id="t", success=True, output="fact")]
    result = await agg.aggregate(task, results)
    assert result.success is True


@pytest.mark.asyncio
async def test_llm_synthesis_truncates_total_budget():
    providers = {"p1": FakeProvider("p1", text="done")}
    agg = LLMSynthesisAggregator(providers)
    task = AgentTask(id="t", prompt="q")
    # Many large findings should trigger total budget trimming
    results = [AgentResult(task_id="t", success=True, output="word " * 2000, provider_used="p1") for _ in range(5)]
    result = await agg.aggregate(task, results)
    assert result.success is True
