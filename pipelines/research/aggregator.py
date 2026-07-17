from core.aggregation.base import AggregationStrategy
from core.aggregation.strategies import LLMSynthesisAggregator


def build_research_aggregator(providers: dict) -> AggregationStrategy:
    synthesis_provider = providers.get("openai") or providers.get("anthropic") or list(providers.values())[0]
    synthesis_model = synthesis_provider.default_model
    return LLMSynthesisAggregator(synthesis_provider, synthesis_model)
