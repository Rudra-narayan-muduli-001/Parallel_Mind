from core.aggregation.base import AggregationStrategy
from core.models import AgentResult, AgentTask


class ConcatAggregator(AggregationStrategy):
    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        outputs = [r.output for r in results if r.success and r.output]
        combined = "\n\n---\n\n".join(str(o) for o in outputs)
        return AgentResult(
            task_id=task.id,
            success=len(outputs) > 0,
            output=combined or None,
            error=None if outputs else "No successful results to concatenate",
            latency_sec=sum(r.latency_sec for r in results),
            tokens_used=sum(r.tokens_used or 0 for r in results),
        )


class FirstSuccessAggregator(AggregationStrategy):
    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        for r in results:
            if r.success:
                return r
        return AgentResult(
            task_id=task.id,
            success=False,
            error="No successful result among candidates",
            latency_sec=sum(r.latency_sec for r in results),
        )


class VotingAggregator(AggregationStrategy):
    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        successful = [r for r in results if r.success and r.output]
        if not successful:
            return AgentResult(task_id=task.id, success=False, error="No successful results to vote on")

        from collections import Counter

        counts: Counter[str] = Counter()
        for r in successful:
            key = str(r.output).strip()
            counts[key] += 1

        best = counts.most_common(1)[0]
        return AgentResult(
            task_id=task.id,
            success=True,
            output=best[0],
            latency_sec=sum(r.latency_sec for r in successful),
            tokens_used=sum(r.tokens_used or 0 for r in successful),
        )


class DedupeMergeAggregator(AggregationStrategy):
    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        seen = set()
        parts = []
        for r in results:
            if not r.success or not r.output:
                continue
            text = str(r.output).strip()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)

        combined = "\n\n---\n\n".join(parts)
        return AgentResult(
            task_id=task.id,
            success=len(parts) > 0,
            output=combined or None,
            error=None if parts else "No unique successful results",
            latency_sec=sum(r.latency_sec for r in results),
            tokens_used=sum(r.tokens_used or 0 for r in results),
        )


class LLMSynthesisAggregator(AggregationStrategy):
    # Per-finding char budget — keeps the synthesis prompt bounded so we don't
    # exceed provider context windows (Groq returned 413 on large research runs).
    MAX_FINDING_CHARS = 1500
    # Max total findings chars (≈ tokens × 4 for English).
    MAX_TOTAL_FINDING_CHARS = 6000

    def __init__(self, provider, model: str, synthesis_prompt_template: str | None = None):
        self.provider = provider
        self.model = model
        self.template = synthesis_prompt_template or (
            "Synthesize the following research findings into a coherent answer.\n"
            "Original question: {task_prompt}\n\n"
            "Findings:\n{findings}\n\n"
            "Provide a consolidated, well-structured response."
        )

    @classmethod
    def _truncate(cls, text: str, budget: int) -> str:
        if len(text) <= budget:
            return text
        return text[:budget].rsplit(" ", 1)[0] + "…"

    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        successful = [r for r in results if r.success and r.output]
        if not successful:
            return AgentResult(task_id=task.id, success=False, error="No successful results to synthesize")

        # Bound each finding, then bound the total so the synthesis prompt
        # always fits within reasonable provider context windows.
        per_finding = max(200, cls.MAX_TOTAL_FINDING_CHARS // max(1, len(successful)))
        per_finding = min(per_finding, cls.MAX_FINDING_CHARS)

        bounded = [cls._truncate(str(r.output), per_finding) for r in successful]
        # Final trim in case total still exceeds budget after equal slicing.
        total = sum(len(b) for b in bounded)
        if total > cls.MAX_TOTAL_FINDING_CHARS:
            ratio = cls.MAX_TOTAL_FINDING_CHARS / total
            bounded = [cls._truncate(b, max(150, int(len(b) * ratio))) for b in bounded]

        findings_text = "\n\n".join(
            f"--- Finding from {r.provider_used or 'unknown'} ---\n{t}"
            for r, t in zip(successful, bounded)
        )
        prompt = self.template.format(task_prompt=task.prompt, findings=findings_text)

        try:
            api_key = await self.provider.key_pool.get_key()
            response = await self.provider.call(self.model, prompt, api_key)
            return AgentResult(
                task_id=task.id,
                success=True,
                output=response.text,
                latency_sec=sum(r.latency_sec for r in successful),
                tokens_used=(response.tokens_used or 0) + sum(r.tokens_used or 0 for r in successful),
            )
        except (KeyError, ValueError, OSError) as e:
            return AgentResult(
                task_id=task.id,
                success=False,
                error=f"Synthesis LLM call failed: {e}",
                latency_sec=sum(r.latency_sec for r in successful),
            )
