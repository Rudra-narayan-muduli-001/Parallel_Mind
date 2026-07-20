import pytest

from core.aggregation.strategies import (
    ConcatAggregator,
    DedupeMergeAggregator,
    FirstSuccessAggregator,
    VotingAggregator,
)
from core.models import AgentResult, AgentTask


@pytest.mark.asyncio
async def test_concat_aggregator():
    task = AgentTask(id="t1", prompt="test")
    results = [
        AgentResult(task_id="t1", success=True, output="First"),
        AgentResult(task_id="t1", success=True, output="Second"),
        AgentResult(task_id="t1", success=False, error="fail"),
    ]
    agg = ConcatAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert "First" in result.output
    assert "Second" in result.output


@pytest.mark.asyncio
async def test_concat_all_fail():
    task = AgentTask(id="t2", prompt="test")
    results = [
        AgentResult(task_id="t2", success=False, error="fail1"),
        AgentResult(task_id="t2", success=False, error="fail2"),
    ]
    agg = ConcatAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is False


@pytest.mark.asyncio
async def test_first_success():
    task = AgentTask(id="t3", prompt="test")
    results = [
        AgentResult(task_id="t3", success=False, error="fail"),
        AgentResult(task_id="t3", success=True, output="Winner"),
        AgentResult(task_id="t3", success=True, output="Loser"),
    ]
    agg = FirstSuccessAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output == "Winner"


@pytest.mark.asyncio
async def test_first_success_all_fail():
    task = AgentTask(id="t4", prompt="test")
    results = [
        AgentResult(task_id="t4", success=False, error="fail"),
    ]
    agg = FirstSuccessAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is False


@pytest.mark.asyncio
async def test_voting():
    task = AgentTask(id="t5", prompt="test")
    results = [
        AgentResult(task_id="t5", success=True, output="cat"),
        AgentResult(task_id="t5", success=True, output="dog"),
        AgentResult(task_id="t5", success=True, output="cat"),
    ]
    agg = VotingAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output == "cat"


@pytest.mark.asyncio
async def test_dedupe_merge():
    task = AgentTask(id="t6", prompt="test")
    results = [
        AgentResult(task_id="t6", success=True, output="Hello"),
        AgentResult(task_id="t6", success=True, output="World"),
        AgentResult(task_id="t6", success=True, output="Hello"),
    ]
    agg = DedupeMergeAggregator()
    result = await agg.aggregate(task, results)
    assert result.success is True
    assert result.output.count("Hello") == 1
    assert result.output.count("World") == 1
