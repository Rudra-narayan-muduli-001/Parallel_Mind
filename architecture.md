# ParallelMind — System Architecture

## 1. Overview

ParallelMind is a lightweight, Python-based framework for launching multiple AI agents
concurrently against multiple LLM providers, with automatic load distribution, failover,
and pluggable result aggregation.

It powers two initial pipelines:
- **Research Pipeline** — decomposes a topic into sub-questions, answers them in parallel, synthesizes a report.
- **Code Review Pipeline** — splits a path into file-level tasks, reviews them in parallel, merges findings.

Both pipelines share the same core engine (Planner/Splitter → batch runner → Executor → Aggregator),
making the system extensible to future pipelines (e.g., test generation, documentation agents)
without touching the core.

---

## 2. Design Principles

1. **Isolation by default** — agents do not share mutable state unless explicitly opted in. This eliminates most race conditions by design, not by discipline.
2. **Fail small, not big** — a single agent/task failure must never crash a batch. Failures are caught, logged, and isolated to a single `AgentResult`.
3. **No wasted latency on backoff when alternatives exist** — if a provider/key/model fails, the system immediately rotates to the next available candidate rather than sleeping and retrying the same broken target.
4. **Routing is explicit, not magical** — the user always knows (or explicitly chooses) which strategy decided where a task went: static rules, an LLM meta-router, or manual selection.
5. **Config over code** — providers and models are defined in config files (`.env`, `model_catalog.yaml`), not hardcoded inside business logic.
6. **Strategy pattern where it matters** — routing policies and aggregation strategies are interchangeable objects, never inline if/else chains.

---

## 3. High-Level Architecture

```

┌──────────────────────────────────────────────────────────────────┐
│                    Entry Points                                     │
│  ┌──────────────────────────────┐  ┌───────────────────────────┐   │
│  │ CLI (Typer + Rich)           │  │ Web (FastAPI)             │   │
│  │ research/review wizard       │  │ REST + SSE endpoints      │   │
│  │ → policy + gen_params        │  │ → serves dashboard UI     │   │
│  └──────────────┬───────────────┘  └────────────┬──────────────┘   │
└───────────────────────────┬────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Pipeline Layer                             │
│  ┌───────────────┐                        ┌────────────────────┐  │
│  │ Research       │                        │ Code Review        │  │
│  │ ResearchPlanner│                        │ CodeReviewSplitter │  │
│  │ (topic→tasks)  │                        │ (path→tasks)       │  │
│  └───────┬───────┘                        └─────────┬──────────┘  │
└──────────┼─────────────────────────────────────────┼──────────────┘
           │              List[AgentTask]              │
           └───────────────────┬────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                 Batch Runner (core/pipeline.py)                    │
│   asyncio.Semaphore(max_concurrency) + asyncio.gather              │
│   Per task: policy.decide() → executor.run()                       │
│   Exceptions → failed AgentResult, batch continues                 │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Router (Policy Layer)                          │
│  RuleBasedPolicy | ManualPolicy | LLMRouterPolicy                 │
│  ROUTING_TABLE lives in core/router/policies.py                   │
│  → returns ORDERED candidate list [(provider, model), ...]        │
│  _RotatingPool rotates the starting candidate per task            │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AgentExecutor (core/executor.py)                │
│  For each candidate in order:                                     │
│    - skip if provider missing or in rate-limit cooldown           │
│    - check CircuitBreaker (provider level)                        │
│    - pull next key from key pool (round robin)                    │
│    - attempt agent.execute() with asyncio.wait_for timeout        │
│    - on failure → immediately try next candidate (no backoff)     │
│    - on 429 → mark provider cooling down, try next candidate      │
│    - on success → return AgentResult                              │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Provider Layer                                  │
│  OpenAICompatibleProvider (OpenAI, Groq, OpenRouter, NVIDIA NIM,  │
│                             OpenCode Zen)                         │
│  AnthropicProvider (Anthropic)                                     │
│  BaseProvider owns: key pool + circuit breaker + rate-limit flag  │
│  (formerly separate modules; inlined into core/providers/base.py) │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
                     External LLM APIs
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Aggregation Layer                               │
│  DedupeMergeAggregator | LLMSynthesisAggregator                   │
└───────────────────────────┬────────────────────────────────────────┘
                            ▼
                     Final Output
```

---

## 4. Component Responsibilities

### 4.1 CLI Layer (`cli/`)
- Entry point for all user interaction (`typer`-based). Commands: `research`, `review`, `providers`, `config`, `web`.
- `research` and `review` each run the Default/Manual wizard (`cli/wizard.py`), which returns a lightweight `SimpleNamespace` run config (mode, effort, selected_targets).
- That config selects a `RoutingPolicy` and generation parameters (`EFFORT_PRESETS` for Manual mode) for the entire run.
- Startup callback in `cli/main.py` validates the routing table against the model catalog and fails fast on unknown model IDs.
- Never contains business logic — only collects input and delegates to pipelines.

