import time
import jwt
import httpx
from pathlib import Path
import structlog

from config.settings import settings

logger = structlog.get_logger()

KLING_BASE_URL = "https://api.klingai.com"

KLING_PRICES = {
    "kling-v2-5-turbo": {"5s": 0.35},
    "kling-v2-6-std": {"5s": 0.28},
    "kling-v2-6-pro": {"5s": 0.49, "10s": 0.98},
}

TASK_POLL_INTERVAL = 5
TASK_MAX_WAIT = 300


class KlingService:
    def __init__(self):
        self.access_key = settings.kling_access_key
        self.secret_key = settings.kling_secret_key
        self.base_url = settings.kling_base_url

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iss": self.access_key,
            "exp": now + 1800,
            "nbf": now - 5,
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._generate_jwt()}",
            "Content-Type": "application/json",
        }

    def text_to_video(
        self,
        prompt: str,
        output_path: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        model: str = "",
        negative_prompt: str = "",
    ) -> dict:
        if not model:
            model = settings.kling_model

        payload = {
            "model_name": model,
            "prompt": prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
            "mode": "std",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.base_url}/v1/videos/text2video",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                raise KlingError(f"未获取到task_id: {data}")

            logger.info("kling_task_submitted", task_id=task_id, model=model, prompt=prompt[:50])

            video_url = self._poll_task(task_id)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self._download_video(video_url, output_path)

            price_key = f"{duration}s"
            usd_cost = KLING_PRICES.get(model, {}).get(price_key, 0.35)
            cny_cost = round(usd_cost * 7.2, 4)

            logger.info("kling_video_generated", path=output_path, cost=cny_cost)
            return {"path": output_path, "cost": cny_cost, "model": model}

        except httpx.HTTPStatusError as e:
            raise KlingError(f"Kling API错误 {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise KlingError(f"Kling网络请求失败: {e}")

    def _poll_task(self, task_id: str) -> str:
        elapsed = 0
        with httpx.Client(timeout=30) as client:
            while elapsed < TASK_MAX_WAIT:
                time.sleep(TASK_POLL_INTERVAL)
                elapsed += TASK_POLL_INTERVAL

                resp = client.get(
                    f"{self.base_url}/v1/videos/{task_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})

                status = data.get("task_status", "")
                if status == "succeed":
                    works = data.get("task_result", {}).get("videos", [])
                    if works:
                        return works[0].get("url", "")
                    raise KlingError("任务成功但未返回视频URL")
                elif status in ("failed", "timeout"):
                    raise KlingError(f"Kling任务失败: {status}")
                else:
                    logger.debug("kling_polling", task_id=task_id, status=status, elapsed=f"{elapsed}s")

        raise KlingError(f"Kling任务超时 ({TASK_MAX_WAIT}s)")

    @staticmethod
    def _download_video(url: str, output_path: str):
        with httpx.stream("GET", url, timeout=120) as r:
            r.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)


class KlingError(Exception):
    pass
