import sys
import uuid
import logging
import structlog

from src.graph import build_graph
from src.schemas.cost import CostTracker
from src.services.cost_tracker import CostTrackerService
from src.agents.base import AgentError, BudgetExceededError
from config.settings import settings

logger = structlog.get_logger()

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def main():
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            LOG_LEVEL_MAP.get(settings.log_level.upper(), logging.INFO)
        ),
    )

    print("=" * 60)
    print("  AI Video Studio - MVP")
    print("=" * 60)

    if not settings.deepseek_api_key:
        print("错误: 请在.env文件中配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    user_input = input("请输入视频主题: ").strip()
    if not user_input:
        print("主题不能为空")
        sys.exit(1)

    print("\n内容类型:")
    print("  [1] 知识科普  [2] 故事/剧情  [3] 热点追踪  [4] 产品带货")
    type_choice = input("请选择 (默认1): ").strip() or "1"
    content_type_map = {"1": "science", "2": "story", "3": "trending", "4": "product"}
    content_type = content_type_map.get(type_choice, "science")

    tone_input = input("语气风格 (默认: 幽默通俗): ").strip() or "幽默通俗"

    duration_input = input("目标时长/秒 (默认: 60): ").strip() or "60"
    duration = int(duration_input)

    video_id = str(uuid.uuid4())[:8]

    initial_state = {
        "video_id": video_id,
        "user_input": user_input,
        "content_type": content_type,
        "tone": tone_input,
        "duration": duration,
        "script": None,
        "production_plan": None,
        "generated_clips": {},
        "generated_images": {},
        "generated_audios": {},
        "video_draft_path": None,
        "final_video_path": None,
        "review_report": None,
        "review_round": 0,
        "cost_tracker": CostTracker(video_id=video_id),
        "human_feedback": None,
        "human_action": None,
        "status": "pending",
        "error": None,
    }

    graph = build_graph()

    try:
        result = graph.invoke(initial_state)
        tracker_service = CostTrackerService(result["cost_tracker"])
        print(tracker_service.print_report())
        if result.get("final_video_path"):
            print(f"\n最终视频: {result['final_video_path']}")
    except BudgetExceededError as e:
        logger.error("budget_exceeded", error=str(e))
        print("预算超限，流水线停止。")
        print(CostTrackerService(initial_state["cost_tracker"]).print_report())
    except AgentError as e:
        logger.error("agent_error", agent=e.agent_name, error=str(e))
        if not e.recoverable:
            print(f"不可恢复错误: {e}")
        else:
            print(f"Agent错误: {e}")
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        logger.exception("unexpected_error")
        print(f"\n流水线执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
