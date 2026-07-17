from core.router.policies import RoutingPolicy


class Router:
    def __init__(self, policy: RoutingPolicy):
        self.policy = policy

    async def decide(self, task) -> list[tuple[str, str]]:
        return await self.policy.decide(task)
