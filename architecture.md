# ParallelMind — System Architecture

## 1. Overview

ParallelMind is a lightweight, Python-based framework for launching multiple AI agents
concurrently against multiple LLM providers, with automatic load distribution, failover,
and pluggable result aggregation.

It powers two initial pipelines:
- **Research Pipeline** — decomposes a topic into sub-questions, answers them in parallel, synthesizes a report.
- **Code Review Pipeline** — splits a repo into file-level tasks, reviews them in parallel, merges findings.

Both pipelines share the same core engine (Planner/Splitter → Parallel Executor → Aggregator),
making the system extensible to future pipelines (e.g., test generation, documentation agents)
without touching the core.

---

## 2. Design Principles

1. **Isolation by default** — agents do not share mutable state unless explicitly opted in. This eliminates most race conditions by design, not by discipline.
2. **Fail small, not big** — a single agent/task failure must never crash a batch. Failures are caught, logged, and isolated to a single `AgentResult`.
3. **No wasted latency on backoff when alternatives exist** — if a provider/key/model fails, the system immediately rotates to the next available candidate rather than sleeping and retrying the same broken target.
4. **Routing is explicit, not magical** — the user always knows (or explicitly chooses) which strategy decided where a task went: static rules, an LLM meta-router, or manual selection.
5. **Config over code** — providers, models, and routing tiers are defined in config files (`.env`, `model_catalog.yaml`, `routing_table.py`), not hardcoded inside business logic.
6. **Strategy pattern everywhere it matters** — routing policies and aggregation strategies are interchangeable, pluggable objects, never inline if/else chains.

---

## 3. High-Level Architecture

```

┌──────────────────────────────────────────────────────────────────┐
│                          CLI Layer                                │
│   Default / Manual Wizard → builds a RunConfig                    │
└───────────────────────────┬────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Pipeline Layer                             │
│  ┌───────────────┐                        ┌────────────────────┐  │
│  │ Research       │                        │ Code Review        │  │
│  │ Planner        │                        │ Splitter           │  │
│  │ (topic→tasks)  │                        │ (repo→tasks)       │  │
│  └───────┬───────┘                        └─────────┬──────────┘  │
└──────────┼─────────────────────────────────────────┼──────────────┘
           │              List[AgentTask]              │
           └───────────────────┬────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Orchestrator                                │
│   asyncio.gather + concurrency semaphore                          │
│   Dispatches each AgentTask to the Executor concurrently          │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Router (Policy Layer)                          │
│  RuleBasedPolicy | ManualPolicy | LLMRouterPolicy                 │
│  → returns ORDERED candidate list [(provider, model), ...]        │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AgentExecutor                                   │
│  For each candidate in order:                                     │
│    - check CircuitBreaker (provider level)                        │
│    - pull next key from APIKeyPool (round robin)                  │
│    - attempt call with timeout                                    │
│    - on failure → immediately try next candidate (no backoff)     │
│    - on success → return AgentResult                              │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Provider Layer                                  │
│  OpenAICompatibleProvider (OpenAI, Groq, OpenRouter, NVIDIA NIM,  │
│                             OpenCode Zen)                         │
│  AnthropicProvider (Anthropic)                                     │
│  Each provider owns: APIKeyPool + CircuitBreaker                  │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
                     External LLM APIs
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Aggregation Layer                               │
│  ConcatAggregator | DedupeMergeAggregator | VotingAggregator |    │
│  LLMSynthesisAggregator | FirstSuccessAggregator                  │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
                     Final Output
```

---

## 4. Component Responsibilities

### 4.1 CLI Layer (`cli/`)
- Entry point for all user interaction (`typer`-based).
- Runs the Default/Manual wizard (`wizard.py`) which produces a `RunConfig`.
- `RunConfig` determines which `RoutingPolicy` and generation parameters (effort) are used for the entire run.
- Never contains business logic — only collects input and delegates to pipelines.

### 4.2 Pipeline Layer (`pipelines/`)
- Converts a high-level user request (a topic, a repo path) into a `List[AgentTask]`.
- **Research:** `planner.py` makes one LLM call to decompose a topic into sub-questions, each tagged with a `complexity_tier`.
- **Code Review:** `splitter.py` parses a repo (no LLM call) and assigns a `complexity_tier` per file using a local heuristic (line count).
- Each pipeline selects its `AggregationStrategy` (Research → `LLMSynthesisAggregator`, Code Review → `DedupeMergeAggregator`).

