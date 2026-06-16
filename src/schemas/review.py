from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    APPROVED = "approved"
    REVISION_NEEDED = "revision_needed"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewIssue(BaseModel):
    severity: Severity
    shot_id: Optional[int] = Field(default=None, description="关联的镜头ID，None表示全局问题")
    dimension: str = Field(description="所属审核维度")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")


class DimensionReview(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewReport(BaseModel):
    review_id: str = Field(description="UUID")
    script_id: str
    round: int = Field(ge=1, description="当前审核轮次")
    max_rounds: int = Field(default=2)
    verdict: Verdict
    overall_score: int = Field(ge=0, le=100)
    dimensions: dict[str, DimensionReview] = Field(description="key为维度名: compliance/technical_quality/content_quality/platform_fit")
    revision_instructions: str = Field(default="", description="打回时的总体修改指引")
