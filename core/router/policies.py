import json
from abc import ABC, abstractmethod

from core.router.candidate_rotation import RotatingCandidatePool
from config.routing_table import ROUTING_TABLE, DEFAULT_TIER


class RoutingPolicy(ABC):
    @abstractmethod
    async def decide(self, task) -> list[tuple[str, str]]:
        ...


class RuleBasedPolicy(RoutingPolicy):
    def __init__(self):
        self._pools: dict[tuple[str, str], RotatingCandidatePool] = {}

    def _get_pool(self, key: tuple[str, str]) -> RotatingCandidatePool:
        if key not in self._pools:
            candidates = ROUTING_TABLE.get(key) or ROUTING_TABLE.get((key[0], DEFAULT_TIER), [])
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
        all_targets = [
            (pname, prov.default_model)
            for pname, prov in providers.items()
            if prov.default_model
        ]
        router_provider = providers.get(settings.router_model_provider)
        if router_provider:
            return LLMRouterPolicy(router_provider, settings.router_model_name, all_targets)

    return RuleBasedPolicy()
