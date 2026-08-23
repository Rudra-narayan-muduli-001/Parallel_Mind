import json
from abc import ABC, abstractmethod

from config.routing_table import DEFAULT_TIER, ROUTING_TABLE
from config.settings import settings
from core.router.candidate_rotation import RotatingCandidatePool


class RoutingPolicy(ABC):
    @abstractmethod
    async def decide(self, task) -> list[tuple[str, str]]: ...


class RuleBasedPolicy(RoutingPolicy):
    """Static 5-tier lookup, filtered to configured providers, with a runtime
    failover list of all available (provider, default_model) pairs so a
    broken tier candidate is immediately followed by another live model.

    When `settings.default_provider` is set, the policy restricts the candidate
    pool to that provider (filtered to free models if `settings.free_models_only`
    is true), so users with only free-tier keys still work without manual config.
    """

    def __init__(self, providers: dict | None = None, catalog=None):
        self._providers = providers or {}
        self._catalog = catalog
        self._default_provider = settings.default_provider if self._providers else None
        self._free_only = settings.free_models_only

        # 1) Build the filtered static routing table.
        self._filtered_table: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for (task_type, tier), candidates in ROUTING_TABLE.items():
            kept = [
                (p, m) for (p, m) in candidates
                if not self._providers or p in self._providers
            ]
            if kept:
                self._filtered_table[(task_type, tier)] = kept

        # 2) Build fallback pool = all configured providers' default_models.
        self._fallback_pool: list[tuple[str, str]] = [
            (name, prov.default_model)
            for name, prov in self._providers.items()
            if getattr(prov, "default_model", None)
        ]

        # 3) Build free-model fallback list (for the default provider).
        self._free_fallback: list[tuple[str, str]] = []
        if self._default_provider and self._catalog:
            self._free_fallback = self._collect_free_models(self._default_provider)

        self._pools: dict[tuple[str, str], RotatingCandidatePool] = {}

    def _collect_free_models(self, provider_name: str) -> list[tuple[str, str]]:
        """Pull free-tier models from the live-discovered catalog for the provider.
        Free tier markers vary: '-free' suffix, ':free' suffix (openrouter), or
        models explicitly listed as free in the provider."""
        from core.providers.base import ModelInfo  # noqa: F401  (ensures attr exists)
        out: list[tuple[str, str]] = []
        entry = self._catalog.providers.get(provider_name) if self._catalog else None
        if not entry:
            return out
        for m in entry.models:
            mid = m.id.lower()
            if mid.endswith("-free") or mid.endswith(":free") or "free" in mid.split("/")[-1]:
                out.append((provider_name, m.id))
        return out

    def _get_pool(self, key: tuple[str, str]) -> RotatingCandidatePool:
        if key in self._pools:
            return self._pools[key]

        # When the user has a default_provider set, prefer that provider's free
        # models above everything else. This is the "free out of the box" path.
        if self._default_provider and self._free_only and self._free_fallback:
            candidates = list(self._free_fallback)
        else:
            candidates = self._filtered_table.get(key) or \
                self._filtered_table.get((key[0], DEFAULT_TIER), [])
            # Append configured-provider fallbacks.
            seen = set(candidates)
            for fb in self._fallback_pool:
                if fb not in seen:
                    candidates.append(fb)
                    seen.add(fb)
            # If free_only is set, restrict the resulting pool to free models
            # when possible.
            if self._free_only and self._free_fallback:
                free_ids = {m for _, m in self._free_fallback}
                free_cands = [c for c in candidates if c[1] in free_ids]
                if free_cands:
                    candidates = free_cands

        self._pools[key] = RotatingCandidatePool(candidates)
        return self._pools[key]

    async def decide(self, task) -> list[tuple[str, str]]:
        task_type = task.metadata.get("task_type", "research")
        tier = task.metadata.get("complexity_tier", DEFAULT_TIER)
        pool = self._get_pool((task_type, tier))
        return await pool.next_ordering()


class ManualPolicy(RoutingPolicy):
    def __init__(self, selected_targets: list[tuple[str, str]], effort: str = "low"):
        self.effort = effort
        self._pool = RotatingCandidatePool(selected_targets)

    async def decide(self, task) -> list[tuple[str, str]]:
        return await self._pool.next_ordering()


class LLMRouterPolicy(RoutingPolicy):
    def __init__(self, router_provider, router_model: str, all_targets: list[tuple[str, str]]):
        self.router_provider = router_provider
        self.router_model = router_model
        self.all_targets = all_targets

    async def decide(self, task) -> list[tuple[str, str]]:
        options = "\n".join(f"- {p}:{m}" for p, m in self.all_targets)
        prompt = f"""Rank the best 3 provider:model options for this task, best first.
Task type: {task.metadata.get('task_type')}
Content: {task.prompt[:400]}
Options:
{options}
Respond ONLY with JSON list: [{{"provider":"...","model":"..."}}, ...]"""

        api_key = await self.router_provider.key_pool.get_key()
        response = await self.router_provider.call(self.router_model, prompt, api_key)

        try:
            ranked = json.loads(response.text)
            return [(r["provider"], r["model"]) for r in ranked]
        except (json.JSONDecodeError, KeyError, TypeError):
            return self.all_targets[:3]


def build_policy(run_config, providers=None) -> RoutingPolicy:
    mode = run_config.mode if hasattr(run_config, "mode") else settings.routing_mode

    if mode == "manual" and getattr(run_config, "selected_targets", None):
        return ManualPolicy(run_config.selected_targets, run_config.effort)

    if mode == "llm_based" and providers:
        all_targets = [(pname, prov.default_model) for pname, prov in providers.items() if prov.default_model]
        router_provider = providers.get(settings.router_model_provider)
        if router_provider:
            return LLMRouterPolicy(router_provider, settings.router_model_name, all_targets)

    return RuleBasedPolicy(providers=providers)
