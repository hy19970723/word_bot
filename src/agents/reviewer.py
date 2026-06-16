import json
import uuid
from pathlib import Path

from src.agents.base import BaseAgent
from src.services.llm import LLMService, LLMOutputError
from src.services.cost_tracker import CostTrackerService
from src.schemas.script import Script
from src.schemas.review import (
    ReviewReport, DimensionReview, Verdict,
    ReviewIssue, Severity,
)
from src.state import VideoState
from src.utils.sensitive_words import check_sensitive_words


REVIEWER_TEMPLATE = Path(__file__).parent.parent.parent / "config" / "templates" / "reviewer" / "default.txt"
PASS_SCORE = 60


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__("reviewer")
        self.llm = LLMService(model_tier="efficient")

    def execute(self, state: VideoState) -> dict:
        self.check_budget(state)

        script: Script = state["script"]
        review_round = state.get("review_round", 0) + 1

        compliance_issues = self._check_compliance(script)
        technical_issues = self._check_technical(script)

        template = REVIEWER_TEMPLATE.read_text(encoding="utf-8")
        json_schema = json.dumps(ReviewReport.model_json_schema(), ensure_ascii=False)

        prompt = template.format(
            title=script.title,
            style=script.style,
            total_duration=script.total_duration,
            shot_count=len(script.shots),
            script_json=script.model_dump_json(indent=2),
            json_schema=json_schema,
        )

        try:
            llm_report, usage = self.llm.generate_structured(prompt, ReviewReport)
        except LLMOutputError as e:
            self.logger.warning("llm_review_failed", error=str(e))
            llm_report = None
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "model": "gpt-4o-mini", "cost": 0.0}

        report = self._merge_results(
            script_id=script.script_id,
            review_round=review_round,
            compliance_issues=compliance_issues,
            technical_issues=technical_issues,
            llm_report=llm_report,
        )

        tracker = CostTrackerService(state["cost_tracker"])
        tracker.record_token_usage(self.name, usage)

        result = {
            "review_report": report,
            "review_round": review_round,
            "cost_tracker": tracker.get_tracker(),
        }

        if report.verdict == Verdict.APPROVED:
            result["final_video_path"] = state.get("video_draft_path")
            result["status"] = "awaiting_video_review"
        else:
            result["status"] = "reviewing"

        self.logger.info("review_complete", verdict=report.verdict.value, score=report.overall_score)
        return result

    def _check_compliance(self, script: Script) -> list[ReviewIssue]:
        issues = []
        all_text = " ".join([s.narration + " " + s.subtitle for s in script.shots])
        all_text += " " + script.title
        found_words = check_sensitive_words(all_text)
        for word in found_words:
            issues.append(ReviewIssue(
                severity=Severity.ERROR,
                shot_id=None,
                dimension="compliance",
                description=f"包含敏感词: {word}",
                suggestion=f"请替换或删除包含'{word}'的内容",
            ))
        return issues

    def _check_technical(self, script: Script) -> list[ReviewIssue]:
        issues = []
        for shot in script.shots:
            if shot.duration < 2.0:
                issues.append(ReviewIssue(
                    severity=Severity.ERROR,
                    shot_id=shot.id,
                    dimension="technical_quality",
                    description=f"镜头{shot.id}时长过短: {shot.duration}秒",
                    suggestion="镜头时长应不少于2秒",
                ))
            if shot.duration > 30.0:
                issues.append(ReviewIssue(
                    severity=Severity.WARNING,
                    shot_id=shot.id,
                    dimension="technical_quality",
                    description=f"镜头{shot.id}时长过长: {shot.duration}秒",
                    suggestion="建议镜头时长不超过30秒",
                ))
            for line in shot.subtitle.split("\n"):
                if len(line) > 15:
                    issues.append(ReviewIssue(
                        severity=Severity.WARNING,
                        shot_id=shot.id,
                        dimension="technical_quality",
                        description=f"镜头{shot.id}字幕单行超过15字: '{line}'",
                        suggestion="每行字幕不超过15个字",
                    ))
                    break

        if script.total_duration < 15:
            issues.append(ReviewIssue(
                severity=Severity.ERROR,
                shot_id=None,
                dimension="technical_quality",
                description=f"总时长过短: {script.total_duration}秒",
                suggestion="短视频时长应不少于15秒",
            ))

        return issues

    def _merge_results(
        self,
        script_id: str,
        review_round: int,
        compliance_issues: list[ReviewIssue],
        technical_issues: list[ReviewIssue],
        llm_report: ReviewReport | None,
    ) -> ReviewReport:
        compliance_passed = len([i for i in compliance_issues if i.severity == Severity.ERROR]) == 0
        compliance_score = 100 if compliance_passed else 0

        if llm_report:
            dimensions = llm_report.dimensions
            dimensions["compliance"] = DimensionReview(
                score=compliance_score,
                passed=compliance_passed,
                issues=compliance_issues,
            )

            tech_dim = dimensions.get("technical_quality")
            if tech_dim:
                merged_issues = technical_issues + tech_dim.issues
                tech_score = max(0, tech_dim.score - len(technical_issues) * 5)
                dimensions["technical_quality"] = DimensionReview(
                    score=tech_score,
                    passed=tech_score >= 50,
                    issues=merged_issues,
                )

            tech_score = dimensions.get("technical_quality", DimensionReview(score=70, passed=True)).score
            content_score = dimensions.get("content_quality", DimensionReview(score=70, passed=True)).score
            platform_score = dimensions.get("platform_fit", DimensionReview(score=70, passed=True)).score
            overall_score = int(tech_score * 0.3 + content_score * 0.4 + platform_score * 0.3)

            if not compliance_passed:
                verdict = Verdict.REVISION_NEEDED
            elif overall_score >= PASS_SCORE:
                verdict = Verdict.APPROVED
            else:
                verdict = Verdict.REVISION_NEEDED

            revision_instructions = llm_report.revision_instructions if verdict == Verdict.REVISION_NEEDED else ""

            return ReviewReport(
                review_id=str(uuid.uuid4())[:8],
                script_id=script_id,
                round=review_round,
                verdict=verdict,
                overall_score=overall_score,
                dimensions=dimensions,
                revision_instructions=revision_instructions,
            )
        else:
            tech_score = max(0, 70 - len(technical_issues) * 5)
            dimensions = {
                "compliance": DimensionReview(score=compliance_score, passed=compliance_passed, issues=compliance_issues),
                "technical_quality": DimensionReview(score=tech_score, passed=tech_score >= 50, issues=technical_issues),
                "content_quality": DimensionReview(score=70, passed=True),
                "platform_fit": DimensionReview(score=70, passed=True),
            }
            overall_score = int(tech_score * 0.3 + 70 * 0.4 + 70 * 0.3)

            if not compliance_passed:
                verdict = Verdict.REVISION_NEEDED
            elif overall_score >= PASS_SCORE:
                verdict = Verdict.APPROVED
            else:
                verdict = Verdict.REVISION_NEEDED

            return ReviewReport(
                review_id=str(uuid.uuid4())[:8],
                script_id=script_id,
                round=review_round,
                verdict=verdict,
                overall_score=overall_score,
                dimensions=dimensions,
                revision_instructions="LLM审核不可用，请根据技术问题列表手动修改" if verdict == Verdict.REVISION_NEEDED else "",
            )
