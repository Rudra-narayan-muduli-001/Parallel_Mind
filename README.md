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
  <img src="https://img.shields.io/badge/Tests-41%20passed-brightgreen.svg" alt="Tests: 41 passed">
  <img src="https://img.shields.io/badge/Async-asyncio-7B5FA6.svg" alt="Async asyncio">
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
| 🔑 **Key Management** | Dual-dimension round robin across API keys and model names |
| 🛡️ **Failover** | Immediate failover — no delay between candidate attempts |
| 🧯 **Circuit Breaker** | Per-provider circuit breaker with automatic key health tracking |
| 🎯 **Routing** | 5-tier complexity routing (low / mid / high / xhigh / max) per task type |
| 🧭 **Routing Modes** | Rule-based (default), Manual (user-selected), LLM-based (meta-router) |
| 💬 **CLI** | Interactive wizard with Default and Manual modes |
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

# 3️⃣ Run a research pipeline
parallelmind research "Explain quantum computing fundamentals"

# 4️⃣ Run a code review
parallelmind review ./src

# 5️⃣ Check provider status
parallelmind providers

# 6️⃣ Validate configuration
parallelmind config
```

> 🎮 Run `parallelmind` without arguments to enter the interactive CLI wizard.

---

## 🖥️ CLI Commands

| Command | Description |
|---|---|
| 📚 `parallelmind research <topic>` | Decompose a topic into sub-questions, research in parallel, synthesize a report |
| 🔍 `parallelmind review <path>` | Review all supported source files in a directory in parallel |
| 📡 `parallelmind providers` | Show configured providers and their health status |
| ✅ `parallelmind config` | Validate routing table, show settings, check model catalog |

---

## ⚙️ Configuration

| File | Purpose |
|---|---|
| 📝 `.env` | API keys (comma-separated), base URLs, default models, orchestration settings |
| 🧾 `config/settings.py` | `pydantic-settings` loader with typed access to `.env` |
| 📦 `config/model_catalog.yaml` | Inventory of all available models per provider |
| 🗺️ `config/routing_table.py` | 5-tier routing policies per task type for `RuleBasedPolicy` |
| 🎚️ `config/effort_presets.py` | Low/High effort generation parameters (temperature, max_tokens, timeout) |

> ⚠️ **Note:** `ROUTING_MODE` supports `rule_based` (default), `llm_based`, and `manual`. The LLM router costs one extra API call per task.

---

## 🔀 Pipelines

### 📚 Research Pipeline (`pipelines/research/`)

```
┌─────────┐   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────┐   ┌─────────┐
│  Topic  │──▶│ Planner (LLM       │──▶│ Parallel Researcher│──▶│ LLM Synthesis  │──▶│ Report  │
└─────────┘   │ decomposition)     │   │ Agents (5x conc.) │   │ Aggregator     │   └─────────┘
              └────────────────────┘   └────────────────────┘   └────────────────┘
```

- `ResearchPlanner` decomposes a topic into 3-5 sub-questions with complexity tiers
- `ResearcherAgent` answers each sub-question concurrently
- `LLMSynthesisAggregator` merges findings into a coherent report

### 🔍 Code Review Pipeline (`pipelines/code_review/`)

```
┌────────┐   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────┐   ┌─────────┐
│  Path  │──▶│ Splitter (file +   │──▶│ Parallel Reviewer  │──▶│ Dedupe Merge   │──▶│ Report  │
└────────┘   │ tier assignment)   │   │ Agents (5x conc.)  │   │ Aggregator     │   └─────────┘
             └────────────────────┘   └────────────────────┘   └────────────────┘
```

- `CodeReviewSplitter` discovers source files and assigns complexity tiers by line count
- `CodeReviewerAgent` reviews each file for bugs, security, and best practices
- `DedupeMergeAggregator` combines findings without duplicates

---

## 🧩 Aggregation Strategies

| Strategy | Behavior | Used By |
|---|---|---|
| 🧠 `LLMSynthesisAggregator` | Merges results with one final LLM call | Research pipeline |
| 🔗 `DedupeMergeAggregator` | Concatenates unique results (pure Python) | Code review pipeline |
| 🗳️ `VotingAggregator` | Picks most common output across candidates | Future use |
| ⚡ `FirstSuccessAggregator` | Returns first successful result | Future use |
| 📜 `ConcatAggregator` | Simple concatenation of all outputs | Future use |

---

## 🧪 Testing

```bash
pytest
```

✅ 41 tests total: **30** in `tests/`, **11** in `cli/`.

> 🛠️ Also run: `ruff check .` for linting, `mypy .` for type checking.

---

## 📁 Project Structure

```
Parallel Mind/
├── 📂 cli/                  Typer CLI: main, wizard, display, commands
├── 📂 config/               Settings, routing table, effort presets, model catalog
├── 📂 core/
│   ├── 📂 aggregation/      Aggregation strategies (Concat, Dedupe, Voting, etc.)
│   ├── 📂 providers/        LLM provider implementations + key pool + circuit breaker
│   ├── 📂 router/           Routing policies (rule-based, manual, LLM-based)
│   └── 📂 state/            Shared context (lock-protected, optional)
├── 📂 pipelines/
│   ├── 📂 research/         Research pipeline (planner + researcher + aggregator)
│   └── 📂 code_review/      Code review pipeline (splitter + reviewer + aggregator)
├── 📂 utils/                Logging and validation utilities
├── 📂 tests/                Core unit tests
├── 📄 architecture.md       Full system architecture document
├── 📄 agents.md             Agent design reference
└── 📄 requirements.txt      Python dependencies
```

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