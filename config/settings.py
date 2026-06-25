from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")

    kling_cli_command: str = Field(default="kling", description="可灵CLI命令路径")
    kling_model: str = Field(default="kling-video-v2_5", description="可灵视频模型: kling-video-v2_5(最便宜) / kling-video-v2_6 / kling-video-v3_0_turbo / kling-video-v3_0")
    kling_resolution: str = Field(default="720p", description="可灵视频分辨率: 720p(省) / 1080p(高清)")
    kling_duration: int = Field(default=5, description="可灵视频时长(秒): 5(省) / 10")
    kling_video_mode: str = Field(default="all_video", description="生成模式: all_video(全视频) / mixed(关键视频+其他图片) / all_image(全图片最省)")
    kling_image_model: str = Field(default="kling-image-v2_1", description="可灵图片模型: kling-image-v2_1(最便宜) / kling-image-v3_0")
    kling_image_resolution: str = Field(default="1k", description="可灵图片分辨率: 1k(省) / 2k / 4k(高清)")

    llm_screenwriter_tier: str = Field(default="auto", description="编剧模型: auto(按类型自动选) / chat(快省) / reasoner(深度思考)")
    llm_reviewer_enabled: bool = Field(default=True, description="是否启用审核Agent: true / false(关闭省一轮LLM)")
    llm_reviewer_tier: str = Field(default="efficient", description="审核模型: efficient(chat快省) / reasoning(reasoner深度)")

    preview_mode: bool = Field(default=False, description="预览模式: true(只生成第1个镜头) / false(全部生成)")

    max_tokens_per_video: int = Field(default=8000)
    max_images_per_video: int = Field(default=8)
    max_shots: int = Field(default=4, description="最大镜头数")
    max_retry_rounds: int = Field(default=2)
    cost_limit_per_video: float = Field(default=5.0)

    output_dir: str = Field(default="./output")
    log_level: str = Field(default="INFO")

    default_voice_speed: float = Field(default=1.0)

    default_resolution: str = Field(default="1080x1920")
    default_fps: int = Field(default=30)
    default_aspect_ratio: str = Field(default="9:16")


settings = Settings()
