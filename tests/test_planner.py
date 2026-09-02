import pytest

from core.models import AgentTask
from pipelines.research.planner import ResearchPlanner


# -- _parse tests --


def test_parse_valid_lines():
    text = "low|What is X?\nmid|How does X work?\nhigh|Advanced implications of X?"
    tasks = ResearchPlanner._parse(text, "topic X")
    assert len(tasks) == 3
    assert tasks[0].prompt == "What is X?"
    assert tasks[0].metadata["complexity_tier"] == "low"
    assert tasks[1].metadata["complexity_tier"] == "mid"
    assert tasks[2].metadata["complexity_tier"] == "high"


def test_parse_ignores_lines_without_pipe():
    text = "low|Valid?\nThis line has no pipe\nmid|Also valid?"
    tasks = ResearchPlanner._parse(text, "topic")
    assert len(tasks) == 2


def test_parse_defaults_invalid_tier_to_mid():
    text = "unknown|Question here?\ninvalid|Another?"
    tasks = ResearchPlanner._parse(text, "topic")
    assert len(tasks) == 2
    assert all(t.metadata["complexity_tier"] == "mid" for t in tasks)


def test_parse_trims_whitespace_and_case_insensitive_tier():
    text = "  HIGH |  What about X?  \n  Low|  basic Q? "
    tasks = ResearchPlanner._parse(text, "topic")
    assert len(tasks) == 2
    assert tasks[0].metadata["complexity_tier"] == "high"
    assert tasks[1].metadata["complexity_tier"] == "low"


def test_parse_empty_text_falls_back():
    tasks = ResearchPlanner._parse("", "my topic")
    assert len(tasks) == 3
    assert all("my topic" in t.prompt for t in tasks)


def test_parse_whitespace_only_falls_back():
    tasks = ResearchPlanner._parse("   \n\n   ", "fallback topic")
    assert len(tasks) == 3


def test_parse_handles_extra_pipes_in_question():
    text = "mid|What is X|Y|Z?"
    tasks = ResearchPlanner._parse(text, "topic")
    assert len(tasks) == 1
    assert tasks[0].prompt == "What is X|Y|Z?"


def test_parse_all_tiers():
    for tier in ["low", "mid", "high", "xhigh", "max"]:
        text = f"{tier}|Q for {tier}?"
        tasks = ResearchPlanner._parse(text, "t")
        assert tasks[0].metadata["complexity_tier"] == tier


# -- _local_fallback tests --


def test_local_fallback_returns_three_tasks():
    tasks = ResearchPlanner._local_fallback("Quantum Computing")
    assert len(tasks) == 3
    assert tasks[0].metadata["task_type"] == "research"
    assert tasks[0].metadata["complexity_tier"] == "low"
    assert all("Quantum Computing" in t.prompt for t in tasks)
    assert tasks[0].id == "research-0"
    assert tasks[1].id == "research-1"
    assert tasks[2].id == "research-2"


# -- plan() with mocked providers --


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeProvider:
    def __init__(self, name, text=None, should_fail=False, fail_msg="500 error", default_model=None):
        self.name = name
        self.default_model = default_model or f"{name}-model"
        self._text = text
        self._should_fail = should_fail
        self._fail_msg = fail_msg
        self.rate_limited_until = 0.0

        class FakeKeyPool:
            async def get_key(self):
                return "fake-key"

        self.key_pool = FakeKeyPool()

    def mark_rate_limited(self, cooldown_sec=30):
        import time

        self.rate_limited_until = time.time() + cooldown_sec

    async def call(self, model, prompt, api_key, **kwargs):
        if self._should_fail:
            raise Exception(self._fail_msg)
        return FakeResponse(self._text)


@pytest.mark.asyncio
async def test_plan_succeeds_with_first_provider():
    providers = {
        "p1": FakeProvider("p1", text="low|Q1?\nmid|Q2?\nhigh|Q3?"),
    }
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("test topic")
    assert len(tasks) == 3
    assert tasks[0].prompt == "Q1?"


@pytest.mark.asyncio
async def test_plan_fails_over_to_second_provider():
    providers = {
        "p1": FakeProvider("p1", should_fail=True, fail_msg="500 boom"),
        "p2": FakeProvider("p2", text="low|Fallback Q1?\nmid|Fallback Q2?"),
    }
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("topic")
    assert len(tasks) == 2
    assert tasks[0].prompt == "Fallback Q1?"


@pytest.mark.asyncio
async def test_plan_429_marks_rate_limited():
    p1 = FakeProvider("p1", should_fail=True, fail_msg="429 Too Many Requests")
    providers = {"p1": p1, "p2": FakeProvider("p2", text="low|Q1?")}
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("topic")
    assert len(tasks) >= 1
    assert p1.rate_limited_until > 0


@pytest.mark.asyncio
async def test_plan_all_providers_fail_uses_local_fallback():
    providers = {
        "p1": FakeProvider("p1", should_fail=True),
        "p2": FakeProvider("p2", should_fail=True),
    }
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("my topic XYZ")
    assert len(tasks) == 3
    assert all("my topic XYZ" in t.prompt for t in tasks)


@pytest.mark.asyncio
async def test_plan_empty_providers_uses_local_fallback():
    planner = ResearchPlanner({})
    tasks = await planner.plan("lonely topic")
    assert len(tasks) == 3
    assert all("lonely topic" in t.prompt for t in tasks)


@pytest.mark.asyncio
async def test_plan_skips_rate_limited_provider():
    import time

    p1 = FakeProvider("p1", text="low|Should not be used")
    p1.rate_limited_until = time.time() + 9999
    p2 = FakeProvider("p2", text="mid|Used Q?")
    providers = {"p1": p1, "p2": p2}
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("topic")
    assert len(tasks) == 1
    assert tasks[0].prompt == "Used Q?"


@pytest.mark.asyncio
async def test_plan_with_explicit_candidates_override():
    p1 = FakeProvider("p1", text="low|Q1?")
    p2 = FakeProvider("p2", text="low|Should not use")
    providers = {"p1": p1, "p2": p2}
    planner = ResearchPlanner(providers, candidates=[("p1", "model-a")])
    tasks = await planner.plan("topic")
    assert tasks[0].prompt == "Q1?"


@pytest.mark.asyncio
async def test_plan_malformed_llm_response_triggers_fallback_parsing():
    # LLM returns garbage without pipes -> _parse returns local fallback
    providers = {"p1": FakeProvider("p1", text="no pipes here at all")}
    planner = ResearchPlanner(providers)
    tasks = await planner.plan("topic fallback check")
    assert len(tasks) == 3
    assert all("topic fallback check" in t.prompt for t in tasks)
