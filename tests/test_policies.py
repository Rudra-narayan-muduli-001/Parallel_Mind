import pytest

from core.models import AgentTask
from core.router.policies import ManualPolicy, RuleBasedPolicy


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


class _FakeProvider:
    def __init__(self, default_model: str):
        self.default_model = default_model


@pytest.mark.asyncio
async def test_rule_based_policy_drops_unconfigured_providers():
    """Providers without configured API keys must not appear in candidates."""
    providers = {"groq": _FakeProvider("openai/gpt-oss-20b")}
    task = AgentTask(id="t5", prompt="test", metadata={"task_type": "research", "complexity_tier": "high"})
    policy = RuleBasedPolicy(providers=providers)
    candidates = await policy.decide(task)
    assert len(candidates) > 0
    # All candidates must be from configured providers.
    for provider_name, _ in candidates:
        assert provider_name in providers, f"Unconfigured provider {provider_name} leaked into candidates"
    # "anthropic"/"openai" are referenced in routing table but should be filtered out.
    assert "anthropic" not in {p for p, _ in candidates}
    assert "openai" not in {p for p, _ in candidates}


@pytest.mark.asyncio
async def test_rule_based_policy_appends_fallback_when_tier_exhausted():
    """If tier candidates all reference unconfigured providers, fallback (every
    configured provider's default_model) must fill the list so failover works."""
    providers = {"groq": _FakeProvider("openai/gpt-oss-20b")}
    # 'high' tier in routing table references nvidia_nim, openai, anthropic (none configured)
    task = AgentTask(id="t6", prompt="test", metadata={"task_type": "research", "complexity_tier": "high"})
    policy = RuleBasedPolicy(providers=providers)
    candidates = await policy.decide(task)
    assert ("groq", "openai/gpt-oss-20b") in candidates, "Configured groq model must appear as failover"
