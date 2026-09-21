import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request

from config.settings import settings, EFFORT_PRESETS
from core.executor import AgentExecutor
from core.models import AgentResult, AgentTask
from core.pipeline import build_orchestrator, run_agent_batch
from core.providers.model_catalog import ModelCatalog
from core.providers.registry import build_providers
from core.router.policies import ManualPolicy, RuleBasedPolicy

BASE_DIR = os.path.dirname(__file__)
template_env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=True,
)

providers = build_providers(settings)
catalog = ModelCatalog()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="ParallelMind", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = template_env.get_template("index.html")
    return HTMLResponse(content=template.render())


@app.get("/api/providers")
async def get_providers():
    result = []
    for name, p in providers.items():
        result.append({
            "name": name,
            "healthy": p.is_healthy(),
            "enabled": p.is_enabled(),
            "default_model": getattr(p, "default_model", ""),
        })
    return {"providers": result}


@app.get("/api/config")
async def get_config():
    return {
        "routing_mode": settings.routing_mode,
        "max_concurrency": settings.default_max_concurrency,
        "timeout_sec": settings.default_timeout_sec,
        "circuit_breaker_fail_threshold": settings.circuit_breaker_fail_threshold,
        "circuit_breaker_reset_sec": settings.circuit_breaker_reset_sec,
        "providers": list(providers.keys()),
        "default_provider": settings.default_provider,
        "free_models_only": settings.free_models_only,
    }


@app.get("/api/models")
async def get_models():
    models = catalog.list_models()
    return {"models": [{"provider": p, "id": m, "display": d} for p, m, d in models]}


@app.get("/api/effort-presets")
async def get_effort_presets():
    return {"presets": {k: dict(v) for k, v in EFFORT_PRESETS.items()}}


def _build_policy_and_params(mode: str, effort: str = "low", selected_targets: list[tuple] = None):
    if mode == "manual" and selected_targets:
        policy = ManualPolicy(selected_targets, effort)
        gen_params = dict(EFFORT_PRESETS.get(effort, EFFORT_PRESETS["low"]))
    else:
        policy = RuleBasedPolicy(providers=providers, catalog=catalog)
        gen_params = {}

    gen_params.setdefault("rate_limit_cooldown_sec", settings.rate_limit_cooldown_sec)
    return policy, gen_params


class _TracedOrchestrator:
    def __init__(self, executor, policy, max_concurrency, queue):
        self._executor = executor
        self._policy = policy
        self._max_concurrency = max_concurrency
        self._queue = queue

    async def run_batch(self, agent, tasks: list[AgentTask], gen_params: dict | None = None) -> list[AgentResult]:
        semaphore = asyncio.Semaphore(self._max_concurrency)
        gen_params = gen_params or {}

        async def _run_one(task: AgentTask) -> AgentResult:
            async with semaphore:
                await self._queue.put({"type": "task_start", "task_id": task.id, "prompt": task.prompt})
                candidates = await self._policy.decide(task)
                start = time.perf_counter()
                result = await self._executor.run(agent, task, candidates, gen_params)
                elapsed = time.perf_counter() - start
                if result.success:
                    await self._queue.put({
                        "type": "task_success",
                        "task_id": task.id,
                        "provider": result.provider_used,
                        "model": result.model_used,
                        "latency_sec": round(elapsed, 2),
                    })
                else:
                    await self._queue.put({
                        "type": "task_fail",
                        "task_id": task.id,
                        "error": result.error or "failed",
                        "latency_sec": round(elapsed, 2),
                    })
                return result

        results = await asyncio.gather(
            *[_run_one(t) for t in tasks],
            return_exceptions=True,
        )
        final: list[AgentResult] = []
        for task, r in zip(tasks, results):
            if isinstance(r, Exception):
                final.append(AgentResult(task_id=task.id, success=False, error=str(r), latency_sec=0.0))
            else:
                assert isinstance(r, AgentResult)
                final.append(r)
        return final


@app.post("/api/research")
async def research(request: Request):
    body = await request.json()
    topic = body.get("topic", "").strip()
    mode = body.get("mode", "default")
    effort = body.get("effort", "low")
    selected_targets = [tuple(t) for t in body.get("targets", [])]

    if not topic:
        return StreamingResponse(
            _event_stream(_error_event("Topic is required")),
            media_type="text/event-stream",
        )

    policy, gen_params = _build_policy_and_params(mode, effort, selected_targets)
    executor = AgentExecutor(providers, default_timeout=settings.default_timeout_sec)

    queue: asyncio.Queue = asyncio.Queue()
    orchestrator = _TracedOrchestrator(executor, policy, settings.default_max_concurrency, queue)
    from pipelines.research.pipeline import ResearchPipeline
    pipeline = ResearchPipeline(executor, policy, providers, gen_params, max_concurrency=settings.default_max_concurrency)

    async def stream():
        yield {"type": "status", "message": "Planning research sub-questions..."}
        pipeline_task = asyncio.create_task(pipeline.run(topic))

        while True:
            if pipeline_task.done():
                while not queue.empty():
                    yield queue.get_nowait()
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield event
            except asyncio.TimeoutError:
                continue

        try:
            result = await pipeline_task
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        if result.success:
            yield {"type": "result", "output": result.output}
        else:
            yield {"type": "error", "message": result.error or "Research failed"}

    return StreamingResponse(_event_stream(stream()), media_type="text/event-stream")


@app.post("/api/review")
async def review(request: Request):
    body = await request.json()
    path = body.get("path", ".").strip()
    mode = body.get("mode", "default")
    effort = body.get("effort", "low")
    selected_targets = [tuple(t) for t in body.get("targets", [])]

    policy, gen_params = _build_policy_and_params(mode, effort, selected_targets)
    executor = AgentExecutor(providers, default_timeout=settings.default_timeout_sec)

    queue: asyncio.Queue = asyncio.Queue()
    orchestrator = _TracedOrchestrator(executor, policy, settings.default_max_concurrency, queue)
    from pipelines.code_review.pipeline import CodeReviewPipeline
    pipeline = CodeReviewPipeline(executor, policy, providers, gen_params, max_concurrency=settings.default_max_concurrency)

    async def stream():
        yield {"type": "status", "message": f"Scanning files in {path}..."}
        pipeline_task = asyncio.create_task(pipeline.run(path))

        while True:
            if pipeline_task.done():
                while not queue.empty():
                    yield queue.get_nowait()
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield event
            except asyncio.TimeoutError:
                continue

        try:
            result = await pipeline_task
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        if result.success:
            yield {"type": "result", "output": result.output}
        else:
            yield {"type": "error", "message": result.error or "Review failed"}

    return StreamingResponse(_event_stream(stream()), media_type="text/event-stream")


async def _event_stream(async_gen):
    async for event in async_gen:
        yield f"data: {json.dumps(event)}\n\n"
    yield "data: [DONE]\n\n"


async def _error_event(msg: str):
    yield {"type": "error", "message": msg}