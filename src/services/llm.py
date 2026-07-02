from openai import OpenAI
from pydantic import BaseModel
import json
import structlog

from config.settings import settings

logger = structlog.get_logger()

MODEL_ROUTING = {
    "reasoning": {
        "model": "deepseek-reasoner",
        "temperature": None,
        "max_tokens": 4096,
    },
    "chat": {
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 4096,
    },
    "creative": {
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 4096,
    },
    "efficient": {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2048,
    },
}

TOKEN_PRICES = {
    "deepseek-chat": {"prompt": 1.0 / 1_000_000, "completion": 2.0 / 1_000_000},
    "deepseek-reasoner": {"prompt": 4.0 / 1_000_000, "completion": 16.0 / 1_000_000},
}

CONTENT_TYPE_TIER = {
    "science": "reasoning",
    "story": "reasoning",
    "trending": "creative",
    "product": "creative",
}


class LLMService:
    def __init__(self, model_tier: str = "efficient"):
        self.tier = model_tier
        self.config = MODEL_ROUTING[model_tier]
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        max_retries: int = 2,
    ) -> tuple[BaseModel, dict]:
        schema_str = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        full_prompt = f"{prompt}\n\n请严格按照以下JSON Schema输出：\n{schema_str}"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                current_prompt = full_prompt
                if attempt > 0:
                    current_prompt += f"\n\n[第{attempt+1}次尝试] 上次输出格式有误：{last_error}，请修正后重新输出。"

                params = {
                    "model": self.config["model"],
                    "messages": [{"role": "user", "content": current_prompt}],
                    "max_tokens": self.config["max_tokens"],
                    "response_format": {"type": "json_object"},
                }
                if self.config["temperature"] is not None:
                    params["temperature"] = self.config["temperature"]

                response = self.client.chat.completions.create(**params)

                content = response.choices[0].message.content
                parsed = response_model.model_validate_json(content)

                usage = self._calculate_usage(response.usage)
                return parsed, usage

            except (json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                logger.warning("llm_parse_failed", attempt=attempt + 1, error=str(e))
                continue

        raise LLMOutputError(f"LLM输出解析失败，已重试{max_retries}次: {last_error}")

    def _calculate_usage(self, usage) -> dict:
        model = self.config["model"]
        prices = TOKEN_PRICES.get(model, {"prompt": 0, "completion": 0})
        cost = (usage.prompt_tokens * prices["prompt"]
                + usage.completion_tokens * prices["completion"])
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "model": model,
            "cost": round(cost, 4),
        }


class LLMOutputError(Exception):
    pass
