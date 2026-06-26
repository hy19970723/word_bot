import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.schemas.project import Project, Character, EpisodeSummary, PlotThread
from config.settings import settings


class ProjectManager:
    def __init__(self, projects_dir: Optional[str] = None):
        self.projects_dir = Path(projects_dir or settings.projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project: Project) -> Path:
        return self.projects_dir / project.name

    def _project_file(self, project: Project) -> Path:
        return self._project_dir(project) / "project.json"

    def list_projects(self) -> list[Project]:
        projects = []
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            project_file = project_dir / "project.json"
            if not project_file.exists():
                continue
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                projects.append(Project(**data))
            except Exception as e:
                print(f"读取项目失败 {project_file}: {e}")
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def get_project(self, project_id: str) -> Optional[Project]:
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            project_file = project_dir / "project.json"
            if not project_file.exists():
                continue
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                if data.get("project_id") == project_id:
                    return Project(**data)
            except Exception:
                continue
        return None

    def get_project_by_name(self, name: str) -> Optional[Project]:
        project_file = self.projects_dir / name / "project.json"
        if not project_file.exists():
            return None
        data = json.loads(project_file.read_text(encoding="utf-8"))
        return Project(**data)

    def create_project(
        self,
        name: str,
        genre: str = "story",
        overall_story: str = "",
        tone: str = "热血爽文",
        characters: Optional[list[Character]] = None,
        world_setting: str = "",
        planned_episodes: Optional[int] = None,
        story_arcs: Optional[list[dict]] = None,
        visual_style: str = "写实",
        color_tone: str = "",
        bgm_style: str = "",
        target_platform: Optional[list[str]] = None,
        publish_schedule: str = "",
        tags: Optional[list[str]] = None,
        target_audience: str = "",
        notes: Optional[list[str]] = None,
    ) -> Project:
        project_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        now = datetime.now().isoformat()

        project = Project(
            project_id=project_id,
            name=name,
            genre=genre,
            overall_story=overall_story,
            tone=tone,
            world_setting=world_setting,
            planned_episodes=planned_episodes,
            story_arcs=story_arcs or [],
            visual_style=visual_style,
            color_tone=color_tone,
            bgm_style=bgm_style,
            target_platform=target_platform or ["douyin"],
            publish_schedule=publish_schedule,
            tags=tags or [],
            target_audience=target_audience,
            notes=notes or [],
            characters=characters or [],
            episodes=[],
            plot_threads=[],
            created_at=now,
            updated_at=now,
        )

        project_dir = self._project_dir(project)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "characters").mkdir(exist_ok=True)
        (project_dir / "episodes").mkdir(exist_ok=True)

        self.save_project(project)
        return project

    def save_project(self, project: Project):
        project.updated_at = datetime.now().isoformat()
        project_file = self._project_file(project)
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def add_episode(self, project: Project, episode: EpisodeSummary):
        project.episodes.append(episode)
        self.save_project(project)

    def get_episode_dir(self, project: Project, episode_number: int) -> Path:
        ep_dir = self._project_dir(project) / "episodes" / f"ep{episode_number:02d}"
        ep_dir.mkdir(parents=True, exist_ok=True)
        return ep_dir

    def get_last_episode(self, project: Project) -> Optional[EpisodeSummary]:
        if not project.episodes:
            return None
        return max(project.episodes, key=lambda e: e.episode_number)

    def get_previous_episodes_summary(self, project: Project, max_episodes: int = 3) -> str:
        if not project.episodes:
            return "这是第一集，没有前情提要。"

        recent = sorted(project.episodes, key=lambda e: e.episode_number, reverse=True)[:max_episodes]
        recent.reverse()

        summaries = []
        for ep in recent:
            summaries.append(f"第{ep.episode_number}集《{ep.title}》: {ep.summary}")

        return "\n".join(summaries)

    def build_screenwriter_context(self, project: Project) -> str:
        context_parts = []

        # 世界观和视觉风格（始终注入）
        if project.world_setting:
            context_parts.append(f"【世界观】{project.world_setting}")
        if project.visual_style:
            context_parts.append(f"【视觉风格】{project.visual_style}")
        if project.color_tone:
            context_parts.append(f"【色调】{project.color_tone}")
        if context_parts:
            context_parts.append("")

        # 故事规划
        if project.story_arcs:
            context_parts.append("【故事阶段】")
            for arc in project.story_arcs:
                context_parts.append(f"- {arc.get('name', '未命名')}: {arc.get('description', '')}")
            context_parts.append("")

        # 创作备忘
        if project.notes:
            context_parts.append("【创作备忘】")
            for note in project.notes:
                context_parts.append(f"- {note}")
            context_parts.append("")

        if not project.episodes:
            return "\n".join(context_parts)

        if project.characters:
            context_parts.append("【角色当前状态】")
            for char in project.characters:
                state_info = char.current_state if char.current_state else "初始状态"
                appearance_info = char.current_appearance if char.current_appearance else char.description
                context_parts.append(f"- {char.name}:")
                context_parts.append(f"  状态: {state_info}")
                context_parts.append(f"  外貌: {appearance_info}")
                if char.reference_image_path:
                    context_parts.append(f"  参考图: {char.reference_image_path}")
            context_parts.append("")

        unresolved = [t for t in project.plot_threads if not t.resolved]
        if unresolved:
            context_parts.append("【未解决的伏笔/剧情线索】")
            for thread in unresolved:
                importance = "【重要】" if thread.importance in ("high", "critical") else ""
                context_parts.append(
                    f"- {importance}{thread.description} (第{thread.introduced_episode}集引入)"
                )
            context_parts.append("")

        recent = sorted(project.episodes, key=lambda e: e.episode_number, reverse=True)[:3]
        recent.reverse()

        context_parts.append("【最近剧情详细回顾】")
        for ep in recent:
            context_parts.append(f"\n第{ep.episode_number}集《{ep.title}》:")
            context_parts.append(f"摘要: {ep.summary}")

            if ep.key_events:
                context_parts.append("关键事件:")
                for event in ep.key_events:
                    context_parts.append(f"  - {event}")

            if ep.character_states:
                context_parts.append("角色状态变化:")
                for char_name, state in ep.character_states.items():
                    context_parts.append(f"  - {char_name}: {state}")

        return "\n".join(context_parts)

    def update_character_states(self, project: Project, episode: EpisodeSummary):
        for char in project.characters:
            if char.name in episode.character_states:
                char.current_state = episode.character_states[char.name]
        self.save_project(project)

    def update_character_appearance(
        self,
        project: Project,
        character_name: str,
        new_appearance: str,
        episode_number: int,
        reason: str = "",
    ):
        for char in project.characters:
            if char.name == character_name:
                old_appearance = char.current_appearance or char.description
                char.appearance_history.append({
                    "episode": episode_number,
                    "description": old_appearance,
                    "reason": reason or f"第{episode_number}集剧情变化",
                })
                char.current_appearance = new_appearance
                self.save_project(project)
                return True
        return False

    def generate_character_reference_image(
        self,
        project: Project,
        character_name: str,
        kling_service,
    ) -> bool:
        for char in project.characters:
            if char.name == character_name:
                prompt = char.current_appearance or char.description
                output_dir = self._project_dir(project) / "characters"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = str(output_dir / f"{char.name}.png")

                try:
                    result = kling_service.text_to_image(
                        prompt=prompt,
                        output_path=output_path,
                        aspect_ratio="1:1",
                    )
                    char.reference_image_path = result["path"]
                    self.save_project(project)
                    return True
                except Exception as e:
                    print(f"生成角色参考图失败 {char.name}: {e}")
                    return False
        return False

    def add_plot_thread(
        self,
        project: Project,
        description: str,
        episode_number: int,
        importance: str = "normal",
    ) -> PlotThread:
        thread_id = f"thread_{len(project.plot_threads) + 1:03d}"
        thread = PlotThread(
            thread_id=thread_id,
            description=description,
            introduced_episode=episode_number,
            resolved=False,
            importance=importance,
        )
        project.plot_threads.append(thread)
        self.save_project(project)
        return thread

    def resolve_plot_thread(self, project: Project, thread_id: str, episode_number: int) -> bool:
        for thread in project.plot_threads:
            if thread.thread_id == thread_id:
                thread.resolved = True
                thread.resolved_episode = episode_number
                self.save_project(project)
                return True
        return False

    def delete_project(self, project_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        import shutil
        project_dir = self._project_dir(project)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False