### 4.2 Web Layer (`web/`)

- FastAPI-based web server exposing REST + SSE streaming endpoints.
- Serves a single-page dashboard (Jinja2 templates + vanilla JS) with tabs for Research, Review, Providers, and Config.
- Endpoints:
  - `GET /` — Dashboard HTML
  - `GET /api/providers` — Provider health/status
  - `GET /api/config` — System configuration
  - `GET /api/models` — Models from the YAML catalog
  - `GET /api/effort-presets` — Effort preset parameters
  - `POST /api/research` — Start research pipeline (SSE stream)
  - `POST /api/review` — Start code review pipeline (SSE stream)
- `_TracedOrchestrator` wraps the same policy/executor path and pushes `task_start` / `task_success` / `task_fail` events onto an `asyncio.Queue` for the live parallel-viz UI.
- Reuses the same pipeline, batch runner, router, and executor layers as the CLI — no duplicated business logic.

### 4.3 Pipeline Layer (`pipelines/`)
- Converts a high-level user request (a topic, a path) into a `List[AgentTask]`.
- **Research:** `ResearchPlanner.plan()` makes one LLM call (rotating across configured providers) to decompose a topic into sub-questions, each tagged with a `complexity_tier` (`TIER|question` line format).
- **Code Review:** `CodeReviewSplitter.split()` walks a file/directory (no LLM call) and assigns a `complexity_tier` per file using a local heuristic (line count). Truncates file content to 8000 chars for the prompt.
- Each pipeline selects its `AggregationStrategy` (Research → `LLMSynthesisAggregator`, Code Review → `DedupeMergeAggregator`).

### 4.4 Batch Runner (`core/pipeline.py`)
- `run_agent_batch()` owns the concurrency cap via `asyncio.Semaphore(max_concurrency)`.
- For each task: `policy.decide(task)` → `executor.run(...)`, all dispatched with `asyncio.gather(..., return_exceptions=True)`.
- Exceptions become failed `AgentResult`s — one failing task never terminates the batch.
- `build_orchestrator()` returns a thin `_Orchestrator` object with a `run_batch(agent, tasks, gen_params)` method used by both pipelines.
- Has no knowledge of providers or aggregation — purely a concurrency/dispatch layer.
- (Formerly `core/orchestrator.py`; consolidated into `core/pipeline.py` during the simplification pass.)

### 4.5 Router (`core/router/policies.py`)
- Central decision point: **"which (provider, model) candidates should this task try, and in what order?"**
- Returns an **ordered list**, not a single choice — this enables immediate failover downstream.
- Three interchangeable policies:
  - `RuleBasedPolicy` — static 5-tier `ROUTING_TABLE` lookup (defined in the same file), filtered to configured providers; free-first fallback from the catalog when `FREE_MODELS_ONLY` is on. **Default.**
  - `ManualPolicy` — built from wizard/web selections (explicit provider/model/effort).
  - `LLMRouterPolicy` — a meta LLM call ranks candidates dynamically (optional, when `ROUTING_MODE=llm_based`).
- `_RotatingPool` (private helper in the same file) ensures successive tasks rotate their starting candidate, spreading load evenly instead of hammering the first entry.
- `build_policy(run_config, providers)` factory maps mode string → policy instance.

### 4.6 Executor (`core/executor.py`)
- Receives a task + ordered candidate list + generation params.
- Walks the candidate list **in order**, skipping instantly (no sleep/backoff) on:
  - Unknown provider name
  - Provider in rate-limit cooldown (`rate_limited_until`)
  - Open circuit breaker for a provider
  - No healthy API key available
  - Actual call failure/timeout/empty/malformed response
- On 429 specifically: marks the provider cooling down (`rate_limit_cooldown_sec`) so *other* concurrent tasks skip it too; does not count as a key failure.
- On the first success, returns immediately with `provider_used` / `model_used` / `latency_sec`.
- If all candidates are exhausted, returns a failed `AgentResult` — isolated and does not propagate to other tasks.

