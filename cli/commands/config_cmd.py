from rich.console import Console
from rich.table import Table

from config.settings import settings
from config.routing_table import ROUTING_TABLE
from config.effort_presets import EFFORT_PRESETS
from core.providers.model_catalog import ModelCatalog
from utils.validation import validate_routing_table_against_catalog

console = Console()


async def check_config():
    console.print("[bold]ParallelMind Configuration Check[/bold]\n")

    table = Table(title="Settings")
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_row("Routing Mode", settings.routing_mode)
    table.add_row("Max Concurrency", str(settings.default_max_concurrency))
    table.add_row("Default Timeout", f"{settings.default_timeout_sec}s")
    table.add_row("Circuit Breaker Threshold", str(settings.circuit_breaker_fail_threshold))
    table.add_row("Circuit Breaker Reset", f"{settings.circuit_breaker_reset_sec}s")
    table.add_row("Router Model", f"{settings.router_model_provider}/{settings.router_model_name}")
    table.add_row("Log Level", settings.log_level)
    table.add_row("Log Format", settings.log_format)
    console.print(table)

    catalog = ModelCatalog()
    try:
        validate_routing_table_against_catalog(ROUTING_TABLE, catalog)
        console.print("[green]✓ Routing table validated against model catalog[/green]")
    except ValueError as e:
        console.print(f"[red]✗ Routing table validation failed:[/red] {e}")

    console.print(f"\n[bold]Effort Presets:[/bold] {len(EFFORT_PRESETS)} configured")
    for name, params in EFFORT_PRESETS.items():
        console.print(f"  [cyan]{name}[/cyan]: {params}")

    console.print(f"\n[bold]Model Catalog:[/bold] {len(catalog.list_provider_names())} providers")
    for pname in catalog.list_provider_names():
        models = catalog.list_models([pname])
        console.print(f"  [cyan]{pname}[/cyan]: {len(models)} models")
