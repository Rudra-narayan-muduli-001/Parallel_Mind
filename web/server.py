import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request

from config.effort_presets import EFFORT_PRESETS
from config.settings import settings
from core.executor import AgentExecutor
from core.orchestrator import Orchestrator
from core.providers.model_catalog import ModelCatalog
from core.providers.registry import build_providers
from core.router.policies import ManualPolicy, RuleBasedPolicy
from core.router.router import Router

BASE_DIR = os.path.dirname(__file__)
template_env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=True,
)

catalog = ModelCatalog()
providers = build_providers(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="ParallelMind", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=__import__("os").path.join(BASE_DIR, "static")), name="static")


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
    }


@app.get("/api/models")
async def get_models():
    models = catalog.list_models()
    return {"models": [{"provider": p, "id": m, "display": d} for p, m, d in models]}


@app.get("/api/effort-presets")
async def get_effort_presets():
    return {"presets": {k: dict(v) for k, v in EFFORT_PRESETS.items()}}


def _build_pipeline(mode: str, effort: str = "low", selected_targets: list[tuple] = None):
    if mode == "manual" and selected_targets:
        policy = ManualPolicy(selected_targets, effort)
        gen_params = dict(EFFORT_PRESETS.get(effort, EFFORT_PRESETS["low"]))
    else:
        policy = RuleBasedPolicy()
        gen_params = {}

    router = Router(policy)
    executor = AgentExecutor(providers, default_timeout=settings.default_timeout_sec)
    orchestrator = Orchestrator(executor, router, max_concurrency=settings.default_max_concurrency)
    return orchestrator, gen_params


async def _event_stream(async_gen):
    async for event in async_gen:
        yield f"data: {json.dumps(event)}\n\n"
    yield "data: [DONE]\n\n"


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

    orchestrator, gen_params = _build_pipeline(mode, effort, selected_targets)
    from pipelines.research.pipeline import ResearchPipeline
    pipeline = ResearchPipeline(orchestrator, providers, gen_params)

    async def stream():
        yield {"type": "status", "message": "Planning research sub-questions..."}
        try:
            result = await pipeline.run(topic)
            if result.success:
                yield {"type": "result", "output": result.output}
            else:
                yield {"type": "error", "message": result.error or "Research failed"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    return StreamingResponse(_event_stream(stream()), media_type="text/event-stream")


@app.post("/api/review")
async def review(request: Request):
    body = await request.json()
    path = body.get("path", ".").strip()
    mode = body.get("mode", "default")
    effort = body.get("effort", "low")
    selected_targets = [tuple(t) for t in body.get("targets", [])]

    orchestrator, gen_params = _build_pipeline(mode, effort, selected_targets)
    from pipelines.code_review.pipeline import CodeReviewPipeline
    pipeline = CodeReviewPipeline(orchestrator, providers, gen_params)

    async def stream():
        yield {"type": "status", "message": f"Scanning files in {path}..."}
        try:
            result = await pipeline.run(path)
            if result.success:
                yield {"type": "result", "output": result.output}
            else:
                yield {"type": "error", "message": result.error or "Review failed"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    return StreamingResponse(_event_stream(stream()), media_type="text/event-stream")


async def _error_event(msg: str):
    yield {"type": "error", "message": msg}
