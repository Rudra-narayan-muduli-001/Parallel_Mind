import json
from abc import ABC, abstractmethod

from config.settings import settings


DEFAULT_TIER = "mid"

ROUTING_TABLE = {
    ("research", "low"): [
        ("groq", "openai/gpt-oss-20b"),
    ],
    ("research", "mid"): [
        ("groq", "openai/gpt-oss-20b"),
        ("openrouter", "meta-llama/llama-3.1-70b-instruct"),
        ("nvidia_nim", "llama-3.3-nemotron-super-49b-v1.5"),
    ],
    ("research", "high"): [
        ("nvidia_nim", "nemotron-3-super-120b-a12b"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku-20241022"),
    ],
    ("research", "xhigh"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("research", "max"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("code_review", "low"): [
        ("groq", "openai/gpt-oss-20b"),
    ],
    ("code_review", "mid"): [
        ("groq", "openai/gpt-oss-20b"),
        ("nvidia_nim", "llama-3.3-nemotron-super-49b-v1.5"),
    ],
    ("code_review", "high"): [
        ("nvidia_nim", "nemotron-3-super-120b-a12b"),
        ("openai", "gpt-4o-mini"),
        ("openrouter", "meta-llama/llama-3.1-70b-instruct"),
    ],
    ("code_review", "xhigh"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("code_review", "max"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
}


class RoutingPolicy(ABC):
    @abstractmethod
    async def decide(self, task) -> list[tuple[str, str]]: ...


class _RotatingPool:
    def __init__(self, candidates: list[tuple[str, str]]):
        self._candidates = candidates
        self._counter = 0

    def next_ordering(self) -> list[tuple[str, str]]:
        if not self._candidates:
            return []
        start = self._counter % len(self._candidates)
        self._counter += 1
        return self._candidates[start:] + self._candidates[:start]


class RuleBasedPolicy(RoutingPolicy):

    def __init__(self, providers: dict | None = None, catalog=None):
        self._providers = providers or {}
        self._catalog = catalog
        self._default_provider = settings.default_provider if self._providers else None
        self._free_only = settings.free_models_only

        self._filtered_table: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for (task_type, tier), candidates in ROUTING_TABLE.items():
            kept = [
                (p, m) for (p, m) in candidates
                if not self._providers or p in self._providers
            ]
            if kept:
                self._filtered_table[(task_type, tier)] = kept

        self._fallback_pool: list[tuple[str, str]] = [
            (name, prov.default_model)
            for name, prov in self._providers.items()
            if getattr(prov, "default_model", None)
        ]

        self._free_fallback: list[tuple[str, str]] = []
        if self._default_provider and self._catalog:
            self._free_fallback = self._collect_free_models(self._default_provider)

        self._pools: dict[tuple[str, str], _RotatingPool] = {}

    def _collect_free_models(self, provider_name: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        entry = self._catalog.providers.get(provider_name) if self._catalog else None
        if not entry:
            return out
        for m in entry.get("models", []):
            mid = m["id"].lower()
            if mid.endswith("-free") or mid.endswith(":free") or "free" in mid.split("/")[-1]:
                out.append((provider_name, m["id"]))
        return out

    def _get_pool(self, key: tuple[str, str]) -> _RotatingPool:
        if key in self._pools:
            return self._pools[key]

        if self._default_provider and self._free_only and self._free_fallback:
            candidates = list(self._free_fallback)
        else:
            candidates = self._filtered_table.get(key) or \
                self._filtered_table.get((key[0], DEFAULT_TIER), [])
            seen = set(candidates)
            for fb in self._fallback_pool:
                if fb not in seen:
                    candidates.append(fb)
                    seen.add(fb)
            if self._free_only and self._free_fallback:
                free_ids = {m for _, m in self._free_fallback}
                free_cands = [c for c in candidates if c[1] in free_ids]
                if free_cands:
                    candidates = free_cands

        self._pools[key] = _RotatingPool(candidates)
        return self._pools[key]

    async def decide(self, task) -> list[tuple[str, str]]:
        task_type = task.metadata.get("task_type", "research")
        tier = task.metadata.get("complexity_tier", DEFAULT_TIER)
        pool = self._get_pool((task_type, tier))
        return pool.next_ordering()


class ManualPolicy(RoutingPolicy):
    def __init__(self, selected_targets: list[tuple[str, str]], effort: str = "low"):
        self.effort = effort
        self._pool = _RotatingPool(selected_targets)

    async def decide(self, task) -> list[tuple[str, str]]:
        return self._pool.next_ordering()


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