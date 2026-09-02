import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.aggregation.strategies import DedupeMergeAggregator
from core.models import AgentResult, AgentTask
from core.orchestrator import Orchestrator
from pipelines.code_review.pipeline import CodeReviewPipeline
from pipelines.research.pipeline import ResearchPipeline


# -- helpers --

class FakeProvider:
    def __init__(self, name="p1"):
        self.name = name
        self.default_model = f"{name}-model"
        self.rate_limited_until = 0.0

        class FakeKeyPool:
            async def get_key(self):
                return "k"

        class FakeBreaker:
            def allow_request(self):
                return True

            def record_success(self):
                pass

            def record_failure(self):
                pass

        self.key_pool = FakeKeyPool()
        self.breaker = FakeBreaker()

    def mark_rate_limited(self, cooldown_sec=30):
        import time
        self.rate_limited_until = time.time() + cooldown_sec

    async def call(self, model, prompt, api_key, **gen_params):
        from core.providers.base import LLMResponse
        return LLMResponse(text=f"response from {self.name}", raw={}, tokens_used=5)


@pytest.mark.asyncio
async def test_research_pipeline_runs_with_mocked_planner_and_orchestrator():
    providers = {"p1": FakeProvider("p1")}
    mock_executor = AsyncMock()
    mock_router = AsyncMock()
    orch = Orchestrator(mock_executor, mock_router)  # type: ignore[arg-type]

    # Patch planner to avoid real LLM calls
    with patch("pipelines.research.pipeline.ResearchPlanner") as MockPlanner:
        planner_instance = AsyncMock()
        planner_instance.plan = AsyncMock(return_value=[
            AgentTask(id="research-0", prompt="Q1", metadata={"task_type": "research", "complexity_tier": "low"}),
            AgentTask(id="research-1", prompt="Q2", metadata={"task_type": "research", "complexity_tier": "mid"}),
        ])
        MockPlanner.return_value = planner_instance

        # Patch orchestrator run_batch
        with patch.object(Orchestrator, "run_batch", new=AsyncMock(return_value=[
            AgentResult(task_id="research-0", success=True, output="answer 1", provider_used="p1"),
            AgentResult(task_id="research-1", success=True, output="answer 2", provider_used="p1"),
        ])):
            # Need to also patch aggregator to avoid needing real providers
            with patch("pipelines.research.pipeline.build_research_aggregator") as mock_build_agg:
                fake_agg = AsyncMock()
                fake_agg.aggregate = AsyncMock(return_value=AgentResult(task_id="research-main", success=True, output="final"))
                mock_build_agg.return_value = fake_agg

                pipeline = ResearchPipeline(orch, providers)
                result = await pipeline.run("test topic")

                assert result.success is True
                assert result.output == "final"
                planner_instance.plan.assert_called_once_with("test topic")


@pytest.mark.asyncio
async def test_research_pipeline_planner_returns_empty():
    providers = {}
    orch = MagicMock()
    with patch("pipelines.research.pipeline.ResearchPlanner") as MockPlanner:
        planner_instance = AsyncMock()
        planner_instance.plan = AsyncMock(return_value=[])
        MockPlanner.return_value = planner_instance
        with patch("pipelines.research.pipeline.build_research_aggregator") as mock_build_agg:
            mock_build_agg.return_value = MagicMock()
            pipeline = ResearchPipeline(orch, providers)
            result = await pipeline.run("topic")
            assert result.success is False
            assert "no tasks" in result.error.lower()


@pytest.mark.asyncio
async def test_code_review_pipeline_no_files():
    providers = {}
    orch = AsyncMock()
    orch.run_batch = AsyncMock(return_value=[])
    pipeline = CodeReviewPipeline(orch, providers)  # type: ignore[arg-type]
    result = await pipeline.run("/nonexistent/path/xyz_12345")
    assert result.success is False
    assert "No reviewable" in result.error