### 4.7 Provider Layer (`core/providers/`)
- `BaseProvider` (`base.py`) — abstract base all providers implement (`call()`); also holds the **inlined key pool and circuit breaker** (see 4.8 / 4.9) plus `rate_limited_until`, `is_healthy()`, `is_enabled()`. Exposes backward-compatible `.key_pool` / `.breaker` proxy properties used by the Executor.
- `OpenAICompatibleProvider` — single implementation reused for 5 providers (OpenAI, Groq, OpenRouter, NVIDIA NIM, OpenCode Zen) since they share the same `/chat/completions` schema; differs only by `base_url` / `api_keys` / `default_model` from config. Also implements `list_models()` against the provider's `/models` API.
- `AnthropicProvider` — separate implementation due to differing `/v1/messages` schema.
- `registry.build_providers(settings)` instantiates only providers that have at least one API key configured.
- `ModelCatalog` (`model_catalog.py`) loads `config/model_catalog.yaml` and exposes queryable model lists — used by the CLI wizard (menus), free-model fallback in `RuleBasedPolicy`, and startup/config validation (routing table consistency check). It is a **static** catalog; it does not refresh from provider APIs at startup.

### 4.8 Key Pool (inlined in `BaseProvider`)
- Round-robins across all configured keys for a provider (`_get_key()` under an `asyncio.Lock`).
- Tracks per-key health: failure count, cooldown timestamp.
- A key that fails repeatedly is marked unhealthy and skipped until cooldown expires; success resets it.
- Raises `NoAvailableKeyError` if all keys are unhealthy — signals the Executor to skip this provider and move to the next candidate.

### 4.9 Circuit Breaker (inlined in `BaseProvider`)
- One logical breaker per provider (key-level health is handled by the key pool).
- States: `CLOSED` (normal) → `OPEN` (provider disabled after N consecutive failures) → `HALF_OPEN` ( after `circuit_breaker_reset_sec`, allows a trial request) → back to `CLOSED` on success.
- Prevents wasting requests on a provider that is clearly down.
- Thresholds come from `.env`: `CIRCUIT_BREAKER_FAIL_THRESHOLD`, `CIRCUIT_BREAKER_RESET_SEC`.

### 4.10 Aggregation Layer (`core/aggregation/strategies.py`)
- Aggregators implement `aggregate(task, results) -> AgentResult` (duck-typed; no shared ABC after the simplification pass).
- Strategy is chosen **per pipeline**, not globally:
  - Research → `LLMSynthesisAggregator` (one more LLM call to merge findings into a coherent report; truncates findings to bounded budgets; walks providers for failover; on total 429 fallback returns raw findings with a note).
  - Code Review → `DedupeMergeAggregator` (pure Python, dedupes by exact text match, no extra LLM cost).

---

## 5. Data Flow — Single Task Lifecycle

```

AgentTask created by Pipeline (with metadata: task_type, complexity_tier)
        │
        ▼
Batch runner acquires semaphore slot
        │
        ▼
policy.decide(task) → [(provider_a, model_x), (provider_b, model_y), (provider_c, model_z)]
        │
        ▼
Executor iterates candidates:
   → provider_a: circuit OPEN → skip immediately
   → provider_b: circuit CLOSED, key pool → key_2 (round robin)
                 → call fails (timeout) → report_failure(key_2) → skip immediately
   → provider_c: circuit CLOSED, key pool → key_1
                 → call succeeds → report_success(key_1) → RETURN
        │
        ▼
AgentResult(success=True, output=..., latency_sec=...)
        │
        ▼
Batch runner collects into List[AgentResult] (via asyncio.gather)
        │
        ▼
Pipeline's aggregate(task, results) → Final Output

```

---

## 6. Configuration Architecture

| File | Purpose |
|---|---|
| `.env` | Secrets: API keys (comma-separated per provider), base URLs, default models, global settings (concurrency, timeouts, circuit breaker thresholds, routing mode) |
| `config/settings.py` | `pydantic-settings` loader — typed access to `.env`, plus `EFFORT_PRESETS` (low/high/xhigh/max → temperature, max_tokens, reasoning_effort, timeout) |
| `config/model_catalog.yaml` | Static inventory of models per provider — used for CLI menus, free-model fallback, and validation |
| `core/router/policies.py` | `ROUTING_TABLE` — static 5-tier (`low/mid/high/xhigh/max`) per task_type candidate lists for `RuleBasedPolicy` |

**Validation:** `validate_routing_table()` (in `cli/main.py` and `cli/commands/config_cmd.py`) cross-checks every model ID referenced in `ROUTING_TABLE` actually exists in `model_catalog.yaml`. This fails fast on typos instead of surfacing as a cryptic API error mid-run.

---

## 7. Concurrency Model

