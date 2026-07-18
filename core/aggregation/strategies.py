from core.models import AgentTask, AgentResult
from core.aggregation.base import AggregationStrategy


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
    def __init__(self, provider, model: str, synthesis_prompt_template: str | None = None):
        self.provider = provider
        self.model = model
        self.template = synthesis_prompt_template or (
            "Synthesize the following research findings into a coherent answer.\n"
            "Original question: {task_prompt}\n\n"
            "Findings:\n{findings}\n\n"
            "Provide a consolidated, well-structured response."
        )

    async def aggregate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        successful = [r for r in results if r.success and r.output]
        if not successful:
            return AgentResult(task_id=task.id, success=False, error="No successful results to synthesize")

        findings_text = "\n\n".join(
            f"--- Finding from {r.provider_used or 'unknown'} ---\n{r.output}"
            for r in successful
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
