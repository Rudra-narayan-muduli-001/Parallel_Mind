from pydantic import BaseModel
from typing import Optional, Any, Literal

ComplexityTier = Literal["low", "mid", "high", "xhigh", "max"]


class AgentTask(BaseModel):
    id: str
    prompt: str
    context: dict = {}
    metadata: dict = {}


class AgentResult(BaseModel):
    task_id: str
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    latency_sec: float = 0.0
    tokens_used: Optional[int] = None
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
