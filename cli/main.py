import asyncio

import typer
from rich.console import Console

from config.routing_table import ROUTING_TABLE
from config.settings import settings
from core.providers.model_catalog import ModelCatalog
from utils.logger import setup_logging
from utils.validation import validate_routing_table_against_catalog

console = Console()
app = typer.Typer(name="parallelmind")


@app.callback()
def main():
    setup_logging(settings.log_level, settings.log_format)
    catalog = ModelCatalog()
    try:
        validate_routing_table_against_catalog(ROUTING_TABLE, catalog)
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
    from cli.commands.providers_cmd import show_providers

    asyncio.run(show_providers())


@app.command()
def config():
    from cli.commands.config_cmd import check_config

    asyncio.run(check_config())


if __name__ == "__main__":
    app()
