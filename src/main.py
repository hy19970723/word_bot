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
            char_with_ref = sum(1 for c in p.characters if c.reference_image_path)
            print(f"  [{i}] {p.name} ({p.genre}) - {ep_count}集 - {char_count}角色({char_with_ref}有参考图)")
        print("  [0] 创建新项目")
        choice = input("请选择: ").strip()
        if choice != "0" and choice.isdigit() and 1 <= int(choice) <= len(projects):
            selected = projects[int(choice) - 1]

            # 显示项目详情
            print(f"\n项目: {selected.name}")
            if selected.characters:
                print("角色:")
                for char in selected.characters:
                    ref_status = "✓" if char.reference_image_path else "✗"
                    appearance = char.current_appearance or char.description
                    print(f"  [{ref_status}] {char.name}: {appearance[:50]}...")

            # 询问是否管理角色参考图
            manage_ref = input("\n管理角色参考图? [y/N]: ").strip().lower()
            if manage_ref == "y":
                _manage_character_references(pm, selected)

            return selected

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

    # 世界观和视觉风格
    print("\n--- 世界观与视觉 ---")
    world_setting = input("世界观设定 (如'现代都市，2025年'，可选): ").strip()
    visual_style = input("画面风格 (电影感/动漫风/写实/赛博朋克，默认: 写实): ").strip() or "写实"
    color_tone = input("色调偏好 (暗色调/暖色调/冷色调，可选): ").strip()

    # 故事规划
    print("\n--- 故事规划 ---")
    planned_eps = input("预计总集数 (可选，回车跳过): ").strip()
    planned_episodes = int(planned_eps) if planned_eps.isdigit() else None

    story_arcs = []
    print("故事阶段划分 (输入空名称结束):")
    while True:
        arc_name = input("  阶段名称 (如'入赘篇'): ").strip()
        if not arc_name:
            break
        arc_episodes = input(f"  {arc_name} 集数范围 (如'1-5'): ").strip()
        arc_desc = input(f"  {arc_name} 描述: ").strip()
        story_arcs.append({
            "name": arc_name,
            "episodes": arc_episodes,
            "description": arc_desc,
        })

    # 音乐和发布
    print("\n--- 音乐与发布 ---")
    bgm_style = input("BGM风格 (紧张悬疑/热血激昂/温馨治愈，可选): ").strip()
    target_platform_input = input("目标平台 (逗号分隔: douyin,tiktok,bilibili，默认douyin): ").strip()
    target_platform = [p.strip() for p in target_platform_input.split(",")] if target_platform_input else ["douyin"]
    publish_schedule = input("发布频率 (每天一集/每周一集，可选): ").strip()

    tags_input = input("标签/关键词 (逗号分隔，可选): ").strip()
    tags = [t.strip() for t in tags_input.split(",")] if tags_input else []

    target_audience = input("目标受众 (如'18-35岁男性'，可选): ").strip()

    # 角色设定
    characters = []
    print("\n--- 角色设定 ---")
    print("角色设定 (输入空名称结束):")
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

    # 创作备忘
    notes = []
    print("\n--- 创作备忘 ---")
    print("创作备忘 (输入空行结束):")
    while True:
        note = input("  备忘: ").strip()
        if not note:
            break
        notes.append(note)

    project = pm.create_project(
        name=name,
        genre=genre,
        overall_story=overall_story,
        tone=tone,
        world_setting=world_setting,
        planned_episodes=planned_episodes,
        story_arcs=story_arcs,
        visual_style=visual_style,
        color_tone=color_tone,
        bgm_style=bgm_style,
        target_platform=target_platform,
        publish_schedule=publish_schedule,
        tags=tags,
        target_audience=target_audience,
        notes=notes,
        characters=characters,
    )
    print(f"\n项目已创建: {project.name} (ID: {project.project_id})")

    if project.characters:
        print("\n是否生成角色参考图? (用于保持角色外貌一致性)")
        gen_ref = input("[y/N]: ").strip().lower()
        if gen_ref == "y":
            from src.services.kling import KlingService
            kling = KlingService(cli_command=settings.kling_cli_command)
            if kling.check_login():
                for char in project.characters:
                    print(f"\n正在生成 {char.name} 的参考图...")
                    print(f"  描述: {char.description}")
                    success = pm.generate_character_reference_image(project, char.name, kling)
                    if success:
                        print(f"  参考图已保存: {char.reference_image_path}")
                    else:
                        print("  生成失败，跳过")
            else:
                print("可灵未登录，跳过角色参考图生成")
                print("提示: 运行 'kling login' 登录后可生成")

    return project


