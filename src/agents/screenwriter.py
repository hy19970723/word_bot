import json
from pathlib import Path

from src.agents.base import BaseAgent, AgentError
from src.services.llm import LLMService, LLMOutputError
from src.services.cost_tracker import CostTrackerService
from src.schemas.script import Script
from src.state import VideoState


SHOT_COUNT_TABLE = {
    "science": [(30, 60, 4, 6), (60, 120, 6, 10), (120, 180, 10, 12)],
    "story": [(60, 120, 6, 10), (120, 300, 10, 20)],
    "trending": [(30, 60, 3, 5), (60, 90, 5, 8)],
    "product": [(30, 60, 4, 8)],
}

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "config" / "templates" / "screenwriter"


def _calculate_shot_count(content_type: str, duration: int) -> int:
    rules = SHOT_COUNT_TABLE.get(content_type, SHOT_COUNT_TABLE["science"])
    for min_dur, max_dur, min_shots, max_shots in rules:
        if min_dur <= duration <= max_dur:
            return max(min_shots, min(max_shots, duration // 10))
    return max(4, min(12, duration // 10))


def _load_template(content_type: str) -> str:
    template_file = TEMPLATE_DIR / f"{content_type}.txt"
    if not template_file.exists():
        template_file = TEMPLATE_DIR / "science.txt"
    return template_file.read_text(encoding="utf-8")


class ScreenwriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("screenwriter")
        self.llm = LLMService(model_tier="creative")

    def execute(self, state: VideoState) -> dict:
        self.check_budget(state)

        topic = state["user_input"]
        content_type = state["content_type"]
        tone = state["tone"]
        duration = state["duration"]
        shot_count = _calculate_shot_count(content_type, duration)

        template = _load_template(content_type)
        json_schema = json.dumps(Script.model_json_schema(), ensure_ascii=False)

        prompt = template.format(
            topic=topic,
            tone=tone,
            duration=duration,
            target_audience="抖音用户",
            shot_count=shot_count,
            json_schema=json_schema,
        )

        feedback = state.get("human_feedback")
        if feedback:
            prompt += f"\n\n用户修改意见：{feedback}\n请根据以上意见调整你的创作。"

        try:
            script, usage = self.llm.generate_structured(prompt, Script)
        except LLMOutputError as e:
            raise AgentError(self.name, str(e), recoverable=False)

        tracker = CostTrackerService(state["cost_tracker"])
        tracker.record_token_usage(self.name, usage)

        self.logger.info("script_generated", title=script.title, shots=len(script.shots))

        return {
            "script": script,
            "cost_tracker": tracker.get_tracker(),
            "status": "awaiting_script_review",
        }
