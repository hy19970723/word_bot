from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import structlog

logger = structlog.get_logger()

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


class ImageGenService:
    def generate(
        self,
        prompt: str,
        output_path: str,
        model: str = "placeholder",
        size: str = "1024x1792",
        quality: str = "hd",
    ) -> dict:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=(30, 30, 40))
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 36)
                small_font = ImageFont.truetype("arial.ttf", 24)
            except (OSError, IOError):
                font = ImageFont.load_default()
                small_font = font

            draw.text(
                (VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2 - 60),
                "[占位图]",
                fill=(200, 200, 200),
                font=font,
                anchor="mm",
            )

            display_prompt = prompt[:60] + "..." if len(prompt) > 60 else prompt
            draw.text(
                (VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2 + 20),
                display_prompt,
                fill=(150, 150, 150),
                font=small_font,
                anchor="mm",
            )

            img.save(output_path, "PNG")

            logger.info("placeholder_image_generated", path=output_path)
            return {"path": output_path, "cost": 0.0, "model": "placeholder"}

        except Exception as e:
            raise ImageGenError(f"占位图生成失败: {e}")


class ImageGenError(Exception):
    pass
