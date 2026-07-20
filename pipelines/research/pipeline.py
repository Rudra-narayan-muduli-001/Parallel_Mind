from core.models import AgentResult, AgentTask
from core.orchestrator import Orchestrator
from pipelines.research.aggregator import build_research_aggregator
from pipelines.research.planner import ResearchPlanner
from pipelines.research.researcher_agent import ResearcherAgent


class ResearchPipeline:
    def __init__(self, orchestrator: Orchestrator, providers: dict, gen_params: dict | None = None):
        self.orchestrator = orchestrator
        self.providers = providers
        self.gen_params = gen_params or {}
        planner_provider = list(providers.values())[0]
        self.planner = ResearchPlanner(planner_provider)
        self.researcher = ResearcherAgent()
        self.aggregator = build_research_aggregator(providers)

    async def run(self, topic: str) -> AgentResult:
        tasks = await self.planner.plan(topic)
        if not tasks:
            return AgentResult(task_id="research", success=False, error="Planner returned no tasks")

        results = await self.orchestrator.run_batch(self.researcher, tasks, self.gen_params)
        main_task = AgentTask(id="research-main", prompt=topic, metadata={"task_type": "research"})
        return await self.aggregator.aggregate(main_task, results)
