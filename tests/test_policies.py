import pytest
from core.models import AgentTask
from core.router.policies import RuleBasedPolicy, ManualPolicy


@pytest.mark.asyncio
async def test_rule_based_policy_returns_candidates():
    task = AgentTask(id="t1", prompt="test", metadata={"task_type": "research", "complexity_tier": "low"})
    policy = RuleBasedPolicy()
    candidates = await policy.decide(task)
    assert len(candidates) > 0
    for provider, model in candidates:
        assert isinstance(provider, str)
        assert isinstance(model, str)


@pytest.mark.asyncio
async def test_rule_based_policy_uses_default_tier():
    task = AgentTask(id="t2", prompt="test", metadata={"task_type": "research"})
    policy = RuleBasedPolicy()
    candidates = await policy.decide(task)
    assert len(candidates) > 0


@pytest.mark.asyncio
async def test_manual_policy_returns_selected():
    targets = [("groq", "llama-3.1-70b-versatile"), ("openai", "gpt-4o")]
    policy = ManualPolicy(targets, effort="high")
    task = AgentTask(id="t3", prompt="test")
    candidates = await policy.decide(task)
    assert candidates == targets


@pytest.mark.asyncio
async def test_manual_policy_rotates():
    targets = [("a", "m1"), ("b", "m2")]
    policy = ManualPolicy(targets)
    task = AgentTask(id="t4", prompt="test")
    r1 = await policy.decide(task)
    r2 = await policy.decide(task)
    assert r1 != r2
