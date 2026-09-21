from config.settings import settings
from core.models import AgentResult, AgentTask
from core.pipeline import build_orchestrator
from core.aggregation.strategies import LLMSynthesisAggregator
from pipelines.research.planner import ResearchPlanner
from pipelines.research.researcher_agent import ResearcherAgent


class ResearchPipeline:
    def __init__(self, executor, policy, providers: dict, gen_params: dict | None = None, max_concurrency: int = 5):
        self.orchestrator = build_orchestrator(executor, policy, max_concurrency)
        self.providers = providers
        self.gen_params = gen_params or {}
        self.planner = ResearchPlanner(providers)
        self.researcher = ResearcherAgent()
        default_model = providers[settings.default_provider].default_model if settings.default_provider in providers else None
        self.aggregator = LLMSynthesisAggregator(providers, default_model=default_model)

    async def run(self, topic: str) -> AgentResult:
        try:
            tasks = await self.planner.plan(topic)
        except Exception as e:
            return AgentResult(task_id="research", success=False, error=f"Planner failed: {e}")

        if not tasks:
            return AgentResult(task_id="research", success=False, error="Planner returned no tasks")

        results = await self.orchestrator.run_batch(self.researcher, tasks, self.gen_params)
        main_task = AgentTask(id="research-main", prompt=topic, metadata={"task_type": "research"})
        return await self.aggregator.aggregate(main_task, results)