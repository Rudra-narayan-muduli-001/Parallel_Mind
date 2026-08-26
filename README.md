```
██████╗  █████╗ ██████╗  █████╗ ██╗     ██╗     ███████╗██╗     ███╗   ███╗██╗███╗   ██╗██████╗
██╔══██╗██╔══██╗██╔══██╗██╔══██╗██║     ██║     ██╔════╝██║     ████╗ ████║██║████╗  ██║██╔══██╗
██████╔╝███████║██████╔╝███████║██║     ██║     █████╗  ██║     ██╔████╔██║██║██╔██╗ ██║██║  ██║
██╔═══╝ ██╔══██║██╔══██╗██╔══██║██║     ██║     ██╔══╝  ██║     ██║╚██╔╝██║██║██║╚██╗██║██║  ██║
██║     ██║  ██║██║  ██║██║  ██║███████╗███████╗███████╗███████╗██║ ╚═╝ ██║██║██║ ╚████║██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝
```

<p align="center">
  <strong>🚀 Lightweight parallel AI agent orchestration framework</strong><br>
  Route tasks across multiple LLM providers with round-robin failover, circuit breakers, and configurable routing policies.
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Tests-45%20passed-brightgreen.svg" alt="Tests: 45 passed">
  <img src="https://img.shields.io/badge/Async-asyncio-7B5FA6.svg" alt="Async asyncio">
  <img src="https://img.shields.io/badge/Web-FastAPI%20%2B%20SSE-009688.svg" alt="Web: FastAPI + SSE">
  <img src="https://img.shields.io/badge/CLI-Typer%20%2B%20Rich-F37626.svg" alt="CLI: Typer + Rich">
</p>

---

<div align="center">

### 📋 Table of Contents

