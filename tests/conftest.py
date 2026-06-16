import pytest
from unittest.mock import MagicMock
from src.schemas.script import (
    Script, Shot, ShotType, TransitionType,
    CameraEffect, BGMMood, ShotPriority, ScriptMetadata,
)
from src.schemas.cost import CostTracker, Budget


@pytest.fixture
def sample_shot() -> Shot:
    return Shot(
        id=1, type=ShotType.OPENING, duration=5.0,
        image_prompt="一个明亮的实验室，桌上放着各种科学仪器",
        narration="你知道吗？今天我们来聊一个有趣的话题",
        subtitle="你知道吗？\n今天我们来聊\n一个有趣的话题",
        transition_in=TransitionType.FADE_IN,
        transition_out=TransitionType.CUT,
        camera_effect=CameraEffect.KEN_BURNS,
        bgm_mood=BGMMood.UPBEAT,
        priority=ShotPriority.HIGH,
    )


@pytest.fixture
def sample_script(sample_shot) -> Script:
    shot2 = Shot(
        id=2, type=ShotType.CONTENT, duration=10.0,
        image_prompt="宇宙星空，银河系的全景图，壮观的场景",
        narration="让我们从宇宙的尺度开始说起",
        subtitle="让我们从\n宇宙的尺度\n开始说起",
        transition_in=TransitionType.CUT,
        transition_out=TransitionType.FADE_OUT,
        camera_effect=CameraEffect.ZOOM_IN_SLOW,
        bgm_mood=BGMMood.MYSTERIOUS,
        priority=ShotPriority.NORMAL,
    )
    return Script(
        script_id="test-001",
        title="测试视频",
        style="science",
        tone="幽默通俗",
        total_duration=30,
        metadata=ScriptMetadata(topic="测试主题"),
        shots=[sample_shot, shot2],
    )


@pytest.fixture
def sample_cost_tracker() -> CostTracker:
    return CostTracker(
        video_id="test-001",
        budget=Budget(
            max_tokens=8000,
            max_images=8,
            max_retry_rounds=2,
            cost_limit=5.0,
        ),
    )


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_image_gen():
    return MagicMock()
