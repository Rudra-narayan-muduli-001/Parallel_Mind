from rich.console import Console
from rich.table import Table

console = Console()


def parse_comma_indices(raw: str, max_index: int) -> list[int]:
    indices = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            i = int(part) - 1
            if 0 <= i < max_index:
                indices.append(i)
    return indices


def render_numbered_list(items: list[str], title: str = "", tip: str = ""):
    console.print(f"\n[bold]{title}[/bold]")
    if tip:
        console.print(f"[dim]{tip}[/dim]")
    for i, item in enumerate(items, start=1):
        console.print(f"{i}. {item}")


def render_provider_status_table(providers: dict):
    table = Table(title="Provider Status")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Model")
    table.add_column("Keys")

    for name, prov in providers.items():
        status = "[green]ENABLED[/green]" if prov.is_enabled() else "[red]DISABLED[/red]"
        healthy = "[green]HEALTHY[/green]" if prov.is_healthy() else "[yellow]DEGRADED[/yellow]"
        model = prov.default_model or "—"
        keys = str(len(prov.key_pool.keys))
        table.add_row(name, f"{status} | {healthy}", model, keys)

    console.print(table)
