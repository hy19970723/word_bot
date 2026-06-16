from src.agents.director import (
    _decide_quality_for_shot, _decide_bgm_style,
    _decide_subtitle_animation, _decide_transition,
)
from src.schemas.script import Shot, ShotType, ShotPriority
from src.schemas.plan import SubtitleAnimation


class TestDirectorDecisions:
    def test_high_priority_quality(self):
        shot = Shot(
            id=1, type=ShotType.OPENING, duration=5.0,
            image_prompt="一个明亮的实验室里摆满了各种精密的科学仪器",
            narration="旁白", subtitle="字幕",
            priority=ShotPriority.HIGH,
        )
        model, quality = _decide_quality_for_shot(shot)
        assert model == "dall-e-3"
        assert quality == "hd"

    def test_normal_priority_quality(self):
        shot = Shot(
            id=1, type=ShotType.CONTENT, duration=5.0,
            image_prompt="一个明亮的实验室里摆满了各种精密的科学仪器",
            narration="旁白", subtitle="字幕",
            priority=ShotPriority.NORMAL,
        )
        model, quality = _decide_quality_for_shot(shot)
        assert model == "dall-e-3"
        assert quality == "standard"

    def test_low_priority_quality(self):
        shot = Shot(
            id=1, type=ShotType.TRANSITION, duration=5.0,
            image_prompt="一个明亮的实验室里摆满了各种精密的科学仪器",
            narration="旁白", subtitle="字幕",
            priority=ShotPriority.LOW,
        )
        model, quality = _decide_quality_for_shot(shot)
        assert quality == "standard"


class TestBGMStyle:
    def test_humorous_tone(self):
        assert _decide_bgm_style("幽默通俗") == "轻快电子"

    def test_serious_tone(self):
        assert _decide_bgm_style("严肃专业") == "简约钢琴"

    def test_tense_tone(self):
        assert _decide_bgm_style("悬疑紧张") == "暗黑氛围"

    def test_default_tone(self):
        assert _decide_bgm_style("普通") == "轻快电子"


class TestSubtitleAnimation:
    def test_science(self):
        assert _decide_subtitle_animation("science") == SubtitleAnimation.TYPEWRITER

    def test_story(self):
        assert _decide_subtitle_animation("story") == SubtitleAnimation.FADE

    def test_product(self):
        assert _decide_subtitle_animation("product") == SubtitleAnimation.SLIDE_UP


class TestTransition:
    def test_trending(self):
        assert _decide_transition("trending") == "cut"

    def test_science(self):
        assert _decide_transition("science") == "crossfade"
