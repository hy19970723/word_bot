from langgraph.graph import StateGraph, START, END

from src.state import VideoState
from src.agents.screenwriter import ScreenwriterAgent
from src.agents.director import DirectorAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent
from config.settings import settings


def build_graph():
    graph = StateGraph(VideoState)

    screenwriter = ScreenwriterAgent()
    director = DirectorAgent()
    editor = EditorAgent()
    reviewer = ReviewerAgent()

    graph.add_node("screenwriting", screenwriter.execute)
    graph.add_node("extract_characters", extract_characters_node)
    graph.add_node("auto_script_review", auto_script_review_node)
    graph.add_node("human_script_review", human_script_review_node)
    graph.add_node("directing", director.execute)
    graph.add_node("human_plan_review", human_plan_review_node)
    graph.add_node("editing", editor.execute)
    graph.add_node("reviewing", reviewer.execute)
    graph.add_node("skip_review", skip_review_node)
    graph.add_node("human_video_review", human_video_review_node)

    # 编剧 → 角色提取 → 自动审核循环
    graph.add_edge(START, "screenwriting")
    graph.add_edge("screenwriting", "extract_characters")
    graph.add_conditional_edges(
        "extract_characters",
        route_screenwriting_to_auto_review,
        {
            "auto_review": "auto_script_review",
            "skip_to_human": "human_script_review",
        }
    )

    # 自动审核 → 通过则人工确认，不通过则回到编剧
    graph.add_conditional_edges(
        "auto_script_review",
        route_auto_script_review,
        {
            "approved": "human_script_review",
            "revision": "screenwriting",
            "max_rounds": "human_script_review",
        }
    )

    # 人工确认脚本
    graph.add_conditional_edges(
        "human_script_review",
        route_after_script_review,
        {
            "approved": "directing",
            "revision": "screenwriting",
            "cancelled": END,
        }
    )

    # 导演 → 人工确认方案
    graph.add_edge("directing", "human_plan_review")
    graph.add_conditional_edges(
        "human_plan_review",
        route_after_plan_review,
        {
            "approved": "editing",
            "revision": "screenwriting",
            "cancelled": END,
        }
    )

    # 剪辑 → 审核
    graph.add_conditional_edges(
        "editing",
        route_editing_to_review,
        {
            "review": "reviewing",
            "skip": "skip_review",
        }
    )
    graph.add_conditional_edges(
        "reviewing",
        route_after_review,
        {
            "approved": "human_video_review",
            "revision_needed": "editing",
            "max_rounds_reached": "human_video_review",
        }
    )
    graph.add_edge("skip_review", "human_video_review")
    graph.add_conditional_edges(
        "human_video_review",
        route_after_video_review,
        {
            "approved": END,
            "revision": "editing",
            "cancelled": END,
        }
    )

    return graph.compile()


def extract_characters_node(state: VideoState) -> dict:
    """从脚本中自动提取角色信息"""
    project = state.get("project")
    script = state.get("script")

    if not project or not script:
        return {}

    if project.characters:
        return {}

    from src.services.character_extractor import CharacterExtractor
    from src.services.project_manager import ProjectManager

    extractor = CharacterExtractor()
    characters = extractor.extract(script)

    if characters:
        project.characters = characters
        pm = ProjectManager()
        pm.save_project(project)

        print(f"\n[自动提取] 发现 {len(characters)} 个角色:")
        for char in characters:
            print(f"  - {char.name}: {char.description[:60]}...")

        return {
            "project": project,
            "character_descriptions": _format_character_descriptions(project),
        }

    return {}


def _format_character_descriptions(project) -> str:
    if not project or not project.characters:
        return ""
    lines = []
    for char in project.characters:
        appearance = char.current_appearance or char.description
        line = f"- {char.name}: {appearance}"
        if char.personality:
            line += f"（性格: {char.personality}）"
        lines.append(line)
    return "\n".join(lines)


def route_screenwriting_to_auto_review(state: VideoState) -> str:
    """编剧完成后，决定是否进行自动审核"""
    if settings.llm_reviewer_enabled:
        return "auto_review"
    return "skip_to_human"


def route_auto_script_review(state: VideoState) -> str:
    """自动审核脚本后的路由"""
    report = state.get("review_report")
    if not report:
        return "approved"

    review_round = state.get("review_round", 0)

    if report.verdict.value == "approved":
        print(f"\n[自动审核] 通过 (评分: {report.overall_score}/100)")
        return "approved"

    if review_round >= report.max_rounds:
        print(f"\n[自动审核] 达到最大轮次 ({review_round}轮)，提交人工确认")
        return "max_rounds"

    print(f"\n[自动审核] 不通过 (评分: {report.overall_score}/100)")
    if report.revision_instructions:
        print(f"  修改建议: {report.revision_instructions[:100]}...")
    print(f"  第{review_round}轮，自动修改中...")
    return "revision"


def auto_script_review_node(state: VideoState) -> dict:
    """自动审核脚本节点 - 包装reviewer并设置feedback"""
    reviewer = ReviewerAgent()
    result = reviewer.execute(state)

    # 如果不通过，将修改建议设为human_feedback供编剧使用
    report = result.get("review_report")
    if report and report.verdict.value != "approved" and report.revision_instructions:
        result["human_feedback"] = report.revision_instructions

    return result


