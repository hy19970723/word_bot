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
    graph.add_node("human_script_review", human_script_review_node)
    graph.add_node("directing", director.execute)
    graph.add_node("human_plan_review", human_plan_review_node)
    graph.add_node("editing", editor.execute)
    graph.add_node("reviewing", reviewer.execute)
    graph.add_node("skip_review", skip_review_node)
    graph.add_node("human_video_review", human_video_review_node)

    graph.add_edge(START, "screenwriting")
    graph.add_edge("screenwriting", "human_script_review")
    graph.add_conditional_edges(
        "human_script_review",
        route_after_script_review,
        {
            "approved": "directing",
            "revision": "screenwriting",
            "cancelled": END,
        }
    )
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
    print("\n" + "=" * 60)
    print("  分镜脚本审核")
    print("=" * 60)
    print(f"标题: {script.title}")
    print(f"风格: {script.style} | 语气: {script.tone}")
    print(f"总时长: {script.total_duration}秒 | 镜头数: {len(script.shots)}")
    print("-" * 60)
    for shot in script.shots:
        print(f"\n镜头 {shot.id} [{shot.type.value}] ({shot.duration}秒)")
        print(f"  画面: {shot.image_prompt[:80]}...")
        print(f"  旁白: {shot.narration}")
        print(f"  字幕: {shot.subtitle}")
    print("\n" + "=" * 60)
    print("操作: [a]确认  [r]修改后重新生成  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break
        print("无效输入，请重新选择")

    if choice == "a":
        return {"human_action": "approve", "status": "directing"}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "screenwriting"}
    else:
        return {"human_action": "cancel", "status": "cancelled"}


def human_plan_review_node(state: VideoState) -> dict:
    script = state["script"]
    plan = state["production_plan"]

    from config.settings import settings
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
        print(f"  Prompt: {prompt[:100]}...")

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
