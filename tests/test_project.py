from src.schemas.project import Project, Character, EpisodeSummary
from src.services.project_manager import ProjectManager


class TestProjectSchema:
    def test_character_creation(self):
        char = Character(name="张伟", description="30岁男性，西装革履", personality="隐忍低调")
        assert char.name == "张伟"
        assert char.description == "30岁男性，西装革履"
        assert char.personality == "隐忍低调"

    def test_character_defaults(self):
        char = Character(name="test", description="desc")
        assert char.reference_image_path is None
        assert char.reference_image_url is None
        assert char.personality == ""

    def test_episode_summary(self):
        ep = EpisodeSummary(
            episode_number=1,
            title="赘婿入门",
            summary="张伟入赘王家，被全家人嘲笑",
        )
        assert ep.episode_number == 1
        assert ep.characters_appeared == []

    def test_project_creation(self):
        project = Project(
            project_id="test_001",
            name="赘婿逆袭",
            genre="story",
            tone="热血爽文",
        )
        assert project.name == "赘婿逆袭"
        assert project.characters == []
        assert project.episodes == []

    def test_project_with_characters(self):
        chars = [
            Character(name="张伟", description="30岁男性"),
            Character(name="王美丽", description="25岁女性"),
        ]
        project = Project(
            project_id="test_002",
            name="赘婿逆袭",
            characters=chars,
        )
        assert len(project.characters) == 2
        assert project.characters[0].name == "张伟"

    def test_project_serialization(self):
        project = Project(
            project_id="test_003",
            name="测试项目",
            characters=[Character(name="主角", description="描述")],
            episodes=[EpisodeSummary(episode_number=1, title="第一集", summary="摘要")],
        )
        json_str = project.model_dump_json()
        restored = Project.model_validate_json(json_str)
        assert restored.name == project.name
        assert len(restored.characters) == 1
        assert len(restored.episodes) == 1


class TestProjectManager:
    def test_create_project(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        project = pm.create_project(
            name="测试项目",
            genre="story",
            tone="热血爽文",
            characters=[Character(name="主角", description="描述")],
        )
        assert project.name == "测试项目"
        assert project.project_id
        assert len(project.characters) == 1

    def test_list_projects(self, tmp_path):
        import time
        pm = ProjectManager(projects_dir=str(tmp_path))
        pm.create_project(name="项目A")
        time.sleep(0.01)
        pm.create_project(name="项目B")
        projects = pm.list_projects()
        assert len(projects) == 2

    def test_get_project(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        created = pm.create_project(name="测试项目")
        loaded = pm.get_project(created.project_id)
        assert loaded is not None
        assert loaded.name == "测试项目"

    def test_get_nonexistent_project(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        assert pm.get_project("nonexistent") is None

    def test_add_episode(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        project = pm.create_project(name="测试项目")
        episode = EpisodeSummary(
            episode_number=1,
            title="第一集",
            summary="剧情摘要",
        )
        pm.add_episode(project, episode)
        loaded = pm.get_project(project.project_id)
        assert len(loaded.episodes) == 1
        assert loaded.episodes[0].title == "第一集"

    def test_get_last_episode(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        project = pm.create_project(name="测试项目")
        assert pm.get_last_episode(project) is None

        pm.add_episode(project, EpisodeSummary(episode_number=1, title="第一集", summary="摘要1"))
        pm.add_episode(project, EpisodeSummary(episode_number=2, title="第二集", summary="摘要2"))
        last = pm.get_last_episode(project)
        assert last.episode_number == 2

    def test_get_previous_episodes_summary(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        project = pm.create_project(name="测试项目")

        summary = pm.get_previous_episodes_summary(project)
        assert "第一集" in summary

        pm.add_episode(project, EpisodeSummary(episode_number=1, title="赘婿入门", summary="张伟入赘王家"))
        pm.add_episode(project, EpisodeSummary(episode_number=2, title="初露锋芒", summary="张伟展示实力"))

        summary = pm.get_previous_episodes_summary(project)
        assert "赘婿入门" in summary
        assert "初露锋芒" in summary

    def test_delete_project(self, tmp_path):
        pm = ProjectManager(projects_dir=str(tmp_path))
        project = pm.create_project(name="测试项目")
        assert pm.delete_project(project.project_id) is True
        assert pm.get_project(project.project_id) is None
        assert pm.delete_project("nonexistent") is False
