import os

from core.models import AgentTask, ComplexityTier

MAX_PROMPT_CHARS = 8000


def _tier_for_lines(count: int) -> ComplexityTier:
    if count < 50:
        return "low"
    elif count <= 200:
        return "mid"
    elif count <= 500:
        return "high"
    elif count <= 1000:
        return "xhigh"
    else:
        return "max"


class CodeReviewSplitter:
    def __init__(self, target_path: str):
        self.target_path = target_path

    def split(self) -> list[AgentTask]:
        tasks = []
        if os.path.isfile(self.target_path):
            tasks.append(self._file_task(self.target_path))
        elif os.path.isdir(self.target_path):
            for root, dirs, files in os.walk(self.target_path):
                dirs[:] = [d for d in dirs if not d.startswith((".", "__pycache__", "node_modules", "venv", ".venv"))]
                for fname in files:
                    if fname.endswith(
                        (".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java", ".cs", ".cpp", ".h", ".hpp")
                    ):
                        fpath = os.path.join(root, fname)
                        tasks.append(self._file_task(fpath))
        return tasks

    def _file_task(self, fpath: str) -> AgentTask:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            content = ""

        lines = content.count("\n") + 1
        tier = _tier_for_lines(lines)
        relpath = os.path.relpath(fpath, self.target_path) if os.path.isdir(self.target_path) else fpath

        return AgentTask(
            id=f"review-{relpath}",
            prompt=content[:MAX_PROMPT_CHARS] if content else "(empty file)",
            metadata={
                "task_type": "code_review",
                "complexity_tier": tier,
                "file_path": relpath,
                "line_count": lines,
            },
        )
