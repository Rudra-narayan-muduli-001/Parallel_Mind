from core.agent_base import BaseAgent
from core.models import AgentTask


class ResearcherAgent(BaseAgent):
    async def execute(self, task: AgentTask, provider, model: str, api_key: str, gen_params: dict) -> dict:
        prompt = f"""You are a research assistant. Answer the following question thoroughly and cite your reasoning.

Question: {task.prompt}

Provide a well-structured answer with key points and evidence."""
        response = await provider.call(model, prompt, api_key, **gen_params)
        return {
            "text": response.text,
            "tokens": response.tokens_used,
        }
