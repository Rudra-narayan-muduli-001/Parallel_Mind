import asyncio
import pytest

from config.effort_presets import EFFORT_PRESETS
from config.routing_table import DEFAULT_TIER, ROUTING_TABLE
from config.settings import Settings
from core.providers.model_catalog import ModelCatalog, ModelEntry, ProviderCatalogEntry
from core.state.shared_context import SharedContext
from utils.validation import validate_routing_table_against_catalog


# ---- SharedContext ----


@pytest.mark.asyncio
async def test_shared_context_set_and_get():
    ctx = SharedContext()
    await ctx.set("key", "value")
    assert await ctx.get("key") == "value"
    assert await ctx.get("missing") is None


@pytest.mark.asyncio
async def test_shared_context_append():
    ctx = SharedContext()
    await ctx.append("list", 1)
    await ctx.append("list", 2)
    await ctx.append("list", 3)
    assert await ctx.get("list") == [1, 2, 3]


@pytest.mark.asyncio
async def test_shared_context_append_creates_list():
    ctx = SharedContext()
    await ctx.append("new_key", "first")
    assert await ctx.get("new_key") == ["first"]


@pytest.mark.asyncio
async def test_shared_context_snapshot_returns_copy():
    ctx = SharedContext()
    await ctx.set("a", 1)
    await ctx.set("b", 2)
    snap = await ctx.snapshot()
    assert snap == {"a": 1, "b": 2}
    snap["a"] = 999
    assert await ctx.get("a") == 1


@pytest.mark.asyncio
async def test_shared_context_overwrite():
    ctx = SharedContext()
    await ctx.set("k", "old")
    await ctx.set("k", "new")
    assert await ctx.get("k") == "new"


@pytest.mark.asyncio
async def test_shared_context_concurrent_access():
    ctx = SharedContext()

    async def writer(n):
        for i in range(20):
            await ctx.append("shared", f"{n}-{i}")

    await asyncio.gather(*(writer(n) for n in range(5)))
    result = await ctx.get("shared")
    assert len(result) == 100


@pytest.mark.asyncio
async def test_shared_context_snapshot_empty():
    ctx = SharedContext()
    assert await ctx.snapshot() == {}


# ---- Settings ----


def test_settings_split_keys():
    s = Settings()
    assert s._split_keys("") == []
    assert s._split_keys("  ") == []
    assert s._split_keys("k1") == ["k1"]
    assert s._split_keys("k1, k2 ,k3") == ["k1", "k2", "k3"]
    assert s._split_keys("k1,,k2") == ["k1", "k2"]


def test_settings_get_provider_configs_shape():
    s = Settings(openai_api_keys="k1,k2", groq_api_keys="g1")
    cfgs = s.get_provider_configs()
    assert "openai" in cfgs
    assert cfgs["openai"]["api_keys"] == ["k1", "k2"]
    assert cfgs["groq"]["api_keys"] == ["g1"]
    assert cfgs["anthropic"]["api_keys"] == []


def test_settings_defaults():
    s = Settings()
    assert s.default_max_concurrency == 3
    assert s.default_timeout_sec == 60
    assert s.routing_mode == "rule_based"
    assert s.circuit_breaker_fail_threshold == 5


# ---- Routing table ----


def test_routing_table_covers_all_tiers():
    for tier in ["low", "mid", "high", "xhigh", "max"]:
        assert ("research", tier) in ROUTING_TABLE
        assert ("code_review", tier) in ROUTING_TABLE


def test_routing_table_default_tier_exists():
    assert DEFAULT_TIER in {"low", "mid", "high", "xhigh", "max"}


def test_routing_table_entries_are_tuples():
    for key, candidates in ROUTING_TABLE.items():
        assert isinstance(key, tuple) and len(key) == 2
        for prov, model in candidates:
            assert isinstance(prov, str)
            assert isinstance(model, str)


# ---- Effort presets ----


def test_effort_presets_shape():
    for name, preset in EFFORT_PRESETS.items():
        assert "temperature" in preset
        assert "max_tokens" in preset
        assert "timeout_sec" in preset
        assert isinstance(preset["temperature"], float)
        assert isinstance(preset["max_tokens"], int)


