from rich.console import Console
from types import SimpleNamespace

from core.providers.model_catalog import ModelCatalog

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


def run_wizard(catalog: ModelCatalog) -> SimpleNamespace:
    console.print("\n[bold]Select configuration mode:[/bold]")
    console.print("1. Default")
    console.print("2. Manual")
    mode_choice = console.input("> ").strip()

    if mode_choice != "2":
        return SimpleNamespace(mode="default", effort="low", selected_targets=[])

    config = SimpleNamespace(mode="manual", effort="low", selected_targets=[])

    console.print("\n[bold]Set Effort[/bold]")
    console.print("1. Low")
    console.print("2. High")
    effort_choice = console.input("> ").strip()
    config.effort = "high" if effort_choice == "2" else "low"

    provider_names = catalog.list_provider_names()
    console.print("\n[bold]Choose Provider(s)[/bold]")
    console.print("[dim]Tip: to select multiple, separate numbers with commas, e.g. 1,3[/dim]")
    for i, pname in enumerate(provider_names, start=1):
        console.print(f"{i}. {pname}")
    raw = console.input("> ").strip()
    chosen_indices = parse_comma_indices(raw, len(provider_names))
    selected_providers = [provider_names[i] for i in chosen_indices] or provider_names

    models = catalog.list_models(selected_providers)
    console.print("\n[bold]Select Model(s)[/bold]")
    console.print("[dim]Tip: to select multiple, separate numbers with commas, e.g. 1,2,4[/dim]")
    for i, (_, _, display) in enumerate(models, start=1):
        console.print(f"{i}. {display}")
    raw = console.input("> ").strip()
    chosen_indices = parse_comma_indices(raw, len(models))
    config.selected_targets = [(models[i][0], models[i][1]) for i in chosen_indices]

    if not config.selected_targets:
        console.print("[red]No models selected — falling back to default mode.[/red]")
        return SimpleNamespace(mode="default", effort="low", selected_targets=[])

    return config