import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.providers.base import BaseProvider, LLMResponse, ModelInfo
from core.providers.anthropic_provider import AnthropicProvider
from core.providers.circuit_breaker import CircuitBreaker
from core.providers.key_pool import APIKeyPool
from core.providers.openai_compatible import OpenAICompatibleProvider
from core.providers.registry import build_providers


# ---- BaseProvider helpers ----


class DummyProvider(BaseProvider):
    async def call(self, model, prompt, api_key, **gen_params):
        return LLMResponse(text="ok", raw={}, tokens_used=1)


def test_base_provider_is_healthy_initially():
    p = DummyProvider(name="test", api_keys=["k1"], base_url="http://x", default_model="m")
    assert p.is_healthy() is True
    assert p.is_enabled() is True


def test_base_provider_not_enabled_without_keys():
    p = DummyProvider(name="test", api_keys=[], base_url="http://x")
    assert p.is_enabled() is False
    assert p.is_healthy() is False


def test_base_provider_mark_rate_limited():
    p = DummyProvider(name="test", api_keys=["k1"], base_url="http://x")
    p.mark_rate_limited(cooldown_sec=60)
    assert p.rate_limited_until > time.time()
    assert p.is_healthy() is False
    # breaker should be tripped
    assert p.breaker.failures == 1


def test_base_provider_rate_limited_expires():
    p = DummyProvider(name="test", api_keys=["k1"], base_url="http://x")
    p.rate_limited_until = time.time() - 1
    assert p.is_healthy() is True


def test_base_provider_mark_rate_limited_extends_only():
    p = DummyProvider(name="test", api_keys=["k1"], base_url="http://x")
    p.mark_rate_limited(cooldown_sec=100)
    first = p.rate_limited_until
    p.mark_rate_limited(cooldown_sec=1)
    assert p.rate_limited_until == first


# ---- OpenAICompatibleProvider ----


@pytest.mark.asyncio
async def test_openai_provider_call_success():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test", default_model="gpt-4o")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}],
        "usage": {"total_tokens": 20},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.call("gpt-4o", "hi", "k", temperature=0.7, max_tokens=100)

    assert result.text == "hello world"
    assert result.tokens_used == 20
    # Verify correct URL and payload
    called_url = mock_client.post.call_args[0][0]
    assert called_url.endswith("/chat/completions")
    payload = mock_client.post.call_args[1]["json"]
    assert payload["model"] == "gpt-4o"
    assert payload["messages"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_openai_provider_call_empty_response_raises():
    provider = OpenAICompatibleProvider(name="groq", api_keys=["k"], base_url="http://test", default_model="m")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "   "}}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="Empty response"):
            await provider.call("m", "hi", "k")


@pytest.mark.asyncio
async def test_openai_provider_call_malformed_raises():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test", default_model="m")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"no_choices": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="Malformed"):
            await provider.call("m", "hi", "k")


@pytest.mark.asyncio
async def test_openai_provider_http_error_propagates():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test", default_model="m")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("429", request=MagicMock(), response=MagicMock(status_code=429))

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await provider.call("m", "hi", "k")


@pytest.mark.asyncio
async def test_openai_list_models_success():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test", default_model="m")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        models = await provider.list_models()
    assert len(models) == 2
    assert {m.id for m in models} == {"gpt-4o", "gpt-4o-mini"}


@pytest.mark.asyncio
async def test_openai_list_models_empty_when_no_keys():
    provider = OpenAICompatibleProvider(name="openai", api_keys=[], base_url="http://test", default_model="m")
    models = await provider.list_models()
    assert models == []


@pytest.mark.asyncio
async def test_openai_list_models_handles_exception():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test", default_model="m")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=Exception("network down"))
        mock_client_cls.return_value = mock_client

        models = await provider.list_models()
    assert models == []


# ---- AnthropicProvider ----


@pytest.mark.asyncio
async def test_anthropic_call_success():
    provider = AnthropicProvider(name="anthropic", api_keys=["k"], base_url="http://test", default_model="claude")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}],
        "usage": {"input_tokens": 5, "output_tokens": 10},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.call("claude-3-5-sonnet", "hi", "k")

    assert result.text == "hello world"
    assert result.tokens_used == 15


@pytest.mark.asyncio
async def test_anthropic_call_filters_non_text_blocks():
    provider = AnthropicProvider(name="anthropic", api_keys=["k"], base_url="http://test", default_model="claude")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [
            {"type": "text", "text": "keep"},
            {"type": "image", "source": "xxx"},
            {"type": "text", "text": " this"},
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await provider.call("claude", "hi", "k")
    assert result.text == "keep this"


@pytest.mark.asyncio
async def test_anthropic_call_empty_raises():
    provider = AnthropicProvider(name="anthropic", api_keys=["k"], base_url="http://test", default_model="claude")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"content": [{"type": "text", "text": "   "}], "usage": {}}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="Empty response"):
            await provider.call("claude", "hi", "k")


@pytest.mark.asyncio
async def test_anthropic_list_models_success():
    provider = AnthropicProvider(name="anthropic", api_keys=["k"], base_url="http://test", default_model="claude")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "claude-3-5-sonnet", "display_name": "Sonnet"}, {"id": "claude-3-haiku"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        models = await provider.list_models()
    assert len(models) == 2
    assert models[0].id == "claude-3-5-sonnet"
    assert models[0].display_name == "Sonnet"
    assert models[1].display_name == "claude-3-haiku"


@pytest.mark.asyncio
async def test_anthropic_list_models_empty_no_keys():
    provider = AnthropicProvider(name="anthropic", api_keys=[], base_url="http://test", default_model="claude")
    assert await provider.list_models() == []


# ---- Registry ----


def test_build_providers_only_configured():
    class FakeSettings:
        def get_provider_configs(self):
            return {
                "openai": {"api_keys": ["k1"], "base_url": "http://o", "default_model": "gpt-4o"},
                "groq": {"api_keys": [], "base_url": "http://g", "default_model": "llama"},
                "anthropic": {"api_keys": ["k2"], "base_url": "http://a", "default_model": "claude"},
                "openrouter": {"api_keys": [], "base_url": "http://r", "default_model": ""},
                "nvidia_nim": {"api_keys": [], "base_url": "http://n", "default_model": ""},
                "opencode_zen": {"api_keys": [], "base_url": "http://z", "default_model": ""},
            }

    providers = build_providers(FakeSettings())
    assert "openai" in providers
    assert "anthropic" in providers
    assert "groq" not in providers
    assert isinstance(providers["anthropic"], AnthropicProvider)
    assert isinstance(providers["openai"], OpenAICompatibleProvider)


def test_build_providers_empty_when_no_keys():
    class FakeSettings:
        def get_provider_configs(self):
            return {
                "openai": {"api_keys": [], "base_url": "http://o", "default_model": "gpt-4o"},
                "anthropic": {"api_keys": [], "base_url": "http://a", "default_model": "claude"},
                "groq": {"api_keys": [], "base_url": "http://g", "default_model": "llama"},
                "openrouter": {"api_keys": [], "base_url": "http://r", "default_model": ""},
                "nvidia_nim": {"api_keys": [], "base_url": "http://n", "default_model": ""},
                "opencode_zen": {"api_keys": [], "base_url": "http://z", "default_model": ""},
            }

    assert build_providers(FakeSettings()) == {}


def test_openai_provider_strips_trailing_slash():
    provider = OpenAICompatibleProvider(name="openai", api_keys=["k"], base_url="http://test///", default_model="m")
    # base_url stored as-is; call should strip
    assert provider.base_url == "http://test///"
