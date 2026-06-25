import sys
import uuid
import logging
import structlog

from src.graph import build_graph
from src.schemas.cost import CostTracker
from src.schemas.project import Character
from src.services.cost_tracker import CostTrackerService
from src.services.project_manager import ProjectManager
from src.agents.base import AgentError, BudgetExceededError
from config.settings import settings

logger = structlog.get_logger()

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def select_or_create_project(pm: ProjectManager):
    projects = pm.list_projects()

    print("\n" + "=" * 60)
    print("  项目管理")
    print("=" * 60)

    if projects:
        print("已有项目:")
        for i, p in enumerate(projects, 1):
            ep_count = len(p.episodes)
            print(f"  [{i}] {p.name} ({p.genre}) - {ep_count}集")
        print("  [0] 创建新项目")
        choice = input("请选择: ").strip()
        if choice != "0" and choice.isdigit() and 1 <= int(choice) <= len(projects):
            return projects[int(choice) - 1]

    print("\n创建新项目:")
    name = input("项目名称 (如'赘婿逆袭'): ").strip()
    if not name:
        name = "未命名项目"

    print("类型: [1]知识科普 [2]故事/剧情 [3]热点追踪 [4]产品带货")
    genre_choice = input("请选择 (默认2): ").strip() or "2"
    genre_map = {"1": "science", "2": "story", "3": "trending", "4": "product"}
    genre = genre_map.get(genre_choice, "story")

    tone = input("语气风格 (默认: 热血爽文): ").strip() or "热血爽文"
    overall_story = input("整体故事大纲 (可选，回车跳过): ").strip()

    characters = []
    print("\n角色设定 (输入空名称结束):")
    while True:
        char_name = input("  角色名称: ").strip()
        if not char_name:
            break
        char_desc = input(f"  {char_name}的外貌描述 (用于AI生成): ").strip()
        char_personality = input(f"  {char_name}的性格描述 (可选): ").strip()
        characters.append(Character(
            name=char_name,
            description=char_desc,
            personality=char_personality,
        ))

    project = pm.create_project(
        name=name,
        genre=genre,
        overall_story=overall_story,
        tone=tone,
        characters=characters,
    )
    print(f"\n项目已创建: {project.name} (ID: {project.project_id})")
    return project


def format_character_descriptions(project) -> str:
    if not project or not project.characters:
        return ""
    lines = []
    for char in project.characters:
        line = f"- {char.name}: {char.description}"
        if char.personality:
            line += f"（性格: {char.personality}）"
        lines.append(line)
    return "\n".join(lines)


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

    pm = ProjectManager()

    use_project = input("\n是否使用项目管理? [y/N]: ").strip().lower()
    project = None
    episode_number = 1
    previous_summary = ""
    character_descriptions = ""

    if use_project == "y":
        project = select_or_create_project(pm)
        episode_number = len(project.episodes) + 1
        previous_summary = pm.get_previous_episodes_summary(project)
        character_descriptions = format_character_descriptions(project)
        print(f"\n当前: {project.name} 第{episode_number}集")

    user_input = input("请输入视频主题: ").strip()
    if not user_input:
        print("主题不能为空")
        sys.exit(1)

    if project:
        content_type = project.genre
        tone_input = project.tone
    else:
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
        "project": project,
        "episode_number": episode_number,
        "previous_episodes_summary": previous_summary,
        "character_descriptions": character_descriptions,
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

        if project and result.get("script") and result.get("final_video_path"):
            from src.schemas.project import EpisodeSummary
            episode = EpisodeSummary(
                episode_number=episode_number,
                title=result["script"].title,
                summary=result["script"].metadata.topic,
                script_path=f"output/{video_id}/script.json",
                video_path=result["final_video_path"],
                characters_appeared=[c.name for c in project.characters],
            )
            pm.add_episode(project, episode)
            print(f"已保存为 {project.name} 第{episode_number}集")

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
