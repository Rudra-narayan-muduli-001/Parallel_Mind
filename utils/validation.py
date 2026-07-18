from core.providers.model_catalog import ModelCatalog


def validate_routing_table_against_catalog(routing_table: dict, catalog: ModelCatalog):
    errors = []
    for (task_type, tier), candidates in routing_table.items():
        for provider_name, model_id in candidates:
            entry = catalog.providers.get(provider_name)
            valid_models = entry.models if entry else []
            if not any(m.id == model_id for m in valid_models):
                errors.append(f"Routing table references unknown model '{model_id}' for provider '{provider_name}'")
    if errors:
        raise ValueError("Routing table validation failed:\n" + "\n".join(errors))
