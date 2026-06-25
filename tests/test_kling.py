from unittest.mock import patch, MagicMock
from src.services.kling import KlingService, KlingError


class TestKlingService:
    def test_init_default(self):
        service = KlingService()
        assert service.cli == "kling"

    def test_init_custom_command(self):
        service = KlingService(cli_command="/usr/local/bin/kling")
        assert service.cli == "/usr/local/bin/kling"

    @patch("src.services.kling.subprocess.run")
    def test_check_login_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"user": "test"}',
            stderr="",
        )
        service = KlingService()
        assert service.check_login() is True

    @patch("src.services.kling.subprocess.run")
    def test_check_login_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="not logged in",
        )
        service = KlingService()
        assert service.check_login() is False

    @patch("src.services.kling.subprocess.run")
    def test_text_to_video_cli_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error: not logged in",
        )
        service = KlingService()
        try:
            service.text_to_video("test prompt", "/tmp/out.mp4")
            assert False, "should have raised"
        except KlingError as e:
            assert "CLI错误" in str(e)

    @patch("src.services.kling.subprocess.run")
    def test_text_to_video_cli_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        service = KlingService()
        try:
            service.text_to_video("test prompt", "/tmp/out.mp4")
            assert False, "should have raised"
        except KlingError as e:
            assert "未安装" in str(e)


class TestKlingUrlExtraction:
    def test_extract_url_direct(self):
        data = {"url": "https://example.com/video.mp4"}
        assert KlingService._extract_url(data, "video") == "https://example.com/video.mp4"

    def test_extract_url_nested_videos(self):
        data = {"task_result": {"videos": [{"url": "https://example.com/v.mp4"}]}}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_nested_images(self):
        data = {"task_result": {"images": [{"url": "https://example.com/i.png"}]}}
        assert KlingService._extract_url(data, "image") == "https://example.com/i.png"

    def test_extract_url_data_key(self):
        data = {"data": {"url": "https://example.com/v.mp4"}}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_video_url_key(self):
        data = {"video_url": "https://example.com/v.mp4"}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_none(self):
        assert KlingService._extract_url({}, "video") is None

    def test_extract_url_list(self):
        data = [{"url": "https://example.com/v.mp4"}]
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_generations(self):
        data = {"generations": [{"url": "https://example.com/v.mp4", "status": "COMPLETE"}]}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_body_generations(self):
        data = {"body": {"generations": [{"url": "https://example.com/v.mp4"}]}}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"

    def test_extract_url_generations_video_url(self):
        data = {"generations": [{"video_url": "https://example.com/v.mp4"}]}
        assert KlingService._extract_url(data, "video") == "https://example.com/v.mp4"


class TestKlingCostEstimate:
    def test_5s_cost(self):
        cost = KlingService._estimate_video_cost(5)
        assert cost == round(0.35 * 7.2, 4)

    def test_10s_cost(self):
        cost = KlingService._estimate_video_cost(10)
        assert cost == round(0.49 * 7.2, 4)
