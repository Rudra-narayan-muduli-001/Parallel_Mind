from enum import Enum


class RoutingMode(str, Enum):
    RULE_BASED = "rule_based"
    LLM_BASED = "llm_based"
    MANUAL = "manual"
