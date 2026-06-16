from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict
from src.schemas.script import Script
from src.schemas.plan import ProductionPlan
from src.schemas.review import ReviewReport
from src.schemas.cost import CostTracker


class VideoState(TypedDict):
    video_id: str
    user_input: str
    content_type: str
    tone: str
    duration: int

    script: Optional[Script]
    production_plan: Optional[ProductionPlan]

    generated_images: dict[int, str]
    generated_audios: dict[int, str]
    video_draft_path: Optional[str]
    final_video_path: Optional[str]

    review_report: Optional[ReviewReport]
    review_round: int

    cost_tracker: CostTracker

    human_feedback: Optional[str]
    human_action: Optional[str]

    status: str
    error: Optional[str]
