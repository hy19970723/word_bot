from unittest.mock import patch
from src.agents.screenwriter import ScreenwriterAgent, _calculate_shot_count, _select_tier
from src.schemas.script import Script


class TestShotCountCalculation:
    def test_science_short(self):
        assert 4 <= _calculate_shot_count("science", 30) <= 6

    def test_science_medium(self):
        assert 6 <= _calculate_shot_count("science", 90) <= 10

    def test_science_long(self):
        assert 10 <= _calculate_shot_count("science", 150) <= 12

    def test_story_medium(self):
        assert 6 <= _calculate_shot_count("story", 90) <= 10

    def test_trending_short(self):
        assert 3 <= _calculate_shot_count("trending", 45) <= 5

    def test_product(self):
        assert 4 <= _calculate_shot_count("product", 45) <= 8

    def test_unknown_type_fallback(self):
        result = _calculate_shot_count("unknown", 60)
        assert result >= 4


class TestModelTierSelection:
    def test_science_uses_reasoning(self):
        assert _select_tier("science") == "reasoning"

    def test_story_uses_reasoning(self):
        assert _select_tier("story") == "reasoning"

    def test_trending_uses_creative(self):
        assert _select_tier("trending") == "creative"

    def test_product_uses_creative(self):
        assert _select_tier("product") == "creative"

    def test_unknown_fallback_to_creative(self):
        assert _select_tier("unknown") == "creative"


class TestScreenwriterAgent:
    @patch("src.agents.screenwriter.LLMService")
    def test_execute_success(self, MockLLM, sample_cost_tracker):
        mock_llm_instance = MockLLM.return_value
        mock_script = Script(
            script_id="test-001",
            title="测试视频",
            style="science",
            tone="幽默通俗",
            total_duration=30,
            metadata={"topic": "测试"},
            shots=[
                {
                    "id": 1, "type": "opening", "duration": 5.0,
                    "image_prompt": "一个明亮的实验室里摆满了各种精密的科学仪器",
                    "narration": "你知道吗",
                    "subtitle": "你知道吗",
                },
                {
                    "id": 2, "type": "content", "duration": 10.0,
                    "image_prompt": "浩瀚宇宙中银河系的全景壮观星空图像",
                    "narration": "让我们开始",
                    "subtitle": "让我们开始",
                },
            ],
        )
        mock_usage = {"prompt_tokens": 100, "completion_tokens": 200, "model": "gpt-4o", "cost": 0.1}
        mock_llm_instance.generate_structured.return_value = (mock_script, mock_usage)

        agent = ScreenwriterAgent()
        state = {
            "video_id": "test",
            "user_input": "黑洞是什么",
            "content_type": "science",
            "tone": "幽默通俗",
            "duration": 30,
            "cost_tracker": sample_cost_tracker,
            "human_feedback": None,
        }

        result = agent.execute(state)
        assert "script" in result
        assert result["status"] == "awaiting_script_review"
        mock_llm_instance.generate_structured.assert_called_once()

    @patch("src.agents.screenwriter.LLMService")
    def test_execute_with_feedback(self, MockLLM, sample_cost_tracker):
        mock_llm_instance = MockLLM.return_value
        mock_script = Script(
            script_id="test-001",
            title="测试视频",
            style="science",
            tone="幽默通俗",
            total_duration=30,
            metadata={"topic": "测试"},
            shots=[
                {
                    "id": 1, "type": "opening", "duration": 5.0,
                    "image_prompt": "一个明亮的实验室里摆满了各种精密的科学仪器",
                    "narration": "你知道吗",
                    "subtitle": "你知道吗",
                },
                {
                    "id": 2, "type": "content", "duration": 10.0,
                    "image_prompt": "浩瀚宇宙中银河系的全景壮观星空图像",
                    "narration": "让我们开始",
                    "subtitle": "让我们开始",
                },
            ],
        )
        mock_usage = {"prompt_tokens": 100, "completion_tokens": 200, "model": "gpt-4o", "cost": 0.1}
        mock_llm_instance.generate_structured.return_value = (mock_script, mock_usage)

        agent = ScreenwriterAgent()
        state = {
            "video_id": "test",
            "user_input": "黑洞是什么",
            "content_type": "science",
            "tone": "幽默通俗",
            "duration": 30,
            "cost_tracker": sample_cost_tracker,
            "human_feedback": "请更幽默一些",
        }

        agent.execute(state)
        call_args = mock_llm_instance.generate_structured.call_args
        prompt = call_args[0][0]
        assert "更幽默一些" in prompt
