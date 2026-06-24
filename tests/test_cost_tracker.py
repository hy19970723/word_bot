from src.services.cost_tracker import CostTrackerService
from src.schemas.cost import BudgetStatus


class TestCostTracker:
    def test_initial_state(self, sample_cost_tracker):
        service = CostTrackerService(sample_cost_tracker)
        assert not service.is_exceeded()
        assert sample_cost_tracker.status == BudgetStatus.WITHIN_BUDGET

    def test_record_token_usage(self, sample_cost_tracker):
        service = CostTrackerService(sample_cost_tracker)
        service.record_token_usage("screenwriter", {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "model": "gpt-4o",
            "cost": 0.5,
        })
        assert sample_cost_tracker.usage.total_cost == 0.5
        assert "screenwriter" in sample_cost_tracker.usage.tokens

    def test_record_image_generation(self, sample_cost_tracker):
        service = CostTrackerService(sample_cost_tracker)
        service.record_image_generation(count=3, cost=1.5)
        assert sample_cost_tracker.usage.images.ai_generated == 3
        assert sample_cost_tracker.usage.images.cost == 1.5
        assert sample_cost_tracker.usage.total_cost == 1.5

    def test_budget_exceeded_by_tokens(self, sample_cost_tracker):
        sample_cost_tracker.budget.max_tokens = 100
        service = CostTrackerService(sample_cost_tracker)
        service.record_token_usage("screenwriter", {
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "model": "gpt-4o",
            "cost": 0.5,
        })
        assert service.is_exceeded()
        assert sample_cost_tracker.status == BudgetStatus.EXCEEDED

    def test_budget_exceeded_by_images(self, sample_cost_tracker):
        sample_cost_tracker.budget.max_images = 2
        service = CostTrackerService(sample_cost_tracker)
        service.record_image_generation(count=5, cost=1.0)
        assert service.is_exceeded()

    def test_budget_exceeded_by_cost(self, sample_cost_tracker):
        sample_cost_tracker.budget.cost_limit = 1.0
        service = CostTrackerService(sample_cost_tracker)
        service.record_image_generation(count=1, cost=2.0)
        assert service.is_exceeded()

    def test_warning_status(self, sample_cost_tracker):
        sample_cost_tracker.budget.cost_limit = 5.0
        service = CostTrackerService(sample_cost_tracker)
        service.record_image_generation(count=1, cost=4.5)
        assert sample_cost_tracker.status == BudgetStatus.WARNING

    def test_print_report(self, sample_cost_tracker):
        service = CostTrackerService(sample_cost_tracker)
        service.record_token_usage("screenwriter", {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "model": "gpt-4o",
            "cost": 0.5,
        })
        report = service.print_report()
        assert "screenwriter" in report
        assert "0.5000 CNY" in report