### 4.3 Orchestrator (`core/orchestrator.py`)
- Owns the concurrency cap via `asyncio.Semaphore`.
- Dispatches all `AgentTask`s concurrently using `asyncio.gather(..., return_exceptions=True)`.
- Guarantees one failing task never terminates the batch.
- Has no knowledge of providers, routing, or aggregation — purely a concurrency/dispatch layer.

### 4.4 Router (`core/router/`)
- Central decision point: **"which (provider, model) candidates should this task try, and in what order?"**
- Returns an **ordered list**, not a single choice — this enables immediate failover downstream.
- Three interchangeable policies (see `agents.md` for details):
  - `RuleBasedPolicy` — static 5-tier lookup table, zero extra API cost (**default**).
  - `ManualPolicy` — built from CLI wizard selections (explicit provider/model/effort).
  - `LLMRouterPolicy` — a meta LLM call ranks candidates dynamically (optional, opt-in).
- `RotatingCandidatePool` ensures successive tasks rotate their starting candidate, spreading load evenly instead of hammering the first entry.

### 4.5 Executor (`core/executor.py`)
- Receives a task + ordered candidate list + generation params.
- Walks the candidate list **in order**, skipping instantly (no sleep/backoff) on:
  - Open circuit breaker for a provider
  - No healthy API key in that provider's pool
  - Actual call failure/timeout/empty response
- On the first success, returns immediately.
- If all candidates are exhausted, returns a failed `AgentResult` — isolated and does not propagate to other tasks.

### 4.6 Provider Layer (`core/providers/`)
- `BaseProvider` — abstract interface all providers implement (`call()`, `is_healthy()`, `is_enabled()`).
- `OpenAICompatibleProvider` — single implementation reused for 5 providers (OpenAI, Groq, OpenRouter, NVIDIA NIM, OpenCode Zen) since they share the same `/chat/completions` schema; differs only by `base_url`/`api_keys`/`default_model` from config.
- `AnthropicProvider` — separate implementation due to differing `/v1/messages` schema.
- Each provider instance owns exactly one `APIKeyPool` and one `CircuitBreaker`.
- `ModelCatalog` (`model_catalog.py`) loads `config/model_catalog.yaml` and exposes queryable model lists — used by both the CLI wizard (for menus) and startup validation (routing table consistency check).

### 4.7 APIKeyPool (`core/providers/key_pool.py`)
- Round-robins across all configured keys for a provider.
- Tracks per-key health: failure count, cooldown timestamp.
- A key that fails repeatedly is marked unhealthy and skipped until cooldown expires.
- `get_key()` raises `NoAvailableKeyError` if all keys are unhealthy — signals the Executor to skip this provider and move to the next candidate.

### 4.8 CircuitBreaker (`core/providers/circuit_breaker.py`)
- One instance per provider (key-level health is handled by `APIKeyPool`).
- States: `CLOSED` (normal) → `OPEN` (provider disabled after N consecutive failures) → `HALF_OPEN` (after cooldown, allows a trial request) → back to `CLOSED` on success.
- Prevents wasting requests on a provider that is clearly down.

### 4.9 Aggregation Layer (`core/aggregation/`)
- `AggregationStrategy` is an abstract interface — every aggregator implements `aggregate(task, results)`.
- Strategy is chosen **per pipeline**, not globally:
  - Research → `LLMSynthesisAggregator` (one more LLM call to merge findings into a coherent report).
  - Code Review → `DedupeMergeAggregator` (pure Python, dedupes by exact text match, no extra LLM cost).
- Other strategies (`VotingAggregator`, `FirstSuccessAggregator`, `ConcatAggregator`) exist for future pipelines.

---

## 5. Data Flow — Single Task Lifecycle

