from core.agent_base import BaseAgent
from core.models import AgentTask


class CodeReviewerAgent(BaseAgent):
    async def execute(self, task: AgentTask, provider, model: str, api_key: str, gen_params: dict) -> dict:
        file_path = task.metadata.get("file_path", "unknown")
        prompt = f"""You are an expert code reviewer. Review the following code for bugs, security issues, and best practices.

File: {file_path}
Code:
```{task.prompt}```

Provide a structured review covering:
1. Critical issues (bugs, security)
2. Code quality concerns
3. Suggestions for improvement"""
        response = await provider.call(model, prompt, api_key, **gen_params)
        return {
            "text": response.text,
            "tokens": response.tokens_used,
            "file_path": file_path,
        }
