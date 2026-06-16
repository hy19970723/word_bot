from src.graph import (
    route_after_script_review,
    route_after_review,
    route_after_video_review,
)
from src.schemas.review import ReviewReport, Verdict


class TestRouting:
    def test_script_review_approved(self):
        state = {"human_action": "approve"}
        assert route_after_script_review(state) == "approved"

    def test_script_review_revision(self):
        state = {"human_action": "revise"}
        assert route_after_script_review(state) == "revision"

    def test_script_review_cancelled(self):
        state = {"human_action": "cancel"}
        assert route_after_script_review(state) == "cancelled"

    def test_review_approved(self):
        report = ReviewReport(
            review_id="r1", script_id="s1", round=1,
            verdict=Verdict.APPROVED, overall_score=85,
            dimensions={},
        )
        state = {"review_report": report, "review_round": 1}
        assert route_after_review(state) == "approved"

    def test_review_revision_needed(self):
        report = ReviewReport(
            review_id="r1", script_id="s1", round=1,
            verdict=Verdict.REVISION_NEEDED, overall_score=40,
            max_rounds=2,
            dimensions={},
        )
        state = {"review_report": report, "review_round": 1}
        assert route_after_review(state) == "revision_needed"

    def test_review_max_rounds_reached(self):
        report = ReviewReport(
            review_id="r1", script_id="s1", round=2,
            verdict=Verdict.REVISION_NEEDED, overall_score=40,
            max_rounds=2,
            dimensions={},
        )
        state = {"review_report": report, "review_round": 2}
        assert route_after_review(state) == "max_rounds_reached"

    def test_video_review_approved(self):
        state = {"human_action": "approve"}
        assert route_after_video_review(state) == "approved"

    def test_video_review_revision(self):
        state = {"human_action": "revise"}
        assert route_after_video_review(state) == "revision"

    def test_video_review_cancelled(self):
        state = {"human_action": "cancel"}
        assert route_after_video_review(state) == "cancelled"
