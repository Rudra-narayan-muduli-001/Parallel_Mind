from core.models import ComplexityTier

ROUTING_TABLE = {
    ("research", "low"): [
        ("groq", "openai/gpt-oss-120b"),
    ],
    ("research", "mid"): [
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "meta-llama/llama-3.1-70b-instruct"),
        ("nvidia_nim", "llama-3.3-nemotron-super-49b-v1.5"),
    ],
    ("research", "high"): [
        ("nvidia_nim", "nemotron-3-super-120b-a12b"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku-20241022"),
    ],
    ("research", "xhigh"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("research", "max"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("code_review", "low"): [
        ("groq", "openai/gpt-oss-120b"),
    ],
    ("code_review", "mid"): [
        ("groq", "openai/gpt-oss-120b"),
        ("nvidia_nim", "llama-3.3-nemotron-super-49b-v1.5"),
    ],
    ("code_review", "high"): [
        ("nvidia_nim", "nemotron-3-super-120b-a12b"),
        ("openai", "gpt-4o-mini"),
        ("openrouter", "meta-llama/llama-3.1-70b-instruct"),
    ],
    ("code_review", "xhigh"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
    ("code_review", "max"): [
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("openai", "gpt-4o"),
    ],
}

DEFAULT_TIER: ComplexityTier = "mid"
