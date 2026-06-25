"""非交互测试脚本 - 自动跳过人工审核"""
import uuid
import logging
from src.graph import build_graph
from src.schemas.cost import CostTracker
from src.services.cost_tracker import CostTrackerService
from src.agents.base import AgentError, BudgetExceededError
import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))

def auto_approve_script(state):
    """自动批准脚本"""
    print("\n[自动审核] 脚本已自动批准")
    return {"human_action": "approve", "status": "directing"}

def auto_approve_plan(state):
    """自动批准制作方案"""
    print("\n[自动审核] 制作方案已自动批准")
    return {"human_action": "approve", "status": "editing"}

def auto_approve_video(state):
    """自动批准成片"""
    print("\n[自动审核] 成片已自动批准")
    return {"human_action": "approve", "status": "completed"}

def main():
    print("=" * 60)
    print("  AI Video Studio - 非交互测试")
    print("=" * 60)

    video_id = str(uuid.uuid4())[:8]
    print(f"视频ID: {video_id}")
    print("主题: 赘婿逆袭")
    print("类型: 故事/爽文")
    print("时长: 10秒")

    initial_state = {
        "video_id": video_id,
        "user_input": "赘婿逆袭：被全家人嘲笑的上门女婿，其实是隐藏的首富之子。当真相揭开的那一刻，所有人都跪了",
        "content_type": "story",
        "tone": "热血爽文",
        "duration": 10,
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

    # 构建图并替换人工审核节点为自动批准
    from langgraph.graph import StateGraph, START, END
    from src.state import VideoState
    from src.agents.screenwriter import ScreenwriterAgent
    from src.agents.director import DirectorAgent
    from src.agents.editor import EditorAgent
    from src.agents.reviewer import ReviewerAgent
    from src.graph import route_after_script_review, route_after_plan_review, route_after_review, route_after_video_review

    graph = StateGraph(VideoState)
    screenwriter = ScreenwriterAgent()
    director = DirectorAgent()
    editor = EditorAgent()
    reviewer = ReviewerAgent()

    graph.add_node("screenwriting", screenwriter.execute)
    graph.add_node("human_script_review", auto_approve_script)
    graph.add_node("directing", director.execute)
    graph.add_node("human_plan_review", auto_approve_plan)
    graph.add_node("editing", editor.execute)
    graph.add_node("reviewing", reviewer.execute)
    graph.add_node("human_video_review", auto_approve_video)

    graph.add_edge(START, "screenwriting")
    graph.add_edge("screenwriting", "human_script_review")
    graph.add_conditional_edges("human_script_review", route_after_script_review,
        {"approved": "directing", "revision": "screenwriting", "cancelled": END})
    graph.add_edge("directing", "human_plan_review")
    graph.add_conditional_edges("human_plan_review", route_after_plan_review,
        {"approved": "editing", "revision": "screenwriting", "cancelled": END})
    graph.add_edge("editing", "reviewing")
    graph.add_conditional_edges("reviewing", route_after_review,
        {"approved": "human_video_review", "revision_needed": "editing", "max_rounds_reached": "human_video_review"})
    graph.add_conditional_edges("human_video_review", route_after_video_review,
        {"approved": END, "revision": "editing", "cancelled": END})

    compiled = graph.compile()

    try:
        result = compiled.invoke(initial_state)
        tracker_service = CostTrackerService(result["cost_tracker"])
        print(tracker_service.print_report())
        if result.get("final_video_path"):
            print(f"\n最终视频: {result['final_video_path']}")
        print("\n测试完成!")
    except BudgetExceededError as e:
        print(f"预算超限: {e}")
    except AgentError as e:
        print(f"Agent错误: {e}")
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
