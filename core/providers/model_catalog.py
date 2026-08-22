import asyncio
import logging

import yaml
from pydantic import BaseModel

logger = logging.getLogger("parallelmind.catalog")


class ModelEntry(BaseModel):
    id: str
    display_name: str


class ProviderCatalogEntry(BaseModel):
    display_name: str
    models: list[ModelEntry] = []


class ModelCatalog:
    """Loads the static YAML catalog and (optionally) augments it with the
    live model list returned by each provider's /models endpoint.

    Use `await ModelCatalog.from_providers(providers)` for live discovery,
    or the default constructor for offline-only mode."""

    def __init__(self, path: str = "config/model_catalog.yaml"):
        self.path = path
        self.providers: dict[str, ProviderCatalogEntry] = {}
        self._load()

    def _load(self):
        with open(self.path, "r") as f:
            raw = yaml.safe_load(f) or {}
        providers_raw = raw.get("providers", {})
        self.providers = {name: ProviderCatalogEntry(**data) for name, data in providers_raw.items()}

    @classmethod
    async def from_providers(cls, providers: dict, yaml_path: str = "config/model_catalog.yaml"):
        """Build catalog from YAML, then live-discover models for each enabled provider.
        Live-discovered models are MERGED with the static ones (live wins on conflict)."""
        cat = cls(path=yaml_path)
        if not providers:
            return cat

        async def discover(name: str, prov):
            try:
                models = await prov.list_models()
                return name, models
            except Exception as e:
                logger.debug(f"Live discovery failed for {name}: {e}")
                return name, []

        results = await asyncio.gather(*(discover(n, p) for n, p in providers.items()))

        for name, models in results:
            if not models:
                continue
            entry = cat.providers.get(name, ProviderCatalogEntry(display_name=name))
            existing_ids = {m.id for m in entry.models}
            new_models = [
                ModelEntry(id=m.id, display_name=m.display_name or m.id)
                for m in models
                if m.id not in existing_ids
            ]
            if new_models or not entry.models:
                # Replace catalog models for this provider with live list (more accurate)
                merged = [ModelEntry(id=m.id, display_name=m.display_name or m.id) for m in models]
                cat.providers[name] = ProviderCatalogEntry(
                    display_name=entry.display_name or name,
                    models=merged,
                )

        return cat

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
