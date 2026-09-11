import httpx

from core.providers.base import BaseProvider, LLMResponse, ModelInfo


class AnthropicProvider(BaseProvider):
    async def call(self, model: str, prompt: str, api_key: str, **gen_params) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": gen_params.get("max_tokens", 2048),
            "temperature": gen_params.get("temperature", 0.5),
            "messages": [{"role": "user", "content": prompt}],
        }
        timeout = gen_params.get("timeout_sec", 60)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            text = "".join(block["text"] for block in data["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise ValueError(f"Malformed response from anthropic: {data}") from e

        if not text or not text.strip():
            raise ValueError(f"Empty response from anthropic/{model}")

        tokens = None
        usage = data.get("usage")
        if usage:
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        return LLMResponse(text=text, raw=data, tokens_used=tokens)

    async def list_models(self) -> list[ModelInfo]:
        if not self.key_pool.keys:
            return []
        url = f"{self.base_url.rstrip('/')}/v1/models"
        try:
            api_key = await self.key_pool.get_key()
        except Exception:
            return []
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        out: list[ModelInfo] = []
        for entry in data.get("data", []) or []:
            mid = entry.get("id")
            if not mid:
                continue
            display = entry.get("display_name") or mid
            out.append(ModelInfo(id=mid, display_name=display))
        return out
