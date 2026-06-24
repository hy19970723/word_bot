from src.schemas.cost import CostTracker, BudgetStatus, TokenUsage


class CostTrackerService:
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def record_token_usage(self, agent_name: str, usage: dict) -> None:
        token_usage = TokenUsage(**usage)
        self.tracker.usage.tokens[agent_name] = token_usage
        self.tracker.usage.total_cost += token_usage.cost
        self._update_status()

    def record_image_generation(self, count: int = 1, cost: float = 0.0) -> None:
        self.tracker.usage.images.ai_generated += count
        self.tracker.usage.images.cost += cost
        self.tracker.usage.total_cost += cost
        self._update_status()

    def record_tts_cost(self, cost: float) -> None:
        self.tracker.usage.tts_cost += cost
        self.tracker.usage.total_cost += cost
        self._update_status()

    def is_exceeded(self) -> bool:
        u = self.tracker.usage
        b = self.tracker.budget
        total_tokens = sum(t.prompt_tokens + t.completion_tokens for t in u.tokens.values())
        return (
            total_tokens > b.max_tokens
            or u.images.ai_generated > b.max_images
            or u.total_cost > b.cost_limit
        )

    def _update_status(self) -> None:
        if self.is_exceeded():
            self.tracker.status = BudgetStatus.EXCEEDED
        elif self.tracker.usage.total_cost > self.tracker.budget.cost_limit * 0.8:
            self.tracker.status = BudgetStatus.WARNING

    def get_tracker(self) -> CostTracker:
        return self.tracker

    def print_report(self) -> str:
        u = self.tracker.usage
        lines = [
            "=" * 40,
            "Cost Report",
            "=" * 40,
            "Token:",
        ]
        for agent, t in u.tokens.items():
            lines.append(f"  {agent}: {t.prompt_tokens}+{t.completion_tokens} tokens ({t.model}) = {t.cost:.4f} CNY")
        lines.extend([
            f"Images: {u.images.ai_generated} = {u.images.cost:.4f} CNY",
            f"TTS: {u.tts_cost:.4f} CNY",
            f"{'-' * 40}",
            f"Total: {u.total_cost:.4f} / Budget {self.tracker.budget.cost_limit:.2f} CNY",
            f"Status: {self.tracker.status.value}",
            "=" * 40,
        ])
        return "\n".join(lines)
