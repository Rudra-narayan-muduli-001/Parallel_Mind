import yaml


class ModelCatalog:
    def __init__(self, path: str = "config/model_catalog.yaml"):
        self.path = path
        self.providers: dict = {}
        self._load()

    def _load(self):
        with open(self.path, "r") as f:
            raw = yaml.safe_load(f) or {}
        self.providers = raw.get("providers", {})

    def list_provider_names(self) -> list[str]:
        return list(self.providers.keys())

    def list_models(self, provider_names: list[str] | None = None) -> list[tuple[str, str, str]]:
        result = []
        targets = provider_names or self.list_provider_names()
        for pname in targets:
            entry = self.providers.get(pname)
            if not entry:
                continue
            for m in entry.get("models", []):
                result.append((pname, m["id"], f"{pname}/{m.get('display_name', m['id'])}"))
        return result

    def is_valid_model(self, provider_name: str, model_id: str) -> bool:
        entry = self.providers.get(provider_name)
        if not entry:
            return False
        return any(m["id"] == model_id for m in entry.get("models", []))