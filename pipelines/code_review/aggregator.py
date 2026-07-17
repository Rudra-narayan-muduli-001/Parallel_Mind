from core.aggregation.base import AggregationStrategy
from core.aggregation.strategies import DedupeMergeAggregator


def build_code_review_aggregator() -> AggregationStrategy:
    return DedupeMergeAggregator()