def route_editing_to_review(state: VideoState) -> str:
    if settings.llm_reviewer_enabled:
        return "review"
    return "skip"


def skip_review_node(state: VideoState) -> dict:
    return {
        "final_video_path": state.get("video_draft_path"),
        "status": "awaiting_video_review",
    }


def route_after_script_review(state: VideoState) -> str:
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def route_after_plan_review(state: VideoState) -> str:
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def route_after_review(state: VideoState) -> str:
    report = state["review_report"]
    if report.verdict.value == "approved":
        return "approved"
    if state["review_round"] >= report.max_rounds:
        return "max_rounds_reached"
    return "revision_needed"


def route_after_video_review(state: VideoState) -> str:
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def human_script_review_node(state: VideoState) -> dict:
    script = state["script"]
    report = state.get("review_report")

    print("\n" + "=" * 60)
    print("  分镜脚本审核")
    print("=" * 60)
    print(f"标题: {script.title}")
    print(f"风格: {script.style} | 语气: {script.tone}")
    print(f"总时长: {script.total_duration}秒 | 镜头数: {len(script.shots)}")

    if report:
        print(f"自动审核评分: {report.overall_score}/100")

    print("-" * 60)
    for shot in script.shots:
        print(f"\n镜头 {shot.id} [{shot.type.value}] ({shot.duration}秒)")
        print(f"  画面: {shot.image_prompt}")
        print(f"  旁白: {shot.narration}")
        print(f"  字幕: {shot.subtitle}")
    print("\n" + "=" * 60)
    print("操作: [a]确认  [r]修改  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break
        print("无效输入，请重新选择")

    if choice == "a":
        return {"human_action": "approve", "status": "directing", "review_round": 0}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "screenwriting", "review_round": 0}
    else:
        return {"human_action": "cancel", "status": "cancelled"}


def human_plan_review_node(state: VideoState) -> dict:
    script = state["script"]
    plan = state["production_plan"]

    resolution = settings.kling_resolution
    model = settings.kling_model
    duration = settings.kling_duration
    mode = settings.kling_video_mode
    image_model = settings.kling_image_model

    print("\n" + "=" * 60)
    print("  制作方案确认（即将调用可灵生成素材）")
    print("=" * 60)
    print(f"标题: {script.title}")
    print(f"镜头数: {len(script.shots)}")
    print(f"视频模型: {model}")
    print(f"分辨率: {resolution} | 时长: {duration}秒")
    print(f"生成模式: {mode}")
    if mode in ("mixed", "all_image"):
        print(f"图片模型: {image_model}")
    print("-" * 60)

    total_cost = 0.0
    for shot in script.shots:
        source = next((s for s in plan.shot_sources if s.shot_id == shot.id), None)
        prompt = source.generate_prompt if source and source.generate_prompt else shot.image_prompt

        use_video = _should_use_video_for_plan(shot, mode)
        if use_video:
            if resolution == "1080p":
                cost = round(0.49 * 7.2, 2) if duration <= 5 else round(0.98 * 7.2, 2)
            else:
                cost = round(0.245 * 7.2, 2) if duration <= 5 else round(0.49 * 7.2, 2)
            media_type = f"视频 {duration}秒"
        else:
            cost = 0.0
            media_type = "图片"

        total_cost += cost
        print(f"\n镜头 {shot.id} [{shot.type.value}] -> 可灵{media_type} (约{cost} CNY)")
        print(f"  Prompt: {prompt}")

    print("\n" + "-" * 60)
    print(f"预估总成本: 约 {total_cost:.2f} CNY")
    print("=" * 60)
    print("操作: [a]确认生成  [r]返回修改脚本  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break
        print("无效输入，请重新选择")

    if choice == "a":
        return {"human_action": "approve", "status": "editing"}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "screenwriting"}
    else:
        return {"human_action": "cancel", "status": "cancelled"}


def _should_use_video_for_plan(shot, mode: str) -> bool:
    from src.schemas.script import ShotType
    if mode == "all_video":
        return True
    if mode == "all_image":
        return False
    if mode == "mixed":
        return shot.type in (ShotType.OPENING, ShotType.CLOSING) or shot.priority.value == "high"
    return True


def human_video_review_node(state: VideoState) -> dict:
    video_path = state.get("final_video_path") or state.get("video_draft_path")
    report = state.get("review_report")

    print("\n" + "=" * 60)
    print("  成片审核")
    print("=" * 60)
    print(f"视频文件: {video_path}")
    if report:
        print(f"自动审核评分: {report.overall_score}/100")
        print(f"审核结论: {report.verdict.value}")
        if report.revision_instructions:
            print(f"修改建议: {report.revision_instructions}")
    print("=" * 60)
    print("操作: [a]确认  [r]重新剪辑  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break
        print("无效输入，请重新选择")

    if choice == "a":
        return {"human_action": "approve", "status": "completed"}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "editing"}
    else:
        return {"human_action": "cancel", "status": "cancelled"}