def test_effort_presets_increasing_tokens():
    assert EFFORT_PRESETS["low"]["max_tokens"] < EFFORT_PRESETS["high"]["max_tokens"]
    assert EFFORT_PRESETS["high"]["max_tokens"] < EFFORT_PRESETS["xhigh"]["max_tokens"]
    assert EFFORT_PRESETS["xhigh"]["max_tokens"] < EFFORT_PRESETS["max"]["max_tokens"]


# ---- ModelCatalog ----


def test_model_catalog_loads_yaml():
    cat = ModelCatalog()
    assert len(cat.providers) > 0
    assert "openai" in cat.providers
    assert "groq" in cat.providers


def test_model_catalog_list_provider_names():
    cat = ModelCatalog()
    names = cat.list_provider_names()
    assert "openai" in names
    assert "anthropic" in names


def test_model_catalog_list_models():
    cat = ModelCatalog()
    models = cat.list_models(["openai"])
    assert len(models) > 0
    for pname, mid, display in models:
        assert pname == "openai"
        assert isinstance(mid, str)
        assert isinstance(display, str)


def test_model_catalog_is_valid_model():
    cat = ModelCatalog()
    assert cat.is_valid_model("openai", "gpt-4o") is True
    assert cat.is_valid_model("openai", "nonexistent-model-xyz") is False
    assert cat.is_valid_model("nonexistent_provider", "gpt-4o") is False


def test_model_catalog_list_models_unknown_provider():
    cat = ModelCatalog()
    assert cat.list_models(["does_not_exist"]) == []


# ---- Validation ----


def test_validate_routing_table_passes_with_real_catalog():
    cat = ModelCatalog()
    # Should not raise for the real routing table against real catalog
    validate_routing_table_against_catalog(ROUTING_TABLE, cat)


def test_validate_routing_table_fails_on_unknown_model():
    catalog = ModelCatalog.__new__(ModelCatalog)
    catalog.providers = {
        "openai": ProviderCatalogEntry(display_name="OpenAI", models=[ModelEntry(id="gpt-4o", display_name="gpt-4o")]),
    }
    bad_table = {("research", "low"): [("openai", "nonexistent-model")]}
    with pytest.raises(ValueError, match="unknown model"):
        validate_routing_table_against_catalog(bad_table, catalog)


def test_validate_routing_table_fails_on_unknown_provider():
    catalog = ModelCatalog.__new__(ModelCatalog)
    catalog.providers = {}
    bad_table = {("research", "low"): [("unknown_provider", "some-model")]}
    with pytest.raises(ValueError, match="unknown model"):
        validate_routing_table_against_catalog(bad_table, catalog)


def test_validate_empty_routing_table_passes():
    catalog = ModelCatalog.__new__(ModelCatalog)
    catalog.providers = {}
    validate_routing_table_against_catalog({}, catalog)


@pytest.mark.asyncio
async def test_model_catalog_from_providers_merges_live():
    from unittest.mock import AsyncMock

    from core.providers.base import ModelInfo

    cat = ModelCatalog()
    original_count = len(cat.providers.get("openai", ProviderCatalogEntry(display_name="x")).models)

    fake_provider = AsyncMock()
    fake_provider.list_models = AsyncMock(return_value=[ModelInfo(id="gpt-4o"), ModelInfo(id="new-live-model")])

    merged = await ModelCatalog.from_providers({"openai": fake_provider})
    assert "openai" in merged.providers
    # live list should replace
    ids = {m.id for m in merged.providers["openai"].models}
    assert "new-live-model" in ids


@pytest.mark.asyncio
async def test_model_catalog_from_providers_handles_failure():
    from unittest.mock import AsyncMock

    fake_provider = AsyncMock()
    fake_provider.list_models = AsyncMock(side_effect=Exception("network error"))
    cat = await ModelCatalog.from_providers({"openai": fake_provider})
    assert "openai" in cat.providers


@pytest.mark.asyncio
async def test_model_catalog_from_providers_empty_dict():
    cat = await ModelCatalog.from_providers({})
    assert len(cat.providers) > 0
