import sys
import uuid
import logging
import structlog
from pathlib import Path

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
            char_count = len(p.characters)
            print(f"  [{i}] {p.name} ({p.genre}) - {ep_count}集 - {char_count}角色")
        print("  [0] 创建新项目")
        choice = input("请选择: ").strip()
        if choice != "0" and choice.isdigit() and 1 <= int(choice) <= len(projects):
            selected = projects[int(choice) - 1]
            print(f"\n已选择: {selected.name} (第{len(selected.episodes) + 1}集)")

            manage = input("管理项目设置(角色/参考图/世界观等)? [y/N]: ").strip().lower()
            if manage == "y":
                _manage_project_settings(pm, selected)

            return selected

    print("\n创建新项目:")
    name = input("项目名称: ").strip()
    if not name:
        name = "未命名项目"

    genre = input("类型 [1]科普 [2]故事 [3]热点 [4]带货 (默认2): ").strip() or "2"
    genre_map = {"1": "science", "2": "story", "3": "trending", "4": "product"}
    genre = genre_map.get(genre, "story")

    tone = input("语气风格 (默认: 热血爽文): ").strip() or "热血爽文"

    project = pm.create_project(name=name, genre=genre, tone=tone)
    print(f"\n项目已创建: {project.name}")

    setup = input("设置项目详情(世界观/角色/参考图等)? [y/N]: ").strip().lower()
    if setup == "y":
        _manage_project_settings(pm, project)

    return project


def _manage_project_settings(pm: ProjectManager, project):
    """项目设置管理菜单"""
    while True:
        print(f"\n--- {project.name} 设置 ---")
        print(f"  类型: {project.genre} | 语气: {project.tone}")
        if project.world_setting:
            print(f"  世界观: {project.world_setting}")
        if project.visual_style:
            print(f"  画面风格: {project.visual_style}")
        print(f"  角色: {len(project.characters)}个")
        for i, c in enumerate(project.characters, 1):
            ref = "✓" if c.reference_image_path else "✗"
            print(f"    [{ref}] {c.name}: {(c.current_appearance or c.description)[:40]}")

        print("\n操作:")
        print("  [1] 修改基本信息")
        print("  [2] 管理角色")
        print("  [3] 生成角色参考图")
        print("  [q] 返回")

        choice = input("请选择: ").strip().lower()
        if choice == "q":
            break
        elif choice == "1":
            project.world_setting = input(f"世界观 (当前: {project.world_setting}): ").strip() or project.world_setting
            project.visual_style = input(f"画面风格 (当前: {project.visual_style}): ").strip() or project.visual_style
            project.color_tone = input(f"色调 (当前: {project.color_tone}): ").strip() or project.color_tone
            project.overall_story = input(f"故事大纲 (当前: {project.overall_story[:30]}...): ").strip() or project.overall_story
            pm.save_project(project)
            print("已保存")
        elif choice == "2":
            _manage_characters(pm, project)
        elif choice == "3":
            _generate_reference_images(pm, project)


def _manage_characters(pm: ProjectManager, project):
    """管理角色"""
    while True:
        print("\n角色列表:")
        for i, c in enumerate(project.characters, 1):
            print(f"  [{i}] {c.name}: {(c.current_appearance or c.description)[:50]}")
        print("  [0] 添加新角色")
        print("  [q] 返回")

        choice = input("请选择: ").strip().lower()
        if choice == "q":
            break
        elif choice == "0":
            name = input("角色名称: ").strip()
            if name:
                desc = input(f"{name}的外貌描述: ").strip()
                personality = input(f"{name}的性格 (可选): ").strip()
                project.characters.append(Character(
                    name=name, description=desc, personality=personality,
                ))
                pm.save_project(project)
                print(f"已添加: {name}")
        elif choice.isdigit() and 1 <= int(choice) <= len(project.characters):
            char = project.characters[int(choice) - 1]
            print(f"\n编辑: {char.name}")
            new_desc = input(f"外貌 (当前: {char.current_appearance or char.description}): ").strip()
            if new_desc:
                char.current_appearance = new_desc
            new_state = input(f"状态 (当前: {char.current_state or '初始'}): ").strip()
            if new_state:
                char.current_state = new_state
            pm.save_project(project)
            print("已保存")


