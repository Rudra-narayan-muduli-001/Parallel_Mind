import pytest
from pydantic import ValidationError

from core.models import AgentResult, AgentTask


def test_agent_task_defaults():
    task = AgentTask(id="t1", prompt="hello")
    assert task.id == "t1"
    assert task.prompt == "hello"
    assert task.context == {}
    assert task.metadata == {}


def test_agent_task_with_metadata_and_context():
    task = AgentTask(
        id="t2",
        prompt="review this",
        context={"file_content": "print('hi')", "diff_hunk": "@@ -1,2 +1,2 @@"},
        metadata={"task_type": "code_review", "complexity_tier": "high", "file_path": "src/app.py"},
    )
    assert task.context["file_content"] == "print('hi')"
    assert task.metadata["complexity_tier"] == "high"


def test_agent_task_requires_id_and_prompt():
    with pytest.raises(ValidationError):
        AgentTask(prompt="missing id")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AgentTask(id="t3")  # type: ignore[call-arg]


def test_agent_task_complexity_tier_values():
    for tier in ["low", "mid", "high", "xhigh", "max"]:
        task = AgentTask(id=f"t-{tier}", prompt="q", metadata={"complexity_tier": tier})
        assert task.metadata["complexity_tier"] == tier


def test_agent_result_success_defaults():
    r = AgentResult(task_id="t1", success=True, output="done")
    assert r.success is True
    assert r.output == "done"
    assert r.error is None
    assert r.latency_sec == 0.0
    assert r.tokens_used is None
    assert r.provider_used is None
    assert r.model_used is None


def test_agent_result_failure():
    r = AgentResult(task_id="t2", success=False, error="boom")
    assert r.success is False
    assert r.error == "boom"
    assert r.output is None


def test_agent_result_with_all_fields():
    r = AgentResult(
        task_id="t3",
        success=True,
        output={"text": "structured"},
        latency_sec=1.23,
        tokens_used=42,
        provider_used="groq",
        model_used="llama-3.1-70b",
    )
    assert r.latency_sec == 1.23
    assert r.tokens_used == 42
    assert r.provider_used == "groq"
    assert r.model_used == "llama-3.1-70b"


def test_agent_result_output_can_be_any_type():
    for output in ["string", 123, {"key": "val"}, ["a", "b"], None]:
        r = AgentResult(task_id="t", success=True, output=output)
        assert r.output == output


def test_agent_task_mutability_metadata():
    task = AgentTask(id="t", prompt="p", metadata={"task_type": "research"})
    task.metadata["new_key"] = "value"
    assert task.metadata["new_key"] == "value"
    task.context["added"] = 1
    assert task.context["added"] == 1


def test_agent_result_requires_task_id_and_success():
    with pytest.raises(ValidationError):
        AgentResult(success=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AgentResult(task_id="t")  # type: ignore[call-arg]
