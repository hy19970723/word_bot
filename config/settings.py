from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")

    kling_cli_command: str = Field(default="kling", description="可灵CLI命令路径")

    max_tokens_per_video: int = Field(default=8000)
    max_images_per_video: int = Field(default=8)
    max_retry_rounds: int = Field(default=2)
    cost_limit_per_video: float = Field(default=5.0)

    output_dir: str = Field(default="./output")
    log_level: str = Field(default="INFO")

    default_voice_speed: float = Field(default=1.0)

    default_resolution: str = Field(default="1080x1920")
    default_fps: int = Field(default=30)
    default_aspect_ratio: str = Field(default="9:16")


settings = Settings()