- **Why asyncio, not threading/multiprocessing:** All agent work is I/O-bound (waiting on HTTP calls to LLM APIs). `asyncio` gives high concurrency without the overhead of OS threads or processes.
- **Concurrency cap:** `asyncio.Semaphore(max_concurrency)` in the batch runner prevents overwhelming providers and hitting rate limits, independent of how many tasks exist.
- **Timeouts:** Every candidate attempt inside the Executor is wrapped in `asyncio.wait_for()` — a hung request cannot block the whole batch indefinitely. Default from `DEFAULT_TIMEOUT_SEC` / effort preset.
- **No shared mutable state by default:** Each task/agent execution is fully independent (map-reduce style). Optional `SharedContext` (`core/state/shared_context.py`, lock-protected) exists for future cross-agent awareness features but is not used in v1 pipelines.

---

## 8. Failure Handling Architecture

| Failure Type | Handled By | Behavior |
|---|---|---|
| Single API call hangs | `asyncio.wait_for()` in Executor | Timeout → candidate failure → next candidate |
| Bad/expired API key | Key pool in `BaseProvider` | Key marked unhealthy after threshold, skipped in future rotations |
| Provider fully down | Circuit breaker in `BaseProvider` | Provider skipped entirely until cooldown expires, trial request in `HALF_OPEN` |
| HTTP 429 rate limit | Executor `_is_rate_limit_error` | Provider `mark_rate_limited(cooldown)`; key not penalized; next candidates tried immediately |
| Model returns malformed/empty output | Provider `call()` raises → caught by Executor | Candidate failure → next candidate |
| Planner (research) all candidates fail | `ResearchPlanner.plan()` | Raises → pipeline returns failed `AgentResult` early |
| All candidates exhausted for one task | Executor | Returns failed `AgentResult` for that task only |
| One task fails entirely | Batch runner (`asyncio.gather(return_exceptions=True)`) | Batch continues; failure isolated to that single result |

No retry-with-backoff is used when redundant candidates exist — failover is immediate.

---

## 9. Extensibility Points

| To add... | Touch these files only |
|---|---|
| A new LLM provider (OpenAI-compatible) | `.env`, `config/model_catalog.yaml`, add name to `OPENAI_COMPATIBLE_PROVIDERS` + settings — minimal Python |
| A new LLM provider (different schema) | New file in `core/providers/`, subclass `BaseProvider`, register in `registry.py` |
| A new routing strategy | New class in `core/router/policies.py` implementing `RoutingPolicy.decide()`; wire into `build_policy()` |
| A new aggregation strategy | New class in `core/aggregation/strategies.py` with `async def aggregate(task, results)` |
| A new pipeline (e.g., test generation) | New folder in `pipelines/`, reusing batch runner / router / executor / aggregation layers untouched |
| A new task type's routing | Add entries to `ROUTING_TABLE` in `core/router/policies.py`; set `metadata.task_type` on tasks |

---

## 10. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Async HTTP | `httpx` |
| Data validation | `pydantic` / `pydantic-settings` |
| CLI | `typer` + `rich` |
| Web server | `fastapi` + `uvicorn` |
| Templating | `jinja2` |
| Config parsing | `PyYAML` |
| Logging | `pythonjsonlogger` (optional) |
| Testing | `pytest` + `pytest-asyncio` |

---

## 11. Non-Goals (v1)

- No persistent job queue (Redis/Kafka) — in-memory `asyncio` orchestration only.
- No cross-agent shared memory in default pipelines — isolation by design.
- No multi-language runtime — Python only.
- No automatic model-catalog refresh from provider APIs — the catalog is a checked-in YAML file.

---

## 12. Recent Simplification Notes

The codebase intentionally consolidated several once-separate modules to remove
over-engineering. Where the code used to live vs. now:

| Former location | Now |
|---|---|
| `core/agent_base.py` (`BaseAgent` ABC) | Removed — agents are plain classes with `async def execute(...)` |
| `core/orchestrator.py` | `core/pipeline.py` (`run_agent_batch` + `build_orchestrator`) |
| `core/providers/key_pool.py` | Inlined into `core/providers/base.py` (exposed via `.key_pool` proxy) |
| `core/providers/circuit_breaker.py` | Inlined into `core/providers/base.py` (exposed via `.breaker` proxy) |
| `core/router/router.py`, `candidate_rotation.py`, `routing_mode.py` | All in `core/router/policies.py` |
| `config/routing_table.py` | `ROUTING_TABLE` in `core/router/policies.py` |
| `config/effort_presets.py` | `EFFORT_PRESETS` in `config/settings.py` |
| `utils/validation.py` | `validate_routing_table()` in `cli/main.py` / `cli/commands/config_cmd.py` |
| `cli/run_config.py` | `SimpleNamespace` returned by `cli/wizard.py` |
| `pipelines/*/aggregator.py` | `core/aggregation/strategies.py` |
| `VotingAggregator`, `FirstSuccessAggregator`, `ConcatAggregator` | Removed (not used by either v1 pipeline) |
