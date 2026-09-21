from core.models import AgentResult, AgentTask
from core.pipeline import build_orchestrator
from core.aggregation.strategies import DedupeMergeAggregator
from pipelines.code_review.reviewer_agent import CodeReviewerAgent
from pipelines.code_review.splitter import CodeReviewSplitter


class CodeReviewPipeline:
    def __init__(self, executor, policy, providers: dict, gen_params: dict | None = None, max_concurrency: int = 5):
        self.orchestrator = build_orchestrator(executor, policy, max_concurrency)
        self.providers = providers
        self.gen_params = gen_params or {}
        self.reviewer = CodeReviewerAgent()
        self.aggregator = DedupeMergeAggregator()

    async def run(self, path: str) -> AgentResult:
        splitter = CodeReviewSplitter(path)
        tasks = splitter.split()

        if not tasks:
            return AgentResult(task_id="review", success=False, error="No reviewable files found")

        results = await self.orchestrator.run_batch(self.reviewer, tasks, self.gen_params)
        main_task = AgentTask(id="review-main", prompt=f"Code review of {path}", metadata={"task_type": "code_review"})
        return await self.aggregator.aggregate(main_task, results)