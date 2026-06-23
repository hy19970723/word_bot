import json
import subprocess
import httpx
from pathlib import Path
import structlog

logger = structlog.get_logger()

KLING_CLI = "kling"
DEFAULT_POLL_TIMEOUT = 300


class KlingService:
    def __init__(self, cli_command: str = KLING_CLI):
        self.cli = cli_command

    def check_login(self) -> bool:
        try:
            result = self._run([self.cli, "who_am_i", "--quiet"], timeout=15)
            return result is not None
        except Exception:
            return False

    def text_to_video(
        self,
        prompt: str,
        output_path: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        model: str = "",
    ) -> dict:
        cmd = [
            self.cli, "text_to_video", prompt,
            "--duration", str(duration),
            "--aspectRatio", aspect_ratio,
            "--poll", str(DEFAULT_POLL_TIMEOUT),
            "--quiet",
        ]
        if model:
            cmd.extend(["--model", model])

        data = self._run(cmd, timeout=DEFAULT_POLL_TIMEOUT + 30)
        if not data:
            raise KlingError("text_to_video 返回空结果")

        video_url = self._extract_url(data, "video")
        if not video_url:
            raise KlingError(f"text_to_video 未返回视频URL: {json.dumps(data, ensure_ascii=False)[:200]}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._download(video_url, output_path)

        cost = self._estimate_video_cost(duration)
        logger.info("kling_video_generated", path=output_path, cost=cost, duration=duration)
        return {"path": output_path, "cost": cost, "model": model or "default"}

    def text_to_image(
        self,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "9:16",
        model: str = "",
    ) -> dict:
        cmd = [
            self.cli, "text_to_image", prompt,
            "--aspectRatio", aspect_ratio,
            "--poll", str(DEFAULT_POLL_TIMEOUT),
            "--quiet",
        ]
        if model:
            cmd.extend(["--model", model])

        data = self._run(cmd, timeout=DEFAULT_POLL_TIMEOUT + 30)
        if not data:
            raise KlingError("text_to_image 返回空结果")

        image_url = self._extract_url(data, "image")
        if not image_url:
            raise KlingError(f"text_to_image 未返回图片URL: {json.dumps(data, ensure_ascii=False)[:200]}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._download(image_url, output_path)

        logger.info("kling_image_generated", path=output_path)
        return {"path": output_path, "cost": 0.0, "model": model or "kolors"}

    def image_to_video(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        model: str = "",
    ) -> dict:
        cmd = [
            self.cli, "image_to_video", prompt,
            "--image", image_path,
            "--poll", str(DEFAULT_POLL_TIMEOUT),
            "--quiet",
        ]
        if model:
            cmd.extend(["--model", model])

        data = self._run(cmd, timeout=DEFAULT_POLL_TIMEOUT + 30)
        if not data:
            raise KlingError("image_to_video 返回空结果")

        video_url = self._extract_url(data, "video")
        if not video_url:
            raise KlingError(f"image_to_video 未返回视频URL: {json.dumps(data, ensure_ascii=False)[:200]}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._download(video_url, output_path)

        cost = self._estimate_video_cost(5)
        logger.info("kling_image_to_video_generated", path=output_path, cost=cost)
        return {"path": output_path, "cost": cost, "model": model or "default"}

    def _run(self, cmd: list[str], timeout: int = 60) -> dict | None:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )
            if result.returncode != 0:
                logger.warning("kling_cli_error", returncode=result.returncode, stderr=result.stderr[:500])
                raise KlingError(f"CLI错误(rc={result.returncode}): {result.stderr[:200]}")

            output = result.stdout.strip()
            if not output:
                return None

            return json.loads(output)

        except subprocess.TimeoutExpired:
            raise KlingError(f"CLI超时({timeout}s)")
        except json.JSONDecodeError as e:
            raise KlingError(f"CLI输出解析失败: {e}")
        except FileNotFoundError:
            raise KlingError("kling CLI未安装，请运行: npm i -g @klingai/cli-cn")

    @staticmethod
    def _extract_url(data: dict, media_type: str) -> str | None:
        if isinstance(data, dict):
            if "url" in data:
                return data["url"]
            if "videos" in data:
                videos = data["videos"]
                if videos and isinstance(videos, list):
                    return videos[0].get("url")
            if "images" in data:
                images = data["images"]
                if images and isinstance(images, list):
                    return images[0].get("url")
            if "result" in data:
                return KlingService._extract_url(data["result"], media_type)
            if "data" in data:
                return KlingService._extract_url(data["data"], media_type)
            if "task_result" in data:
                return KlingService._extract_url(data["task_result"], media_type)
            for key in ("video_url", "image_url", "download_url", "file_url"):
                if key in data:
                    return data[key]
        if isinstance(data, list) and data:
            return KlingService._extract_url(data[0], media_type)
        return None

    @staticmethod
    def _download(url: str, output_path: str):
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    @staticmethod
    def _estimate_video_cost(duration: int) -> float:
        if duration <= 5:
            return round(0.35 * 7.2, 4)
        return round(0.49 * 7.2, 4)


class KlingError(Exception):
    pass
