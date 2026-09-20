from core.models import AgentResult, AgentTask


class DedupeMergeAggregator:
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


class LLMSynthesisAggregator:
    MAX_FINDING_CHARS = 1500
    MAX_TOTAL_FINDING_CHARS = 6000

    def __init__(self, providers: dict, default_model: str | None = None,
                 synthesis_prompt_template: str | None = None):
        self.providers = providers
        self.default_model = default_model
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

        per_finding = max(200, self.MAX_TOTAL_FINDING_CHARS // max(1, len(successful)))
        per_finding = min(per_finding, self.MAX_FINDING_CHARS)

        bounded = [self._truncate(str(r.output), per_finding) for r in successful]
        total = sum(len(b) for b in bounded)
        if total > self.MAX_TOTAL_FINDING_CHARS:
            ratio = self.MAX_TOTAL_FINDING_CHARS / total
            bounded = [self._truncate(b, max(150, int(len(b) * ratio))) for b in bounded]

        findings_text = "\n\n".join(
            f"--- Finding from {r.provider_used or 'unknown'} ---\n{t}"
            for r, t in zip(successful, bounded)
        )
        prompt = self.template.format(task_prompt=task.prompt, findings=findings_text)

        import time as _time
        for name, provider in self.providers.items():
            if _time.time() < getattr(provider, "rate_limited_until", 0):
                continue
            model = self.default_model or provider.default_model
            if not model:
                continue
            try:
                api_key = await provider.key_pool.get_key()
                response = await provider.call(model, prompt, api_key)
                return AgentResult(
                    task_id=task.id,
                    success=True,
                    output=response.text,
                    latency_sec=sum(r.latency_sec for r in successful),
                    tokens_used=(response.tokens_used or 0) + sum(r.tokens_used or 0 for r in successful),
                )
            except Exception as e:
                err_text = str(e)
                if "429" in err_text or "Too Many Requests" in err_text or "rate limit" in err_text.lower():
                    provider.mark_rate_limited(cooldown_sec=30.0)
                continue

        return AgentResult(
            task_id=task.id,
            success=True,
            output="(Synthesis skipped — all providers rate-limited.)\n\n" + findings_text,
            latency_sec=sum(r.latency_sec for r in successful),
            tokens_used=sum(r.tokens_used or 0 for r in successful),
        )