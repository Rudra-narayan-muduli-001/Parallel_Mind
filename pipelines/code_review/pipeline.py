from core.models import AgentTask, AgentResult
from core.orchestrator import Orchestrator
from pipelines.code_review.splitter import CodeReviewSplitter
from pipelines.code_review.reviewer_agent import CodeReviewerAgent
from pipelines.code_review.aggregator import build_code_review_aggregator


class CodeReviewPipeline:
    def __init__(self, orchestrator: Orchestrator, providers: dict, gen_params: dict = None):
        self.orchestrator = orchestrator
        self.providers = providers
        self.gen_params = gen_params or {}
        self.reviewer = CodeReviewerAgent()
        self.aggregator = build_code_review_aggregator()

    async def run(self, path: str) -> AgentResult:
        splitter = CodeReviewSplitter(path)
        tasks = splitter.split()

        if not tasks:
            return AgentResult(task_id="review", success=False, error="No reviewable files found")

        results = await self.orchestrator.run_batch(self.reviewer, tasks, self.gen_params)
        main_task = AgentTask(id="review-main", prompt=f"Code review of {path}", metadata={"task_type": "code_review"})
        return await self.aggregator.aggregate(main_task, results)
