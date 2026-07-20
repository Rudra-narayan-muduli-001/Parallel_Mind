```
PARALLEL MIND
```

# ParallelMind

Lightweight parallel AI agent orchestration framework. Routes tasks across multiple LLM providers with round-robin failover, interactive CLI wizard, and configurable routing policies.

## Features

- **Multi-provider support**: OpenAI, Anthropic, Groq, OpenRouter, NVIDIA NIM, OpenCode Zen
- **Dual-dimension round robin**: Rotates across both API keys and model names
- **Immediate failover**: No delay between candidate attempts — skip failed targets instantly
- **Interactive CLI wizard**: Default (tier-driven) or Manual (user-selected models) mode
- **5-tier complexity routing**: low / mid / high / xhigh / max per task type
- **Circuit breaker + key health tracking**: Automatic skip of failing providers/keys
- **Research pipeline**: Planner decomposes topics → parallel sub-question execution → LLM synthesis
- **Code review pipeline**: File-aware splitter → parallel review → deduplicated merge
- **Aggregation strategies**: Concat, FirstSuccess, Voting, DedupeMerge, LLMSynthesis

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
parallelmind research "your topic"
parallelmind review ./src
parallelmind providers
parallelmind config
```

Run `parallelmind` without arguments to enter the interactive CLI wizard.

## Configuration

- `.env` — API keys and provider settings
- `config/model_catalog.yaml` — Available models per provider
- `config/routing_table.py` — 5-tier routing policies per task type
- `config/effort_presets.py` — Low/High effort generation parameters

## Testing

```bash
pytest
```

41 tests total (30 in `tests/`, 11 in `cli/`).

## Contributing

Pull requests and issues are welcome.

## Architecture

See `architecture.md` for the full design document.
