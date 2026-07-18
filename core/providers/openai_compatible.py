import httpx
from core.providers.base import BaseProvider, LLMResponse


class OpenAICompatibleProvider(BaseProvider):
    """Covers any provider exposing an OpenAI-style /chat/completions endpoint:
    OpenAI,
    Groq,
    OpenRouter,
    NVIDIA NIM,
    Ollama Cloud,
    OpenCode Zen."""


    async def call(self, model: str, prompt: str, api_key: str, **gen_params) -> LLMResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": gen_params.get("temperature", 0.5),
            "max_tokens": gen_params.get("max_tokens", 2048),
        }
        timeout = gen_params.get("timeout_sec", 60)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Malformed response from {self.name}: {data}") from e

        if not text or not text.strip():
            raise ValueError(f"Empty response from {self.name}/{model}")

        tokens = data.get("usage", {}).get("total_tokens")
        return LLMResponse(text=text, raw=data, tokens_used=tokens)
