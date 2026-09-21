import logging

from core.models import AgentTask, ComplexityTier

logger = logging.getLogger("parallelmind.planner")

DEFAULT_TIER: ComplexityTier = "mid"


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


class ResearchPlanner:

    PLANNER_PROMPT = (
        "Decompose the following research topic into 3-5 sub-questions.\n"
        "For each sub-question, assign a complexity tier from: low, mid, high, xhigh, max.\n"
        "Format each line as: TIER|sub-question text\n\n"
        "Topic: {topic}\n\n"
        "Example:\n"
        "low|What is the basic definition of X?\n"
        "high|What are the advanced implications of X?\n"
    )

    def __init__(self, providers: dict, planner_model: str | None = None,
                 candidates: list[tuple[str, str]] | None = None):
        self.providers = providers
        self._candidates_override = candidates
        if candidates:
            self._pool = _RotatingPool(candidates)
        else:
            cands: list[tuple[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for name, prov in providers.items():
                if getattr(prov, "default_model", None):
                    pair = (name, prov.default_model)
                    if pair not in seen:
                        cands.append(pair)
                        seen.add(pair)
            self._pool = _RotatingPool(cands)

    async def plan(self, topic: str) -> list[AgentTask]:
        candidates = self._pool.next_ordering()
        prompt = self.PLANNER_PROMPT.format(topic=topic)

        last_error = "no candidates"
        for provider_name, model in candidates:
            provider = self.providers.get(provider_name)
            if provider is None:
                continue
            import time as _time
            if _time.time() < getattr(provider, "rate_limited_until", 0):
                continue
            try:
                api_key = await provider.key_pool.get_key()
            except Exception:
                continue
            try:
                response = await provider.call(model, prompt, api_key)
                return self._parse(response.text, topic)
            except Exception as e:
                err_text = str(e)
                last_error = err_text
                logger.warning(f"Planner {provider_name}/{model} failed: {err_text[:120]}")
                if "429" in err_text or "Too Many Requests" in err_text or "rate limit" in err_text.lower():
                    provider.mark_rate_limited(cooldown_sec=30.0)
                continue

        raise RuntimeError(f"Planner exhausted all candidates: {last_error}")

    @staticmethod
    def _parse(text: str, topic: str) -> list[AgentTask]:
        tasks: list[AgentTask] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if "|" not in line:
                continue
            tier_str, question = line.split("|", 1)
            tier_str = tier_str.strip().lower()
            tier: ComplexityTier = DEFAULT_TIER
            if tier_str in {"low", "mid", "high", "xhigh", "max"}:
                tier = tier_str
            tasks.append(
                AgentTask(
                    id=f"research-{len(tasks)}",
                    prompt=question.strip(),
                    metadata={"task_type": "research", "complexity_tier": tier},
                )
            )
        if not tasks:
            raise ValueError("Planner returned no valid tasks")
        return tasks