def _manage_character_references(pm: ProjectManager, project):
    """管理角色参考图"""
    from src.services.kling import KlingService

    kling = KlingService(cli_command=settings.kling_cli_command)
    if not kling.check_login():
        print("可灵未登录，无法生成参考图")
        print("提示: 运行 'kling login' 登录")
        return

    if not project.characters:
        print("该项目没有角色")
        return

    print("\n角色参考图管理:")
    for i, char in enumerate(project.characters, 1):
        ref_status = f"有: {char.reference_image_path}" if char.reference_image_path else "无"
        appearance = char.current_appearance or char.description
        print(f"  [{i}] {char.name}")
        print(f"      外貌: {appearance}")
        print(f"      参考图: {ref_status}")

    while True:
        choice = input("\n选择角色编号生成/更新参考图 (回车结束): ").strip()
        if not choice:
            break
        if not choice.isdigit() or not (1 <= int(choice) <= len(project.characters)):
            print("无效选择")
            continue

        char = project.characters[int(choice) - 1]
        print(f"\n正在生成 {char.name} 的参考图...")
        print(f"  描述: {char.current_appearance or char.description}")

        # 允许修改描述
        new_desc = input("  修改描述 (回车使用当前): ").strip()
        if new_desc:
            char.current_appearance = new_desc
            pm.save_project(project)

        success = pm.generate_character_reference_image(project, char.name, kling)
        if success:
            print(f"  参考图已保存: {char.reference_image_path}")
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
        if char.reference_image_path:
            line += "（有参考图）"
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
    project_context = ""

    if use_project == "y":
        project = select_or_create_project(pm)
        episode_number = len(project.episodes) + 1
        previous_summary = pm.get_previous_episodes_summary(project)
        character_descriptions = format_character_descriptions(project)
        project_context = pm.build_screenwriter_context(project)
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

    # 确定输出目录
    if project:
        ep_dir = pm.get_episode_dir(project, episode_number)
        output_dir = str(ep_dir)
    else:
        output_dir = str(Path(settings.output_dir) / video_id)

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

        if project and result.get("script") and result.get("final_video_path"):
            from src.schemas.project import EpisodeSummary

            # 收集本集的详细信息
            print("\n" + "=" * 60)
            print("  本集信息录入")
            print("=" * 60)

            # 剧情摘要
            summary = input("本集剧情摘要: ").strip()
            if not summary:
                summary = result["script"].metadata.topic

            # 关键事件
            key_events = []
            print("\n关键事件 (输入空行结束):")
            while True:
                event = input("  事件: ").strip()
                if not event:
                    break
                key_events.append(event)

            # 角色状态变化
            character_states = {}
            if project.characters:
                print("\n角色状态变化 (回车跳过):")
                for char in project.characters:
                    current = char.current_state or "初始状态"
                    new_state = input(f"  {char.name} (当前: {current}) -> 新状态: ").strip()
                    if new_state:
                        character_states[char.name] = new_state

            # 伏笔管理
            print("\n伏笔/剧情线索管理:")
            plot_thread_ids = []

            # 新增伏笔
            print("新增伏笔 (输入空描述结束):")
            while True:
                desc = input("  伏笔描述: ").strip()
                if not desc:
                    break
                importance = input("  重要性 [low/normal/high/critical] (默认normal): ").strip() or "normal"
                thread = pm.add_plot_thread(project, desc, episode_number, importance)
                plot_thread_ids.append(thread.thread_id)
                print(f"  已添加: {thread.thread_id}")

            # 解决已有伏笔
            unresolved = [t for t in project.plot_threads if not t.resolved]
            if unresolved:
                print("\n未解决的伏笔:")
                for t in unresolved:
                    print(f"  [{t.thread_id}] {t.description} (第{t.introduced_episode}集)")
                resolve_id = input("本集解决了哪个伏笔? (输入ID，回车跳过): ").strip()
                if resolve_id:
                    pm.resolve_plot_thread(project, resolve_id, episode_number)
                    plot_thread_ids.append(resolve_id)

            episode = EpisodeSummary(
                episode_number=episode_number,
                title=result["script"].title,
                summary=summary,
                script_path=f"{output_dir}/script.json",
                video_path=result["final_video_path"],
                characters_appeared=[c.name for c in project.characters],
                character_states=character_states,
                plot_threads=plot_thread_ids,
                key_events=key_events,
            )
            pm.add_episode(project, episode)

            # 更新角色状态
            if character_states:
                pm.update_character_states(project, episode)

            # 记录本集花费
            episode_cost = result["cost_tracker"].usage.total_cost
            project.episode_costs[str(episode_number)] = episode_cost
            project.total_cost += episode_cost
            pm.save_project(project)

            # 角色外貌变化
            if project.characters:
                print("\n角色外貌变化 (回车跳过):")
                for char in project.characters:
                    current_appearance = char.current_appearance or char.description
                    new_appearance = input(f"  {char.name} (当前: {current_appearance}) -> 新外貌: ").strip()
                    if new_appearance:
                        reason = input("  变化原因: ").strip()
                        pm.update_character_appearance(
                            project, char.name, new_appearance, episode_number, reason
                        )
                        print(f"  已更新 {char.name} 的外貌")

                        # 询问是否重新生成参考图
                        regen = input(f"  是否重新生成 {char.name} 的参考图? [y/N]: ").strip().lower()
                        if regen == "y":
                            from src.services.kling import KlingService
                            kling = KlingService(cli_command=settings.kling_cli_command)
                            if kling.check_login():
                                success = pm.generate_character_reference_image(project, char.name, kling)
                                if success:
                                    print(f"  参考图已更新: {char.reference_image_path}")
                                else:
                                    print("  生成失败")
                            else:
                                print("  可灵未登录，跳过")

            print(f"\n已保存为 {project.name} 第{episode_number}集")

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
