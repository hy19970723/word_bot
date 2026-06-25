from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str = Field(description="角色名称")
    description: str = Field(description="角色外貌描述，用于AI生成")
    reference_image_path: Optional[str] = Field(default=None, description="角色参考图路径")
    reference_image_url: Optional[str] = Field(default=None, description="角色参考图URL（可灵返回的）")
    personality: str = Field(default="", description="角色性格描述")


class EpisodeSummary(BaseModel):
    episode_number: int = Field(description="集数")
    title: str = Field(description="本集标题")
    summary: str = Field(description="剧情摘要")
    script_path: str = Field(default="", description="脚本JSON路径")
    video_path: str = Field(default="", description="视频路径")
    characters_appeared: list[str] = Field(default_factory=list, description="出场角色名列表")


class Project(BaseModel):
    project_id: str = Field(description="项目ID")
    name: str = Field(description="项目名称，如'赘婿逆袭'")
    genre: str = Field(default="story", description="类型: science/story/trending/product")
    overall_story: str = Field(default="", description="整体故事大纲")
    tone: str = Field(default="热血爽文", description="语气风格")
    characters: list[Character] = Field(default_factory=list, description="角色列表")
    episodes: list[EpisodeSummary] = Field(default_factory=list, description="已完成集数")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")