| | | |
|---|---|---|
| [✨ Features](#-features) | [🔌 Supported Providers](#-supported-providers) | [⚡ Quick Start](#-quick-start) |
| [🖥️ CLI Commands](#️-cli-commands) | [⚙️ Configuration](#️-configuration) | [🔀 Pipelines](#-pipelines) |
| [🧩 Aggregation Strategies](#-aggregation-strategies) | [🧪 Testing](#-testing) | [📁 Project Structure](#-project-structure) |
| [🤝 Contributing](#-contributing) | [📄 License](#-license) | [🏗️ Architecture](#️-architecture) |

</div>

---

## ✨ Features

| Category | Details |
|---|---|
| 🔗 **Providers** | OpenAI, Anthropic, Groq, OpenRouter, NVIDIA NIM, OpenCode Zen |
| 🔄 **Live Model Discovery** | Fetches the current model list from each provider's `/models` API at startup — no stale config |
| 🔑 **Key Management** | Round-robin across API keys with auto-recovery after cooldown |
| 🛡️ **Failover** | Immediate failover across providers *and* models — no delay between attempts |
| ⏳ **Rate-Limit Handling** | 429-aware: per-provider cooldown, parallel tasks skip throttled providers instantly |
| 🧯 **Circuit Breaker** | Per-provider circuit breaker with automatic key health tracking |
| 🎯 **Routing** | 5-tier complexity routing (low / mid / high / xhigh / max) per task type |
| 🆓 **Free-First Defaults** | Ships configured for free-tier models (`DEFAULT_PROVIDER`, `FREE_MODELS_ONLY`) — works without paid keys |
| 🧭 **Routing Modes** | Rule-based (default), Manual (user-selected), LLM-based (meta-router) |
| 💬 **CLI** | Interactive wizard with Default and Manual modes |
| 🌐 **Web UI** | Chat-style dashboard with SSE streaming, conversation history (localStorage), markdown rendering |
| 👁️ **Parallel Viz** | Real-time visualization of each parallel agent task — start/finish, provider/model used, latency |
| 📊 **Pipelines** | Research (topic decomposition + parallel synthesis), Code Review (file-aware parallel review) |

---

## 🔌 Supported Providers

| Provider | Base URL | Auth |
|---|---|---|
| 🟢 **OpenAI** | `https://api.openai.com/v1` | API Key |
| 🟠 **Anthropic** | `https://api.anthropic.com` | API Key |
| 🟣 **Groq** | `https://api.groq.com/openai/v1` | API Key |
| 🔵 **OpenRouter** | `https://openrouter.ai/api/v1` | API Key |
| 🟢 **NVIDIA NIM** | `https://integrate.api.nvidia.com/v1` | API Key |
| ⚫ **OpenCode Zen** | `https://opencode.ai/zen/v1` | API Key |

> 💡 **Tip:** Only providers with at least one API key configured in `.env` are registered at runtime. Empty keys = auto-disabled, no code change needed.

---

## ⚡ Quick Start

```bash
# 1️⃣ Install dependencies
pip install -r requirements.txt

# 2️⃣ Configure your API keys
cp .env.example .env
# ✏️ Edit .env — fill in keys for the providers you use
# (works out of the box with only a free OpenCode Zen key)

# 3️⃣ Launch the web UI
python run.py
# 🌐 Open http://127.0.0.1:8080 — chat-style research + parallel agent viz

# 4️⃣ Or use the CLI
parallelmind research "Explain quantum computing fundamentals"
parallelmind review ./src

# 5️⃣ Check provider status / validate config
parallelmind providers
parallelmind config
```

> 🎮 Run `parallelmind` without arguments to enter the interactive CLI wizard.
> 🌐 `python run.py` or `parallelmind web` both start the dashboard at http://127.0.0.1:8080.
> 🚀 Or simply: **`run.py`** → type a topic in the chat box, hit Enter, watch the parallel agents run live.

---

## 🖥️ CLI Commands

| Command | Description |
|---|---|
| 📚 `parallelmind research <topic>` | Decompose a topic into sub-questions, research in parallel, synthesize a report |
| 🔍 `parallelmind review <path>` | Review all supported source files in a directory in parallel |
| 🌐 `parallelmind web` | Launch the web dashboard (default: http://127.0.0.1:8080) |
| 📡 `parallelmind providers` | Show configured providers and their health status |
| ✅ `parallelmind config` | Validate routing table, show settings, check model catalog |

---

## ⚙️ Configuration

| File | Purpose |
|---|---|
| 📝 `.env` | API keys (comma-separated), base URLs, default models, orchestration settings |
| 🧾 `config/settings.py` | `pydantic-settings` loader with typed access to `.env` |
| 📦 `config/model_catalog.yaml` | Fallback model inventory — augmented by **live discovery** from each provider's API |
| 🗺️ `config/routing_table.py` | 5-tier routing policies per task type for `RuleBasedPolicy` |
| 🎚️ `config/effort_presets.py` | Low/High/X-High/Max effort presets (temperature, max_tokens, timeout) |

### Key `.env` settings

| Variable | Default | Purpose |
|---|---|---|
| `DEFAULT_PROVIDER` | `opencode_zen` | Provider whose models are preferred for all tasks |
| `FREE_MODELS_ONLY` | `true` | Restrict candidates to free-tier models (`-free` / `:free`) |
| `DEFAULT_MAX_CONCURRENCY` | `3` | Max parallel agent tasks per run |
| `RATE_LIMIT_COOLDOWN_SEC` | `30` | How long to skip a provider after a 429 |
| `ROUTING_MODE` | `rule_based` | Also supports `llm_based` and `manual` |

> 💡 **Free-first design:** With the defaults, ParallelMind routes everything through free-tier models of one provider and fails over instantly between them — so it works without any paid API keys.

---

## 🔀 Pipelines

### 📚 Research Pipeline (`pipelines/research/`)

```
┌─────────┐    ┌────────────────────┐     ┌────────────────────┐    ┌────────────────┐    ┌─────────┐
│  Topic  │──▶│ Planner (LLM       │──▶│ Parallel Researcher│──▶│ LLM Synthesis │──▶│ Report  │
└─────────┘    │ decomposition)     │     │ Agents (5x conc.)  │    │ Aggregator     │    └─────────┘
               └────────────────────┘     └────────────────────┘    └────────────────┘
```

- `ResearchPlanner` decomposes a topic into 3-5 sub-questions with complexity tiers
- `ResearcherAgent` answers each sub-question concurrently
- `LLMSynthesisAggregator` merges findings into a coherent report

### 🔍 Code Review Pipeline (`pipelines/code_review/`)

```
┌────────┐    ┌────────────────────┐     ┌────────────────────┐    ┌────────────────┐     ┌─────────┐
│  Path  │──▶│ Splitter (file +   │──▶│ Parallel Reviewer  │──▶│ Dedupe Merge   │──▶│ Report  │
└────────┘    │ tier assignment)   │     │ Agents (5x conc.)  │    │ Aggregator     │     └─────────┘
              └────────────────────┘     └────────────────────┘    └────────────────┘
```

- `CodeReviewSplitter` discovers source files and assigns complexity tiers by line count
- `CodeReviewerAgent` reviews each file for bugs, security, and best practices
- `DedupeMergeAggregator` combines findings without duplicates

---

## 🧩 Aggregation Strategies

| Strategy | Behavior | Used By |
|---|---|---|
| 🧠 `LLMSynthesisAggregator` | Merges results with one final LLM call; walks every provider for failover, falls back to raw findings on 429 | Research pipeline |
| 🔗 `DedupeMergeAggregator` | Concatenates unique results (pure Python) | Code review pipeline |
| 🗳️ `VotingAggregator` | Picks most common output across candidates | Future use |
| ⚡ `FirstSuccessAggregator` | Returns first successful result | Future use |
| 📜 `ConcatAggregator` | Simple concatenation of all outputs | Future use |

---

## 🧪 Testing

```bash
pytest
```

✅ 45 tests total: **34** in `tests/`, **11** in `cli/`.

> 🛠️ Also run: `ruff check .` for linting, `mypy .` for type checking.

---

## 📁 Project Structure

```
Parallel Mind/
├── 📂 cli/                  Typer CLI: main, wizard, display, commands
├── 📂 config/               Settings, routing table, effort presets, model catalog
├── 📂 core/
│   ├── 📂 aggregation/      Aggregation strategies (Synthesis, Dedupe, Voting, etc.)
│   ├── 📂 providers/        LLM providers + live model discovery + key pool + circuit breaker
│   ├── 📂 router/           Routing policies (rule-based, manual, LLM-based)
│   └── 📂 state/            Shared context (lock-protected, optional)
├── 📂 pipelines/
│   ├── 📂 research/         Research pipeline (planner + researcher + aggregator)
│   └── 📂 code_review/      Code review pipeline (splitter + reviewer + aggregator)
├── 📂 web/                  FastAPI web server: SSE streaming, chat UI, parallel viz
│   ├── 📄 server.py         REST + SSE endpoints, orchestrator instrumentation
│   ├── 📂 templates/        Jinja2 dashboard (chat interface)
│   └── 📂 static/           CSS + JS (markdown rendering, viz, history)
├── 📂 utils/                Logging and validation utilities
├── 📂 tests/                Core unit tests
├── 📄 run.py                One-command launcher for the web UI
├── 📄 architecture.md       Full system architecture document
├── 📄 agents.md             Agent design reference
└── 📄 requirements.txt      Python dependencies
```

---

## 🌐 Web Dashboard

Launch with `python run.py` and open **http://127.0.0.1:8080**:

- 💬 **Chat-style research** — type a topic, hit Enter, results stream in as rendered Markdown
- 👁️ **Live parallel agent visualization** — each sub-question appears as a task card the moment its agent starts; watch progress bars, then completion badges showing provider/model/latency (`groq/openai/gpt-oss-20b 4.4s`)
- 🕘 **Conversation history** — stored in your browser (localStorage), click to reload any past session, delete individually or clear all
- ➕ **New Conversation** button for fresh sessions
- 🎚️ **Manual mode** — pick exact providers/models and effort level (Low / High / X-High / Max)
- 📡 **Providers tab** — health status of every configured provider
- ⚙️ **Config tab** — live settings plus full model catalog with a Refresh button that re-fetches models from provider APIs on demand

---

## 🤝 Contributing

Pull requests and issues are welcome.

> 🌟 If you find this project useful, consider giving it a **star**! ⭐

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🏗️ Architecture

See [`architecture.md`](architecture.md) for the full system architecture document and [`agents.md`](agents.md) for agent design details.