@pytest.mark.asyncio
async def test_code_review_pipeline_with_temp_file(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("def foo():\n    return 42\n")
    providers = {}

    # Mock orchestrator to return a fake review
    mock_orch = AsyncMock()
    mock_orch.run_batch = AsyncMock(return_value=[
        AgentResult(task_id="review-hello.py", success=True, output="Looks good", provider_used="p1")
    ])

    # Use real aggregator (DedupeMergeAggregator) - it will combine results
    pipeline = CodeReviewPipeline(mock_orch, providers)  # type: ignore[arg-type]
    result = await pipeline.run(str(tmp_path))

    assert result.success is True
    assert "Looks good" in result.output
    mock_orch.run_batch.assert_called_once()
    # Verify tasks passed were for the file
    call_tasks = mock_orch.run_batch.call_args[0][1]
    assert len(call_tasks) == 1
    assert call_tasks[0].metadata["file_path"] is not None


@pytest.mark.asyncio
async def test_code_review_pipeline_aggregates_multiple_files(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.py").write_text("y=2\n")
    mock_orch = AsyncMock()
    mock_orch.run_batch = AsyncMock(return_value=[
        AgentResult(task_id="t1", success=True, output="Review A"),
        AgentResult(task_id="t2", success=True, output="Review B"),
    ])
    pipeline = CodeReviewPipeline(mock_orch, {})  # type: ignore[arg-type]
    result = await pipeline.run(str(tmp_path))
    assert result.success is True
    assert "Review A" in result.output
    assert "Review B" in result.output


@pytest.mark.asyncio
async def test_research_pipeline_calls_aggregator_with_correct_args():
    providers = {"p1": FakeProvider("p1")}
    orch = MagicMock()

    fake_tasks = [AgentTask(id="research-0", prompt="Q1", metadata={"task_type": "research"})]
    fake_results = [AgentResult(task_id="research-0", success=True, output="ans")]

    with patch("pipelines.research.pipeline.ResearchPlanner") as MockPlanner:
        planner_instance = AsyncMock()
        planner_instance.plan = AsyncMock(return_value=fake_tasks)
        MockPlanner.return_value = planner_instance

        with patch.object(Orchestrator, "run_batch", new=AsyncMock(return_value=fake_results)):
            fake_agg = AsyncMock()
            fake_agg.aggregate = AsyncMock(return_value=AgentResult(task_id="research-main", success=True, output="done"))
            with patch("pipelines.research.pipeline.build_research_aggregator", return_value=fake_agg):
                pipeline = ResearchPipeline(Orchestrator(MagicMock(), MagicMock()), providers)
                # override orchestrator's run_batch via instance patch
                pipeline.orchestrator.run_batch = AsyncMock(return_value=fake_results)  # type: ignore[method-assign]
                result = await pipeline.run("topic")

                assert result.success is True
                # Aggregator should be called with main task + results
                agg_call_task = fake_agg.aggregate.call_args[0][0]
                assert agg_call_task.id == "research-main"
                assert agg_call_task.prompt == "topic"
                assert fake_agg.aggregate.call_args[0][1] == fake_results


@pytest.mark.asyncio
async def test_code_review_aggregator_builder():
    from pipelines.code_review.aggregator import build_code_review_aggregator
    agg = build_code_review_aggregator()
    assert isinstance(agg, DedupeMergeAggregator)


@pytest.mark.asyncio
async def test_research_aggregator_builder_prefers_default_provider():
    from pipelines.research.aggregator import build_research_aggregator
    from unittest.mock import patch as mock_patch

    providers = {
        "groq": FakeProvider("groq"),
        "openai": FakeProvider("openai"),
    }
    with mock_patch("pipelines.research.aggregator.settings") as mock_settings:
        mock_settings.default_provider = "groq"
        agg = build_research_aggregator(providers)
        assert agg.default_model == "groq-model"

    with mock_patch("pipelines.research.aggregator.settings") as mock_settings:
        mock_settings.default_provider = "nonexistent"
        agg = build_research_aggregator(providers)
        assert agg.default_model is None
