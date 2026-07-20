from cli.display import console, render_provider_status_table
from config.settings import settings
from core.providers.registry import build_providers


async def show_providers():
    providers = build_providers(settings)
    if not providers:
        console.print("[yellow]No providers configured. Check your .env file.[/yellow]")
        return
    render_provider_status_table(providers)
