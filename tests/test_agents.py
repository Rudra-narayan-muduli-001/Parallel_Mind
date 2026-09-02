import pytest

from core.models import AgentTask
from pipelines.code_review.reviewer_agent import CodeReviewerAgent
from pipelines.research.researcher_agent import ResearcherAgent
from core.providers.base import LLMResponse


class MockProvider:
    def __init__(self, response_text="mock answer", tokens=10, should_fail=False):
        self._text = response_text
        self._tokens = tokens
        self._should_fail = should_fail
        self.last_call_args = None

    async def call(self, model, prompt, api_key, **gen_params):
        self.last_call_args = (model, prompt, api_key, gen_params)
        if self._should_fail:
            raise RuntimeError("provider failure")
        return LLMResponse(text=self._text, raw={"choices": []}, tokens_used=self._tokens)


@pytest.mark.asyncio
async def test_researcher_agent_returns_text_and_tokens():
    agent = ResearcherAgent()
    task = AgentTask(id="r1", prompt="What is AI?", metadata={"task_type": "research"})
    provider = MockProvider(response_text="AI is ...", tokens=42)
    result = await agent.execute(task, provider, "test-model", "key-123", {})
    assert result["text"] == "AI is ..."
    assert result["tokens"] == 42


@pytest.mark.asyncio
async def test_researcher_agent_builds_prompt_from_task():
    agent = ResearcherAgent()
    task = AgentTask(id="r2", prompt="Explain quantum computing")
    provider = MockProvider()
    await agent.execute(task, provider, "m", "k", {})
    _, prompt, _, _ = provider.last_call_args
    assert "Explain quantum computing" in prompt
    assert "research assistant" in prompt.lower()


@pytest.mark.asyncio
async def test_researcher_agent_passes_gen_params():
    agent = ResearcherAgent()
    task = AgentTask(id="r3", prompt="q")
    provider = MockProvider()
    await agent.execute(task, provider, "m", "k", {"temperature": 0.9, "max_tokens": 512})
    _, _, _, gen_params = provider.last_call_args
    assert gen_params["temperature"] == 0.9
    assert gen_params["max_tokens"] == 512


@pytest.mark.asyncio
async def test_researcher_agent_propagates_provider_failure():
    agent = ResearcherAgent()
    task = AgentTask(id="r4", prompt="q")
    provider = MockProvider(should_fail=True)
    with pytest.raises(RuntimeError, match="provider failure"):
        await agent.execute(task, provider, "m", "k", {})


@pytest.mark.asyncio
async def test_code_reviewer_agent_returns_expected_shape():
    agent = CodeReviewerAgent()
    task = AgentTask(
        id="review-src/app.py",
        prompt="def foo(): pass",
        metadata={"task_type": "code_review", "file_path": "src/app.py"},
    )
    provider = MockProvider(response_text="Looks good", tokens=15)
    result = await agent.execute(task, provider, "m", "k", {})
    assert result["text"] == "Looks good"
    assert result["tokens"] == 15
    assert result["file_path"] == "src/app.py"


@pytest.mark.asyncio
async def test_code_reviewer_agent_includes_file_path_in_prompt():
    agent = CodeReviewerAgent()
    task = AgentTask(
        id="review-1",
        prompt="x = 1",
        metadata={"file_path": "utils/helper.py"},
    )
    provider = MockProvider()
    await agent.execute(task, provider, "m", "k", {})
    _, prompt, _, _ = provider.last_call_args
    assert "utils/helper.py" in prompt
    assert "x = 1" in prompt


@pytest.mark.asyncio
async def test_code_reviewer_agent_defaults_file_path_to_unknown():
    agent = CodeReviewerAgent()
    task = AgentTask(id="review-2", prompt="code", metadata={})
    provider = MockProvider()
    result = await agent.execute(task, provider, "m", "k", {})
    assert result["file_path"] == "unknown"
    _, prompt, _, _ = provider.last_call_args
    assert "unknown" in prompt


@pytest.mark.asyncio
async def test_code_reviewer_agent_covers_review_dimensions():
    agent = CodeReviewerAgent()
    task = AgentTask(id="r", prompt="code", metadata={"file_path": "a.py"})
    provider = MockProvider()
    await agent.execute(task, provider, "m", "k", {})
    _, prompt, _, _ = provider.last_call_args
    low = prompt.lower()
    assert "bug" in low
    assert "security" in low


@pytest.mark.asyncio
async def test_agents_are_stateless():
    """Same agent instance reused across tasks should not leak state."""
    researcher = ResearcherAgent()
    p1 = MockProvider(response_text="answer 1")
    p2 = MockProvider(response_text="answer 2")
    t1 = AgentTask(id="t1", prompt="Q1")
    t2 = AgentTask(id="t2", prompt="Q2")
    r1 = await researcher.execute(t1, p1, "m", "k", {})
    r2 = await researcher.execute(t2, p2, "m", "k", {})
    assert r1["text"] == "answer 1"
    assert r2["text"] == "answer 2"

    reviewer = CodeReviewerAgent()
    p3 = MockProvider(response_text="review 1")
    p4 = MockProvider(response_text="review 2")
    rt1 = AgentTask(id="rv1", prompt="code1", metadata={"file_path": "a.py"})
    rt2 = AgentTask(id="rv2", prompt="code2", metadata={"file_path": "b.py"})
    rr1 = await reviewer.execute(rt1, p3, "m", "k", {})
    rr2 = await reviewer.execute(rt2, p4, "m", "k", {})
    assert rr1["file_path"] == "a.py"
    assert rr2["file_path"] == "b.py"
