from dataclasses import dataclass, field


@dataclass
class RunConfig:
    mode: str = "default"
    effort: str = "low"
    selected_providers: list[str] = field(default_factory=list)
    selected_targets: list[tuple[str, str]] = field(default_factory=list)
