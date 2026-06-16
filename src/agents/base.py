from abc import ABC, abstractmethod
from src.state import VideoState
from src.services.cost_tracker import CostTrackerService
import structlog

logger = structlog.get_logger()


class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logger.bind(agent=name)

    @abstractmethod
    def execute(self, state: VideoState) -> dict:
        pass

    def check_budget(self, state: VideoState) -> None:
        tracker = CostTrackerService(state["cost_tracker"])
        if tracker.is_exceeded():
            raise BudgetExceededError(
                f"Agent {self.name}: 预算超限，当前花费 {tracker.tracker.usage.total_cost}"
            )

    def update_cost(self, state: VideoState, **kwargs) -> CostTrackerService:
        tracker = CostTrackerService(state["cost_tracker"])
        tracker.record(self.name, **kwargs)
        return tracker.get_tracker()


class AgentError(Exception):
    def __init__(self, agent_name: str, message: str, recoverable: bool = True):
        self.agent_name = agent_name
        self.recoverable = recoverable
        super().__init__(f"[{agent_name}] {message}")


class BudgetExceededError(AgentError):
    def __init__(self, message: str):
        super().__init__("budget", message, recoverable=False)
