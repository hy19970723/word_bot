from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class BudgetStatus(str, Enum):
    WITHIN_BUDGET = "within_budget"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    cost: float = 0.0


class ImageUsage(BaseModel):
    ai_generated: int = 0
    reused: int = 0
    local_generated: int = 0
    cost: float = 0.0


class Budget(BaseModel):
    max_tokens: int = 8000
    max_images: int = 8
    max_retry_rounds: int = 2
    cost_limit: float = 5.0
    currency: str = "CNY"


class Usage(BaseModel):
    tokens: dict[str, TokenUsage] = Field(default_factory=dict, description="key为agent名")
    images: ImageUsage = Field(default_factory=ImageUsage)
    tts_cost: float = 0.0
    total_cost: float = 0.0


class CostTracker(BaseModel):
    video_id: str
    budget: Budget = Field(default_factory=Budget)
    usage: Usage = Field(default_factory=Usage)
    status: BudgetStatus = BudgetStatus.WITHIN_BUDGET
