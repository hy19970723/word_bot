from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str = Field(description="角色名称")
    description: str = Field(description="角色外貌描述，用于AI生成")
    reference_image_path: Optional[str] = Field(default=None, description="角色参考图路径")
    reference_image_url: Optional[str] = Field(default=None, description="角色参考图URL（可灵返回的）")
    personality: str = Field(default="", description="角色性格描述")
    current_state: str = Field(default="", description="当前状态（随剧情更新）")
    current_appearance: str = Field(default="", description="当前外貌描述（可随剧情变化）")
    appearance_history: list[dict] = Field(default_factory=list, description="外貌变化历史 [{episode, description, reason}]")


class PlotThread(BaseModel):
    thread_id: str = Field(description="伏笔ID")
    description: str = Field(description="伏笔描述")
    introduced_episode: int = Field(description="引入集数")
    resolved: bool = Field(default=False, description="是否已解决")
    resolved_episode: Optional[int] = Field(default=None, description="解决集数")
    importance: str = Field(default="normal", description="重要性: low/normal/high/critical")


class EpisodeSummary(BaseModel):
    episode_number: int = Field(description="集数")
    title: str = Field(description="本集标题")
    summary: str = Field(description="剧情摘要")
    script_path: str = Field(default="", description="脚本JSON路径")
    video_path: str = Field(default="", description="视频路径")
    characters_appeared: list[str] = Field(default_factory=list, description="出场角色名列表")
    character_states: dict[str, str] = Field(default_factory=dict, description="角色状态变化 {角色名: 状态}")
    plot_threads: list[str] = Field(default_factory=list, description="本集涉及的伏笔ID")
    key_events: list[str] = Field(default_factory=list, description="关键事件列表")


class Project(BaseModel):
    project_id: str = Field(description="项目ID")
    name: str = Field(description="项目名称，如'赘婿逆袭'")
    genre: str = Field(default="story", description="类型: science/story/trending/product")
    overall_story: str = Field(default="", description="整体故事大纲")
    tone: str = Field(default="热血爽文", description="语气风格")

    # 世界观
    world_setting: str = Field(default="", description="世界观设定，如'现代都市，2025年'")

    # 故事规划
    planned_episodes: Optional[int] = Field(default=None, description="预计总集数")
    story_arcs: list[dict] = Field(default_factory=list, description="故事阶段划分 [{name, episodes, description}]")

    # 视觉风格
    visual_style: str = Field(default="写实", description="画面风格: 电影感/动漫风/写实/赛博朋克等")
    color_tone: str = Field(default="", description="色调偏好: 暗色调/暖色调/冷色调等")

    # 音乐
    bgm_style: str = Field(default="", description="BGM风格偏好: 紧张悬疑/热血激昂/温馨治愈等")
    bgm_tracks: list[str] = Field(default_factory=list, description="已用过的BGM列表")

    # 发布
    target_platform: list[str] = Field(default_factory=lambda: ["douyin"], description="目标平台: douyin/tiktok/bilibili等")
    publish_schedule: str = Field(default="", description="发布频率: 每天一集/每周一集等")
    tags: list[str] = Field(default_factory=list, description="标签/关键词，用于SEO")

    # 受众
    target_audience: str = Field(default="", description="目标用户画像: 18-35岁男性等")

    # 统计
    total_cost: float = Field(default=0.0, description="累计花费(CNY)")
    episode_costs: dict[str, float] = Field(default_factory=dict, description="每集花费记录 {集数: 花费}")

    # 素材库
    reusable_assets: list[dict] = Field(default_factory=list, description="可复用素材 [{name, type, path, description}]")

    # 备注
    notes: list[str] = Field(default_factory=list, description="创作备忘")

    characters: list[Character] = Field(default_factory=list, description="角色列表")
    episodes: list[EpisodeSummary] = Field(default_factory=list, description="已完成集数")
    plot_threads: list[PlotThread] = Field(default_factory=list, description="伏笔/剧情线索")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")
