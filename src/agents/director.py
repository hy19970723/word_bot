import uuid

from src.agents.base import BaseAgent
from src.schemas.script import Script
from src.schemas.plan import (
    ProductionPlan, ShotSourceMapping, ImageSource,
    GenerationParams, AudioPlan, EditPlan, ProductionBudget,
    SubtitleAnimation,
)
from src.state import VideoState


def _decide_quality_for_shot(shot) -> tuple[str, str]:
    if shot.priority.value == "high":
        return "dall-e-3", "hd"
    return "dall-e-3", "standard"


def _decide_bgm_style(tone: str) -> str:
    if any(k in tone for k in ("幽默", "轻松", "通俗")):
        return "轻快电子"
    elif any(k in tone for k in ("严肃", "专业")):
        return "简约钢琴"
    elif any(k in tone for k in ("悬疑", "紧张")):
        return "暗黑氛围"
    return "轻快电子"


def _decide_subtitle_animation(style: str) -> SubtitleAnimation:
    mapping = {
        "science": SubtitleAnimation.TYPEWRITER,
        "story": SubtitleAnimation.FADE,
        "trending": SubtitleAnimation.SLIDE_UP,
        "product": SubtitleAnimation.SLIDE_UP,
    }
    return mapping.get(style, SubtitleAnimation.TYPEWRITER)


def _decide_transition(style: str) -> str:
    if style in ("trending", "product"):
        return "cut"
    return "crossfade"


class DirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__("director")

    def execute(self, state: VideoState) -> dict:
        self.check_budget(state)

        script: Script = state["script"]
        style = script.style

        shot_sources = []
        for shot in script.shots:
            model, quality = _decide_quality_for_shot(shot)
            shot_sources.append(ShotSourceMapping(
                shot_id=shot.id,
                source=ImageSource.AI_GENERATE,
                generate_prompt=shot.image_prompt,
                image_model=model,
            ))

        plan = ProductionPlan(
            plan_id=str(uuid.uuid4())[:8],
            script_id=script.script_id,
            shot_sources=shot_sources,
            generation_params=GenerationParams(
                image_model="dall-e-3",
                image_size="1024x1792",
                image_quality="hd",
            ),
            audio_plan=AudioPlan(
                voice_id=script.global_settings.voice_id,
                voice_speed=script.global_settings.voice_speed,
            ),
            edit_plan=EditPlan(
                default_transition=_decide_transition(style),
                subtitle_animation=_decide_subtitle_animation(style),
            ),
            budget=ProductionBudget(
                max_images_to_generate=len(script.shots),
            ),
        )

        self.logger.info("plan_generated", shots=len(shot_sources))

        return {
            "production_plan": plan,
            "status": "editing",
        }
