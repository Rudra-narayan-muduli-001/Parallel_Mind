from core.providers.anthropic_provider import AnthropicProvider
from core.providers.base import BaseProvider
from core.providers.openai_compatible import OpenAICompatibleProvider

OPENAI_COMPATIBLE_PROVIDERS = {"openai", "groq", "openrouter", "nvidia_nim", "opencode_zen"}


def build_providers(settings) -> dict[str, BaseProvider]:
    """Only providers with at least one configured API key get registered.
    Empty API_KEYS in .env = provider automatically disabled, no code change needed."""

    providers: dict[str, BaseProvider] = {}
    provider_configs = settings.get_provider_configs()

    for name, cfg in provider_configs.items():
        if not cfg["api_keys"]:
            continue

        if name == "anthropic":
            providers[name] = AnthropicProvider(
                name=name,
                api_keys=cfg["api_keys"],
                base_url=cfg["base_url"],
                default_model=cfg["default_model"],
            )
        elif name in OPENAI_COMPATIBLE_PROVIDERS:
            providers[name] = OpenAICompatibleProvider(
                name=name,
                api_keys=cfg["api_keys"],
                base_url=cfg["base_url"],
                default_model=cfg["default_model"],
            )

    return providers
