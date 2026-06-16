from src.services.video_compose import VideoComposeService


class TestVideoCompose:
    def test_format_srt_time(self):
        assert VideoComposeService._format_srt_time(0) == "00:00:00,000"
        assert VideoComposeService._format_srt_time(5.5) == "00:00:05,500"
        assert VideoComposeService._format_srt_time(65.123) == "00:01:05,123"
        assert VideoComposeService._format_srt_time(3661.5) == "01:01:01,500"

    def test_generate_srt(self, tmp_path):
        service = VideoComposeService()
        shots = [
            {"id": 1, "duration": 5.0, "subtitle": "第一行字幕"},
            {"id": 2, "duration": 10.0, "subtitle": "第二行字幕"},
        ]
        output_path = str(tmp_path / "test.srt")
        service._generate_srt(shots, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "第一行字幕" in content
        assert "第二行字幕" in content
        assert "00:00:00,000 --> 00:00:05,000" in content
        assert "00:00:05,000 --> 00:00:15,000" in content
