from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ShotType(str, Enum):
    OPENING = "opening"
    CONTENT = "content"
    TRANSITION = "transition"
    CLOSING = "closing"


class ImageStyle(str, Enum):
    REALISTIC = "realistic"
    ILLUSTRATION = "illustration"
    ANIME = "anime"
    PHOTOGRAPHIC = "photographic"
    CINEMATIC = "cinematic"
    THREE_D = "3d_render"


class TransitionType(str, Enum):
    CUT = "cut"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CROSSFADE = "crossfade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"


class CameraEffect(str, Enum):
    STATIC = "static"
    ZOOM_IN_SLOW = "zoom_in_slow"
    ZOOM_OUT_SLOW = "zoom_out_slow"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    KEN_BURNS = "ken_burns"


class BGMMood(str, Enum):
    MYSTERIOUS = "mysterious"
    CASUAL = "casual"
    UPBEAT = "upbeat"
    DRAMATIC = "dramatic"
    EMOTIONAL = "emotional"
    TENSE = "tense"
    INSPIRING = "inspiring"


class ShotPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Shot(BaseModel):
    id: int = Field(description="镜头序号，从1开始")
    type: ShotType = Field(description="镜头类型")
    duration: float = Field(ge=2.0, le=30.0, description="镜头时长（秒）")
    image_prompt: str = Field(min_length=10, max_length=500, description="画面描述，用于AI生图，要求具体、可视化")
    image_style: ImageStyle = Field(default=ImageStyle.REALISTIC, description="画面风格")
    narration: str = Field(min_length=1, max_length=200, description="旁白文案，口语化")
    subtitle: str = Field(description="字幕文本，用\\n换行，每行不超过15个字")
    transition_in: TransitionType = Field(default=TransitionType.CUT, description="进入转场")
    transition_out: TransitionType = Field(default=TransitionType.CUT, description="离开转场")
    camera_effect: CameraEffect = Field(default=CameraEffect.KEN_BURNS, description="镜头运动效果")
    bgm_mood: BGMMood = Field(default=BGMMood.CASUAL, description="该镜头的BGM情绪")
    priority: ShotPriority = Field(default=ShotPriority.NORMAL, description="素材生成优先级，high=用高质量模型")


class GlobalSettings(BaseModel):
    bgm_style: str = Field(default="轻快电子", description="BGM整体风格")
    voice_id: str = Field(default="zh-CN-YunxiNeural", description="TTS音色ID")
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率")
    subtitle_font: str = Field(default="NotoSansSC-Bold", description="字幕字体")
    subtitle_font_size: int = Field(default=42, description="字幕字号")
    subtitle_position: str = Field(default="bottom", description="字幕位置: bottom/center/top")
    subtitle_color: str = Field(default="#FFFFFF", description="字幕颜色")
    subtitle_outline_color: str = Field(default="#000000", description="字幕描边颜色")
    subtitle_outline_width: int = Field(default=2, description="字幕描边宽度")


class ScriptMetadata(BaseModel):
    topic: str = Field(description="主题")
    target_audience: str = Field(default="", description="目标受众")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    platform: list[str] = Field(default=["douyin", "tiktok"], description="目标平台")


class Script(BaseModel):
    script_id: str = Field(description="UUID")
    version: int = Field(default=1, description="脚本版本号，每次修改+1")
    title: str = Field(min_length=1, max_length=50, description="视频标题")
    style: str = Field(description="内容类型: science/story/trending/product")
    tone: str = Field(default="幽默通俗", description="语气风格")
    total_duration: int = Field(ge=15, le=600, description="总时长（秒）")
    aspect_ratio: str = Field(default="9:16", description="画面比例")
    resolution: str = Field(default="1080x1920", description="分辨率")
    fps: int = Field(default=30, description="帧率")
    metadata: ScriptMetadata
    shots: list[Shot] = Field(min_length=2, max_length=30, description="镜头列表")
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)
