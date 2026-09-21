import asyncio

import typer
from rich.console import Console

from config.settings import settings
from core.providers.model_catalog import ModelCatalog
from core.providers.registry import build_providers
from core.router.policies import ROUTING_TABLE
from utils.logger import setup_logging

console = Console()
app = typer.Typer(name="parallelmind")


def validate_routing_table(catalog: ModelCatalog):
    errors = []
    for (task_type, tier), candidates in ROUTING_TABLE.items():
        for provider_name, model_id in candidates:
            if not catalog.is_valid_model(provider_name, model_id):
                errors.append(f"Routing table references unknown model '{model_id}' for provider '{provider_name}'")
    if errors:
        raise ValueError("Routing table validation failed:\n" + "\n".join(errors))


@app.callback()
def main():
    setup_logging(settings.log_level, settings.log_format)
    catalog = ModelCatalog()
    try:
        validate_routing_table(catalog)
    except ValueError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def research(topic: str):
    from cli.commands.research_cmd import run_research

    asyncio.run(run_research(topic))


@app.command()
def review(path: str = "."):
    from cli.commands.review_cmd import run_review

    asyncio.run(run_review(path))


@app.command()
def providers():
    async def show_providers():
        providers = build_providers(settings)
        if not providers:
            console.print("[yellow]No providers configured. Check your .env file.[/yellow]")
            return
        from cli.display import render_provider_status_table
        render_provider_status_table(providers)

    asyncio.run(show_providers())


@app.command()
def config():
    from cli.commands.config_cmd import check_config

    asyncio.run(check_config())


@app.command()
def web(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn

    from web.server import app as web_app
    from cli.display import console

    console.print(f"[bold green]Starting ParallelMind Web UI[/bold green]")
    console.print(f"[dim]Open http://{host}:{port} in your browser[/dim]\n")
    uvicorn.run(web_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()