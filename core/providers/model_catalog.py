import yaml
from pydantic import BaseModel


class ModelEntry(BaseModel):
    id: str
    display_name: str


class ProviderCatalogEntry(BaseModel):
    display_name: str
    models: list[ModelEntry] = []


class ModelCatalog:
    def __init__(self, path: str = "config/model_catalog.yaml"):
        self.path = path
        self.providers: dict[str, ProviderCatalogEntry] = {}
        self._load()

    def _load(self):
        with open(self.path, "r") as f:
            raw = yaml.safe_load(f) or {}
        providers_raw = raw.get("providers", {})
        self.providers = {name: ProviderCatalogEntry(**data) for name, data in providers_raw.items()}

    def list_provider_names(self) -> list[str]:
        return list(self.providers.keys())

    def list_models(self, provider_names: list[str] | None = None) -> list[tuple[str, str, str]]:
        """Returns [(provider_name, model_id, display_string), ...]"""
        result = []
        targets = provider_names or self.list_provider_names()
        for pname in targets:
            entry = self.providers.get(pname)
            if not entry:
                continue
            for m in entry.models:
                result.append((pname, m.id, f"{pname}/{m.display_name}"))
        return result

    def is_valid_model(self, provider_name: str, model_id: str) -> bool:
        entry = self.providers.get(provider_name)
        if not entry:
            return False
        return any(m.id == model_id for m in entry.models)
