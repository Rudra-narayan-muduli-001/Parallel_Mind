ROUTING_TABLE = {
    # ---------------- RESEARCH ----------------
    ("research", "low"): [
        ("groq", "llama-3.1-8b-instant"),
        ("ollama_cloud", "llama3.1:8b"),
    ],
    ("research", "mid"): [
        ("groq", "llama-3.1-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.1-70b-instruct"),
        ("nvidia_nim", "meta/llama-3.1-70b-instruct"),
    ],
    ("research", "high"): [
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

    # ---------------- CODE REVIEW ----------------
    ("code_review", "low"): [
        ("groq", "llama-3.1-8b-instant"),
        ("ollama_cloud", "llama3.1:8b"),
    ],
    ("code_review", "mid"): [
        ("groq", "llama-3.1-70b-versatile"),
        ("nvidia_nim", "meta/llama-3.1-70b-instruct"),
    ],
    ("code_review", "high"): [
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

DEFAULT_TIER = "mid"