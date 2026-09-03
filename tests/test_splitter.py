import os
import tempfile

import pytest

from pipelines.code_review.splitter import CodeReviewSplitter, _tier_for_lines


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "low"),
        (49, "low"),
        (50, "mid"),
        (200, "mid"),
        (201, "high"),
        (500, "high"),
        (501, "xhigh"),
        (1000, "xhigh"),
        (1001, "max"),
        (5000, "max"),
    ],
)
def test_tier_for_lines(count, expected):
    assert _tier_for_lines(count) == expected


def test_splitter_single_file(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("print('hi')\n" * 10)
    splitter = CodeReviewSplitter(str(f))
    tasks = splitter.split()
    assert len(tasks) == 1
    assert tasks[0].metadata["task_type"] == "code_review"
    assert tasks[0].metadata["file_path"] == str(f)
    assert tasks[0].metadata["complexity_tier"] == "low"


def test_splitter_directory_filters_extensions(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.js").write_text("var x=1;\n")
    (tmp_path / "c.txt").write_text("should be ignored\n")
    (tmp_path / "d.md").write_text("# also ignored\n")
    splitter = CodeReviewSplitter(str(tmp_path))
    tasks = splitter.split()
    paths = {t.metadata["file_path"] for t in tasks}
    assert any("a.py" in p for p in paths)
    assert any("b.js" in p for p in paths)
    assert not any("c.txt" in p for p in paths)
    assert not any("d.md" in p for p in paths)


def test_splitter_skips_hidden_and_cache_dirs(tmp_path):
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.py").write_text("x=1\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("x=1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x=1\n")
    (tmp_path / "ok.py").write_text("x=1\n")
    splitter = CodeReviewSplitter(str(tmp_path))
    tasks = splitter.split()
    assert len(tasks) == 1
    assert "ok.py" in tasks[0].metadata["file_path"]


def test_splitter_handles_empty_file(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("")
    splitter = CodeReviewSplitter(str(f))
    tasks = splitter.split()
    assert len(tasks) == 1
    assert tasks[0].prompt == "(empty file)"


def test_splitter_truncates_large_file(tmp_path):
    f = tmp_path / "big.py"
    content = "a" * 20000
    f.write_text(content)
    splitter = CodeReviewSplitter(str(f))
    from pipelines.code_review.splitter import MAX_PROMPT_CHARS

    tasks = splitter.split()
    assert len(tasks[0].prompt) <= MAX_PROMPT_CHARS


def test_splitter_tiers_by_line_count(tmp_path):
    small = tmp_path / "small.py"
    small.write_text("\n".join(["x=1"] * 10))
    big = tmp_path / "big.py"
    big.write_text("\n".join(["x=1"] * 600))
    splitter_small = CodeReviewSplitter(str(small))
    splitter_big = CodeReviewSplitter(str(big))
    t_small = splitter_small.split()[0]
    t_big = splitter_big.split()[0]
    assert t_small.metadata["complexity_tier"] == "low"
    assert t_big.metadata["complexity_tier"] == "xhigh"


def test_splitter_directory_with_nested_structure(tmp_path):
    sub = tmp_path / "src" / "utils"
    sub.mkdir(parents=True)
    (sub / "helper.py").write_text("def foo(): pass\n")
    (tmp_path / "main.go").write_text("package main\n")
    splitter = CodeReviewSplitter(str(tmp_path))
    tasks = splitter.split()
    assert len(tasks) == 2


def test_splitter_supports_multiple_extensions(tmp_path):
    for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java", ".cs", ".cpp", ".h", ".hpp"]:
        (tmp_path / f"file{ext}").write_text("content\n")
    splitter = CodeReviewSplitter(str(tmp_path))
    tasks = splitter.split()
    assert len(tasks) == 12


def test_splitter_nonexistent_path_returns_empty():
    splitter = CodeReviewSplitter("/nonexistent/path/xyz_12345")
    tasks = splitter.split()
    assert tasks == []


def test_splitter_file_task_metadata_line_count(tmp_path):
    f = tmp_path / "count.py"
    lines = ["line"] * 42
    f.write_text("\n".join(lines))
    splitter = CodeReviewSplitter(str(f))
    task = splitter.split()[0]
    assert task.metadata["line_count"] == 42
    assert task.id.startswith("review-")
