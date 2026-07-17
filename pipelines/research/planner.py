from core.models import AgentTask, ComplexityTier
from config.routing_table import DEFAULT_TIER


class ResearchPlanner:
    def __init__(self, planner_provider, planner_model: str = None):
        self.provider = planner_provider
        self.model = planner_model or planner_provider.default_model

    async def plan(self, topic: str) -> list[AgentTask]:
        prompt = (
            f"Decompose the following research topic into 3-5 sub-questions.\n"
            f"For each sub-question, assign a complexity tier from: low, mid, high, xhigh, max.\n"
            f"Format each line as: TIER|sub-question text\n\n"
            f"Topic: {topic}\n\n"
            f"Example:\n"
            f"low|What is the basic definition of X?\n"
            f"high|What are the advanced implications of X?\n"
        )

        api_key = await self.provider.key_pool.get_key()
        response = await self.provider.call(self.model, prompt, api_key)

        tasks = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if "|" not in line:
                continue
            tier_str, question = line.split("|", 1)
            tier_str = tier_str.strip().lower()
            tier: ComplexityTier = tier_str if tier_str in ("low", "mid", "high", "xhigh", "max") else DEFAULT_TIER
            tasks.append(AgentTask(
                id=f"research-{len(tasks)}",
                prompt=question.strip(),
                metadata={"task_type": "research", "complexity_tier": tier},
            ))

        if not tasks:
            tasks.append(AgentTask(
                id="research-0",
                prompt=topic,
                metadata={"task_type": "research", "complexity_tier": DEFAULT_TIER},
            ))

        return tasks
