import json
import pytest

from core.models import AgentTask
from core.router.router import Router
from core.router.policies import LLMRouterPolicy, ManualPolicy, RuleBasedPolicy, build_policy
from core.providers.base import LLMResponse


# -- Router wrapper --

@pytest.mark.asyncio
async def test_router_delegates_to_policy():
    class FakePolicy:
        async def decide(self, task):
            return [("p1", "m1")]

    router = Router(FakePolicy())  # type: ignore[arg-type]
    task = AgentTask(id="t", prompt="hi")
    result = await router.decide(task)
    assert result == [("p1", "m1")]


# -- LLMRouterPolicy --

class FakeLLMProvider:
    def __init__(self, response_text, should_fail=False):
        self._text = response_text
        self._should_fail = should_fail

        class FakeKeyPool:
            async def get_key(self):
                return "k"

        self.key_pool = FakeKeyPool()

    async def call(self, model, prompt, api_key, **kwargs):
        if self._should_fail:
            raise RuntimeError("call failed")
        return LLMResponse(text=self._text, raw={}, tokens_used=5)


@pytest.mark.asyncio
async def test_llm_router_parses_valid_json():
    provider = FakeLLMProvider(json.dumps([{"provider": "openai", "model": "gpt-4o"}, {"provider": "groq", "model": "llama"}]))
    policy = LLMRouterPolicy(provider, "router-model", [("openai", "gpt-4o"), ("groq", "llama"), ("anthropic", "claude")])
    task = AgentTask(id="t", prompt="research task")
    result = await policy.decide(task)
    assert result == [("openai", "gpt-4o"), ("groq", "llama")]


@pytest.mark.asyncio
async def test_llm_router_fallback_on_invalid_json():
    provider = FakeLLMProvider("not json at all {{{")
    all_targets = [("a", "m1"), ("b", "m2"), ("c", "m3"), ("d", "m4")]
    policy = LLMRouterPolicy(provider, "router-model", all_targets)
    task = AgentTask(id="t", prompt="q")
    result = await policy.decide(task)
    assert result == all_targets[:3]


@pytest.mark.asyncio
async def test_llm_router_fallback_on_missing_keys():
    provider = FakeLLMProvider(json.dumps([{"bad": "data"}]))
    all_targets = [("a", "m1"), ("b", "m2")]
    policy = LLMRouterPolicy(provider, "router-model", all_targets)
    task = AgentTask(id="t", prompt="q")
    result = await policy.decide(task)
    assert result == all_targets[:3]


@pytest.mark.asyncio
async def test_llm_router_prompt_contains_options():
    captured = {}

    class CapturingProvider(FakeLLMProvider):
        async def call(self, model, prompt, api_key, **kwargs):
            captured["prompt"] = prompt
            return LLMResponse(text=json.dumps([{"provider": "a", "model": "m1"}]), raw={})

    provider = CapturingProvider(json.dumps([{"provider": "a", "model": "m1"}]))
    policy = LLMRouterPolicy(provider, "router-model", [("a", "m1"), ("b", "m2")])
    task = AgentTask(id="t", prompt="my special task", metadata={"task_type": "research"})
    await policy.decide(task)
    assert "a:m1" in captured["prompt"]
    assert "b:m2" in captured["prompt"]
    assert "my special task" in captured["prompt"]


@pytest.mark.asyncio
async def test_llm_router_truncates_long_prompt():
    long_prompt = "x" * 1000
    captured = {}

    class CapturingProvider:
        class FakeKeyPool:
            async def get_key(self):
                return "k"

        key_pool = FakeKeyPool()

        async def call(self, model, prompt, api_key, **kwargs):
            captured["prompt"] = prompt
            return LLMResponse(text=json.dumps([{"provider": "a", "model": "m1"}]), raw={})

    provider = CapturingProvider()
    policy = LLMRouterPolicy(provider, "m", [("a", "m1")])  # type: ignore[arg-type]
    task = AgentTask(id="t", prompt=long_prompt)
    await policy.decide(task)
    # Prompt includes task.prompt[:400]
    assert long_prompt[:400] in captured["prompt"]
    assert long_prompt[500:] not in captured["prompt"]


# -- build_policy --

def test_build_policy_manual_mode():
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        mode = "manual"
        selected_targets = [("groq", "llama")]
        effort = "high"

    policy = build_policy(FakeConfig(), providers={})
    assert isinstance(policy, ManualPolicy)


def test_build_policy_llm_based_mode():
    from dataclasses import dataclass
    from unittest.mock import MagicMock, patch

    @dataclass
    class FakeConfig:
        mode = "llm_based"

    fake_provider = MagicMock()
    fake_provider.default_model = "m1"
    fake_provider.key_pool = MagicMock()
    providers = {"groq": fake_provider}

    with patch("core.router.policies.settings") as mock_settings:
        mock_settings.routing_mode = "rule_based"
        mock_settings.router_model_provider = "groq"
        mock_settings.router_model_name = "llama"
        policy = build_policy(FakeConfig(), providers=providers)
        assert isinstance(policy, LLMRouterPolicy)


def test_build_policy_defaults_to_rule_based():
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        mode = "rule_based"

    policy = build_policy(FakeConfig(), providers={})
    assert isinstance(policy, RuleBasedPolicy)


def test_build_policy_uses_settings_routing_mode_when_no_mode_attr():
    class NoModeConfig:
        pass

    with pytest.MonkeyPatch.context() as mp:
        # Use real settings but ensure it returns RuleBased
        policy = build_policy(NoModeConfig(), providers={})
        assert isinstance(policy, RuleBasedPolicy)


# -- RuleBased edge cases --

@pytest.mark.asyncio
async def test_rule_based_unknown_task_type_falls_back():
    policy = RuleBasedPolicy(providers={})
    task = AgentTask(id="t", prompt="hi", metadata={"task_type": "unknown_type", "complexity_tier": "low"})
    result = await policy.decide(task)
    # Should still return something (default tier fallback)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_rule_based_empty_providers_still_returns_static_candidates():
    policy = RuleBasedPolicy(providers={})
    task = AgentTask(id="t", prompt="hi", metadata={"task_type": "research", "complexity_tier": "low"})
    result = await policy.decide(task)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_manual_policy_effort_stored():
    policy = ManualPolicy([("a", "m1")], effort="max")
    assert policy.effort == "max"
    task = AgentTask(id="t", prompt="hi")
    result = await policy.decide(task)
    assert result == [("a", "m1")]
