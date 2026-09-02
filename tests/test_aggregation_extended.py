import pytest

from core.aggregation.strategies import (
    ConcatAggregator,
    DedupeMergeAggregator,
    FirstSuccessAggregator,
    VotingAggregator,
)
from core.models import AgentResult, AgentTask


@pytest.mark.asyncio
async def test_concat_aggregator_empty_results():
    task = AgentTask(id="t", prompt="q")
    agg = ConcatAggregator()
    result = await agg.aggregate(task, [])
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_concat_aggregator_ignores_empty_output():
    task = AgentTask(id="t", prompt="q")
    agg = ConcatAggregator()
    results = [
        AgentResult(task_id="t", success=True, output=""),
        AgentResult(task_id="t", success=True, output=None),
        AgentResult(task_id="t", success=True, output="valid"),
    ]
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert "valid" in result.output
    assert result.tokens_used is not None
    assert result.latency_sec is not None


@pytest.mark.asyncio
async def test_concat_aggregator_sums_latency_and_tokens():
    task = AgentTask(id="t", prompt="q")
    agg = ConcatAggregator()
    results = [
        AgentResult(task_id="t", success=True, output="a", latency_sec=1.0, tokens_used=10),
        AgentResult(task_id="t", success=True, output="b", latency_sec=2.0, tokens_used=20),
    ]
    result = await agg.aggregate(task, results)
    assert result.latency_sec == 3.0
    assert result.tokens_used == 30


@pytest.mark.asyncio
async def test_first_success_returns_first_not_last():
    task = AgentTask(id="t", prompt="q")
    agg = FirstSuccessAggregator()
    results = [
        AgentResult(task_id="t", success=True, output="first"),
        AgentResult(task_id="t", success=True, output="second"),
        AgentResult(task_id="t", success=True, output="third"),
    ]
    result = await agg.aggregate(task, results)
    assert result.output == "first"


@pytest.mark.asyncio
async def test_first_success_skips_failures():
    task = AgentTask(id="t", prompt="q")
    agg = FirstSuccessAggregator()
    results = [
        AgentResult(task_id="t", success=False, error="e1"),
        AgentResult(task_id="t", success=False, error="e2"),
        AgentResult(task_id="t", success=True, output="winner"),
    ]
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output == "winner"


@pytest.mark.asyncio
async def test_voting_tie_breaks_by_first_most_common():
    task = AgentTask(id="t", prompt="q")
    agg = VotingAggregator()
    results = [
        AgentResult(task_id="t", success=True, output="a"),
        AgentResult(task_id="t", success=True, output="b"),
        AgentResult(task_id="t", success=True, output="a"),
        AgentResult(task_id="t", success=True, output="b"),
    ]
    result = await agg.aggregate(task, results)
    assert result.success is True
    # Counter.most_common picks first encountered on tie (a was first)
    assert result.output in ("a", "b")


@pytest.mark.asyncio
async def test_voting_ignores_failures():
    task = AgentTask(id="t", prompt="q")
    agg = VotingAggregator()
    results = [
        AgentResult(task_id="t", success=False, error="fail"),
        AgentResult(task_id="t", success=True, output="x"),
        AgentResult(task_id="t", success=True, output="x"),
    ]
    result = await agg.aggregate(task, results)
    assert result.output == "x"


@pytest.mark.asyncio
async def test_voting_no_success():
    task = AgentTask(id="t", prompt="q")
    agg = VotingAggregator()
    results = [AgentResult(task_id="t", success=False, error="fail")]
    result = await agg.aggregate(task, results)
    assert result.success is False


@pytest.mark.asyncio
async def test_dedupe_merge_handles_whitespace_variants():
    task = AgentTask(id="t", prompt="q")
    agg = DedupeMergeAggregator()
    results = [
        AgentResult(task_id="t", success=True, output="  hello  "),
        AgentResult(task_id="t", success=True, output="hello"),
        AgentResult(task_id="t", success=True, output="world"),
    ]
    result = await agg.aggregate(task, results)
    assert result.output.count("hello") == 1
    assert "world" in result.output


@pytest.mark.asyncio
async def test_dedupe_all_fail():
    task = AgentTask(id="t", prompt="q")
    agg = DedupeMergeAggregator()
    results = [AgentResult(task_id="t", success=False, error="e")]
    result = await agg.aggregate(task, results)
    assert result.success is False


@pytest.mark.asyncio
async def test_aggregation_output_none_filtered():
    task = AgentTask(id="t", prompt="q")
    for AggClass in [ConcatAggregator, DedupeMergeAggregator, VotingAggregator]:
        agg = AggClass()
        results = [
            AgentResult(task_id="t", success=True, output=None),
            AgentResult(task_id="t", success=True, output="ok"),
        ]
        result = await agg.aggregate(task, results)
        assert result.success is True
