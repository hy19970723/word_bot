from langgraph.graph import StateGraph, START, END

from src.state import VideoState
from src.agents.screenwriter import ScreenwriterAgent
from src.agents.director import DirectorAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent


def build_graph():
    graph = StateGraph(VideoState)

    screenwriter = ScreenwriterAgent()
    director = DirectorAgent()
    editor = EditorAgent()
    reviewer = ReviewerAgent()

    graph.add_node("screenwriting", screenwriter.execute)
    graph.add_node("human_script_review", human_script_review_node)
    graph.add_node("directing", director.execute)
    graph.add_node("editing", editor.execute)
    graph.add_node("reviewing", reviewer.execute)
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
    graph.add_edge("directing", "editing")
    graph.add_edge("editing", "reviewing")
    graph.add_conditional_edges(
        "reviewing",
        route_after_review,
        {
            "approved": "human_video_review",
            "revision_needed": "editing",
            "max_rounds_reached": "human_video_review",
        }
    )
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


def route_after_script_review(state: VideoState) -> str:
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
