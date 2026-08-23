from config.settings import settings
from core.aggregation.base import AggregationStrategy
from core.aggregation.strategies import LLMSynthesisAggregator


def build_research_aggregator(providers: dict) -> AggregationStrategy:
    # Prefer the configured default_provider; the aggregator itself walks every
    # available provider for failover on 429.
    default_model = None
    if settings.default_provider in providers:
        default_model = providers[settings.default_provider].default_model
    return LLMSynthesisAggregator(providers, default_model=default_model)
