import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.schemas.project import Project, Character, EpisodeSummary
from config.settings import settings


class ProjectManager:
    def __init__(self, projects_dir: Optional[str] = None):
        self.projects_dir = Path(projects_dir or settings.projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[Project]:
        projects = []
        for project_file in self.projects_dir.glob("*.json"):
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                projects.append(Project(**data))
            except Exception as e:
                print(f"读取项目失败 {project_file}: {e}")
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def get_project(self, project_id: str) -> Optional[Project]:
        project_file = self.projects_dir / f"{project_id}.json"
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
    ) -> Project:
        project_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        now = datetime.now().isoformat()

        project = Project(
            project_id=project_id,
            name=name,
            genre=genre,
            overall_story=overall_story,
            tone=tone,
            characters=characters or [],
            episodes=[],
            created_at=now,
            updated_at=now,
        )

        self.save_project(project)
        return project

    def save_project(self, project: Project):
        project.updated_at = datetime.now().isoformat()
        project_file = self.projects_dir / f"{project.project_id}.json"
        project_file.write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def add_episode(self, project: Project, episode: EpisodeSummary):
        project.episodes.append(episode)
        self.save_project(project)

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

    def delete_project(self, project_id: str) -> bool:
        project_file = self.projects_dir / f"{project_id}.json"
        if project_file.exists():
            project_file.unlink()
            return True
        return False
