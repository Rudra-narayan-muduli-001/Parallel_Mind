import asyncio
import logging
import time

import httpx

from core.models import AgentResult

logger = logging.getLogger("parallelmind.executor")


class AgentExecutor:
    def __init__(self, providers: dict, default_timeout: int = 60):
        self.providers = providers
        self.default_timeout = default_timeout

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code == 429
        msg = str(exc)
        return "429" in msg or "Too Many Requests" in msg or "rate limit" in msg.lower()

    async def run(self, agent, task, candidates: list[tuple[str, str]], gen_params: dict | None = None) -> AgentResult:
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

            if time.time() < getattr(provider, "rate_limited_until", 0):
                logger.debug(f"Task {task.id}: {provider_name} in rate-limit cooldown, skipping")
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
                rate_limited = self._is_rate_limit_error(e)
                if not rate_limited:
                    provider.key_pool.report_failure(api_key)
                last_error = f"{provider_name}/{model} failed: {e}"
                logger.warning(f"Task {task.id}: {last_error} — trying next candidate")
                if rate_limited:
                    cooldown = gen_params.get("rate_limit_cooldown_sec", 30.0)
                    provider.mark_rate_limited(cooldown_sec=cooldown)
                    logger.warning(
                        f"{provider_name} hit 429 — cooling down for {cooldown}s "
                        f"(next task will skip this provider)"
                    )
                continue

        return AgentResult(task_id=task.id, success=False, error=last_error, latency_sec=0.0)
