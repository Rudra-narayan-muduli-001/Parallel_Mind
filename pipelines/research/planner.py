import asyncio
import logging

from config.routing_table import DEFAULT_TIER
from core.models import AgentResult, AgentTask, ComplexityTier
from core.router.candidate_rotation import RotatingCandidatePool

logger = logging.getLogger("parallelmind.planner")


class ResearchPlanner:

    LOCAL_FALLBACK_PROMPT = (
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
            self._pool = RotatingCandidatePool(candidates)
        else:
            cands: list[tuple[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for name, prov in providers.items():
                if getattr(prov, "default_model", None):
                    pair = (name, prov.default_model)
                    if pair not in seen:
                        cands.append(pair)
                        seen.add(pair)
            self._pool = RotatingCandidatePool(cands)

    async def plan(self, topic: str) -> list[AgentTask]:
        candidates = await self._pool.next_ordering()
        prompt = self.LOCAL_FALLBACK_PROMPT.format(topic=topic)

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

        logger.warning(f"Planner exhausted all candidates ({last_error}); using local fallback")
        return self._local_fallback(topic)

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
            return ResearchPlanner._local_fallback(topic)
        return tasks

    @staticmethod
    def _local_fallback(topic: str) -> list[AgentTask]:
        return [
            AgentTask(
                id="research-0",
                prompt=f"Define and explain: {topic}",
                metadata={"task_type": "research", "complexity_tier": "low"},
            ),
            AgentTask(
                id="research-1",
                prompt=f"What are the main components or aspects of: {topic}",
                metadata={"task_type": "research", "complexity_tier": "mid"},
            ),
            AgentTask(
                id="research-2",
                prompt=f"What are practical implications or applications of: {topic}",
                metadata={"task_type": "research", "complexity_tier": "mid"},
            ),
        ]
