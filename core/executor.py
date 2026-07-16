import asyncio
import time
import logging
from core.models import AgentResult

logger = logging.getLogger("parallelmind.executor")


class AgentExecutor:
    """Walks an ordered candidate list [(provider, model), ...] and attempts each
    in sequence. On any failure (circuit open, no healthy key, call error/timeout),
    immediately moves to the next candidate — no backoff/sleep between attempts."""

    def __init__(self, providers: dict, default_timeout: int = 60):
        self.providers = providers
        self.default_timeout = default_timeout

    async def run(self, agent, task, candidates: list[tuple[str, str]], gen_params: dict = None) -> AgentResult:
        gen_params = gen_params or {}
        timeout = gen_params.get("timeout_sec", self.default_timeout)

        if not candidates:
            return AgentResult(task_id=task.id, success=False, error="No candidates provided", latency_sec=0.0)

        last_error = "Unknown error"

        for provider_name, model in candidates:
            provider = self.providers.get(provider_name)
            if provider is None:
                last_error = f"Provider '{provider_name}' not configured"
                logger.debug(last_error)
                continue

            if not provider.breaker.allow_request():
                last_error = f"{provider_name}: circuit breaker OPEN"
                logger.debug(last_error)
                continue

            try:
                api_key = await provider.key_pool.get_key()
            except Exception as e:
                last_error = f"{provider_name}: no healthy API key ({e})"
                logger.debug(last_error)
                continue

            start = time.time()
            try:
                output = await asyncio.wait_for(
                    agent.execute(task, provider, model, api_key, gen_params),
                    timeout=timeout,
                )
                provider.breaker.record_success()
                provider.key_pool.report_success(api_key)
                return AgentResult(
                    task_id=task.id,
                    success=True,
                    output=output,
                    latency_sec=time.time() - start,
                    provider_used=provider_name,
                    model_used=model,
                )
            except Exception as e:
                provider.breaker.record_failure()
                provider.key_pool.report_failure(api_key)
                last_error = f"{provider_name}/{model} failed: {e}"
                logger.warning(f"Task {task.id}: {last_error} — trying next candidate")
                continue

        return AgentResult(task_id=task.id, success=False, error=last_error, latency_sec=0.0)