```

AgentTask created by Pipeline (with metadata: task_type, complexity_tier)
        │
        ▼
Orchestrator acquires semaphore slot
        │
        ▼
Router.decide(task) → [(provider_a, model_x), (provider_b, model_y), (provider_c, model_z)]
        │
        ▼
Executor iterates candidates:
   → provider_a: circuit OPEN → skip immediately
   → provider_b: circuit CLOSED, key_pool.get_key() → key_2 (round robin)
                 → call fails (timeout) → report_failure(key_2) → skip immediately
   → provider_c: circuit CLOSED, key_pool.get_key() → key_1
                 → call succeeds → report_success(key_1) → RETURN
        │
        ▼
AgentResult(success=True, output=..., latency_sec=...)
        │
        ▼
Orchestrator collects into List[AgentResult] (via asyncio.gather)
        │
        ▼
Pipeline's AggregationStrategy.aggregate(results) → Final Output

```

---

## 6. Configuration Architecture

| File | Purpose |
|---|---|
| `.env` | Secrets: API keys (comma-separated per provider), base URLs, default models, global settings (concurrency, timeouts, circuit breaker thresholds, routing mode) |
| `config/settings.py` | `pydantic-settings` loader — typed access to `.env`, validated at startup |
| `config/model_catalog.yaml` | Inventory of all available models per provider — used for CLI menus and startup validation |
| `config/routing_table.py` | Static 5-tier (`low/mid/high/xhigh/max`) per task_type lookup table for `RuleBasedPolicy` |
| `config/effort_presets.py` | Maps `"low"`/`"high"` effort (Manual mode) to generation parameters (temperature, max_tokens, timeout) |

**Startup validation:** `utils/validation.py` cross-checks every model ID referenced in `routing_table.py` actually exists in `model_catalog.yaml`. This fails fast on typos instead of surfacing as a cryptic API error mid-run.

---

## 7. Concurrency Model

- **Why asyncio, not threading/multiprocessing:** All agent work is I/O-bound (waiting on HTTP calls to LLM APIs). `asyncio` gives high concurrency without the overhead of OS threads or processes.
- **Concurrency cap:** `asyncio.Semaphore(max_concurrency)` in the Orchestrator prevents overwhelming providers and hitting rate limits, independent of how many tasks exist.
- **Timeouts:** Every candidate attempt inside the Executor is wrapped in `asyncio.wait_for()` — a hung request cannot block the whole batch indefinitely.
- **No shared mutable state by default:** Each task/agent execution is fully independent (map-reduce style). Optional `SharedContext` (lock-protected) exists for future cross-agent awareness features but is not used in v1 pipelines.

---

## 8. Failure Handling Architecture

| Failure Type | Handled By | Behavior |
|---|---|---|
| Single API call hangs | `asyncio.wait_for()` in Executor | Timeout → candidate failure → next candidate |
| Bad/expired API key | `APIKeyPool` | Key marked unhealthy after threshold, skipped in future rotations |
| Provider fully down | `CircuitBreaker` | Provider skipped entirely until cooldown expires, trial request in `HALF_OPEN` |
| Model returns malformed/empty output | Agent's output parser raises → caught by Executor | Candidate failure → next candidate |
| All candidates exhausted for one task | Executor | Returns failed `AgentResult` for that task only |
| One task fails entirely | Orchestrator (`asyncio.gather(return_exceptions=True)`) | Batch continues; failure isolated to that single result |

No retry-with-backoff is used when redundant candidates exist — failover is immediate.

---

## 9. Extensibility Points

| To add... | Touch these files only |
|---|---|
| A new LLM provider (OpenAI-compatible) | `.env`, `config/model_catalog.yaml` — zero new Python code needed |
| A new LLM provider (different schema) | New file in `core/providers/`, implement `BaseProvider` |
| A new routing strategy | New class in `core/router/policies.py` implementing `RoutingPolicy` |
| A new aggregation strategy | New class in `core/aggregation/strategies.py` implementing `AggregationStrategy` |
| A new pipeline (e.g., test generation) | New folder in `pipelines/`, reusing Orchestrator/Router/Executor/Aggregation layers untouched |

---

## 10. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Async HTTP | `httpx` |
| Data validation | `pydantic` / `pydantic-settings` |
| CLI | `typer` + `rich` |
| Config parsing | `PyYAML` |
| Logging | `pythonjsonlogger` (optional) |
| Testing | `pytest` + `pytest-asyncio` |

---

## 11. Non-Goals (v1)

- No persistent job queue (Redis/Kafka) — in-memory `asyncio` orchestration only.
- No web UI/dashboard — CLI only.
- No cross-agent shared memory in default pipelines — isolation by design.
- No multi-language runtime — Python only.
