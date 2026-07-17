from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # OpenAI
    openai_api_keys: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_keys: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_default_model: str = "claude-3-5-sonnet-20241022"

    # Groq
    groq_api_keys: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_default_model: str = "llama-3.1-70b-versatile"

    # OpenRouter
    openrouter_api_keys: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "meta-llama/llama-3.1-70b-instruct"

    # NVIDIA NIM
    nvidia_nim_api_keys: str = ""
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_default_model: str = "llama-3.3-nemotron-super-49b-v1.5"

    # OpenCode Zen
    opencode_zen_api_keys: str = ""
    opencode_zen_base_url: str = "https://opencode.ai/zen/v1"
    opencode_zen_default_model: str = ""

    # Orchestration
    default_max_concurrency: int = 5
    default_timeout_sec: int = 60
    circuit_breaker_fail_threshold: int = 5
    circuit_breaker_reset_sec: int = 60

    # Routing
    routing_mode: str = "rule_based"  # rule_based | llm_based | manual
    router_model_provider: str = "groq"
    router_model_name: str = "llama-3.1-8b-instant"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @staticmethod
    def _split_keys(raw: str) -> list[str]:
        return [k.strip() for k in raw.split(",") if k.strip()]

    def get_provider_configs(self) -> dict:
        return {
            "openai": {
                "api_keys": self._split_keys(self.openai_api_keys),
                "base_url": self.openai_base_url,
                "default_model": self.openai_default_model,
            },
            "anthropic": {
                "api_keys": self._split_keys(self.anthropic_api_keys),
                "base_url": self.anthropic_base_url,
                "default_model": self.anthropic_default_model,
            },
            "groq": {
                "api_keys": self._split_keys(self.groq_api_keys),
                "base_url": self.groq_base_url,
                "default_model": self.groq_default_model,
            },
            "openrouter": {
                "api_keys": self._split_keys(self.openrouter_api_keys),
                "base_url": self.openrouter_base_url,
                "default_model": self.openrouter_default_model,
            },
            "nvidia_nim": {
                "api_keys": self._split_keys(self.nvidia_nim_api_keys),
                "base_url": self.nvidia_nim_base_url,
                "default_model": self.nvidia_nim_default_model,
            },
            "opencode_zen": {
                "api_keys": self._split_keys(self.opencode_zen_api_keys),
                "base_url": self.opencode_zen_base_url,
                "default_model": self.opencode_zen_default_model,
            },
        }


settings = Settings()