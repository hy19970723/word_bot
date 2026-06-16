import pytest
from pydantic import ValidationError
from src.schemas.script import (
    Script, Shot, ShotType, ScriptMetadata, GlobalSettings,
)
from src.schemas.plan import ProductionPlan, ShotSourceMapping, ImageSource
from src.schemas.review import ReviewReport, Verdict, DimensionReview
from src.schemas.cost import CostTracker, BudgetStatus


class TestScriptSchema:
    def test_valid_script(self, sample_script):
        assert sample_script.script_id == "test-001"
        assert len(sample_script.shots) == 2
        assert sample_script.total_duration == 30

    def test_script_serialization(self, sample_script):
        json_str = sample_script.model_dump_json()
        restored = Script.model_validate_json(json_str)
        assert restored.title == sample_script.title
        assert len(restored.shots) == len(sample_script.shots)

    def test_shot_duration_min(self):
        with pytest.raises(ValidationError):
            Shot(
                id=1, type=ShotType.OPENING, duration=1.0,
                image_prompt="一个画面描述",
                narration="旁白",
                subtitle="字幕",
            )

    def test_shot_duration_max(self):
        with pytest.raises(ValidationError):
            Shot(
                id=1, type=ShotType.OPENING, duration=31.0,
                image_prompt="一个画面描述",
                narration="旁白",
                subtitle="字幕",
            )

    def test_shot_image_prompt_min_length(self):
        with pytest.raises(ValidationError):
            Shot(
                id=1, type=ShotType.OPENING, duration=5.0,
                image_prompt="短",
                narration="旁白",
                subtitle="字幕",
            )

    def test_script_min_shots(self):
        with pytest.raises(ValidationError):
            Script(
                script_id="test",
                title="test",
                style="science",
                total_duration=30,
                metadata=ScriptMetadata(topic="test"),
                shots=[
                    Shot(
                        id=1, type=ShotType.OPENING, duration=5.0,
                        image_prompt="一个画面描述内容",
                        narration="旁白",
                        subtitle="字幕",
                    )
                ],
            )

    def test_script_title_max_length(self):
        with pytest.raises(ValidationError):
            Script(
                script_id="test",
                title="x" * 51,
                style="science",
                total_duration=30,
                metadata=ScriptMetadata(topic="test"),
                shots=[
                    Shot(
                        id=1, type=ShotType.OPENING, duration=5.0,
                        image_prompt="一个画面描述内容",
                        narration="旁白",
                        subtitle="字幕",
                    ),
                    Shot(
                        id=2, type=ShotType.CONTENT, duration=5.0,
                        image_prompt="另一个画面描述",
                        narration="旁白2",
                        subtitle="字幕2",
                    ),
                ],
            )

    def test_default_global_settings(self):
        gs = GlobalSettings()
        assert gs.voice_id == "zh-CN-YunxiNeural"
        assert gs.voice_speed == 1.0
        assert gs.subtitle_font_size == 42


class TestPlanSchema:
    def test_valid_plan(self, sample_script):
        sources = [
            ShotSourceMapping(shot_id=s.id, source=ImageSource.AI_GENERATE)
            for s in sample_script.shots
        ]
        plan = ProductionPlan(
            plan_id="plan-001",
            script_id=sample_script.script_id,
            shot_sources=sources,
        )
        assert plan.plan_id == "plan-001"
        assert len(plan.shot_sources) == 2

    def test_plan_serialization(self, sample_script):
        sources = [
            ShotSourceMapping(shot_id=s.id, source=ImageSource.AI_GENERATE)
            for s in sample_script.shots
        ]
        plan = ProductionPlan(
            plan_id="plan-001",
            script_id=sample_script.script_id,
            shot_sources=sources,
        )
        json_str = plan.model_dump_json()
        restored = ProductionPlan.model_validate_json(json_str)
        assert restored.plan_id == plan.plan_id


class TestReviewSchema:
    def test_valid_review(self):
        report = ReviewReport(
            review_id="rev-001",
            script_id="script-001",
            round=1,
            verdict=Verdict.APPROVED,
            overall_score=85,
            dimensions={
                "technical_quality": DimensionReview(score=80, passed=True),
                "content_quality": DimensionReview(score=90, passed=True),
                "platform_fit": DimensionReview(score=85, passed=True),
                "compliance": DimensionReview(score=100, passed=True),
            },
        )
        assert report.verdict == Verdict.APPROVED
        assert report.overall_score == 85


class TestCostSchema:
    def test_valid_cost_tracker(self, sample_cost_tracker):
        assert sample_cost_tracker.video_id == "test-001"
        assert sample_cost_tracker.status == BudgetStatus.WITHIN_BUDGET
        assert sample_cost_tracker.budget.cost_limit == 5.0

    def test_cost_tracker_serialization(self, sample_cost_tracker):
        json_str = sample_cost_tracker.model_dump_json()
        restored = CostTracker.model_validate_json(json_str)
        assert restored.video_id == sample_cost_tracker.video_id
