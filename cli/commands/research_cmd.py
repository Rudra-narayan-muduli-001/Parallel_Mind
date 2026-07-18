from config.settings import settings
from config.effort_presets import EFFORT_PRESETS
from core.providers.model_catalog import ModelCatalog
from core.providers.registry import build_providers
from core.router.policies import RuleBasedPolicy, ManualPolicy
from core.router.router import Router
from core.executor import AgentExecutor
from core.orchestrator import Orchestrator
from cli.wizard import run_wizard
from cli.display import console
from pipelines.research.pipeline import ResearchPipeline


async def run_research(topic: str):
    catalog = ModelCatalog()
    run_config = run_wizard(catalog)
    providers = build_providers(settings)

    if run_config.mode == "manual":
        policy: RuleBasedPolicy | ManualPolicy = ManualPolicy(run_config.selected_targets, run_config.effort)
        gen_params = dict(EFFORT_PRESETS[run_config.effort])
    else:
        policy = RuleBasedPolicy()
        gen_params = {}

    router = Router(policy)
    executor = AgentExecutor(providers, default_timeout=settings.default_timeout_sec)
    orchestrator = Orchestrator(executor, router, max_concurrency=settings.default_max_concurrency)

    pipeline = ResearchPipeline(orchestrator, providers, gen_params)
    result = await pipeline.run(topic)

    if result.success:
        console.print("\n[bold green]Research Complete[/bold green]")
        console.print(result.output)
    else:
        console.print("\n[bold red]Research Failed[/bold red]")
        console.print(result.error or "Unknown error")
