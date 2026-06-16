from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ImageSource(str, Enum):
    AI_GENERATE = "ai_generate"
    STOCK_LIBRARY = "stock_library"
    REUSE_FROM_POOL = "reuse_from_pool"


class TTSEngine(str, Enum):
    EDGE_TTS = "edge-tts"
    FISH_AUDIO = "fish-audio"
    COSYVOICE = "cosyvoice"


class SubtitleAnimation(str, Enum):
    STATIC = "static"
    TYPEWRITER = "typewriter"
    FADE = "fade"
    SLIDE_UP = "slide_up"


class ShotSourceMapping(BaseModel):
    shot_id: int
    source: ImageSource
    search_query: str = Field(default="", description="素材库搜索关键词（source=stock/reuse时使用）")
    generate_prompt: str = Field(default="", description="AI生图prompt（source=ai_generate时使用，可覆盖script中的image_prompt）")
    image_model: str = Field(default="dall-e-3", description="使用的生图模型")


class GenerationParams(BaseModel):
    image_model: str = Field(default="dall-e-3")
    image_size: str = Field(default="1024x1792")
    image_quality: str = Field(default="hd")
    fallback_model: str = Field(default="stable-diffusion-xl")


class AudioPlan(BaseModel):
    tts_engine: TTSEngine = Field(default=TTSEngine.EDGE_TTS)
    voice_id: str = Field(default="zh-CN-YunxiNeural")
    voice_speed: float = Field(default=1.0)
    bgm_track: str = Field(default="", description="BGM文件路径或名称")
    bgm_volume: float = Field(default=0.15, ge=0.0, le=1.0)
    narration_volume: float = Field(default=1.0, ge=0.0, le=1.0)


class EditPlan(BaseModel):
    default_transition: str = Field(default="crossfade")
    transition_duration: float = Field(default=0.5, ge=0.1, le=2.0)
    subtitle_animation: SubtitleAnimation = Field(default=SubtitleAnimation.TYPEWRITER)
    opening_effect: str = Field(default="fade_in")
    ending_effect: str = Field(default="fade_out")


class ProductionBudget(BaseModel):
    max_images_to_generate: int = Field(default=8)
    max_cost: float = Field(default=5.0, description="预算上限（CNY）")
    currency: str = Field(default="CNY")


class ProductionPlan(BaseModel):
    plan_id: str = Field(description="UUID")
    script_id: str
    shot_sources: list[ShotSourceMapping] = Field(description="每个镜头的素材来源策略")
    generation_params: GenerationParams = Field(default_factory=GenerationParams)
    audio_plan: AudioPlan = Field(default_factory=AudioPlan)
    edit_plan: EditPlan = Field(default_factory=EditPlan)
    budget: ProductionBudget = Field(default_factory=ProductionBudget)
