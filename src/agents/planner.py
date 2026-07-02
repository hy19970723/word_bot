"""策划Agent - 从一句话生成完整项目规划"""
from typing import Optional
from pydantic import BaseModel, Field
from src.schemas.project import Project, Character
from src.services.llm import LLMService
from src.services.project_manager import ProjectManager
import structlog

logger = structlog.get_logger()


class StoryArc(BaseModel):
    """故事阶段"""
    name: str = Field(description="阶段名称，如'初入江湖'")
    episodes: str = Field(description="集数范围，如'1-20'")
    description: str = Field(description="阶段描述")


class EpisodeOutline(BaseModel):
    """分集大纲"""
    episode_number: int = Field(description="集数")
    title: str = Field(description="集标题")
    summary: str = Field(description="剧情摘要")
    key_events: list[str] = Field(default_factory=list, description="关键事件")


class ProjectPlan(BaseModel):
    """项目规划"""
    name: str = Field(description="项目名称")
    genre: str = Field(description="内容类型: science/story/trending/product")
    tone: str = Field(description="语气风格")
    overall_story: str = Field(description="整体故事大纲")
    world_setting: str = Field(description="世界观设定")
    visual_style: str = Field(description="视觉风格建议")
    color_tone: str = Field(description="色调建议")
    bgm_style: str = Field(description="BGM风格建议")
    target_audience: str = Field(description="目标受众")
    characters: list[Character] = Field(description="角色列表")
    story_arcs: list[StoryArc] = Field(description="故事阶段划分")
    episode_outlines: list[EpisodeOutline] = Field(description="前5集分集大纲")


PLANNER_PROMPT = """你是一个专业的短视频内容策划专家。请根据用户的简短描述，生成完整的项目规划。

用户输入：{user_input}

请生成以下内容：

1. 项目基本信息
   - 项目名称（简短有力）
   - 内容类型（story/science/trending/product）
   - 语气风格（如"热血爽文"、"幽默轻松"、"悬疑紧张"）

2. 故事大纲
   - 整体故事走向（200字以内）
   - 故事阶段划分（3-5个阶段，每个阶段包含名称、集数范围、描述）

3. 世界观设定
   - 时代背景、地点、规则等（100字以内）

4. 视觉风格
   - 画面风格建议（如"电影感"、"动漫风"、"写实"）
   - 色调建议（如"暗色调"、"暖色调"）

5. 音乐风格
   - BGM风格建议（如"热血激昂"、"温馨治愈"）

6. 目标受众
   - 用户画像（如"18-35岁男性"）

7. 角色设定（3-5个主要角色）
   - 每个角色包含：名称、详细外貌描述（用于AI生图）、性格描述、角色关系

8. 前5集分集大纲
   - 每集包含：集数、标题、剧情摘要、关键事件（2-3个）

要求：
- 角色外貌描述要非常详细具体，包含年龄、性别、发型、服装、体型等
- 故事要有吸引力，节奏紧凑
- 适合短视频平台（抖音/TikTok）

请严格按照以下JSON格式输出：
{json_schema}
"""


class PlannerAgent:
    """策划Agent - 生成项目规划"""

    def __init__(self):
        self.name = "planner"
        self.llm = LLMService(model_tier="reasoning")

    def plan(self, user_input: str) -> Optional[ProjectPlan]:
        """生成项目规划"""
        logger.info("planner_start", user_input=user_input)

        json_schema = ProjectPlan.model_json_schema()

        prompt = PLANNER_PROMPT.format(
            user_input=user_input,
            json_schema=json_schema
        )

        try:
            plan, usage = self.llm.generate_structured(prompt, ProjectPlan)
            logger.info("planner_success", project_name=plan.name, character_count=len(plan.characters), cost=usage.get("cost", 0))
            return plan
        except Exception as e:
            logger.error("planner_failed", error=str(e))
            return None

    def create_project_from_plan(self, plan: ProjectPlan, pm: ProjectManager) -> Project:
        """从规划创建项目"""
        # 转换 story_arcs 为 dict 格式
        story_arcs = [
            {"name": arc.name, "episodes": arc.episodes, "description": arc.description}
            for arc in plan.story_arcs
        ]

        # 创建项目
        project = pm.create_project(
            name=plan.name,
            genre=plan.genre,
            tone=plan.tone,
            overall_story=plan.overall_story,
            world_setting=plan.world_setting,
            visual_style=plan.visual_style,
            color_tone=plan.color_tone,
            bgm_style=plan.bgm_style,
            target_audience=plan.target_audience,
            story_arcs=story_arcs,
            characters=plan.characters,
        )

        logger.info("project_created", project_id=project.project_id, name=project.name)
        return project

    def display_plan(self, plan: ProjectPlan):
        """展示规划给用户"""
        print("\n" + "=" * 60)
        print("项目规划")
        print("=" * 60)

        print(f"\n【基本信息】")
        print(f"  名称: {plan.name}")
        print(f"  类型: {plan.genre}")
        print(f"  风格: {plan.tone}")

        print(f"\n【故事大纲】")
        print(f"  {plan.overall_story}")

        print(f"\n【故事阶段】")
        for arc in plan.story_arcs:
            print(f"  {arc.name} ({arc.episodes}集): {arc.description}")

        print(f"\n【世界观】")
        print(f"  {plan.world_setting}")

        print(f"\n【视觉风格】")
        print(f"  画面: {plan.visual_style}")
        print(f"  色调: {plan.color_tone}")

        print(f"\n【音乐风格】")
        print(f"  {plan.bgm_style}")

        print(f"\n【目标受众】")
        print(f"  {plan.target_audience}")

        print(f"\n【角色设定】")
        for char in plan.characters:
            print(f"\n  {char.name}")
            print(f"    外貌: {char.description}")
            if char.personality:
                print(f"    性格: {char.personality}")

        print(f"\n【前5集大纲】")
        for ep in plan.episode_outlines:
            print(f"\n  第{ep.episode_number}集: {ep.title}")
            print(f"    {ep.summary}")
            if ep.key_events:
                print(f"    关键事件: {', '.join(ep.key_events)}")

        print("\n" + "=" * 60)
