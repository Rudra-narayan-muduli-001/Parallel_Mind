from cli.display import console
from cli.wizard import run_wizard
from config.settings import settings, EFFORT_PRESETS
from core.executor import AgentExecutor
from core.providers.model_catalog import ModelCatalog
from core.providers.registry import build_providers
from core.router.policies import ManualPolicy, RuleBasedPolicy
from pipelines.research.pipeline import ResearchPipeline


async def run_research(topic: str):
    providers = build_providers(settings)
    catalog = ModelCatalog()
    run_config = run_wizard(catalog)

    if run_config.mode == "manual":
        policy = ManualPolicy(run_config.selected_targets, run_config.effort)
        gen_params = dict(EFFORT_PRESETS[run_config.effort])
    else:
        policy = RuleBasedPolicy(providers=providers, catalog=catalog)
        gen_params = {}

    executor = AgentExecutor(providers, default_timeout=settings.default_timeout_sec)
    pipeline = ResearchPipeline(executor, policy, providers, gen_params, max_concurrency=settings.default_max_concurrency)
    result = await pipeline.run(topic)

    if result.success:
        console.print("\n[bold green]Research Complete[/bold green]")
        console.print(result.output)
    else:
        console.print("\n[bold red]Research Failed[/bold red]")
        console.print(result.error or "Unknown error")