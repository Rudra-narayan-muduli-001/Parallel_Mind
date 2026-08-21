import json
from abc import ABC, abstractmethod

from config.routing_table import DEFAULT_TIER, ROUTING_TABLE
from core.router.candidate_rotation import RotatingCandidatePool


class RoutingPolicy(ABC):
    @abstractmethod
    async def decide(self, task) -> list[tuple[str, str]]: ...


class RuleBasedPolicy(RoutingPolicy):
    """Static 5-tier lookup, filtered to configured providers, with a runtime
    failover list of all available (provider, default_model) pairs so a
    broken tier candidate is immediately followed by another live model.
    """

    def __init__(self, providers: dict | None = None):
        self._providers = providers or {}
        # Filter routing table at startup: drop entries for unconfigured providers.
        self._filtered_table: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for (task_type, tier), candidates in ROUTING_TABLE.items():
            kept = [
                (p, m) for (p, m) in candidates
                if not self._providers or p in self._providers
            ]
            if kept:
                self._filtered_table[(task_type, tier)] = kept

        # Fallback pool = every configured provider's (name, default_model)
        self._fallback_pool: list[tuple[str, str]] = [
            (name, prov.default_model)
            for name, prov in self._providers.items()
            if getattr(prov, "default_model", None)
        ]

        self._pools: dict[tuple[str, str], RotatingCandidatePool] = {}

    def _get_pool(self, key: tuple[str, str]) -> RotatingCandidatePool:
        if key in self._pools:
            return self._pools[key]
        candidates = self._filtered_table.get(key) or \
            self._filtered_table.get((key[0], DEFAULT_TIER), [])
        # Append fallback candidates (deduped, excluding tier candidates already listed).
        seen = set(candidates)
        for fb in self._fallback_pool:
            if fb not in seen:
                candidates.append(fb)
                seen.add(fb)
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
    from config.settings import settings

    mode = run_config.mode if hasattr(run_config, "mode") else settings.routing_mode

    if mode == "manual" and getattr(run_config, "selected_targets", None):
        return ManualPolicy(run_config.selected_targets, run_config.effort)

    if mode == "llm_based" and providers:
        all_targets = [(pname, prov.default_model) for pname, prov in providers.items() if prov.default_model]
        router_provider = providers.get(settings.router_model_provider)
        if router_provider:
            return LLMRouterPolicy(router_provider, settings.router_model_name, all_targets)

    return RuleBasedPolicy(providers=providers)