def _generate_reference_images(pm: ProjectManager, project):
    """生成角色参考图"""
    from src.services.kling import KlingService
    kling = KlingService(cli_command=settings.kling_cli_command)
    if not kling.check_login():
        print("可灵未登录，请先运行: kling login")
        return

    if not project.characters:
        print("没有角色，请先添加角色")
        return

    for char in project.characters:
        desc = char.current_appearance or char.description
        print(f"\n{char.name}: {desc}")
        gen = input("生成参考图? [Y/n]: ").strip().lower()
        if gen != "n":
            print("  正在生成...")
            success = pm.generate_character_reference_image(project, char.name, kling)
            if success:
                print(f"  已保存: {char.reference_image_path}")
            else:
                print("  生成失败")


def format_character_descriptions(project) -> str:
    if not project or not project.characters:
        return ""
    lines = []
    for char in project.characters:
        appearance = char.current_appearance or char.description
        line = f"- {char.name}: {appearance}"
        if char.personality:
            line += f"（性格: {char.personality}）"
        if char.current_state:
            line += f"（状态: {char.current_state}）"
        lines.append(line)
    return "\n".join(lines)


def main():
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            LOG_LEVEL_MAP.get(settings.log_level.upper(), logging.INFO)
        ),
    )

    print("=" * 60)
    print("  AI Video Studio")
    print("=" * 60)

    if not settings.deepseek_api_key:
        print("错误: 请在.env文件中配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    pm = ProjectManager()

    # 项目选择
    project = None
    episode_number = 1
    previous_summary = ""
    character_descriptions = ""
    project_context = ""
    content_type = "story"
    tone = "热血爽文"

    use_project = input("\n选择项目? [Y/n]: ").strip().lower()
    if use_project != "n":
        project = select_or_create_project(pm)
        episode_number = len(project.episodes) + 1
        previous_summary = pm.get_previous_episodes_summary(project)
        character_descriptions = format_character_descriptions(project)
        project_context = pm.build_screenwriter_context(project)
        content_type = project.genre
        tone = project.tone

    # 极简输入
    user_input = input("\n视频主题: ").strip()
    if not user_input:
        print("主题不能为空")
        sys.exit(1)

    tone_override = input(f"语气风格 (回车使用默认: {tone}): ").strip()
    if tone_override:
        tone = tone_override

    # 自动计算时长
    duration = 30
    duration_input = input(f"目标时长/秒 (回车默认{duration}): ").strip()
    if duration_input.isdigit():
        duration = max(15, int(duration_input))

    video_id = str(uuid.uuid4())[:8]

    if project:
        ep_dir = pm.get_episode_dir(project, episode_number)
        output_dir = str(ep_dir)
    else:
        output_dir = str(Path(settings.output_dir) / video_id)

    initial_state = {
        "video_id": video_id,
        "user_input": user_input,
        "content_type": content_type,
        "tone": tone,
        "duration": duration,
        "project": project,
        "episode_number": episode_number,
        "previous_episodes_summary": previous_summary,
        "character_descriptions": character_descriptions,
        "project_context": project_context,
        "output_dir": output_dir,
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

        # 自动保存集数信息
        if project and result.get("script") and result.get("final_video_path"):
            from src.schemas.project import EpisodeSummary

            # 简化录入：自动填充，用户可修改
            summary = result["script"].metadata.topic
            print(f"\n本集摘要: {summary}")
            edit_summary = input("修改摘要 (回车跳过): ").strip()
            if edit_summary:
                summary = edit_summary

            episode = EpisodeSummary(
                episode_number=episode_number,
                title=result["script"].title,
                summary=summary,
                script_path=f"{output_dir}/script.json",
                video_path=result["final_video_path"],
                characters_appeared=[c.name for c in project.characters],
            )
            pm.add_episode(project, episode)

            episode_cost = result["cost_tracker"].usage.total_cost
            project.episode_costs[str(episode_number)] = episode_cost
            project.total_cost += episode_cost
            pm.save_project(project)

            print(f"已保存为 {project.name} 第{episode_number}集 (花费: {episode_cost:.4f} CNY)")

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
