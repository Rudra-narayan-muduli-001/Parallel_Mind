EFFORT_PRESETS = {
    "low": {
        "temperature": 0.3,
        "max_tokens": 1024,
        "reasoning_effort": "low",
        "timeout_sec": 30,
    },
    "high": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "reasoning_effort": "high",
        "timeout_sec": 90,
    },
    "xhigh": {
        "temperature": 0.8,
        "max_tokens": 8192,
        "reasoning_effort": "xhigh",
        "timeout_sec": 120,
    },
    "max": {
        "temperature": 1.0,
        "max_tokens": 16384,
        "reasoning_effort": "max",
        "timeout_sec": 180,
    },
}
